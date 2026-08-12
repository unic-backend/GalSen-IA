"""
Ce qu'une action sur une interface est, et ce qu'elle rend (VOLET 34, ch. 06).

ADR-017 §4 : **une action doit pouvoir nommer sa cible**. Ces types portent cette
exigence dans leur forme — une action vise un `ScreenElement`, jamais un couple
de coordonnées. Un portillon qui demande d'approuver « cliquer en (412, 380) »
n'est pas un portillon : c'est un tampon accompagné d'une ligne de journal.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from src.tools.screen.types import ScreenElement


class ActionKind(Enum):
    """Les gestes qu'un agent peut proposer."""

    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    TYPE = "type"
    PRESS = "press"


@dataclass(frozen=True)
class GUIAction:
    """
    Un geste proposé, avec sa cible identifiée.

    Attributes:
        kind: Le geste.
        target: L'élément visé. Obligatoire sauf pour `PRESS`, qui va au focus
            courant — et qui est le seul cas où l'absence de cible est honnête.
        text: Texte à saisir, pour `TYPE`.
        key: Touche à presser, pour `PRESS`.
        reason: Pourquoi l'agent veut ce geste. Un humain décide avec ça.
    """

    kind: ActionKind
    target: Optional[ScreenElement] = None
    text: str = ""
    key: str = ""
    reason: str = ""

    def describe(self) -> str:
        """
        Décrit le geste en une phrase, telle qu'elle sera soumise à l'humain.

        C'est la seule chose que le décideur verra. Elle nomme la cible, jamais
        une position seule.
        """
        if self.kind is ActionKind.PRESS:
            geste = f"presser « {self.key} »"
            cible = f" sur {self.target.describe()}" if self.target else " (focus courant)"
            return geste + cible

        cible = self.target.describe() if self.target else "cible absente"
        if self.kind is ActionKind.TYPE:
            return f"saisir {len(self.text)} caractères dans {cible}"
        if self.kind is ActionKind.DOUBLE_CLICK:
            return f"double-cliquer sur {cible}"
        return f"cliquer sur {cible}"

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'action. **Le texte saisi n'est jamais inclus.**"""
        return {
            "kind": self.kind.value,
            "target": self.target.to_dict() if self.target else None,
            # Seule la longueur : un texte saisi peut être un mot de passe, et un
            # journal d'audit qui le conserve est une fuite qui survit au
            # redémarrage depuis que l'audit persiste.
            "text_length": len(self.text),
            "key": self.key,
            "reason": self.reason,
            "description": self.describe(),
        }


@dataclass
class ActionOutcome:
    """Ce qu'il est advenu d'une action proposée."""

    status: str
    detail: str = ""
    approval_request_id: Optional[str] = None
    action: Optional[GUIAction] = None
    notes: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat."""
        return {
            "status": self.status,
            "detail": self.detail,
            "approval_request_id": self.approval_request_id,
            "action": self.action.to_dict() if self.action else None,
            "notes": self.notes,
        }
