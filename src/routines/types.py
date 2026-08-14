"""
What a routine is, and what it may never be.

A routine is work the platform does with nobody watching. That single fact is
what makes it different from everything else built so far: there is no one to
read a warning, no one to approve a step, and no one to notice that it has been
failing every hour since Tuesday.

So the rules here are all about the moment of **declaration**, not the moment of
execution. A routine naming a tool it may not run unattended is refused when it
is written, not when it fires — a routine that fails every night at three in the
morning is a routine nobody sees fail.

Four rules, each closing a way this goes wrong:

1. **Every tool it names must be runnable without a witness.** That question was
   built in phase 38.1 (`may_run_unattended`) and this is its first real caller.
   A pre-approved bound counts: `python -m pytest` is approved, `python -c` is
   not.
2. **Declaring is not enabling.** A new routine is `enabled: false`, exactly as
   a source in the acquisition registry is. Writing one down and having it start
   running are two decisions, and they belong to two different moments.
3. **A routine belongs to someone, or to the platform — never to nobody.** One
   that touches a person's data must name that person, because there is no
   session to infer it from at three in the morning.
4. **There is a floor under the interval.** A routine every second is a denial
   of service against one's own platform, and against whatever it calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#: Intervalle minimal entre deux exécutions, en secondes. Cinq minutes : assez
#: court pour une surveillance utile, assez long pour qu'une routine mal réglée
#: ne devienne pas une attaque contre son propre fournisseur.
INTERVALLE_MINIMAL_SECONDES = 300

#: Nombre maximal d'actions dans une routine. Au-delà, ce n'est plus une
#: routine mais un workflow, qui a son propre moteur (VOLET 49) avec reprise et
#: points de contrôle — choses qu'une routine n'a pas.
ACTIONS_MAXIMUM = 10


class RoutineRefused(ValueError):
    """Une routine qui ne peut pas être déclarée. Levée à la déclaration."""


@dataclass(frozen=True)
class RoutineAction:
    """
    Un appel d'outil dans une routine.

    Attributes:
        tool_id: L'outil appelé.
        operation: Le premier argument de l'appel — l'opération nommée, ou la
            commande. C'est lui qui décide si une borne pré-approuvée couvre
            l'appel (phase 39.3).
        options: Les arguments nommés.
    """

    tool_id: str
    operation: Any = None
    options: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "tool_id": self.tool_id,
            "operation": self.operation,
            "options": dict(self.options),
        }


@dataclass
class Routine:
    """
    Un travail répété, exécuté sans personne devant.

    Attributes:
        routine_id: Son identifiant, unique au registre.
        description: Ce qu'elle fait, en une phrase lisible par la personne à
            qui elle appartient.
        actions: Les appels d'outils, dans l'ordre.
        interval_seconds: Le temps entre deux exécutions.
        subject: À qui elle appartient. `None` pour une routine de plateforme,
            qui ne peut alors toucher aucune donnée de personne.
        enabled: Déclarée n'est pas active. Le défaut est `False`.
        created_at: Quand elle a été déclarée.
    """

    routine_id: str
    description: str
    actions: List[RoutineAction]
    interval_seconds: int
    subject: Optional[str] = None
    enabled: bool = False
    created_at: float = 0.0

    @property
    def belongs_to_platform(self) -> bool:
        """Vrai si la routine n'appartient à personne en particulier."""
        return self.subject is None

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "routine_id": self.routine_id,
            "description": self.description,
            "actions": [action.as_dict() for action in self.actions],
            "interval_seconds": self.interval_seconds,
            "subject": self.subject,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "belongs_to_platform": self.belongs_to_platform,
        }
