"""
Les langues du Sénégal, et ce que « supporter une langue » veut dire ici
(VOLET 36, chapitre B).

## Le malentendu que ce module existe pour empêcher

Ajouter `WO`, `FF` et `SRR` à `Language` **ne veut pas dire que la plateforme
comprend le wolof**. Cela veut dire qu'un document wolof peut être étiqueté,
stocké, filtré et retrouvé lexicalement comme wolof — ce qui était impossible
jusqu'ici, et ce qui est le préalable de tout le reste.

La confusion entre les deux est le mensonge le plus facile à écrire dans une
plateforme d'IA : trois lignes dans une énumération, et la page d'accueil
annonce quatre langues. `language_support()` est le contrepoids honnête — il
dit, capacité par capacité, ce qui est réel, ce qui est partiel, ce qui n'existe
pas, et ce qui n'a **jamais été mesuré ici**.

## Les codes

`WO` (wolof) et `FF` (pulaar) sont des codes ISO 639-1. Le sérère n'a pas de
code à deux lettres : `SRR` est son code ISO 639-3. L'énumération mélange donc
deux registres — c'est le registre qui est incomplet, pas la liste.

## Quatre verdicts, pas deux

`UNKNOWN` n'est pas `NO`. Le récupérateur sémantique et la génération n'ont
jamais été mesurés sur ces langues dans ce dépôt : répondre « non » serait aussi
faux que répondre « oui », et refermerait la question au lieu de la poser.
"""

import os
from enum import Enum
from typing import Any, Dict, List, Optional

from src.text_normalization import normalization_rules

from .types import Language

#: Langues du Sénégal reconnues par la plateforme. Le français est la langue
#: officielle ; le wolof, le pulaar et le sérère sont trois des langues
#: nationales. La liste n'est pas la liste complète des langues du pays — elle
#: nomme celles pour lesquelles la plateforme sait au moins étiqueter un
#: document.
SENEGAL_LANGUAGES = (Language.FR, Language.WO, Language.FF, Language.SRR)

#: Jeu d'évaluation lu pour mesurer la capacité `evaluation`, relatif à la
#: racine du dépôt. Même fichier que `src/training/evaluation.py` : deux chemins
#: pour un même jeu donneraient deux vérités sur la couverture.
EVALUATION_SET = os.path.join("docs", "evaluation", "retrieval.jsonl")


class Capability(Enum):
    """
    Les capacités qu'on confond sous le mot « supporter ».

    Neuf entrées pour huit capacités : la récupération est coupée en deux parce
    que ses deux moitiés n'ont pas le même verdict — la lexicale marche, la
    sémantique n'a jamais été mesurée. Les fondre rendrait la première fausse ou
    la seconde invisible.
    """

    UI = "ui"
    DETECTION = "detection"
    CLASSIFICATION = "classification"
    NORMALIZATION = "normalization"
    TRANSLATION = "translation"
    LEXICAL_RETRIEVAL = "lexical_retrieval"
    SEMANTIC_RETRIEVAL = "semantic_retrieval"
    GENERATION = "generation"
    EVALUATION = "evaluation"


class Support(Enum):
    """
    Ce qu'on peut dire d'une capacité pour une langue donnée.

    `UNKNOWN` dit « personne n'a mesuré » et ne doit jamais passer pour un
    « non » : un « non » ferme la question, un `unknown` nomme ce qui reste à
    mesurer et ce qui le bloque.
    """

    YES = "yes"
    PARTIAL = "partial"
    NO = "no"
    UNKNOWN = "unknown"


class LanguageRefused(ValueError):
    """Une langue inconnue a été déclarée."""


