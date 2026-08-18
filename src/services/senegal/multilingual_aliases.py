"""
Une question en français, des données en anglais : la couche d'alias.

Le défaut était mesuré, pas supposé : « Quelle est la monnaie du Sénégal ? »
rendait `UNKNOWN` alors que la réponse — `currency : XOF` — était en base. Les
jeux acquis sont en anglais, les questions arrivent en français ou en wolof, et
aucun pont n'existait entre les deux.

## Ce que cette couche fait, et ce qu'elle ne fait pas

Elle **étend les termes d'une question** avec leurs équivalents dans les trois
langues, avant le classement. C'est une table de **vocabulaire**, pas de faits :
une erreur ici fait manquer ou ajouter une correspondance, jamais fabriquer une
affirmation sur le Sénégal.

Elle ne traduit pas, ne devine pas la langue de la question, et n'écrit rien
dans la base. Une question qui n'a aucun terme connu de la table reste
exactement ce qu'elle était.

## Pourquoi l'expansion ne peut pas faire perdre une correspondance

Elle **ajoute** des termes, elle n'en retire aucun. Le pire cas est un fragment
retrouvé en trop — que la pondération IDF et le plancher de score écartent
ensuite. C'est la même propriété que `token_variants()` du VOLET 36 : une
normalisation qui ajoute ne peut pas empêcher une correspondance.

## Le wolof

Les termes wolof viennent du **propriétaire du projet**, locuteur, et sont
marqués non relus (`corpus/languages/aliases.yaml`). Chaque expansion qui s'en
sert le dit. Ils suivent l'orthographe CLAD : `ë`, `ñ`, `ŋ` sont des lettres,
et la comparaison passe par la normalisation du dépôt, qui plie les accents des
**deux** côtés — la symétrie est donc préservée.
"""

import os
from typing import Any, Dict, List, Optional, Set

#: Fichier d'alias, relatif à la racine du dépôt.
ALIAS = os.path.join("corpus", "languages", "aliases.yaml")

#: Les trois langues couvertes.
LANGUES = ("fr", "wo", "en")

INCONNU = "UNKNOWN"

_CACHE: Dict[str, Dict[str, Any]] = {}


def _racine() -> str:
    """Retourne la racine du dépôt."""
    ici = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(os.path.dirname(ici)))


def _normalise(terme: str) -> str:
    """
    Retourne la forme comparable d'un terme, sans règle propre à une langue.

    La règle du pluriel française n'est **pas** appliquée : elle amputerait un
    terme wolof, et `src/text_normalization.py` le refuse depuis le VOLET 36.
    Seuls la casse et les accents sont pliés, des deux côtés.
    """
    from ...text_normalization import strip_accents

    return strip_accents(str(terme or "").strip().lower())


