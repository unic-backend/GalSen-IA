"""
Lecture d'écran (VOLET 34, ch. 05).

Cet outil **lit** l'écran et n'agit pas : agir est le chapitre 06. Les séparer
permet de donner la vue à un agent sans lui donner la main.
"""

from .backends import backends_disponibles, raisons_d_indisponibilite, session_graphique
from .interfaces import ScreenBackend, ScreenUnavailable
from .tool import ScreenCaptureLeavingHost, ScreenTool, assert_stays_local
from .types import ScreenElement, ScreenSnapshot

__all__ = [
    "ScreenBackend",
    "ScreenCaptureLeavingHost",
    "ScreenElement",
    "ScreenSnapshot",
    "ScreenTool",
    "ScreenUnavailable",
    "assert_stays_local",
    "backends_disponibles",
    "raisons_d_indisponibilite",
    "session_graphique",
]