def parse_language(valeur: Any, defaut: Language = Language.FR) -> Language:
    """
    Lit une langue depuis sa forme textuelle.

    Args:
        valeur: `wo`, `WO`, une `Language`, ou rien.
        defaut: Rendu quand la valeur est vide. Un document dont personne n'a
            déclaré la langue est traité comme français parce que c'est la
            langue de la plateforme — **c'est une déclaration, pas une
            détection** : rien dans le dépôt ne sait inférer une langue
            (`Capability.DETECTION` vaut `no`).

    Raises:
        LanguageRefused: Code inconnu. Une langue mal écrite **n'est pas
            devinée** : elle retomberait sur le français, et le document serait
            introuvable par la langue sur laquelle on le cherchera.
    """
    if isinstance(valeur, Language):
        return valeur
    texte = str(valeur or "").strip().lower()
    if not texte:
        return defaut
    try:
        return Language(texte)
    except ValueError:
        connues = ", ".join(langue.value for langue in Language)
        raise LanguageRefused(f"Langue « {valeur} » inconnue. Langues déclarées : {connues}.")


def known_languages() -> List[str]:
    """Retourne les langues déclarées, pour un manifeste ou une documentation."""
    return [langue.value for langue in Language]


def _racine() -> str:
    """Retourne la racine du dépôt."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cas_d_evaluation_par_langue(chemin: Optional[str] = None) -> Dict[str, int]:
    """
    Compte les cas du jeu d'évaluation, par langue.

    C'est la seule capacité mesurée sur un fichier réel plutôt que déclarée :
    un jeu de test existe ou n'existe pas, et le dépôt sait le dire. Un fichier
    absent rend un compte vide — donc `no` partout, ce qui est la vérité.
    """
    import json

    cible = chemin or os.path.join(_racine(), EVALUATION_SET)
    comptes: Dict[str, int] = {}
    if not os.path.isfile(cible):
        return comptes
    with open(cible, "r", encoding="utf-8") as fichier:
        for ligne in fichier:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("//"):
                continue
            try:
                cas = json.loads(ligne)
            except ValueError:
                # Une ligne illisible n'est pas comptée : elle gonflerait une
                # couverture qui n'existe pas.
                continue
            langue = str(cas.get("language") or Language.FR.value).strip().lower()
            comptes[langue] = comptes.get(langue, 0) + 1
    return comptes


def _verdict(support: Support, preuve: str, bloque_par: str = "") -> Dict[str, Any]:
    """Assemble un verdict de capacité avec sa preuve."""
    entree: Dict[str, Any] = {"support": support.value, "evidence": preuve}
    if bloque_par:
        entree["blocked_on"] = bloque_par
    return entree


def language_support(
    language: Any = Language.FR, evaluation_set: Optional[str] = None
) -> Dict[str, Any]:
    """
    Dit, capacité par capacité, ce que la plateforme sait réellement faire
    dans cette langue.

    Args:
        language: La langue interrogée.
        evaluation_set: Jeu d'évaluation à lire ; celui du dépôt par défaut.

    Returns:
        Un verdict par capacité, chacun avec sa preuve, et `blocked_on` quand la
        mesure attend quelque chose qui n'est pas dans ce dépôt.
    """
    langue = parse_language(language)
    est_francais = langue is Language.FR
    cas = _cas_d_evaluation_par_langue(evaluation_set).get(langue.value, 0)

    capacites = {
        Capability.UI.value: _verdict(
            Support.YES if est_francais else Support.NO,
            "L'interface et les messages sont écrits en français ; aucun catalogue "
            "de traduction n'existe dans le dépôt. Ajouter une locale est une "
            "question de données, pas de linguistique.",
        ),
        Capability.DETECTION.value: _verdict(
            Support.NO,
            "Aucun détecteur de langue n'existe, pour aucune langue. La langue est "
            "déclarée à l'ingestion (`ingest_file(language=…)`), jamais inférée.",
        ),
        Capability.CLASSIFICATION.value: _verdict(
            Support.YES,
            f"`Language.{langue.name}` est un champ de `KnowledgeItem` : un document "
            "peut être étiqueté, stocké et listé dans cette langue.",
        ),
        Capability.NORMALIZATION.value: _verdict(
            Support.YES if est_francais else Support.PARTIAL,
            "Règles appliquées à cette langue : "
            + ", ".join(normalization_rules(langue.value))
            + ". Depuis L3, la règle du pluriel `-s` ne vaut que pour les langues qui "
            "la connaissent : un texte wolof n'est plus amputé."
            + ("" if est_francais else
               " Reste le pliage des accents, qui fond « ñ » et « n » alors qu'ils sont "
               "deux lettres en wolof. Il est symétrique — il ne peut pas faire perdre "
               "une correspondance, seulement en créer une de trop — et un vrai "
               "analyseur morphologique manque toujours."),
        ),
        Capability.TRANSLATION.value: _verdict(
            Support.NO,
            "Aucun composant de traduction n'existe dans le dépôt.",
        ),
        Capability.LEXICAL_RETRIEVAL.value: _verdict(
            Support.YES,
            "La recherche lexicale et le filtre `language` du magasin ne dépendent "
            "d'aucune langue en particulier.",
        ),
        Capability.SEMANTIC_RETRIEVAL.value: _verdict(
            Support.UNKNOWN,
            "Si le modèle d'embeddings (ADR-015) représente utilement cette langue "
            "n'a jamais été mesuré ici : les poids ne sont pas joignables dans cet "
            "environnement.",
            bloque_par="C1 — modèle local disponible, puis un corpus de test",
        ),
        Capability.GENERATION.value: _verdict(
            Support.UNKNOWN,
            "La qualité de génération est une propriété du modèle, pas de ce dépôt. "
            "Elle devient mesurable une fois le modèle local joignable.",
            bloque_par="C1 — modèle local disponible",
        ),
        Capability.EVALUATION.value: _verdict(
            Support.PARTIAL if cas else Support.NO,
            f"{cas} cas dans `{EVALUATION_SET}`. La machinerie existe et refuse déjà "
            "d'appeler « amélioration » un gain dans une langue payé par une perte "
            "dans une autre (`src/training/evaluation.py`) ; ce qui manque est le jeu "
            "de test.",
            bloque_par="" if cas else "un jeu de test dans cette langue",
        ),
    }

    return {
        "language": langue.value,
        "senegal": langue in SENEGAL_LANGUAGES,
        "capabilities": capacites,
        # Le compte de ce qui n'est pas acquis se lit sans parcourir le détail.
        # Une page qui n'afficherait que les `yes` annoncerait quatre langues
        # supportées, ce que ce module existe pour empêcher.
        "unknown": sorted(
            nom for nom, verdict in capacites.items()
            if verdict["support"] == Support.UNKNOWN.value
        ),
        "missing": sorted(
            nom for nom, verdict in capacites.items()
            if verdict["support"] == Support.NO.value
        ),
    }


def languages_report(evaluation_set: Optional[str] = None) -> Dict[str, Any]:
    """
    Rassemble le rapport de capacités pour les langues du Sénégal.

    Le rapport ne couvre que `SENEGAL_LANGUAGES` : les autres langues de
    l'énumération sont étiquetables, et rien de plus n'a été mesuré à leur
    sujet — le dire langue par langue donnerait onze verdicts identiques et sans
    valeur. `known_languages()` reste la liste complète de ce qui s'étiquette.
    """
    return {
        "declared": known_languages(),
        "senegal": [langue.value for langue in SENEGAL_LANGUAGES],
        "capabilities": [capacite.value for capacite in Capability],
        "evaluation_set": EVALUATION_SET,
        "support": {
            langue.value: language_support(langue, evaluation_set)
            for langue in SENEGAL_LANGUAGES
        },
        # Ce que le rapport ne dit pas : étiqueter n'est pas comprendre. La
        # phrase est dans la réponse pour qu'elle survive à la lecture d'un
        # tableau de `yes`.
        "caveat": (
            "Étiqueter un document comme wolof ne veut pas dire que la plateforme "
            "comprend le wolof. Les capacités marquées `unknown` n'ont jamais été "
            "mesurées ici."
        ),
    }
