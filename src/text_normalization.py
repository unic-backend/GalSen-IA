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
conjuguées.

## La règle du pluriel est française, et elle le dit maintenant (VOLET 36, L3)

Retirer un `s` final est juste en français et en anglais. Le wolof n'a pas de
pluriel en `-s` ; le pulaar marque la classe par suffixe. Appliquée à ces
langues, la règle **abîme le mot** : `ndaws` devenait `ndaw`, une forme que
personne n'a écrite.

Elle est donc conditionnée à la langue du texte, avec un défaut français —
c'est la langue de la plateforme, et changer le défaut réécrirait en silence le
comportement de tous les appelants existants.

**La symétrie est préservée autrement.** Un texte wolof est désormais indexé
sans amputation, mais une requête arrive sans langue déclarée — aucun détecteur
n'existe (ch. B). `token_variants()` rend donc les deux formes d'un terme de
requête, et l'index est interrogé avec les deux : on gagne des correspondances,
on n'en perd aucune.
"""

import re
import unicodedata
from typing import Iterable, List

# Longueur minimale avant de retirer une marque de pluriel. « pas », « bus » ou
# « gaz » ne doivent pas devenir « pa », « bu » ou « ga » : sur des mots courts,
# le `s` final appartient bien plus souvent au mot qu'à son pluriel.
LONGUEUR_MINIMALE_PLURIEL = 4

# Langue supposée quand personne ne la déclare. C'est celle de la plateforme ;
# changer ce défaut réécrirait en silence le comportement de tous les appelants
# existants, ce qui est exactement le genre de modification invisible que ce
# dépôt refuse.
LANGUE_PAR_DEFAUT = "fr"

# Langues dont le pluriel se marque par un `s` final. La règle leur est réservée.
LANGUES_A_PLURIEL_S = frozenset({"fr", "en", "es", "de", "af"})

# Code conventionnel désignant « une langue sans pluriel en -s », pour les
# appelants qui veulent la forme non amputée sans nommer une langue précise.
SANS_PLURIEL = "wo"


def applique_le_pluriel(language: str) -> bool:
    """Indique si la règle du pluriel `-s` vaut pour cette langue."""
    return str(language or LANGUE_PAR_DEFAUT).strip().lower() in LANGUES_A_PLURIEL_S

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


def singularize(mot: str, language: str = LANGUE_PAR_DEFAUT) -> str:
    """
    Retire une marque de pluriel finale simple, **si la langue la connaît**.

    Args:
        mot: un mot déjà en minuscules.
        language: code de langue du texte. La règle ne s'applique qu'aux langues
            de `LANGUES_A_PLURIEL_S` ; ailleurs le mot est rendu tel quel, parce
            que l'amputer produirait une forme que personne n'a écrite.

    Returns:
        Le mot sans son `s` ou `x` final quand il est assez long. Aucun mot n'est
        allongé : un singulier reste identique à lui-même, ce qui garantit que
        singulier et pluriel se rejoignent sur la même forme.
    """
    if not applique_le_pluriel(language):
        return mot
    if len(mot) > LONGUEUR_MINIMALE_PLURIEL and mot[-1] in ("s", "x"):
        return mot[:-1]
    return mot


def normalize_token(mot: str, language: str = LANGUE_PAR_DEFAUT) -> str:
    """
    Applique la normalisation complète à un mot : minuscules, accents, pluriel.

    Args:
        mot: un mot brut.
        language: code de langue du texte.

    Returns:
        La forme comparable du mot.
    """
    return singularize(strip_accents(mot.lower()), language)


def token_variants(mot: str) -> List[str]:
    """
    Rend les formes comparables d'un mot **de requête**, toutes langues confondues.

    Une requête n'a pas de langue déclarée et rien ici ne sait l'inférer
    (VOLET 36, ch. B). Interroger l'index avec la seule forme française ferait
    manquer un terme wolof indexé sans amputation ; interroger avec les deux
    formes ne peut qu'ajouter des correspondances.
    """
    formes = []
    for langue in (LANGUE_PAR_DEFAUT, SANS_PLURIEL):
        forme = normalize_token(mot, langue)
        if forme not in formes:
            formes.append(forme)
    return formes


def tokenize(texte: str, stop_words: Iterable[str] = (),
             language: str = LANGUE_PAR_DEFAUT) -> List[str]:
    """
    Découpe un texte en mots normalisés, en retirant les mots vides.

    Les mots vides sont normalisés eux aussi : sans cela, « à » resterait dans
    l'index alors que « a » en est exclu, et la liste ne filtrerait qu'à moitié.

    Args:
        texte: le texte à découper.
        stop_words: mots à écarter, dans n'importe quelle graphie.
        language: code de langue du texte, qui décide des règles appliquées.

    Returns:
        Les mots normalisés, dans leur ordre d'apparition.
    """
    vides = {normalize_token(mot, language) for mot in stop_words}
    mots = (normalize_token(mot, language) for mot in _MOT.findall(texte))
    return [mot for mot in mots if mot not in vides and len(mot) > 1]


def normalization_rules(language: str = LANGUE_PAR_DEFAUT) -> List[str]:
    """
    Dit quelles règles s'appliquent à cette langue.

    Sert au rapport de capacités (`language_support()`) : une normalisation qui
    ne dirait pas ce qu'elle fait laisserait croire qu'elle comprend la langue.
    """
    regles = ["lowercase", "strip_accents"]
    if applique_le_pluriel(language):
        regles.append("plural_s")
    return regles
