"""
Quand deux sources ne disent pas la même chose (VOLET 35, chapitre 09).

Une base de connaissances vieillit mal pour une raison simple : un document
récent contredit un document validé, et **quelque chose décide en silence**. Le
plus souvent, le plus récent gagne. C'est presque toujours faux : une source
récente peut être une reprise approximative, et une source ancienne peut être le
texte de loi lui-même.

## Rapporter, jamais résoudre

Ce module ne classe pas, ne masque pas, ne supprime pas. Il **nomme les couples
en désaccord**, avec leurs deux provenances, et laisse la décision à qui peut la
prendre. Écraser silencieusement un fait validé est exactement la façon dont une
base pourrit.

C'est aussi pourquoi il ne rend aucun « gagnant » : un champ `winner` serait lu
comme une conclusion, et personne ne rouvrirait le couple.

## Comment le désaccord est repéré

Deux passages du **même sujet et de la même portée** — comparer une loi
sénégalaise à une loi française n'est pas une contradiction, c'est deux pays —
qui partagent l'essentiel de leurs termes et diffèrent sur :

- **la polarité** : l'un nie ce que l'autre affirme ;
- **les nombres** : mêmes termes, chiffres différents. C'est le désaccord le
  plus fréquent dans une base statistique, et le plus facile à citer de travers.

C'est mécanique et étroit, comme la mesure du VOLET 36 ch. C dont ce module
réutilise le découpage. Ce qu'il ne voit pas, il ne le prétend pas : le rapport
porte `method` et `not_detected`.
"""

import re
from typing import Any, Dict, Iterable, List

from .factual_evaluation import carries_negation, lexical_terms
from .scope import GLOBAL

#: Part de termes communs à partir de laquelle deux passages parlent
#: probablement de la même chose. En dessous, un désaccord de polarité ne veut
#: rien dire : ce sont deux sujets différents.
SEUIL_DE_RECOUVREMENT = 0.5

#: Ce que la détection ne voit pas, nommé plutôt que sous-entendu.
NON_DETECTE = (
    "une contradiction reformulée sans mots communs : elle demande une mesure sémantique",
    "une contradiction implicite (une date qui exclut l'autre sans la nier)",
    "une source qui se contredit elle-même d'un passage à l'autre",
)

#: Nombres d'un passage. Les séparateurs de milliers sont retirés avant
#: comparaison : « 18 000 » et « 18000 » sont le même nombre, et les traiter
#: comme deux serait un faux désaccord à chaque page.
_NOMBRE = re.compile(r"\d[\d\s ]*(?:[.,]\d+)?")


def _texte(element: Any) -> str:
    """Retourne le texte d'un élément, objet ou dictionnaire."""
    if isinstance(element, dict):
        return str(element.get("content") or element.get("text") or "")
    return str(getattr(element, "content", "") or "")


def _champ(element: Any, nom: str, defaut: str = "") -> str:
    """Retourne un champ d'un élément, objet ou dictionnaire."""
    if isinstance(element, dict):
        valeur = element.get(nom)
    else:
        valeur = getattr(element, nom, None)
    return str(getattr(valeur, "value", valeur) or defaut)


def _nombres(texte: str) -> List[str]:
    """Retourne les nombres d'un texte, normalisés."""
    return [
        nombre.replace(" ", "").replace(" ", "").replace(",", ".").rstrip(".")
        for nombre in _NOMBRE.findall(texte)
    ]


def _recouvrement(gauche: Iterable[str], droite: Iterable[str]) -> float:
    """Part de termes communs entre deux passages."""
    a, b = set(gauche), set(droite)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def detect_contradictions(items: Iterable[Any]) -> Dict[str, Any]:
    """
    Repère les couples de passages en désaccord, et les rapporte.

    Args:
        items: Connaissances à comparer — objets ou dictionnaires.

    Returns:
        Les couples en désaccord, chacun avec ses deux provenances et le type de
        désaccord. **Aucun gagnant n'est désigné** : un champ « vainqueur »
        serait lu comme une conclusion et personne ne rouvrirait le couple.
    """
    elements = list(items)
    prepares = [
        {
            "element": element,
            "id": _champ(element, "id"),
            "scope": _champ(element, "scope", GLOBAL),
            "subject": _champ(element, "subject", "unspecified"),
            "terms": lexical_terms(_texte(element)),
            "numbers": _nombres(_texte(element)),
        }
        for element in elements
    ]

    conflits: List[Dict[str, Any]] = []
    for index, gauche in enumerate(prepares):
        for droite in prepares[index + 1:]:
            # Deux pays ne se contredisent pas : ils diffèrent. Comparer une loi
            # sénégalaise à une loi française produirait un conflit permanent
            # que personne ne pourrait résoudre, parce qu'il n'en est pas un.
            if gauche["scope"] != droite["scope"] or gauche["subject"] != droite["subject"]:
                continue
            recouvrement = _recouvrement(gauche["terms"], droite["terms"])
            if recouvrement < SEUIL_DE_RECOUVREMENT:
                continue

            polarites = carries_negation(gauche["terms"]) != carries_negation(droite["terms"])
            chiffres = (
                bool(gauche["numbers"]) and bool(droite["numbers"])
                and set(gauche["numbers"]) != set(droite["numbers"])
            )
            if not polarites and not chiffres:
                continue

            conflits.append({
                "type": "polarity" if polarites else "numeric",
                "subject": gauche["subject"],
                "scope": gauche["scope"],
                "overlap": round(recouvrement, 3),
                "left": {"id": gauche["id"], "excerpt": _texte(gauche["element"])[:240]},
                "right": {"id": droite["id"], "excerpt": _texte(droite["element"])[:240]},
                "resolution": (
                    "Aucune. Le plus récent n'est pas automatiquement le bon, et "
                    "écraser un fait validé en silence est la façon dont une base "
                    "pourrit. La décision revient à une personne."
                ),
            })

    return {
        "compared": len(prepares),
        "contradictions": conflits,
        "by_type": {
            "polarity": sum(1 for conflit in conflits if conflit["type"] == "polarity"),
            "numeric": sum(1 for conflit in conflits if conflit["type"] == "numeric"),
        },
        "method": "lexical",
        "overlap_threshold": SEUIL_DE_RECOUVREMENT,
        "resolved": 0,
        "not_detected": list(NON_DETECTE),
        "note": (
            "Rapporté, jamais résolu. Aucun élément n'est modifié, déclassé ni "
            "supprimé par cette mesure."
        ),
    }
