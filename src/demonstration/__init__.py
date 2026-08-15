"""
Démonstration de bout en bout : ce qu'un travail traverse réellement.

Une suite de tests prouve que chaque pièce se comporte comme son auteur
l'attendait ; elle ne prouve pas qu'un travail peut traverser la plateforme d'un
bout à l'autre. Les coutures sont l'endroit où les choses cassent.
"""

from .scenario import (
    BLOCAGES_CONNUS,
    BLOQUE,
    ECHOUE,
    REUSSI,
    run_demonstration,
)

__all__ = [
    "BLOCAGES_CONNUS",
    "BLOQUE",
    "ECHOUE",
    "REUSSI",
    "run_demonstration",
]
