"""
Routine safety: the budget, the stop, and what a routine can never reach.

Phase 47 made routines correct. This one makes them *bounded*, which is a
different property: a correct routine can still call a metered API every five
minutes for a year, and nobody notices until the invoice.

Three things live here.

**A budget, counted per day and enforced by stopping.** Not by skipping — a
routine silently skipped is a routine that appears to run and does nothing,
which is the failure mode this whole VOLET exists to avoid. When the budget is
spent the routine is disabled with the reason recorded, so someone can raise it
deliberately rather than discover it by absence.

**An emergency stop, global and explicit.** One switch halts every routine
without needing to know their names, because the moment you need it is the
moment you do not have the list. It **never expires on its own**: a stop that
lifts itself after an hour is not a stop, it is a delay, and whoever engaged it
would have to keep watching — which is exactly what they were trying to stop
doing.

**A limit on what a routine can reach at all.** Routines call tools, and no tool
manages routines — so a routine cannot enable another, raise its own budget, or
release the emergency stop. That is true today by construction rather than by a
check, which is the better kind of true; a guard test keeps it that way, because
the day someone adds a `routines` tool it stops being true silently.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

#: Fenêtre du budget, en secondes. Une journée : assez long pour qu'une routine
#: horaire ait un sens, assez court pour qu'un emballement se voie le jour même
#: plutôt qu'à la fin du mois.
FENETRE_SECONDES = 86_400

#: Nombre de tours autorisés par fenêtre, à défaut de déclaration. 288 = un tour
#: toutes les cinq minutes, soit la cadence maximale que le plancher
#: d'intervalle autorise. Le défaut ne restreint donc rien de ce qui est déjà
#: déclarable ; il attrape ce qui **change** après coup.
TOURS_PAR_FENETRE_PAR_DEFAUT = 288


class RoutineHalted(RuntimeError):
    """L'arrêt d'urgence est engagé. Aucune routine ne démarre."""


@dataclass
class BudgetState:
    """
    Ce qu'une routine a consommé dans la fenêtre en cours.

    Attributes:
        window_started_at: Début de la fenêtre courante.
        runs: Tours effectués depuis.
        limit: Tours autorisés par fenêtre.
    """

    window_started_at: float
    runs: int = 0
    limit: int = TOURS_PAR_FENETRE_PAR_DEFAUT

    def remaining(self) -> int:
        """Ce qu'il reste, jamais négatif."""
        return max(0, self.limit - self.runs)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "window_started_at": self.window_started_at,
            "runs": self.runs,
            "limit": self.limit,
            "remaining": self.remaining(),
        }


