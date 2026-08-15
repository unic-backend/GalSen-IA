"""
Moteur de routines — le travail que la plateforme fait sans personne devant.

Tout ce qui coûte cher est vérifié à la **déclaration** : une routine qui échoue
chaque nuit à trois heures est une routine dont personne ne voit l'échec.
"""

from .journal import TOURS_CONSERVES, RoutineJournal, RoutineStats
from .registry import RoutineRegistry
from .safety import (
    AGENTS_PAR_FENETRE_PAR_DEFAUT,
    FENETRE_SECONDES,
    TOURS_PAR_FENETRE_PAR_DEFAUT,
    BudgetState,
    RoutineHalted,
    RoutineSafety,
    routine_reachable_tools,
)
from .scheduler import (
    ECHECS_AVANT_ARRET,
    ActionOutcome,
    RoutineRun,
    RoutineScheduler,
)
from .types import (
    ACTIONS_MAXIMUM,
    INTERVALLE_MINIMAL_SECONDES,
    Routine,
    RoutineAction,
    RoutineRefused,
)
from .workflow_action import (
    ACTION_WORKFLOW,
    STATUT_SUSPENDU,
    WorkflowAction,
    workflow_runnable_unattended,
)

__all__ = [
    "ACTION_WORKFLOW",
    "AGENTS_PAR_FENETRE_PAR_DEFAUT",
    "ACTIONS_MAXIMUM",
    "ActionOutcome",
    "ECHECS_AVANT_ARRET",
    "INTERVALLE_MINIMAL_SECONDES",
    "Routine",
    "RoutineAction",
    "RoutineRefused",
    "BudgetState",
    "FENETRE_SECONDES",
    "RoutineHalted",
    "RoutineJournal",
    "RoutineRegistry",
    "RoutineRun",
    "RoutineScheduler",
    "RoutineSafety",
    "RoutineStats",
    "TOURS_PAR_FENETRE_PAR_DEFAUT",
    "routine_reachable_tools",
    "STATUT_SUSPENDU",
    "TOURS_CONSERVES",
    "WorkflowAction",
    "workflow_runnable_unattended",
]
