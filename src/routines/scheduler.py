"""
Scheduling and firing: deciding what is due, and running it once.

Two things are separated here on purpose, because merging them is what makes
schedulers untestable.

**Deciding is pure.** `due_at(now)` is a function of the registry and a
timestamp. No clock is read, no thread is started, nothing sleeps. Whoever
drives time — a loop, a cron entry, a test — passes it in. A scheduler that
reads `time.time()` internally can only be tested by waiting, and a test that
waits is a test that is eventually deleted.

**Running is guarded.** Three guards, and each exists because of what "nobody is
watching" means:

- **The capability is re-checked at firing.** Declaration checked it (47.1), but
  the tool registry can be reloaded between then and three in the morning. The
  check costs nothing and closes the window.
- **A routine does not overlap itself.** If it is still running when its next
  turn comes, the turn is skipped and said so. Two copies of the same nightly
  job racing each other is a class of bug nobody debugs at that hour.
- **Repeated failure stops the routine.** A routine that fails every hour is not
  monitoring anything; it is generating noise and consuming a slot. After a
  named number of consecutive failures it disables itself **and records why**,
  because stopping silently would be worse than failing loudly.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..audit_engine.types import generate_request_id
from ..tool.capabilities import CapabilityRegistry, may_run_unattended
from .registry import RoutineRegistry
from .safety import RoutineSafety
from .types import Routine, RoutineAction
from .workflow_action import ACTION_WORKFLOW, STATUT_SUSPENDU, WorkflowAction

#: Échecs consécutifs au-delà desquels une routine s'arrête d'elle-même. Trois :
#: assez pour absorber une panne passagère, assez peu pour qu'une routine
#: durablement cassée cesse de consommer un créneau sans que personne ne le voie.
ECHECS_AVANT_ARRET = 3


@dataclass
class ActionOutcome:
    """
    Ce qu'une action a donné.

    Attributes:
        tool_id: L'outil appelé.
        status: `success`, `refused` ou `error`.
        detail: Ce qui s'est passé, en clair.
        elapsed_ms: Durée mesurée.
    """

    tool_id: str
    status: str
    detail: str = ""
    elapsed_ms: float = 0.0
    run_id: str = ""

    @property
    def ok(self) -> bool:
        """
        Vrai pour un succès franc.

        `suspended` n'en est pas un : une exécution arrêtée sur une approbation
        n'a pas fini. La compter comme réussie ferait de « personne n'était là
        pour répondre » un « oui ».
        """
        return self.status == "success"

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, sans le résultat de l'outil."""
        rendu = {
            "tool_id": self.tool_id,
            "status": self.status,
            "detail": self.detail,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }
        if self.run_id:
            # Sans lui, une exécution suspendue attend une décision que personne
            # ne peut retrouver.
            rendu["run_id"] = self.run_id
        return rendu


@dataclass
class RoutineRun:
    """
    Une exécution de routine, réussie ou non.

    Attributes:
        routine_id: La routine exécutée.
        started_at: Quand.
        actions: Le résultat de chaque action, dans l'ordre.
        skipped: Pourquoi le tour a été sauté, s'il l'a été.
        disabled_after: Vrai si la routine s'est arrêtée à la fin de ce tour.
        correlation_id: L'identifiant qui suit ce tour partout où il va
            (VOLET 66). Il devient le `request_id` du workflow déclenché, donc
            celui de ses événements d'audit : c'est ce qui permet de relire un
            travail de bout en bout au lieu de trois fragments qui se
            ressemblent.
    """

    routine_id: str
    started_at: float
    actions: List[ActionOutcome] = field(default_factory=list)
    skipped: str = ""
    disabled_after: bool = False
    correlation_id: str = ""

    @property
    def ok(self) -> bool:
        """
        Vrai si le tour a fait ce qu'il devait.

        Un tour sauté n'est **pas** un succès : il n'a rien fait. Le compter
        comme réussi cacherait une routine qui ne tourne jamais.
        """
        return not self.skipped and bool(self.actions) and all(
            action.ok for action in self.actions
        )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "routine_id": self.routine_id,
            "started_at": self.started_at,
            "ok": self.ok,
            "skipped": self.skipped,
            "disabled_after": self.disabled_after,
            "correlation_id": self.correlation_id,
            "actions": [action.as_dict() for action in self.actions],
        }