class RoutineSafety:
    """
    Le budget des routines et l'arrêt d'urgence.

    Séparé du planificateur : ce qui protège ne doit pas dépendre de ce qui
    exécute. Un arrêt d'urgence qui vit dans le moteur qu'il arrête est un
    arrêt qu'une panne de ce moteur emporte avec elle.
    """

    def __init__(self, window_seconds: int = FENETRE_SECONDES) -> None:
        """
        Args:
            window_seconds: Durée de la fenêtre de budget.
        """
        self._verrou = threading.RLock()
        self._fenetre = int(window_seconds)
        self._budgets: Dict[str, BudgetState] = {}
        self._limites: Dict[str, int] = {}
        self._arret: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # L'arrêt d'urgence
    # ------------------------------------------------------------------

    def halt(self, engaged_by: str, reason: str, now: Optional[float] = None) -> Dict[str, Any]:
        """
        Engage l'arrêt d'urgence : plus aucune routine ne démarre.

        Args:
            engaged_by: Qui l'engage. Un arrêt anonyme ne se lève pas — personne
                ne sait s'il peut.
            reason: Pourquoi. Elle sera lue par celui qui envisagera de lever.
            now: L'instant, pour les tests.

        Returns:
            L'état de l'arrêt.

        Raises:
            ValueError: Si l'auteur ou la raison manquent.
        """
        if not (engaged_by or "").strip():
            raise ValueError(
                "Un arrêt d'urgence nomme qui l'engage : sinon personne ne sait "
                "s'il a le droit de le lever."
            )
        if not (reason or "").strip():
            raise ValueError(
                "Un arrêt d'urgence dit pourquoi : la raison sera lue par celui "
                "qui envisagera de le lever, peut-être des jours plus tard."
            )

        with self._verrou:
            self._arret = {
                "engaged_by": engaged_by.strip(),
                "reason": reason.strip(),
                "engaged_at": now if now is not None else time.time(),
            }
            return dict(self._arret)

    def release(self) -> bool:
        """
        Lève l'arrêt d'urgence.

        **Il ne se lève jamais tout seul.** Un arrêt qui expire après une heure
        n'est pas un arrêt mais un délai, et celui qui l'a engagé devrait
        continuer à surveiller — précisément ce qu'il cherchait à cesser de
        faire.

        Returns:
            True si un arrêt était engagé.
        """
        with self._verrou:
            engage = self._arret is not None
            self._arret = None
            return engage

    @property
    def halted(self) -> bool:
        """Vrai si l'arrêt d'urgence est engagé."""
        with self._verrou:
            return self._arret is not None

    def halt_state(self) -> Optional[Dict[str, Any]]:
        """L'état de l'arrêt, ou `None`."""
        with self._verrou:
            return dict(self._arret) if self._arret else None

    # ------------------------------------------------------------------
    # Le budget
    # ------------------------------------------------------------------

    def set_limit(self, routine_id: str, runs_per_window: int) -> int:
        """
        Fixe le budget d'une routine.

        Args:
            routine_id: La routine.
            runs_per_window: Tours autorisés par fenêtre.

        Returns:
            La limite retenue.

        Raises:
            ValueError: Si la limite est nulle ou négative. Une limite de zéro
                est une désactivation déguisée : elle laisserait une routine
                paraître active sans jamais tourner.
        """
        limite = int(runs_per_window)
        if limite <= 0:
            raise ValueError(
                f"Budget de {limite} tour(s) pour '{routine_id}' : une limite "
                "nulle est une désactivation déguisée. Arrêtez la routine "
                "explicitement."
            )
        with self._verrou:
            self._limites[routine_id] = limite
            budget = self._budgets.get(routine_id)
            if budget is not None:
                budget.limit = limite
        return limite

    def check(self, routine_id: str, now: float) -> Tuple[bool, str]:
        """
        Cette routine peut-elle démarrer un tour maintenant ?

        Ne consomme rien : demander n'est pas dépenser. C'est `consume` qui
        décompte.

        Args:
            routine_id: La routine.
            now: L'instant considéré.

        Returns:
            Le verdict et sa raison.
        """
        with self._verrou:
            if self._arret is not None:
                return False, (
                    f"Arrêt d'urgence engagé par « {self._arret['engaged_by']} » : "
                    f"{self._arret['reason']}"
                )
            budget = self._budget(routine_id, now)
            if budget.remaining() <= 0:
                return False, (
                    f"Budget épuisé : {budget.runs} tours dans la fenêtre, "
                    f"limite {budget.limit}."
                )
        return True, "Dans le budget."

    def consume(self, routine_id: str, now: float) -> BudgetState:
        """
        Décompte un tour du budget.

        Args:
            routine_id: La routine.
            now: L'instant considéré.

        Returns:
            L'état du budget après décompte.
        """
        with self._verrou:
            budget = self._budget(routine_id, now)
            budget.runs += 1
            return BudgetState(
                window_started_at=budget.window_started_at,
                runs=budget.runs, limit=budget.limit,
            )

    def _budget(self, routine_id: str, now: float) -> BudgetState:
        """Retourne le budget courant, en ouvrant une fenêtre si besoin."""
        budget = self._budgets.get(routine_id)
        limite = self._limites.get(routine_id, TOURS_PAR_FENETRE_PAR_DEFAUT)

        if budget is None or now - budget.window_started_at >= self._fenetre:
            budget = BudgetState(window_started_at=now, runs=0, limit=limite)
            self._budgets[routine_id] = budget
        return budget

    def budget_state(self, routine_id: str) -> Optional[Dict[str, Any]]:
        """L'état du budget d'une routine, ou `None` si elle n'a jamais tourné."""
        with self._verrou:
            budget = self._budgets.get(routine_id)
            return budget.as_dict() if budget else None

    # ------------------------------------------------------------------
    # Rapport
    # ------------------------------------------------------------------

    def safety_report(self) -> Dict[str, Any]:
        """
        Ce qui protège les routines, et ce que ça ne fait pas.

        Returns:
            L'état de l'arrêt, les budgets, et les règles tenues.
        """
        with self._verrou:
            budgets = {
                identifiant: budget.as_dict()
                for identifiant, budget in self._budgets.items()
            }
            arret = dict(self._arret) if self._arret else None

        return {
            "halted": arret is not None,
            "halt": arret,
            "window_seconds": self._fenetre,
            "default_runs_per_window": TOURS_PAR_FENETRE_PAR_DEFAUT,
            "budgets": budgets,
            "rules": [
                "Le budget épuisé **arrête** la routine ; il ne la saute pas. "
                "Une routine sautée en silence paraît tourner et ne fait rien.",
                "L'arrêt d'urgence est global : au moment où l'on en a besoin, "
                "on n'a pas la liste des routines.",
                "Il ne se lève jamais tout seul — un arrêt qui expire est un "
                "délai.",
                "Il nomme qui l'engage et pourquoi : sinon nul ne sait s'il "
                "peut le lever.",
            ],
            "does_not": [
                "Interrompre un tour déjà commencé : il finit, et aucun autre "
                "ne démarre.",
                "Remplacer une limite de dépense chez un fournisseur.",
            ],
        }


def routine_reachable_tools(capabilities: Any) -> Dict[str, Any]:
    """
    Ce qu'une routine peut atteindre, et ce qu'elle ne peut pas.

    Une routine n'appelle que des outils, et aucun outil ne gère les routines :
    elle ne peut donc ni en activer une autre, ni relever son propre budget, ni
    lever l'arrêt d'urgence. C'est vrai **par construction** plutôt que par un
    contrôle, ce qui est la meilleure sorte de vrai — mais cela cesserait
    silencieusement le jour où un outil `routines` serait ajouté au catalogue.

    Args:
        capabilities: Le registre des capacités d'outils.

    Returns:
        Les outils atteignables sans témoin, et l'absence d'outil de gestion
        des routines.
    """
    atteignables = sorted(getattr(capabilities, "unattended_ids", lambda: [])())
    gestion = [
        tool_id for tool_id in atteignables
        if "routine" in tool_id.lower() or "schedul" in tool_id.lower()
    ]
    return {
        "unattended_tools": atteignables,
        "routine_management_tools": gestion,
        "self_escalation_possible": bool(gestion),
        "note": (
            "Aucun outil ne gère les routines : une routine ne peut ni en "
            "activer une autre, ni relever son budget, ni lever l'arrêt "
            "d'urgence. Vrai par construction, gardé par un test."
        ),
    }
