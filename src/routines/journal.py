"""
The routine journal: what actually happened, and what is no longer kept.

A routine runs unattended, so the journal is the only place anyone will ever
learn what it did. That gives it one hard requirement and one easy way to
betray it.

The requirement: it must stay bounded. A routine firing hourly produces nine
thousand entries a year, and a journal that grows without limit is one that gets
truncated by whoever runs out of disk — losing exactly the oldest evidence.

The betrayal: keeping only the last N runs makes a broken routine look healthy.
Fail on Monday, succeed twenty times by Thursday, and the journal shows nothing
but success while the failure that mattered has scrolled off. So **counters
survive eviction**: total runs, failures, and the last failure's detail are kept
whatever happens to the entries. « It has been fine, look at the journal » is
then a claim the journal can actually support.

Nothing here holds what a routine read. `RoutineRun` already carries no tool
output (phase 47.2), and this module adds nothing to it.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from ..security.isolation import Audience, Owner, may_read
from .scheduler import RoutineRun

#: Nombre de tours conservés par routine. Cinquante : de quoi voir deux jours
#: d'une routine horaire, sans qu'une installation oubliée pendant un an
#: accumule des dizaines de milliers d'entrées.
TOURS_CONSERVES = 50


@dataclass
class RoutineStats:
    """
    Ce qui survit à l'oubli des entrées.

    Sans ces compteurs, une routine cassée le lundi et rétablie le jeudi
    paraîtrait n'avoir jamais échoué : l'échec a défilé hors du journal.

    Attributes:
        runs: Nombre total de tours.
        failures: Nombre total d'échecs.
        skipped: Nombre de tours sautés — ils n'ont rien fait.
        last_failure_at: Quand le dernier échec a eu lieu.
        last_failure_detail: Ce qu'il disait.
        disabled_at: Quand la routine s'est arrêtée d'elle-même, s'il y a lieu.
    """

    runs: int = 0
    failures: int = 0
    skipped: int = 0
    last_failure_at: Optional[float] = None
    last_failure_detail: str = ""
    disabled_at: Optional[float] = None

    @property
    def success_rate(self) -> Optional[float]:
        """
        La part de tours réussis, ou `None` si aucun tour n'a eu lieu.

        `None` et non `1.0` : une routine qui n'a jamais tourné n'a pas un
        succès parfait, elle n'a pas de taux.
        """
        if self.runs == 0:
            return None
        return round((self.runs - self.failures) / self.runs, 4)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "runs": self.runs,
            "failures": self.failures,
            "skipped": self.skipped,
            "success_rate": self.success_rate,
            "last_failure_at": self.last_failure_at,
            "last_failure_detail": self.last_failure_detail,
            "disabled_at": self.disabled_at,
        }


@dataclass
class _Entree:
    """Les tours conservés et les compteurs d'une routine."""

    subject: Optional[str]
    tours: Deque[RoutineRun] = field(
        default_factory=lambda: deque(maxlen=TOURS_CONSERVES)
    )
    stats: RoutineStats = field(default_factory=RoutineStats)


class RoutineJournal:
    """
    Le journal des exécutions, borné, avec des compteurs qui ne le sont pas.

    Thread-safe. Comme le registre, il est en mémoire : la persistance suivra le
    même contrat, et ce qui compte ici est ce qui est conservé et ce qui ne
    l'est pas.
    """

    def __init__(self) -> None:
        self._verrou = threading.RLock()
        self._entrees: Dict[str, _Entree] = {}

    def record(self, run: RoutineRun, subject: Optional[str] = None) -> None:
        """
        Consigne un tour.

        Args:
            run: Le compte rendu produit par le planificateur.
            subject: À qui appartient la routine, pour que le journal se filtre
                comme elle.
        """
        with self._verrou:
            entree = self._entrees.get(run.routine_id)
            if entree is None:
                entree = _Entree(subject=subject)
                self._entrees[run.routine_id] = entree
            elif subject is not None:
                entree.subject = subject

            entree.tours.append(run)
            entree.stats.runs += 1

            if run.skipped:
                entree.stats.skipped += 1
            if not run.ok:
                entree.stats.failures += 1
                entree.stats.last_failure_at = run.started_at
                entree.stats.last_failure_detail = self._motif(run)
            if run.disabled_after:
                entree.stats.disabled_at = run.started_at

    @staticmethod
    def _motif(run: RoutineRun) -> str:
        """Résume pourquoi un tour a échoué, sans recopier ce qu'il a lu."""
        if run.skipped:
            return run.skipped
        for action in run.actions:
            if not action.ok:
                return f"{action.tool_id} : {action.detail}"
        return "Aucune action exécutée."

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def runs(
        self, routine_id: str, subject: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Les derniers tours d'une routine, du plus récent au plus ancien.

        Args:
            routine_id: La routine.
            subject: Pour qui la lecture est faite.
            limit: Combien de tours au plus.

        Returns:
            Les tours visibles par cette audience. Vide si la routine
            appartient à quelqu'un d'autre — le journal de quelqu'un dit ce
            qu'il surveille, exactement comme la liste de ses routines.
        """
        with self._verrou:
            entree = self._entrees.get(routine_id)
            if entree is None or not self._visible(entree, subject):
                return []
            tours = list(entree.tours)

        return [tour.as_dict() for tour in reversed(tours)][: max(1, int(limit))]

    def stats(
        self, routine_id: str, subject: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Les compteurs d'une routine, qui survivent à l'oubli des entrées.

        Args:
            routine_id: La routine.
            subject: Pour qui la lecture est faite.

        Returns:
            Les compteurs, ou `None` si la routine est inconnue ou invisible.
        """
        with self._verrou:
            entree = self._entrees.get(routine_id)
            if entree is None or not self._visible(entree, subject):
                return None
            return entree.stats.as_dict()

    @staticmethod
    def _visible(entree: _Entree, subject: Optional[str]) -> bool:
        """Applique la même règle d'audience que la liste des routines."""
        if entree.subject is None:
            return True
        audience = Audience.user(subject) if subject else Audience.platform()
        return may_read(audience, Owner.user(entree.subject))[0]

    def journal_report(self, subject: Optional[str] = None) -> Dict[str, Any]:
        """
        L'état du journal pour une audience.

        Args:
            subject: Pour qui la lecture est faite.

        Returns:
            Le décompte, les routines en échec, et ce que le journal ne garde
            pas.
        """
        with self._verrou:
            visibles = {
                identifiant: entree
                for identifiant, entree in self._entrees.items()
                if self._visible(entree, subject)
            }
            resume = {
                identifiant: entree.stats.as_dict()
                for identifiant, entree in visibles.items()
            }

        return {
            "routines": len(visibles),
            "retained_runs_per_routine": TOURS_CONSERVES,
            "stats": resume,
            "failing": sorted(
                identifiant for identifiant, stats in resume.items()
                if stats["failures"] > 0 and stats["last_failure_at"] is not None
            ),
            "note": (
                "Les compteurs survivent à l'oubli des entrées : sans eux, une "
                "routine cassée lundi et rétablie jeudi paraîtrait n'avoir "
                "jamais échoué."
            ),
            "never_kept": [
                "Ce qu'une routine a lu — un journal n'est pas un magasin de "
                "données.",
                "Le journal d'une autre personne.",
            ],
        }
