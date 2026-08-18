"""
Le contrat d'un lecteur d'écran (VOLET 34, ch. 05).

Un backend lit l'écran et rend des éléments **identifiés**. Deux familles
existent, et l'ordre entre elles est décidé, pas laissé au hasard
(`docs/architecture/computer-use-comparison.md`) :

1. **L'arbre d'accessibilité** — la liste structurée que le système tient pour
   les lecteurs d'écran. Rôle, libellé, bornes. Rien ne quitte la machine.
2. **Les pixels**, en repli déclaré, pour ce que l'arbre ne décrit pas.

Le second est un repli et non une alternative, parce qu'une capture envoyée à un
modèle est exactement ce qu'ADR-014 existe pour refuser — et parce que des pixels
ne portent aucune identité, donc aucune approbation lisible.

Un backend indisponible **dit pourquoi**. « Aucun élément » et « je ne sais pas
regarder » sont deux réponses différentes, et les confondre est le mode d'échec
que ce dépôt traque partout.
"""

import abc
from typing import Optional

from .types import ScreenSnapshot


class ScreenBackend(abc.ABC):
    """Contrat d'un lecteur d'écran."""

    #: Nom court, inscrit dans chaque instantané.
    name: str = "abstract"

    #: `accessibility` ou `pixels`. Détermine l'ordre de préférence.
    family: str = "accessibility"

    @abc.abstractmethod
    def unavailable_reason(self) -> Optional[str]:
        """
        Retourne la raison pour laquelle ce backend ne peut pas servir.

        Returns:
            `None` si le backend est utilisable ; sinon une phrase qui nomme ce
            qui manque et, quand c'est possible, comment l'obtenir.
        """

    @abc.abstractmethod
    def snapshot(self) -> ScreenSnapshot:
        """
        Lit l'écran et retourne ses éléments.

        Raises:
            ScreenUnavailable: Si le backend ne peut pas lire l'écran.
        """

    def available(self) -> bool:
        """Indique si ce backend peut servir maintenant."""
        return self.unavailable_reason() is None


class ScreenUnavailable(RuntimeError):
    """
    Aucun lecteur d'écran ne peut servir.

    Levée avec la raison, jamais silencieuse : un agent qui reçoit une liste
    vide croirait que l'écran est vide.
    """
