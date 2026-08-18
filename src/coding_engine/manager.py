"""
Coding Engine : le moteur natif de GalSen IA (ADR-028).

C'est ici que la plateforme reste propriétaire de son architecture. OpenHands,
Aider et SWE-agent sont des **implémentations** derrière une interface ; le
gouvernement de l'exécution — confinement, approbation, audit, choix du modèle —
appartient à GalSen IA et ne leur est jamais délégué.

Une exécution suit toujours le même ordre, et cet ordre est la garantie :

1. L'espace de travail est résolu ; rien ne se fait hors de lui.
2. La politique de conteneur est vérifiée, si l'exploitant en exige un.
3. L'instruction est examinée : destructrice → refus, sensible → approbation.
4. Le moteur est choisi par capacité, jamais par nom.
5. Le modèle vient du Model Engine ; **aucun** moteur n'en choisit un.
6. Le moteur travaille sous une borne de temps finie.
7. L'audit enregistre ce qui s'est passé, sans jamais un secret.

Les moteurs d'audit et d'approbation sont ceux de la plateforme
(`src/audit_engine/`, `src/approval_engine/`). Aucune seconde gouvernance n'est
créée ici : ADR-006 a tranché, et un second mécanisme aurait fait deux vérités.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence

from src.approval_engine.types import ApprovalRequest, ApprovalStatus
from src.audit_engine.types import AuditEvent, AuditEventType, AuditStatus
from src.coding_engine.interfaces import CodingEngineAdapter
from src.coding_engine.router import CodingRouter, RoutingDecision
from src.coding_engine.types import (
    CodingStatus,
    CodingTask,
    CodingTaskResult,
    EngineAvailability,
    ModelSpec,
)
from src.coding_engine.workspace import (
    WorkspaceError,
    container_required,
    inspect_instruction,
    resolve_workspace,
    running_in_container,
)

logger = logging.getLogger(__name__)

VARIABLE_MOTEURS = "GALSEN_CODING_ENGINES"

# Un moteur de codage peut travailler longtemps ; la borne haute existe pour
# qu'une requête d'API ne puisse pas immobiliser un fil indéfiniment.
DELAI_MAXIMUM_SECONDES = 3600


class CodingEngineManager:
    """Point d'entrée unique du Coding Engine."""

    def __init__(
        self,
        adapters: Optional[Sequence[CodingEngineAdapter]] = None,
        audit_manager: Any = None,
        approval_manager: Any = None,
        model_manager: Any = None,
    ):
        """
        Initialise le moteur.

        Args:
            adapters: Adaptateurs à enregistrer. Les trois adaptateurs livrés
                sont pris par défaut, filtrés par `GALSEN_CODING_ENGINES`.
            audit_manager: Moteur d'audit de la plateforme.
            approval_manager: Moteur d'approbation de la plateforme.
            model_manager: Moteur de modèles, source unique du choix de modèle.
        """
        self._adapters: List[CodingEngineAdapter] = list(
            adapters if adapters is not None else _adaptateurs_par_defaut()
        )
        self._audit = audit_manager
        self._approval = approval_manager
        self._models = model_manager
        self._router = CodingRouter(self._adapters)

    # ------------------------------------------------------------------
    # Registre
    # ------------------------------------------------------------------

    def register(self, adapter: CodingEngineAdapter) -> None:
        """
        Enregistre un adaptateur, ou remplace celui de même identifiant.

        Args:
            adapter: L'adaptateur à enregistrer.
        """
        self._adapters = [a for a in self._adapters if a.engine_id != adapter.engine_id]
        self._adapters.append(adapter)
        self._router = CodingRouter(self._adapters)

    @property
    def engine_ids(self) -> List[str]:
        """Identifiants des moteurs enregistrés, dans l'ordre de préférence."""
        return [a.engine_id for a in self._adapters]

    def get(self, engine_id: str) -> Optional[CodingEngineAdapter]:
        """
        Retourne un adaptateur par son identifiant.

        Args:
            engine_id: Identifiant du moteur.

        Returns:
            L'adaptateur, ou `None` s'il n'est pas enregistré.
        """
        return next((a for a in self._adapters if a.engine_id == engine_id), None)

    def availability(self) -> List[EngineAvailability]:
        """
        Interroge l'état de chaque moteur.

        Un adaptateur qui lève est rapporté indisponible : l'état de la
        plateforme ne doit pas tomber parce qu'un moteur externe se comporte mal.

        Returns:
            L'état de chaque moteur enregistré.
        """
        etats = []
        for adaptateur in self._adapters:
            try:
                etats.append(adaptateur.check_availability())
            except Exception as erreur:  # noqa: BLE001 — un moteur tiers peut tout lever
                logger.warning("Sonde de %s en échec : %s", adaptateur.engine_id, erreur)
                etats.append(
                    EngineAvailability(
                        engine_id=adaptateur.engine_id, available=False,
                        detail=f"Sonde en échec : {erreur}",
                        capabilities=adaptateur.capabilities,
                    )
                )
        return etats

    def status(self) -> Dict[str, Any]:
        """
        Décrit l'état du moteur pour l'API et la supervision.

        Returns:
            Les moteurs, leur état, et si au moins un peut travailler.
        """
        etats = self.availability()
        return {
            "engines": [e.to_dict() for e in etats],
            "available_engines": [e.engine_id for e in etats if e.available],
            "any_available": any(e.available for e in etats),
            "container_required": container_required(),
            "in_container": running_in_container(),
        }

    # ------------------------------------------------------------------
    # Exécution
    # ------------------------------------------------------------------

    def execute(self, task: CodingTask) -> CodingTaskResult:
        """
        Exécute une tâche de codage de bout en bout.

        Args:
            task: La tâche demandée.

        Returns:
            Le résultat normalisé. La méthode ne lève pas : une panne de moteur
            externe est une donnée du résultat, pas une exception qui remonte
            jusqu'à l'appelant.
        """
        debut = time.time()
        refus = self._verifier_les_prealables(task, debut)
        if refus is not None:
            return self._journaliser(task, refus, None)

        attente = self._verifier_l_approbation(task, debut)
        if attente is not None:
            return self._journaliser(task, attente, None)

        decision = self._router.route(task, self._disponibilite())
        if decision.engine_id is None:
            return self._journaliser(
                task,
                CodingTaskResult.unavailable(
                    "aucun", task.id, decision.reason,
                    execution_time_seconds=time.time() - debut,
                    raw_metadata={"rejected": decision.rejected},
                ),
                decision,
            )

        adaptateur = self.get(decision.engine_id)
        modele = self._modele()
        try:
            resultat = adaptateur.execute(_borner_le_delai(task), modele)
        except Exception as erreur:  # noqa: BLE001 — un moteur tiers peut tout lever
            logger.exception("Le moteur %s a levé", decision.engine_id)
            resultat = CodingTaskResult(
                status=CodingStatus.FAILURE, engine_id=decision.engine_id,
                task_id=task.id, summary=f"Le moteur a levé une exception : {erreur}",
                errors=[str(erreur)], execution_time_seconds=time.time() - debut,
                model=modele,
            )

        return self._journaliser(task, resultat, decision)

    # ------------------------------------------------------------------
    # Préalables
    # ------------------------------------------------------------------

    def _verifier_les_prealables(
        self, task: CodingTask, debut: float
    ) -> Optional[CodingTaskResult]:
        """
        Contrôle l'espace de travail, la politique de conteneur et l'instruction.

        Returns:
            Un résultat de refus, ou `None` si tout passe.
        """
        try:
            resolve_workspace(task.workspace)
        except WorkspaceError as erreur:
            return CodingTaskResult(
                status=CodingStatus.FAILURE, engine_id="aucun", task_id=task.id,
                summary=str(erreur), errors=[str(erreur)],
                execution_time_seconds=time.time() - debut,
            )

        if container_required() and not running_in_container():
            detail = (
                "Exécution refusée : l'exploitant exige un conteneur "
                "(GALSEN_CODING_REQUIRE_CONTAINER) et ce processus n'en est pas un. "
                "Un moteur de codage lancé hors conteneur voit tout ce que voit "
                "l'utilisateur courant."
            )
            return CodingTaskResult(
                status=CodingStatus.REJECTED, engine_id="aucun", task_id=task.id,
                summary=detail, errors=[detail],
                execution_time_seconds=time.time() - debut,
            )

        verdict = inspect_instruction(task.instruction, allow_push=task.allow_push)
        if not verdict.allowed:
            detail = (
                "Instruction refusée — "
                + ", ".join(verdict.reasons)
                + ". Ce refus n'est pas contournable par approbation."
            )
            return CodingTaskResult(
                status=CodingStatus.REJECTED, engine_id="aucun", task_id=task.id,
                summary=detail, errors=[detail],
                execution_time_seconds=time.time() - debut,
            )
        return None

    def _verifier_l_approbation(
        self, task: CodingTask, debut: float
    ) -> Optional[CodingTaskResult]:
        """
        Soumet une demande d'approbation quand l'instruction en exige une.

        Une demande déjà approuvée, transmise par `metadata["approval_request_id"]`,
        laisse passer l'exécution. Une demande rejetée l'arrête.

        Returns:
            Un résultat en attente ou rejeté, ou `None` si l'exécution peut suivre.
        """
        verdict = inspect_instruction(task.instruction, allow_push=task.allow_push)
        if not verdict.needs_approval:
            return None

        identifiant = task.metadata.get("approval_request_id")
        if identifiant and self._approval:
            demande = self._approval.get(identifiant)
            if demande and demande.status == ApprovalStatus.APPROVED.value:
                return None
            if demande and demande.status == ApprovalStatus.REJECTED.value:
                detail = f"Approbation refusée : {demande.reason or 'sans motif'}."
                return CodingTaskResult(
                    status=CodingStatus.REJECTED, engine_id="aucun", task_id=task.id,
                    summary=detail, errors=[detail], approval_request_id=identifiant,
                    execution_time_seconds=time.time() - debut,
                )

        if not self._approval:
            # Sans moteur d'approbation, on refuse plutôt que de passer outre :
            # une porte de gouvernance absente n'est pas une porte ouverte.
            detail = (
                "Cette tâche exige une approbation humaine ("
                + ", ".join(verdict.reasons)
                + ") et le moteur d'approbation est indisponible."
            )
            return CodingTaskResult(
                status=CodingStatus.REJECTED, engine_id="aucun", task_id=task.id,
                summary=detail, errors=[detail],
                execution_time_seconds=time.time() - debut,
            )

        demande = ApprovalRequest(
            agent_id="coding_engine",
            request_id=task.request_id,
            action=f"coding:{task.engine_id or 'auto'}",
            description=(
                "Tâche de codage exigeant une approbation ("
                + ", ".join(verdict.reasons)
                + f") : {task.instruction[:300]}"
            ),
            metadata={
                "task_id": task.id,
                "workspace": task.workspace,
                "reasons": verdict.reasons,
                "user_id": task.user_id,
            },
        )
        nouvel_identifiant = self._approval.submit(demande)
        detail = (
            "En attente d'approbation humaine : " + ", ".join(verdict.reasons) + "."
        )
        return CodingTaskResult(
            status=CodingStatus.REQUIRES_APPROVAL, engine_id="aucun", task_id=task.id,
            summary=detail, approval_request_id=nouvel_identifiant or demande.id,
            execution_time_seconds=time.time() - debut,
        )

    # ------------------------------------------------------------------
    # Modèle et disponibilité
    # ------------------------------------------------------------------

    def _disponibilite(self) -> Dict[str, bool]:
        """Retourne l'état de chaque moteur, sous forme de table."""
        return {etat.engine_id: etat.available for etat in self.availability()}

    def _modele(self) -> Optional[ModelSpec]:
        """
        Demande un modèle au Model Engine et le traduit pour les adaptateurs.

        Aucun modèle n'est choisi ici, et aucun fournisseur n'est privilégié :
        c'est le Model Engine qui décide, comme pour toute autre génération de
        la plateforme. C'est la condition de l'indépendance vis-à-vis des
        fournisseurs.

        Returns:
            La description du modèle, ou `None` si aucun n'est disponible.
        """
        if self._models is None:
            return None
        try:
            choix = self._models.select_model_for_task(
                {"task_type": "code_generation", "complexity": "high"}
            )
        except Exception as erreur:  # noqa: BLE001 — le moteur de modèles peut lever
            logger.warning("Sélection de modèle en échec : %s", erreur)
            return None
        if choix is None:
            return None

        metadonnees = getattr(choix, "metadata", {}) or {}
        return ModelSpec(
            provider_id=getattr(choix, "provider", "") or "",
            model_name=getattr(choix, "name", "") or getattr(choix, "model_id", ""),
            base_url=metadonnees.get("base_url"),
            api_key_env=metadonnees.get("api_key_env"),
        )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def _journaliser(
        self,
        task: CodingTask,
        resultat: CodingTaskResult,
        decision: Optional[RoutingDecision],
    ) -> CodingTaskResult:
        """
        Enregistre l'exécution dans l'audit de la plateforme.

        Aucun secret n'entre dans la trace : `ModelSpec` ne porte que le **nom**
        de la variable d'environnement d'une clé, et `ProcessResult.to_dict()`
        ne rend que le nom de l'exécutable, jamais ses arguments.

        Returns:
            Le résultat, enrichi de l'identifiant d'audit quand il existe.
        """
        if self._audit is None:
            return resultat

        evenement = AuditEvent(
            event_type=AuditEventType.CODING,
            action=f"coding.{resultat.engine_id}",
            agent_id="coding_engine",
            request_id=task.request_id,
            user_request=task.instruction[:500],
            model_id=resultat.model.model_name if resultat.model else None,
            status=_statut_d_audit(resultat.status),
            execution_time_seconds=resultat.execution_time_seconds,
            detail=resultat.summary[:500],
            metadata={
                "task": task.to_dict(),
                "engine_id": resultat.engine_id,
                "files_changed": [f.to_dict() for f in resultat.files_changed],
                "tests": resultat.tests.to_dict() if resultat.tests else None,
                "errors": resultat.errors[:5],
                "approval_request_id": resultat.approval_request_id,
                "model": resultat.model.to_dict() if resultat.model else None,
                "routing": {
                    "reason": decision.reason,
                    "considered": decision.considered,
                    "rejected": decision.rejected,
                } if decision else None,
            },
        )
        try:
            identifiant = self._audit.record(evenement)
        except Exception as erreur:  # noqa: BLE001 — l'audit ne doit jamais casser l'appel
            logger.warning("Audit de la tâche %s impossible : %s", task.id, erreur)
            return resultat

        return CodingTaskResult(
            **{**resultat.__dict__, "audit_id": identifiant}
        )