def load_aliases(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge la table d'alias déclarée.

    Un fichier absent rend une table **vide** : sans pont, les questions se
    comportent comme avant cette couche. Perdre la donnée ne doit pas inventer
    de correspondances.
    """
    import yaml

    cible = chemin or os.path.join(_racine(), ALIAS)
    if cible in _CACHE:
        return _CACHE[cible]

    if not os.path.isfile(cible):
        resultat = {"loaded": False, "concepts": [], "index": {}, "path": cible}
        _CACHE[cible] = resultat
        return resultat

    with open(cible, "r", encoding="utf-8") as fichier:
        donnees = yaml.safe_load(fichier) or {}

    concepts, index = [], {}
    for entree in donnees.get("concepts", []) or []:
        termes: Dict[str, List[str]] = {}
        # La forme **écrite** est conservée à côté de la forme repliée. Le
        # repliement sert à comparer ; il ne doit pas décider de ce qu'on
        # affiche. Ne garder que `mbey` rendrait du wolof mal orthographié à un
        # lecteur alors que `ë`, `ñ` et `ŋ` sont des lettres du standard CLAD,
        # jamais des accents (`src/wolof/clad.py`).
        ecrits: Dict[str, List[str]] = {}
        for langue in LANGUES:
            declares = [
                str(terme).strip() for terme in (entree.get(langue) or [])
                if str(terme).strip()
            ]
            ecrits[langue] = declares
            termes[langue] = [_normalise(terme) for terme in declares]
        toutes = {terme for liste in termes.values() for terme in liste}
        if not toutes:
            continue
        concept = {
            "id": entree.get("id", INCONNU), "terms": termes,
            "written": ecrits, "all": sorted(toutes),
        }
        concepts.append(concept)
        for terme in toutes:
            index.setdefault(terme, []).append(concept)

    resultat = {
        "loaded": True,
        "path": cible,
        "version": str(donnees.get("version") or INCONNU),
        "wo_source": str(donnees.get("wo_source") or INCONNU),
        "wo_reviewed": bool(donnees.get("wo_reviewed", False)),
        "concepts": concepts,
        "index": index,
    }
    _CACHE[cible] = resultat
    return resultat


def expand_terms(termes: Set[str], chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Étend un ensemble de termes avec leurs équivalents dans les trois langues.

    Args:
        termes: Les termes de la question, déjà normalisés.
        chemin: Fichier d'alias, pour les tests.

    Returns:
        `terms` — les termes d'origine **plus** les équivalents — `added`, les
        concepts touchés, et `caveat` quand un terme wolof non relu a servi.
        Les termes d'origine ne sont jamais retirés : l'expansion ajoute, donc
        elle ne peut pas faire perdre une correspondance.
    """
    table = load_aliases(chemin)
    if not table["loaded"] or not termes:
        return {
            "terms": set(termes),
            "added": set(),
            "concepts": [],
            "used_unreviewed_wolof": False,
            "available": table["loaded"],
        }

    ajoutes: Set[str] = set()
    touches: List[str] = []
    wolof_non_relu = False

    for terme in termes:
        for concept in table["index"].get(terme, []):
            if concept["id"] not in touches:
                touches.append(concept["id"])
            ajoutes |= set(concept["all"])
            if terme in concept["terms"]["wo"] and not table["wo_reviewed"]:
                wolof_non_relu = True

    ajoutes -= set(termes)
    resultat = {
        "terms": set(termes) | ajoutes,
        "added": ajoutes,
        "concepts": touches,
        "used_unreviewed_wolof": wolof_non_relu,
        "available": True,
    }
    if wolof_non_relu:
        resultat["caveat"] = (
            "Un terme wolof de la question a été reconnu par une table déclarée "
            f"par {table['wo_source']} et **non relue** contre un dictionnaire. "
            "L'expansion vaut un élargissement de recherche, pas une traduction "
            "certifiée."
        )
    return resultat


def translate(terme: str, vers: str = "en", chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Retourne les équivalents d'un terme dans une langue donnée.

    Returns:
        `found: False` **avec la langue demandée** quand le terme est inconnu de
        la table — inventer une traduction plausible serait le seul moyen de se
        tromper ici, et il est fermé.

    Note:
        Les termes rendus sont dans leur forme **écrite** : `mbéy`, pas `mbey`.
        Cette fonction sert à montrer un terme à quelqu'un, et le repliement
        n'existe que pour comparer. `expand_terms`, qui sert à chercher,
        continue de rendre la forme repliée.
    """
    table = load_aliases(chemin)
    cible = str(vers or "").strip().lower()
    if cible not in LANGUES:
        return {"found": False, "reason": f"Langue « {vers} » hors de {LANGUES}.", "terms": []}

    concepts = table["index"].get(_normalise(terme), [])
    if not concepts:
        return {
            "found": False,
            "reason": "Terme absent de la table d'alias. Aucune traduction n'est devinée.",
            "terms": [],
        }
    return {
        "found": True,
        "term": terme,
        "target": cible,
        "concepts": [concept["id"] for concept in concepts],
        "terms": sorted({t for concept in concepts for t in concept["written"][cible]}),
        "reviewed": table["wo_reviewed"] if cible == "wo" else True,
    }


def alias_report(chemin: Optional[str] = None) -> Dict[str, Any]:
    """Décrit la table : combien de concepts, combien de termes par langue."""
    table = load_aliases(chemin)
    if not table["loaded"]:
        return {"available": False, "concepts": 0, "terms": {langue: 0 for langue in LANGUES}}

    par_langue = {
        langue: sum(len(concept["terms"][langue]) for concept in table["concepts"])
        for langue in LANGUES
    }
    return {
        "available": True,
        "version": table["version"],
        "concepts": len(table["concepts"]),
        "terms": par_langue,
        "terms_total": sum(par_langue.values()),
        "wo_source": table["wo_source"],
        "wo_reviewed": table["wo_reviewed"],
        "note": (
            "Table de vocabulaire, pas de faits : une erreur ici fait manquer ou "
            "ajouter une correspondance, jamais fabriquer une affirmation. "
            "L'expansion ajoute des termes et n'en retire aucun, donc elle ne "
            "peut pas faire perdre une correspondance."
        ),
    }
