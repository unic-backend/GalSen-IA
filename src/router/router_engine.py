"""
Router Engine for GalSen IA.

The central orchestrator that receives user requests, builds an execution plan
from the declared workflow, runs the agents **in sequence**, collects results,
detects failures, retries failed tasks and merges output into a final response.

Two limits are stated here rather than discovered later (VOLET 06):

- **Execution is sequential.** Workflows declare `parallel_agents`, and nothing
  runs them concurrently: they are appended to the sequential order. The plan
  reports `parallel_supported: False` so no caller mistakes the declaration for
  a behaviour.
- **The plan does not depend on the request.** The order of agents comes from
  the workflow declaration. Intent detection exists in `PlannerAgent` and is not
  wired to routing — see `docs/architecture/orchestration.md`.
"""

import os
import time
from typing import Dict, Any, Optional
from .config_loader import ConfigLoader
from .agent_loader import AgentLoader
from .workflow_loader import WorkflowLoader
from .execution_planner import ExecutionPlanner
from .result_aggregator import ResultAggregator
from .retry_manager import RetryManager
from .agent_dispatcher import AgentDispatcher
from .workflow_history import WorkflowHistory
from .workflow_checkpoint import CheckpointRefused, WorkflowCheckpoints
from .decision_trace import decision_trace, recommended_agents, selection_appliquee
from .logger import Logger
from .output_validation import (
    STATUS_REQUIRES_APPROVAL,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    counts,
)
from ..agent.context import AgentContext
from ..audit_engine.types import AuditEventType, AuditStatus, generate_request_id
from ..integration.engine_registry import get_shared_registry


