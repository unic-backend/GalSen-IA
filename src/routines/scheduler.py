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

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..tool.capabilities import CapabilityRegistry, may_run_unattended
from .registry import RoutineRegistry
from .types import Routine, RoutineAction

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

    @property
    def ok(self) -> bool:
        """Vrai pour un succès franc."""
        return self.status == "success"

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, sans le résultat de l'outil."""
        return {
            "tool_id": self.tool_id,
            "status": self.status,
            "detail": self.detail,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


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
    """

    routine_id: str
    started_at: float
    actions: List[ActionOutcome] = field(default_factory=list)
    skipped: str = ""
    disabled_after: bool = False

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
    ) -> None:
        """
        Args:
            registry: Le registre des routines déclarées.
            tool_engine: Le moteur d'outils. Sans lui, une exécution rapporte
                son indisponibilité au lieu de prétendre avoir tourné.
            capabilities: Les capacités, pour la revérification au
                déclenchement. Celles du moteur d'outils par défaut.
        """
        self.registry = registry
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
        tour = RoutineRun(routine_id=routine.routine_id, started_at=instant)

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

        try:
            for action in routine.actions:
                tour.actions.append(self._executer(action))
        finally:
            with self._verrou:
                self._en_cours.discard(routine.routine_id)

        self._compter(routine, tour)
        return tour

    def _executer(self, action: RoutineAction) -> ActionOutcome:
        """
        Exécute une action, en revérifiant qu'elle peut tourner sans témoin.

        La déclaration l'avait vérifié (47.1) ; le registre des capacités peut
        avoir été rechargé depuis. Revérifier ne coûte rien et ferme la fenêtre.
        """
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
            tour.actions.append(ActionOutcome(
                tool_id="—", status="error",
                detail=(
                    f"{compte} échecs consécutifs : la routine s'arrête. Une "
                    "routine qui échoue chaque tour ne surveille rien, elle "
                    "occupe un créneau."
                ),
            ))

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