class RoutineScheduler:
    """
    Décide ce qui est dû, exécute ce qui l'est, et arrête ce qui échoue.

    Ne démarre aucun fil et ne dort jamais : le temps est fourni par l'appelant.
    """

    def __init__(
        self,
        registry: RoutineRegistry,
        tool_engine: Any = None,
        capabilities: Optional[CapabilityRegistry] = None,
        safety: Optional[RoutineSafety] = None,
        notifier: Any = None,
        orchestrator: Any = None,
    ) -> None:
        """
        Args:
            registry: Le registre des routines déclarées.
            tool_engine: Le moteur d'outils. Sans lui, une exécution rapporte
                son indisponibilité au lieu de prétendre avoir tourné.
            capabilities: Les capacités, pour la revérification au
                déclenchement. Celles du moteur d'outils par défaut.
            safety: Le budget et l'arrêt d'urgence (VOLET 48). Séparé du
                planificateur : ce qui protège ne doit pas dépendre de ce qui
                exécute.
            notifier: Le témoin (VOLET 50). Facultatif, et jamais bloquant :
                une routine qui s'arrête à trois heures du matin ne le dit à
                personne, et un journal n'est pas une notification — il est lu
                par quelqu'un qui soupçonne déjà quelque chose.
            orchestrator: Le moteur de routage (VOLET 64), pour les routines qui
                déclenchent un workflow. Sans lui, une telle action rapporte
                l'orchestrateur absent au lieu de prétendre avoir tourné.
        """
        self.registry = registry
        self._temoin = notifier
        self._orchestrateur = orchestrator
        self.safety = safety if safety is not None else RoutineSafety()
        self._outils = tool_engine
        self._capacites = capabilities if capabilities is not None else getattr(
            tool_engine, "capabilities", None
        )
        self._verrou = threading.RLock()
        self._derniere_execution: Dict[str, float] = {}
        self._en_cours: set = set()
        self._echecs: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Décider
    # ------------------------------------------------------------------

    def due_at(self, now: float) -> List[Routine]:
        """
        Les routines actives dont le tour est venu.

        Une routine jamais exécutée est due immédiatement : attendre un
        intervalle complet avant le premier tour rendrait une routine horaire
        inerte pendant une heure après son activation, ce que personne
        n'attend.

        Args:
            now: L'instant considéré.

        Returns:
            Les routines dues, triées par identifiant.
        """
        if self.safety.halted:
            # Rien n'est dû pendant un arrêt : le dire ici évite que l'appelant
            # boucle sur des tours refusés un par un.
            return []

        dues = []
        with self._verrou:
            for routine in self.registry.enabled_routines():
                derniere = self._derniere_execution.get(routine.routine_id)
                if derniere is None or now - derniere >= routine.interval_seconds:
                    dues.append(routine)
        return dues

    def next_due(self, routine_id: str, now: float) -> Optional[float]:
        """
        Quand une routine sera due, en secondes depuis l'époque.

        Args:
            routine_id: La routine.
            now: L'instant considéré.

        Returns:
            L'instant du prochain tour, ou `None` si elle est inactive.
        """
        routine = self.registry.get(routine_id)
        if routine is None or not routine.enabled:
            return None
        with self._verrou:
            derniere = self._derniere_execution.get(routine_id)
        return now if derniere is None else derniere + routine.interval_seconds

    # ------------------------------------------------------------------
    # Exécuter
    # ------------------------------------------------------------------

    def run(self, routine: Routine, now: Optional[float] = None) -> RoutineRun:
        """
        Exécute une routine, une fois.

        Args:
            routine: La routine à exécuter.
            now: L'instant, pour les tests.

        Returns:
            Le compte rendu du tour, y compris quand il a été sauté.
        """
        instant = now if now is not None else time.time()
        # L'identifiant est posé avant tout, y compris avant les gardes : un
        # tour refusé par le budget est un fait à retrouver, pas un non-
        # événement.
        tour = RoutineRun(
            routine_id=routine.routine_id, started_at=instant,
            correlation_id=generate_request_id(),
        )

        permis, motif = self.safety.check(routine.routine_id, instant)
        if not permis:
            tour.skipped = motif
            if "Budget épuisé" in motif:
                # Épuisé n'est pas « saute ce tour » : une routine sautée en
                # silence paraît tourner et ne fait rien. Elle s'arrête, et
                # quelqu'un relèvera le budget délibérément.
                self.registry.disable(routine.routine_id)
                tour.disabled_after = True
                self._prevenir(routine, motif)
            return tour

        with self._verrou:
            if routine.routine_id in self._en_cours:
                tour.skipped = (
                    "Le tour précédent n'est pas terminé. Deux copies de la "
                    "même routine qui se courent après sont un bogue que "
                    "personne ne débogue à trois heures du matin."
                )
                return tour
            self._en_cours.add(routine.routine_id)
            self._derniere_execution[routine.routine_id] = instant
        self.safety.consume(routine.routine_id, instant)

        try:
            for action in routine.actions:
                tour.actions.append(self._executer(action, routine, tour.correlation_id))
        finally:
            with self._verrou:
                self._en_cours.discard(routine.routine_id)

        self._compter(routine, tour)
        return tour

    def _executer(
        self, action: RoutineAction, routine: Routine, correlation_id: str = "",
    ) -> ActionOutcome:
        """
        Exécute une action, en revérifiant qu'elle peut tourner sans témoin.

        La déclaration l'avait vérifié (47.1) ; le registre des capacités peut
        avoir été rechargé depuis. Revérifier ne coûte rien et ferme la fenêtre.

        Args:
            action: L'action à exécuter — un appel d'outil, ou un workflow.
            routine: La routine à qui elle appartient. C'est d'elle que vient le
                propriétaire de l'exécution : à trois heures du matin il n'y a
                pas de session dont le déduire.
            correlation_id: L'identifiant du tour, transmis à ce qui sait le
                porter.
        """
        if isinstance(action, WorkflowAction):
            return self._executer_workflow(action, routine, correlation_id)

        autorise, motif = may_run_unattended(
            action.tool_id, self._capacites, arguments=action.operation
        )
        if not autorise:
            return ActionOutcome(
                tool_id=action.tool_id, status="refused",
                detail=f"Revérifié au déclenchement : {motif}",
            )

        if self._outils is None:
            return ActionOutcome(
                tool_id=action.tool_id, status="error",
                detail=(
                    "Moteur d'outils indisponible : le tour est rapporté comme "
                    "en échec, pas comme réussi sans rien faire."
                ),
            )

        depart = time.monotonic()
        try:
            self._outils.execute_tool(
                action.tool_id, action.operation, **dict(action.options)
            )
        except Exception as erreur:
            return ActionOutcome(
                tool_id=action.tool_id, status="error",
                detail=f"{type(erreur).__name__}: {erreur}",
                elapsed_ms=(time.monotonic() - depart) * 1000,
            )

        return ActionOutcome(
            tool_id=action.tool_id, status="success",
            elapsed_ms=(time.monotonic() - depart) * 1000,
        )

    def _executer_workflow(
        self, action: WorkflowAction, routine: Routine, correlation_id: str = "",
    ) -> ActionOutcome:
        """
        Fait tourner un workflow complet, sans personne devant.

        Le travail passe par l'**orchestrateur du dépôt**, celui de tout le
        reste : il apporte ses points de reprise, son historique d'exécution,
        ses reprises d'agent et son événement d'audit. Un second chemin
        d'exécution qui n'aurait rien de tout cela serait une implémentation
        parallèle, et c'est précisément ce que ce VOLET referme.

        La règle propre à l'exécution sans témoin : **une approbation n'est
        jamais accordée par l'absence de quelqu'un pour la refuser.** Une
        exécution arrêtée sur `requires_approval` est rendue `suspended`, avec
        son `run_id` — quelqu'un la reprendra.

        Args:
            action: L'action de workflow.
            routine: La routine, d'où viennent le propriétaire et la demande de
                repli.
            correlation_id: L'identifiant du tour. Il **devient** le
                `request_id` de l'exécution, donc celui de ses événements
                d'audit : sans cela, un tour de routine et le travail qu'il
                déclenche portent deux identifiants que rien ne relie.

        Returns:
            Le résultat de l'exécution, y compris suspendue.
        """
        if self._orchestrateur is None:
            return ActionOutcome(
                tool_id=ACTION_WORKFLOW, status="error",
                detail=(
                    "Orchestrateur indisponible : le tour est rapporté comme en "
                    "échec, pas comme réussi sans rien faire."
                ),
            )

        depart = time.monotonic()
        try:
            reponse = self._orchestrateur.process_request(
                action.operation or routine.description,
                workflow_id=action.workflow_id,
                user_id=routine.subject,
                # L'exécution est la même ; sa lecture d'après ne l'est pas. Une
                # approbation restée sans réponse toute la nuit se lirait sinon
                # comme un utilisateur qui a changé d'avis.
                unattended=True,
                request_id=correlation_id or None,
            )
        except Exception as erreur:
            return ActionOutcome(
                tool_id=ACTION_WORKFLOW, status="error",
                detail=f"{type(erreur).__name__}: {erreur}",
                elapsed_ms=(time.monotonic() - depart) * 1000,
            )

        duree = (time.monotonic() - depart) * 1000
        statut = reponse.get("status")
        identifiant = str(reponse.get("run_id") or "")

        if statut == "requires_approval":
            return ActionOutcome(
                tool_id=ACTION_WORKFLOW, status=STATUT_SUSPENDU,
                detail=(
                    f"Workflow '{action.workflow_id}' suspendu : une étape "
                    "attend une décision humaine. Personne n'était là pour la "
                    "prendre, et l'absence de refus n'est pas un accord."
                ),
                elapsed_ms=duree, run_id=identifiant,
            )

        if statut == "success":
            return ActionOutcome(
                tool_id=ACTION_WORKFLOW, status="success",
                detail=f"Workflow '{action.workflow_id}' exécuté.",
                elapsed_ms=duree, run_id=identifiant,
            )

        return ActionOutcome(
            tool_id=ACTION_WORKFLOW, status="error",
            detail=(
                f"Workflow '{action.workflow_id}' : {statut}. "
                f"{reponse.get('error') or ''}".strip()
            ),
            elapsed_ms=duree, run_id=identifiant,
        )

    def _compter(self, routine: Routine, tour: RoutineRun) -> None:
        """
        Compte les échecs consécutifs, et arrête la routine au-delà du seuil.

        S'arrêter **en le disant** : une routine qui cesserait en silence
        laisserait croire qu'elle veille encore, ce qui est pire que d'échouer
        bruyamment.
        """
        with self._verrou:
            if tour.ok:
                self._echecs.pop(routine.routine_id, None)
                return
            compte = self._echecs.get(routine.routine_id, 0) + 1
            self._echecs[routine.routine_id] = compte

        if compte >= ECHECS_AVANT_ARRET:
            self.registry.disable(routine.routine_id)
            tour.disabled_after = True
            arret = (
                f"{compte} échecs consécutifs : la routine s'arrête. Une "
                "routine qui échoue chaque tour ne surveille rien, elle "
                "occupe un créneau."
            )
            tour.actions.append(ActionOutcome(tool_id="—", status="error", detail=arret))
            self._prevenir(routine, arret)

    def _prevenir(self, routine: Routine, motif: str) -> None:
        """
        Prévient qu'une routine s'est arrêtée d'elle-même.

        Le témoin est facultatif et ne fait jamais tomber le tour : une routine
        qui vient de s'arrêter a assez d'ennuis.
        """
        if self._temoin is None:
            return
        try:
            self._temoin.routine_stopped(
                routine.routine_id, motif, subject=routine.subject,
            )
        except Exception as erreur:
            logging.getLogger(__name__).warning(
                "Arrêt de la routine '%s' non notifié : %s",
                routine.routine_id, erreur,
            )

    def tick(self, now: float) -> List[RoutineRun]:
        """
        Exécute tout ce qui est dû à cet instant.

        Args:
            now: L'instant considéré.

        Returns:
            Les comptes rendus, dans l'ordre d'exécution.
        """
        return [self.run(routine, now=now) for routine in self.due_at(now)]

    # ------------------------------------------------------------------
    # État
    # ------------------------------------------------------------------

    def consecutive_failures(self, routine_id: str) -> int:
        """Le nombre d'échecs consécutifs d'une routine."""
        with self._verrou:
            return self._echecs.get(routine_id, 0)

    def scheduler_report(self, now: Optional[float] = None) -> Dict[str, Any]:
        """
        Ce que le planificateur sait, sans rien exécuter.

        Args:
            now: L'instant considéré.

        Returns:
            Les routines actives, leur prochain tour, et les règles tenues.
        """
        instant = now if now is not None else time.time()
        actives = self.registry.enabled_routines()

        return {
            "enabled": len(actives),
            "due_now": [r.routine_id for r in self.due_at(instant)],
            "running": sorted(self._en_cours),
            "failures": dict(self._echecs),
            "failures_before_stop": ECHECS_AVANT_ARRET,
            "tool_engine_attached": self._outils is not None,
            "safety": self.safety.safety_report(),
            "rules": [
                "La capacité est revérifiée au déclenchement, pas seulement à "
                "la déclaration.",
                "Une routine ne se chevauche pas elle-même ; le tour est sauté "
                "et dit.",
                "Un tour sauté n'est pas un succès : il n'a rien fait.",
                f"{ECHECS_AVANT_ARRET} échecs consécutifs arrêtent la routine, "
                "en le disant.",
                "Le temps vient de l'appelant : rien ne dort, rien ne lit "
                "l'horloge en douce.",
            ],
        }
