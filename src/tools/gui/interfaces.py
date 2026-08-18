"""
Le contrat d'un exécutant de gestes (VOLET 34, ch. 06).

Un backend GUI **exécute** ce qu'un humain a déjà approuvé. Il ne décide rien :
les refus, le portillon et l'audit sont au-dessus de lui, dans `GUITool`. Un
backend qui déciderait aurait deux gardiens, et deux gardiens finissent par ne
plus dire la même chose — le défaut que ce dépôt a trouvé quatre fois.
"""

import abc
from typing import Optional

from src.tools.screen.types import ScreenElement


class GUIBackend(abc.ABC):
    """Contrat d'un exécutant de gestes."""

    #: Nom court, inscrit dans chaque résultat et dans l'audit.
    name: str = "abstract"

    @abc.abstractmethod
    def unavailable_reason(self) -> Optional[str]:
        """Retourne pourquoi ce backend ne peut pas agir, ou None s'il le peut."""

    @abc.abstractmethod
    def click(self, element: ScreenElement, double: bool = False) -> None:
        """Clique sur un élément déjà approuvé."""

    @abc.abstractmethod
    def type_text(self, element: ScreenElement, text: str) -> None:
        """Saisit du texte dans un élément déjà approuvé."""

    @abc.abstractmethod
    def press(self, key: str, element: Optional[ScreenElement] = None) -> None:
        """Presse une touche, sur un élément ou sur le focus courant."""

    def available(self) -> bool:
        """Indique si ce backend peut agir maintenant."""
        return self.unavailable_reason() is None


class GUIUnavailable(RuntimeError):
    """Aucun exécutant ne peut agir ; la raison accompagne toujours l'exception."""


class ApprovalRequired(PermissionError):
    """
    Une action a été demandée sans décision humaine accordée.

    Même exception, même intention que `GuardedEditor` (VOLET 31) : la capacité
    d'agir n'existe qu'après une approbation, elle n'est pas retirée après coup.
    """
