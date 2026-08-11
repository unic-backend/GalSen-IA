"""
Normalisation des mots avant indexation et recherche.

Deux défauts mesurés séparaient une requête de ce qui était pourtant indexé :

```
« pluviométrie » → 1 résultat      « pluviometrie » → 0
« Sénégal »      → 1 résultat      « senegal »      → 0
« arachides »    → 1 résultat      « arachide »     → 0
```

Le premier est une question de contexte plus que de linguistique : sur un
clavier utilisé au Sénégal, la frappe sans accents est la norme, et une
plateforme qui ne trouve rien sans accents ne trouve rien pour ses utilisateurs.
Le second est le cas le plus banal d'une recherche — chercher au singulier ce
qui est écrit au pluriel.

Ce module ne prétend pas être un analyseur morphologique. Il applique deux
transformations, **des deux côtés** — sur les termes indexés comme sur ceux de
la requête — et c'est cette symétrie qui le rend sûr : une normalisation qui
perd de l'information ne peut pas empêcher une correspondance, elle peut
seulement en créer une de trop.

Ce qu'il ne fait **pas**, et qu'il faudrait un vrai analyseur pour faire :
les pluriels en `-aux` (journal/journaux), les irréguliers, les formes verbales
conjuguées, et les langues autres que le français.
"""

import re
import unicodedata
from typing import Iterable, List

# Longueur minimale avant de retirer une marque de pluriel. « pas », « bus » ou
# « gaz » ne doivent pas devenir « pa », « bu » ou « ga » : sur des mots courts,
# le `s` final appartient bien plus souvent au mot qu'à son pluriel.
LONGUEUR_MINIMALE_PLURIEL = 4

_MOT = re.compile(r"\w+", re.UNICODE)


def strip_accents(texte: str) -> str:
    """
    Retire les diacritiques sans toucher au reste du texte.

    Args:
        texte: le texte à normaliser.

    Returns:
        Le même texte, sans signes diacritiques.
    """
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def singularize(mot: str) -> str:
    """
    Retire une marque de pluriel finale simple.

    Args:
        mot: un mot déjà en minuscules.

    Returns:
        Le mot sans son `s` ou `x` final quand il est assez long. Aucun mot n'est
        allongé : un singulier reste identique à lui-même, ce qui garantit que
        singulier et pluriel se rejoignent sur la même forme.
    """
    if len(mot) > LONGUEUR_MINIMALE_PLURIEL and mot[-1] in ("s", "x"):
        return mot[:-1]
    return mot


def normalize_token(mot: str) -> str:
    """
    Applique la normalisation complète à un mot : minuscules, accents, pluriel.

    Args:
        mot: un mot brut.

    Returns:
        La forme comparable du mot.
    """
    return singularize(strip_accents(mot.lower()))


def tokenize(texte: str, stop_words: Iterable[str] = ()) -> List[str]:
    """
    Découpe un texte en mots normalisés, en retirant les mots vides.

    Les mots vides sont normalisés eux aussi : sans cela, « à » resterait dans
    l'index alors que « a » en est exclu, et la liste ne filtrerait qu'à moitié.

    Args:
        texte: le texte à découper.
        stop_words: mots à écarter, dans n'importe quelle graphie.

    Returns:
        Les mots normalisés, dans leur ordre d'apparition.
    """
    vides = {normalize_token(mot) for mot in stop_words}
    mots = (normalize_token(mot) for mot in _MOT.findall(texte))
    return [mot for mot in mots if mot not in vides and len(mot) > 1]
