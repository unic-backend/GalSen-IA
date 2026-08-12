"""
Les exécutants de gestes, et pourquoi ils ne sont pas disponibles (ch. 06).

La détection de plateforme est **celle du chapitre 05** : `BackendDePlateforme`
répond déjà aux trois questions — session graphique, bibliothèque, implémentation
— et la réécrire ici ferait deux vérités sur un même fait. Ce module n'ajoute que
les gestes.
"""

from typing import List, Optional

from src.tools.screen.backends import BackendDePlateforme
from src.tools.screen.types import ScreenElement

from .interfaces import GUIBackend, GUIUnavailable


class _GestesDePlateforme(BackendDePlateforme, GUIBackend):
    """
    Base des exécutants liés à un système, en refus tant qu'ils ne sont pas écrits.

    Elle hérite de la détection du chapitre 05 et refuse chaque geste avec la même
    raison : agir sans pouvoir vérifier qu'on a agi produirait un compte rendu
    plausible et faux, ce que `.claude/rules/verification.md` interdit.
    """

    family = "accessibility"
    reference = "VOLET 34, ch. 06"

    def _refuser(self) -> None:
        raise GUIUnavailable(self.unavailable_reason())

    def click(self, element: ScreenElement, double: bool = False) -> None:
        """Refuse, en nommant la raison."""
        self._refuser()

    def type_text(self, element: ScreenElement, text: str) -> None:
        """Refuse, en nommant la raison."""
        self._refuser()

    def press(self, key: str, element: Optional[ScreenElement] = None) -> None:
        """Refuse, en nommant la raison."""
        self._refuser()


class UiaGestes(_GestesDePlateforme):
    """Gestes sur Windows, via UI Automation."""

    name = "uia"
    systeme = "Windows"
    module = "pywinauto"
    installation = "« pip install pywinauto »."


class AtSpiGestes(_GestesDePlateforme):
    """Gestes sur Linux, via AT-SPI."""

    name = "at-spi"
    systeme = "Linux"
    module = "pyatspi"
    installation = "Sur Debian ou Ubuntu : « apt install python3-pyatspi »."


class AxGestes(_GestesDePlateforme):
    """Gestes sur macOS, via l'API Accessibility."""

    name = "ax"
    systeme = "Darwin"
    module = "ApplicationServices"
    installation = "« pip install pyobjc-framework-ApplicationServices »."


#: Exécutants connus, dans l'ordre où ils sont examinés.
BACKENDS: List[type] = [UiaGestes, AtSpiGestes, AxGestes]


def executants(candidats: Optional[List[GUIBackend]] = None) -> List[GUIBackend]:
    """Retourne les exécutants examinés — ceux de la plateforme par défaut."""
    return candidats if candidats is not None else [classe() for classe in BACKENDS]