class RouterEngine:
    """Moteur principal d'orchestration de GalSen IA."""

    def __init__(self):
        """Initialise le moteur de routage avec des chemins absolus."""
        # Déterminer le répertoire racine du projet (deux niveaux au-dessus de ce fichier)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))

        # Chemins absolus vers les fichiers de configuration
        config_path = os.path.join(project_root, 'config', 'settings.yaml')
        agents_registry_path = os.path.join(project_root, 'agents', 'registry.yaml')
        workflows_registry_path = os.path.join(project_root, 'workflows', 'workflows.yaml')

        # Initialiser les chargeurs avec des chemins absolus
        self.config_loader = ConfigLoader(config_path)
        self.agent_loader = AgentLoader(agents_registry_path)
        self.workflow_loader = WorkflowLoader(workflows_registry_path)
        self.execution_planner = ExecutionPlanner(self.workflow_loader)
        self.result_aggregator = ResultAggregator()
        self.retry_manager = RetryManager(
            max_attempts=self.config_loader.get('workflows.execution.failure.max_attempts', 3),
            delay_seconds=1.0  # Peut être rendu configurable plus tard
        )
        self.agent_dispatcher = AgentDispatcher()
        self.logger_manager = Logger(self.config_loader)
        self.logger = self.logger_manager.get_logger(__name__)

        # Registre partagé : les agents orchestrés ici utilisent les mêmes
        # moteurs que le reste de la plateforme
        self.engine_registry = get_shared_registry()

        # Validation des workflows au démarrage (VOLET 08, ch. 02 et 03). Un
        # workflow sans étape rapportait `success` sans rien faire, et un
        # workflow citant un agent inexistant s'arrêtait à mi-parcours : les
        # deux se chargeaient sans le moindre signal.
        self.workflow_loader.validate(self.agent_loader.get_all_agents().keys())

        # Journal borné des exécutions, pour le taux de succès du chapitre 09.
        self.history = WorkflowHistory()

        # Points de reprise (VOLET 49). L'historique dit ce qu'une exécution a
        # fait une fois finie ; ceci retient où elle en est pendant qu'elle
        # dure, pour qu'une reprise ne refasse pas les étapes déjà abouties.
        self.checkpoints = WorkflowCheckpoints()

        # Le témoin (VOLET 50). Une exécution morte au huitième agent laissait
        # un point de reprise que personne ne savait exister ; posé par
        # l'intégration, il reste `None` tant que le service n'est pas monté.
        self.notifier = None

        self.logger.info("RouterEngine initialisé avec succès.")

    def process_request(
        self,
        user_request: str,
        workflow_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        resume_run_id: Optional[str] = None,
        unattended: bool = False,
    ) -> Dict[str, Any]:
        """
        Traite une requête utilisateur en orchestrant les agents selon le workflow.

        Args:
            user_request: La requête de l'utilisateur en langage naturel.
            workflow_id: Identifiant du workflow à utiliser (optionnel, utilise le défaut sinon).
            user_id: Utilisateur à l'origine de la requête, pour isoler ses mémoires.
            session_id: Session à laquelle rattacher la requête.
            resume_run_id: Exécution interrompue à reprendre (VOLET 49). Les
                étapes déjà abouties ne sont pas refaites, et le workflow vient
                du point de reprise, pas de l'appelant.
            unattended: Vrai quand une routine déclenche l'exécution, sans
                personne devant (VOLET 64). Ne change rien à ce qui tourne :
                l'orchestration ne doit pas se comporter autrement selon qui
                regarde. Le marquer permet de **distinguer** dans l'audit et les
                métriques une exécution que personne n'a lancée — sans quoi une
                approbation restée sans réponse toute la nuit se lit comme un
                utilisateur qui a changé d'avis.

        Returns:
            Un dictionnaire contenant la réponse finale et les métadonnées d'exécution.
        """
        start_time = time.time()
        request_id = generate_request_id()
        # Le contexte n'est créé qu'après la planification ; il reste None si une
        # exception survient avant, et l'audit d'échec doit le prendre en compte.
        context: Optional[AgentContext] = None
        # Le point de reprise suit la même règle : il n'existe qu'après la
        # planification, et l'échec doit pouvoir dire s'il en existe un.
        point = None
        self.logger.info(f"Début du traitement de la requête: {user_request[:100]}...")

        try:
            # Reprise d'une exécution interrompue (VOLET 49). Le workflow vient
            # du point de reprise et non de l'appelant : reprendre sous un autre
            # workflow serait en commencer un autre sous l'identifiant du
            # premier, avec les étapes déjà faites de celui-ci.
            reprise = None
            if resume_run_id:
                reprise = self.checkpoints.resume(resume_run_id, subject=user_id)
                workflow_id = reprise.workflow_id
                # La demande aussi vient du point de reprise. La redemander à
                # l'appelant permettrait d'en changer sans que rien ne le dise,
                # et les étapes déjà faites répondraient alors à une autre
                # question que celles qui restent.
                if reprise.request:
                    user_request = reprise.request

            # Étape 1: Planifier l'exécution
            execution_plan = self.execution_planner.plan_execution(workflow_id)
            workflow_id_to_use = workflow_id or self.workflow_loader.get_default_workflow()
            workflow_config = self.workflow_loader.get_workflow(workflow_id_to_use)

            # Un workflow inexécutable est refusé ici plutôt que de produire une
            # réponse crédible : mieux vaut une erreur qui nomme la cause qu'un
            # `success` obtenu sans avoir exécuté un seul agent.
            if not self.workflow_loader.is_executable(workflow_id_to_use):
                raisons = "; ".join(
                    p.message for p in self.workflow_loader.get_problems(workflow_id_to_use)
                    if p.gravite == "error"
                )
                raise ValueError(
                    f"Workflow '{workflow_id_to_use}' inexécutable : {raisons}"
                )

            self.logger.info(f"Workflow '{workflow_id_to_use}' sélectionné.")
            # Le journal dit ce qui va se passer, pas ce que le workflow déclare :
            # les agents marqués « parallèles » sont exécutés à la suite des autres.
            declares_paralleles = execution_plan['parallel']
            self.logger.info(
                "Plan d'exécution — séquentiel : %s%s",
                execution_plan['sequential'],
                (f" ; {declares_paralleles} déclarés parallèles, exécutés séquentiellement "
                 "(le moteur n'exécute rien en parallèle)") if declares_paralleles else "",
            )

            # Étape 2: Préparer les données d'entrée initiales
            pipeline = workflow_config.get('pipeline', [])
            # Filtrer le router du pipeline car il est déjà l'orchestrateur
            pipeline_agents = [agent_id for agent_id in pipeline if agent_id != 'router']

            # Si le pipeline était vide ou ne contenait que le router, nous utilisons les groupes d'exécution
            if not pipeline_agents:
                # Utiliser l'ordre séquentiel + parallèle comme défini dans l'exécution
                ordered_agents = execution_plan['sequential'] + execution_plan['parallel']
            else:
                ordered_agents = pipeline_agents

            # Le plan d'une reprise est celui du point de reprise : le workflow
            # a pu changer entre-temps, et les étapes déjà faites l'ont été
            # selon l'ancien.
            if reprise is not None:
                ordered_agents = list(reprise.steps)

            self.logger.info(f"Ordre d'exécution des agents: {ordered_agents}")

            # Un contexte unique est partagé par tous les agents de la requête :
            # ils voient ainsi la même mémoire, la même session et les résultats
            # des agents qui les ont précédés.
            context = AgentContext(
                request=user_request,
                agent_id='router',
                registry=self.engine_registry,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
            )

            # Point de reprise de cette exécution. Ouvert avant le premier
            # agent : un point de reprise créé à la fin ne servirait qu'aux
            # exécutions qui n'en ont pas besoin.
            if reprise is not None:
                point = reprise
            elif ordered_agents:
                point = self.checkpoints.start(
                    workflow_id_to_use, ordered_agents, subject=user_id,
                    request=user_request,
                )
            else:
                point = None

            # Exécution séquentielle des agents (pour une première version simple)
            all_agent_results = []  # Pour stocker tous les résultats détaillés
            agent_durations = {}  # Durée observée de chaque agent, reprises comprises

            # Ce qu'une reprise ne refait pas. Les productions des étapes déjà
            # abouties rejoignent le contexte : l'agent suivant doit voir ce qui
            # l'a précédé, qu'il vienne de tourner ou d'avoir tourné hier.
            deja_faits = set()
            if reprise is not None:
                for etape in reprise.completed:
                    if not etape.ok or etape.skipped:
                        continue
                    deja_faits.add(etape.agent_id)
                    repris = {
                        "agent": etape.agent_id,
                        "status": STATUS_SUCCESS,
                        "result": etape.output,
                        "resumed": True,
                    }
                    all_agent_results.append(repris)
                    context.previous_results.append(repris)
                deja_faits.update(
                    etape.agent_id for etape in reprise.completed if etape.skipped
                )
                self.logger.info(
                    "Reprise de l'exécution %s : %s étapes déjà abouties ne sont "
                    "pas refaites.", reprise.run_id, len(deja_faits),
                )

            # Sélection pilotée par le planificateur, si le workflow la déclare
            # (`execution.agent_selection: planner`). Elle **restreint** le
            # pipeline déclaré, jamais elle ne l'élargit : `workflows.yaml`
            # reste l'autorité sur ce qui peut tourner, le planificateur décide
            # ce qui tourne parmi cela.
            selection_par_planificateur = (
                (workflow_config.get('execution') or {}).get('agent_selection') == 'planner'
            )
            selection_appliquee_effectivement = False
            agents_retenus = None

            for agent_id in ordered_agents:
                if agent_id in deja_faits:
                    # La règle de tout le VOLET : refaire une étape qui a déjà
                    # eu un effet au-dehors est la façon dont un courriel
                    # devient deux.
                    self.logger.info(
                        "Agent '%s' déjà abouti lors d'une exécution précédente : "
                        "non refait.", agent_id,
                    )
                    continue
                if agents_retenus is not None and agent_id not in agents_retenus:
                    motif = (
                        "Le planificateur ne l'a pas retenu pour cette demande."
                    )
                    self.logger.info("Agent '%s' écarté : %s", agent_id, motif)
                    self._marquer_saut(point, agent_id, motif, user_id)
                    continue
                if not self.agent_loader.is_enabled(agent_id):
                    self.logger.warning(f"L'agent '{agent_id}' est désactivé. Ignoré.")
                    self._marquer_saut(point, agent_id, "Agent désactivé.", user_id)
                    continue

                agent_config = self.agent_loader.get_agent(agent_id)
                self.logger.info(f"Exécution de l'agent: {agent_id}")

                # Définir la fonction d'appel pour le agent dispatcher
                def dispatch_agent(config, data):
                    return self._dispatch_agent(config, data, context)

                # Chaque agent reçoit la demande d'origine. Les productions des
                # agents précédents lui parviennent par le contexte, ce qui évite
                # de déformer la demande à chaque étape.
                # Durée par agent (VOLET 19, ch. 03 étapes 5 et 7). Seule la
                # durée totale était mesurée, si bien que l'orchestration ne
                # pouvait pas nommer son propre goulot d'étranglement. Le temps
                # inclut les reprises : c'est ce que la requête a réellement
                # attendu.
                debut_agent = time.perf_counter()
                agent_result = self.retry_manager.execute_with_retry(
                    dispatch_agent,
                    agent_config,
                    user_request
                )
                agent_durations[agent_id] = round(time.perf_counter() - debut_agent, 3)

                all_agent_results.append(agent_result)
                # Le contexte est enrichi au fur et à mesure : l'agent suivant
                # peut consulter ce qui vient d'être produit
                context.previous_results.append(agent_result)
                self._consigner_etape(point, agent_id, agent_result, user_id)

                # Dès que le planificateur a rendu sa décision, le reste du
                # pipeline s'y conforme. Une recommandation vide ou absente
                # laisse le pipeline entier : ne rien exécuter parce qu'une
                # heuristique n'a rien reconnu serait pire que d'en faire trop.
                if selection_par_planificateur and agents_retenus is None and agent_id == 'planner':
                    restreint = selection_appliquee(
                        ordered_agents, recommended_agents(all_agent_results),
                    )
                    if restreint is not None:
                        agents_retenus = set(restreint) | {'planner'}
                        selection_appliquee_effectivement = True
                        self.logger.info(
                            "Pipeline restreint par le planificateur : %s sur %d agents déclarés.",
                            restreint, len(ordered_agents),
                        )
                    else:
                        self.logger.info(
                            "Le planificateur n'a retenu aucun agent : le pipeline déclaré s'applique."
                        )

                if agent_result.get('status') != 'success':
                    if agent_result.get('status') == 'requires_approval':
                        # L'action attend une décision humaine : le pipeline est
                        # suspendu, pas en échec (ADR-006).
                        self.logger.info(
                            f"L'agent '{agent_id}' attend une approbation humaine. "
                            "Suspension du pipeline."
                        )
                    else:
                        self.logger.error(f"L'agent '{agent_id}' a échoué après plusieurs tentatives: {agent_result.get('error')}")
                    # Selon la configuration de failure, nous pourrions vouloir arrêter ou continuer
                    if not self.config_loader.get('workflows.execution.failure.rollback', True):
                        self.logger.warning("Continuation malgré l'échec (rollback désactivé).")
                    else:
                        self.logger.info("Arrêt de l'exécution en raison du statut non terminé (rollback activé).")
                        break

            # Étape 3: Agréger les résultats
            final_result = self.result_aggregator.aggregate(all_agent_results)

            # Étape 4: Préparer la réponse finale
            end_time = time.time()
            execution_time = end_time - start_time

            # Les résultats validés par l'agrégateur, et non les bruts : le
            # routeur comptait sur les seconds, si bien qu'une sortie non
            # conforme y était comptée selon une forme que plus rien en aval
            # n'utilisait.
            all_agent_results = final_result["agent_results"]

            # Comptés explicitement, jamais déduits par soustraction : le calcul
            # `total - succès - approbations` rangeait les agents `skipped`
            # parmi les échecs, sans que rien ne le dise, pendant que
            # l'agrégateur les effaçait et rendait `success`. La même réponse
            # portait les deux verdicts.
            comptes = counts(all_agent_results)
            successful_agents = comptes[STATUS_SUCCESS]
            pending_approval_agents = comptes[STATUS_REQUIRES_APPROVAL]
            skipped_agents = comptes[STATUS_SKIPPED]
            failed_agents = comptes["error"] + comptes["invalid"]

            # Quels agents ont échoué, et pas seulement combien : l'analyse des
            # défaillances du chapitre 06 (VOLET 18) demande de nommer la cause,
            # et un compteur ne dit pas si c'est toujours le même agent.
            failing_agents = [
                r.get('agent') for r in all_agent_results
                if r.get('status') == 'error' and r.get('agent')
            ]

            # Une seule règle, partagée avec l'agrégateur (`output_validation`).
            status = final_result["status"]

            approval_request_ids = [
                r.get('approval_request_id')
                for r in all_agent_results
                if r.get('status') == STATUS_REQUIRES_APPROVAL
                and r.get('approval_request_id')
            ]

            # Historique d'exécution (VOLET 08, ch. 03 et 09) : sans lui, on ne
            # peut pas dire si un workflow échoue une fois sur dix ou neuf.
            self.history.record(
                workflow_id=workflow_id_to_use,
                workflow_version=self.workflow_loader.get_version(workflow_id_to_use),
                status=status,
                duration_seconds=execution_time,
                agents_executed=len(all_agent_results),
                failed_agents=failed_agents,
                failing_agents=failing_agents,
                agent_durations=agent_durations,
                request_id=request_id,
            )

            response = {
                "status": status,
                "user_request": user_request,
                "workflow_used": workflow_id_to_use,
                "execution_time_seconds": round(execution_time, 2),
                "agent_results": all_agent_results,
                "aggregated_result": final_result,
                "metadata": {
                    "total_agents_executed": len(all_agent_results),
                    "successful_agents": successful_agents,
                    "failed_agents": failed_agents,
                    "pending_approval_agents": pending_approval_agents,
                    # Un agent qui a décidé de ne pas agir n'est ni un succès ni
                    # une panne ; il était compté parmi les échecs.
                    "skipped_agents": skipped_agents,
                    # Ce que le planificateur a décidé, et ce qui a tourné
                    # (VOLET 22, ch. 03 étape 10). La décision existe et n'est
                    # pas suivie ; l'enregistrer est la seule façon de le voir.
                    "decision": decision_trace(
                        all_agent_results,
                        [r.get('agent') for r in all_agent_results if r.get('agent')],
                        applied=selection_appliquee_effectivement,
                    ),
                    # Qui a lancé cette exécution : quelqu'un, ou une routine à
                    # trois heures du matin. Les deux suivent le même chemin ;
                    # seule la lecture d'après diffère.
                    "unattended": unattended,
                }
            }
            if approval_request_ids:
                response["approval_request_ids"] = approval_request_ids
            # L'identifiant du point de reprise fait partie de la réponse :
            # sans lui, personne ne peut reprendre ce qui vient d'échouer.
            if point is not None:
                response["run_id"] = point.run_id
                response["metadata"]["run_status"] = point.status.value
                response["metadata"]["resumed_steps"] = len(deja_faits)
                self._prevenir_interruption(point, failing_agents)

            self.logger.info(f"Requête traitée en {execution_time:.2f} secondes. Statut: {response['status']}")

            # Un événement REQUEST résume toute la requête : c'est l'entrée de
            # plus haut niveau du système d'audit pour cette exécution.
            if context is not None:
                context.record_audit(
                    AuditEventType.REQUEST,
                    "process_request",
                    status=response["status"],
                    execution_time_seconds=execution_time,
                    metadata={
                        "workflow_id": workflow_id_to_use,
                        "total_agents_executed": len(all_agent_results),
                        "successful_agents": successful_agents,
                        "failed_agents": failed_agents,
                        "pending_approval_agents": pending_approval_agents,
                        "unattended": unattended,
                    },
                )
            response["request_id"] = request_id
            return response

        except CheckpointRefused:
            # Une reprise refusée n'a **rien démarré** : c'est une erreur
            # d'appel, pas une exécution en échec. La compter dans l'historique
            # ferait baisser le taux de succès des workflows pour une exécution
            # qui n'a jamais eu lieu.
            raise
        except Exception as e:
            self.logger.error(f"Erreur inattendue lors du traitement de la requête: {e}", exc_info=True)
            duree = time.time() - start_time
            # Un échec compte dans l'historique : un taux de succès qui n'observe
            # que les réussites vaut toujours 100 %.
            workflow_en_echec = workflow_id or self.workflow_loader.get_default_workflow()
            self.history.record(
                workflow_id=workflow_en_echec,
                workflow_version=self.workflow_loader.get_version(workflow_en_echec),
                status="error",
                duration_seconds=duree,
            )
            error_response = {
                "status": "error",
                "user_request": user_request,
                "error": str(e),
                "request_id": request_id,
                "execution_time_seconds": round(duree, 2)
            }
            if point is not None:
                # Une exécution morte en route se reprend : encore faut-il
                # savoir laquelle.
                error_response["run_id"] = point.run_id
            if context is not None:
                context.record_audit(
                    AuditEventType.REQUEST,
                    "process_request",
                    status=AuditStatus.FAILURE,
                    execution_time_seconds=round(time.time() - start_time, 2),
                    detail=str(e),
                    metadata={"workflow_id": workflow_id, "unattended": unattended},
                )
            return error_response

    def _prevenir_interruption(self, point: Any, failing_agents: list) -> None:
        """
        Prévient qu'une exécution s'est interrompue et peut être reprise.

        Sans cela, le point de reprise existe et personne ne sait qu'il existe :
        la reprise resterait une possibilité théorique. Le témoin est facultatif
        et ne fait jamais tomber la requête qu'il observe.

        Args:
            point: Le point de reprise de l'exécution.
            failing_agents: Les agents en échec, pour nommer où elle s'est
                arrêtée.
        """
        if self.notifier is None or point.status.value != "failed":
            return
        try:
            self.notifier.workflow_interrupted(
                point.run_id, point.workflow_id,
                failing_agent=failing_agents[0] if failing_agents else None,
                subject=point.subject,
            )
        except Exception as erreur:
            self.logger.warning("Interruption non notifiée : %s", erreur)

    def _consigner_etape(
        self,
        point: Optional[Any],
        agent_id: str,
        agent_result: Dict[str, Any],
        user_id: Optional[str],
    ) -> None:
        """
        Consigne une étape terminée dans le point de reprise.

        Une étape qui attend une approbation humaine n'est **pas** consignée :
        elle n'a pas fini. La laisser ouverte est ce qui permet à la reprise de
        la relancer une fois la décision prise ; la marquer aboutie ferait
        passer l'approbation pour acquise.

        Args:
            point: Le point de reprise, ou `None` si l'exécution n'en a pas.
            agent_id: L'agent qui vient de finir.
            agent_result: Ce qu'il a rendu.
            user_id: Le propriétaire de l'exécution.
        """
        if point is None:
            return
        statut = agent_result.get("status")
        if statut == STATUS_REQUIRES_APPROVAL:
            return
        try:
            self.checkpoints.record_step(
                point.run_id, agent_id,
                ok=statut == STATUS_SUCCESS,
                output=agent_result.get("result", ""),
                subject=user_id,
            )
        except CheckpointRefused as refus:
            # Le point de reprise ne doit jamais faire échouer la requête qu'il
            # observe : il est un filet, pas un maillon.
            self.logger.warning("Point de reprise non mis à jour : %s", refus)

    def _marquer_saut(
        self,
        point: Optional[Any],
        agent_id: str,
        motif: str,
        user_id: Optional[str],
    ) -> None:
        """
        Marque une étape franchie sans avoir tourné.

        Un agent désactivé ou écarté ne tournera pas davantage à la reprise :
        le laisser « à faire » rendrait l'exécution indéfiniment inachevée.

        Args:
            point: Le point de reprise, ou `None`.
            agent_id: L'agent écarté.
            motif: Pourquoi.
            user_id: Le propriétaire de l'exécution.
        """
        if point is None:
            return
        try:
            self.checkpoints.record_skip(point.run_id, agent_id, motif, subject=user_id)
        except CheckpointRefused as refus:
            self.logger.warning("Point de reprise non mis à jour : %s", refus)

    def _dispatch_agent(
        self,
        agent_config: Dict[str, Any],
        input_data: Any,
        context: Optional[AgentContext] = None,
    ) -> Dict[str, Any]:
        """
        Envoie la tâche à un agent spécifique en utilisant le AgentDispatcher.

        Args:
            agent_config: Configuration de l'agent à exécuter.
            input_data: Données d'entrée pour l'agent.
            context: Contexte partagé de la requête, donnant accès aux moteurs.

        Returns:
            Résultat de l'exécution de l'agent.
        """
        agent_id = agent_config.get('id')

        # Cas spécial : le routeur est l'orchestrateur actuel, nous ne nous exécutons pas nous-mêmes
        if agent_id == 'router':
            # Le routeur ne s'appelle pas lui-même pour éviter la récursion infinie.
            # Au lieu de cela, nous retournons simplement la demande utilisateur telle quelle
            # ou nous pourrions effectuer un prétraitement ici si nécessaire.
            return {
                "agent": agent_id,
                "status": "success",
                "result": input_data,  # Passe la demande telle quelle
                "note": "Le routeur agit en tant qu'orchestrateur et transmet l'entrée."
            }

        # Utiliser le dispatcher pour les autres agents
        return self.agent_dispatcher.dispatch(agent_config, input_data, context)