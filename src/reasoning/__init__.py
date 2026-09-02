"""
Raisonnement délibératif : générer, critiquer, reprendre, s'arrêter.

Deux modules, et la frontière entre eux est le point de la conception :

- `critics` **constate**. Il ne corrige rien et n'appelle aucun modèle.
- `deliberation` **décide quoi faire d'un constat**, et quand cesser.

Séparer la mesure de ce qu'on en fait est la règle qu'`agents/verifier/agent.py`
posait déjà pour la vérification factuelle. Elle vaut ici pour la même raison :
un composant qui mesure et corrige à la fois ne permet plus de savoir laquelle
des deux moitiés s'est trompée.
"""

from .critics import BLOQUANT, CONTROLES, SIGNAL, Constat, critiquer
from .deliberation import (
    BUDGET_EPUISE,
    DELAI_DEPASSE,
    DELAI_PAR_DEFAUT_SECONDES,
    GENERATION_IMPOSSIBLE,
    REPRISES_PAR_DEFAUT,
    VERIFIEE,
    Deliberation,
    Tentative,
    consigne_de_reprise,
    deliberer,
)

__all__ = [
    "BLOQUANT",
    "SIGNAL",
    "CONTROLES",
    "Constat",
    "critiquer",
    "Deliberation",
    "Tentative",
    "deliberer",
    "consigne_de_reprise",
    "VERIFIEE",
    "BUDGET_EPUISE",
    "DELAI_DEPASSE",
    "GENERATION_IMPOSSIBLE",
    "REPRISES_PAR_DEFAUT",
    "DELAI_PAR_DEFAUT_SECONDES",
]