# ----------------------------------------------------------------------
# Construction
# ----------------------------------------------------------------------

def _adaptateurs_par_defaut() -> List[CodingEngineAdapter]:
    """
    Construit les adaptateurs livrés, filtrés par la configuration.

    `GALSEN_CODING_ENGINES` restreint et **ordonne** la liste : c'est ainsi que
    l'exploitant désactive un moteur ou change la préférence en cas d'égalité,
    sans toucher au code.

    Returns:
        Les adaptateurs à enregistrer.
    """
    from src.coding_engine.adapters import AiderAdapter, OpenHandsAdapter, SweAgentAdapter

    connus = {
        "aider": AiderAdapter,
        "openhands": OpenHandsAdapter,
        "swe_agent": SweAgentAdapter,
    }
    demandes = [
        nom.strip() for nom in os.environ.get(VARIABLE_MOTEURS, "").split(",") if nom.strip()
    ]
    if not demandes:
        return [AiderAdapter(), SweAgentAdapter(), OpenHandsAdapter()]

    adaptateurs = []
    for nom in demandes:
        classe = connus.get(nom)
        if classe is None:
            logger.warning("Moteur de codage « %s » inconnu, ignoré.", nom)
            continue
        adaptateurs.append(classe())
    return adaptateurs


def _borner_le_delai(task: CodingTask) -> CodingTask:
    """
    Ramène le délai d'une tâche dans les bornes de la plateforme.

    Un délai nul ou négatif serait une attente sans fin ; un délai démesuré
    immobiliserait un fil pour la journée.
    """
    delai = min(max(int(task.timeout_seconds), 1), DELAI_MAXIMUM_SECONDES)
    if delai == task.timeout_seconds:
        return task
    return CodingTask(**{**task.__dict__, "timeout_seconds": delai})


def _statut_d_audit(statut: CodingStatus) -> AuditStatus:
    """Traduit un statut de codage en statut d'audit."""
    return {
        CodingStatus.SUCCESS: AuditStatus.SUCCESS,
        CodingStatus.FAILURE: AuditStatus.FAILURE,
        CodingStatus.UNAVAILABLE: AuditStatus.UNAVAILABLE,
        CodingStatus.TIMEOUT: AuditStatus.FAILURE,
        CodingStatus.CANCELLED: AuditStatus.SKIPPED,
        CodingStatus.REJECTED: AuditStatus.FAILURE,
        CodingStatus.REQUIRES_APPROVAL: AuditStatus.REQUIRES_APPROVAL,
    }[statut]
