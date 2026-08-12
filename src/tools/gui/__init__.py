"""
Contrôle d'interface graphique, sous portillon (VOLET 34, ch. 06).

Le chapitre 05 donne des yeux, celui-ci donne une main : séparés, pour qu'un
agent puisse recevoir la vue sans recevoir le geste.
"""

from .backends import executants
from .interfaces import ApprovalRequired, GUIBackend, GUIUnavailable
from .tool import ROLES_DE_SECRET, GUITool
from .types import ActionKind, ActionOutcome, GUIAction

__all__ = [
    "ROLES_DE_SECRET",
    "ActionKind",
    "ActionOutcome",
    "ApprovalRequired",
    "GUIAction",
    "GUIBackend",
    "GUITool",
    "GUIUnavailable",
    "executants",
]
