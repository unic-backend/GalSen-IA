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

import logging
import os
import time
from typing import Dict, Any, List, Optional
from .config_loader import ConfigLoader
from .agent_loader import AgentLoader
from .workflow_loader import WorkflowLoader
from .execution_planner import ExecutionPlanner
from .result_aggregator import ResultAggregator
from .retry_manager import RetryManager
from .agent_dispatcher import AgentDispatcher
from .workflow_history import WorkflowHistory
from .logger import Logger
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

        self.logger.info("RouterEngine initialisé avec succès.")

    def process_request(
        self,
        user_request: str,
        workflow_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Traite une requête utilisateur en orchestrant les agents selon le workflow.

        Args:
            user_request: La requête de l'utilisateur en langage naturel.
            workflow_id: Identifiant du workflow à utiliser (optionnel, utilise le défaut sinon).
            user_id: Utilisateur à l'origine de la requête, pour isoler ses mémoires.
            session_id: Session à laquelle rattacher la requête.

        Returns:
            Un dictionnaire contenant la réponse finale et les métadonnées d'exécution.
        """
        start_time = time.time()
        request_id = generate_request_id()
        # Le contexte n'est créé qu'après la planification ; il reste None si une
        # exception survient avant, et l'audit d'échec doit le prendre en compte.
        context: Optional[AgentContext] = None
        self.logger.info(f"Début du traitement de la requête: {user_request[:100]}...")

        try:
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

            # Exécution séquentielle des agents (pour une première version simple)
            all_agent_results = []  # Pour stocker tous les résultats détaillés
            agent_durations = {}  # Durée observée de chaque agent, reprises comprises

            for agent_id in ordered_agents:
                if not self.agent_loader.is_enabled(agent_id):
                    self.logger.warning(f"L'agent '{agent_id}' est désactivé. Ignoré.")
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

            successful_agents = sum(
                1 for r in all_agent_results if r.get('status') == 'success'
            )
            pending_approval_agents = sum(
                1 for r in all_agent_results if r.get('status') == 'requires_approval'
            )
            failed_agents = (
                len(all_agent_results) - successful_agents - pending_approval_agents
            )
            # Quels agents ont échoué, et pas seulement combien : l'analyse des
            # défaillances du chapitre 06 (VOLET 18) demande de nommer la cause,
            # et un compteur ne dit pas si c'est toujours le même agent.
            failing_agents = [
                r.get('agent') for r in all_agent_results
                if r.get('status') not in ('success', 'requires_approval') and r.get('agent')
            ]

            if failed_agents > 0:
                status = "partial_success"
            elif pending_approval_agents > 0:
                # Aucune erreur mais au moins une action attend une décision
                # humaine : la requête est suspendue (ADR-006).
                status = "requires_approval"
            else:
                status = "success"

            approval_request_ids = [
                r.get('approval_request_id')
                for r in all_agent_results
                if r.get('status') == 'requires_approval'
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
                }
            }
            if approval_request_ids:
                response["approval_request_ids"] = approval_request_ids

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
                    },
                )
            response["request_id"] = request_id
            return response

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
            if context is not None:
                context.record_audit(
                    AuditEventType.REQUEST,
                    "process_request",
                    status=AuditStatus.FAILURE,
                    execution_time_seconds=round(time.time() - start_time, 2),
                    detail=str(e),
                    metadata={"workflow_id": workflow_id},
                )
            return error_response

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