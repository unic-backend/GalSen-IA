"""
La santé se répond autrement (VOLET 35, chapitre 10).

La connaissance de santé s'ingère comme le reste. Elle ne se **répond** pas
comme le reste, et le brief le demandait explicitement.

## Trois règles, dont deux sont des refus

1. **Un plancher de sources.** Seules `OFFICIAL`, `GOVERNMENT` et
   `PEER_REVIEWED` peuvent porter une réponse de santé. Le seuil de fiabilité
   général ne suffit pas ici : une documentation industrielle fiable sur un
   sujet technique reste une documentation industrielle sur une maladie.
2. **Un avertissement, sur chaque réponse.** Pas « quand c'est utile » : une
   personne qui lit une réponse de santé doit voir, dans la même réponse, qu'un
   professionnel reste nécessaire.
3. **Ni diagnostic, ni posologie, ni ordonnance** — quoi que disent les sources.

## Pourquoi la troisième règle est du code

Un modèle qui a lu le bon document peut quand même produire une phrase
dangereuse. « 500 mg toutes les six heures » se trouve dans une notice
officielle ; répétée hors contexte à quelqu'un dont on ignore le poids, l'âge,
la grossesse ou les autres traitements, c'est une phrase qui blesse.

Une consigne d'invite ne tient pas cette règle : elle est un vœu que le modèle
suit la plupart du temps. Le filtre, lui, s'applique **après** la génération,
sur le texte réellement produit.

## Ce que ce module ne fait pas

Il ne juge pas la vérité médicale d'une phrase — il n'en a pas les moyens et
personne dans ce dépôt ne les a. Il repère des **formes** : une posologie, une
affirmation diagnostique, une prescription. Ce qu'il ne voit pas est nommé dans
`NON_DETECTE` plutôt que sous-entendu.
"""

import re
from typing import Any, Dict, Iterable, List

from .scope import SAFETY_CRITICAL_SUBJECTS, KnowledgeSubject, parse_subject
from .types import SourceCategory

#: Catégories qui peuvent porter une réponse de santé. Plus strictes que le
#: seuil général : ici, une source « fiable » ne suffit pas.
PLANCHER_DE_SOURCES = frozenset({
    SourceCategory.OFFICIAL,
    SourceCategory.GOVERNMENT,
    SourceCategory.PEER_REVIEWED,
})

#: L'avertissement, attaché à **toute** réponse de santé.
AVERTISSEMENT = (
    "⚠️ Information générale, pas un avis médical. Consultez un professionnel de "
    "santé : lui seul connaît votre situation — âge, poids, grossesse, traitements "
    "en cours, antécédents."
)

#: Formes refusées, avec ce que chacune produirait si elle passait.
MOTIFS_INTERDITS = (
    (
        "posology",
        re.compile(
            r"\b\d+\s*(mg|g|ml|mcg|µg|ui|comprim|gouttes?|cuiller)|"
            r"\b\d+\s*fois\s+par\s+(jour|semaine)|toutes\s+les\s+\d+\s*(h|heures)",
            re.IGNORECASE,
        ),
        "une posologie : elle dépend d'un poids, d'un âge et d'un dossier que la "
        "plateforme ne connaît pas",
    ),
    (
        "diagnosis",
        re.compile(
            r"\bvous\s+(avez|souffrez|êtes atteint|présentez)\b|"
            r"\b(il|elle)\s+(a|souffre d')\s+(un|une|le|la)\s+\w+",
            re.IGNORECASE,
        ),
        "un diagnostic : nommer la maladie de quelqu'un demande de l'examiner",
    ),
    (
        "prescription",
        re.compile(
            r"\b(prenez|prends|administrez|injectez|arrêtez\s+votre\s+traitement|"
            r"je\s+vous\s+prescris|il\s+faut\s+prendre)\b",
            re.IGNORECASE,
        ),
        "une prescription : elle engage une responsabilité qu'un agent n'a pas",
    ),
)

#: Ce que le filtre ne voit pas, nommé plutôt que sous-entendu.
NON_DETECTE = (
    "une posologie écrite en toutes lettres (« deux comprimés matin et soir »)",
    "un conseil dangereux sans forme reconnaissable",
    "une erreur factuelle dans une source par ailleurs officielle",
)


def is_health_subject(subject: Any) -> bool:
    """Indique si ce sujet relève de la politique santé."""
    return parse_subject(subject) in SAFETY_CRITICAL_SUBJECTS


def _categorie(element: Any) -> Any:
    """Retourne la catégorie de source d'un élément, objet ou dictionnaire."""
    if isinstance(element, dict):
        valeur = element.get("source_category") or (element.get("source") or {}).get(
            "source_category"
        )
    else:
        source = getattr(element, "source", None)
        valeur = getattr(source, "source_category", None)
    valeur = getattr(valeur, "value", valeur)
    if valeur is None:
        return None
    try:
        return SourceCategory(str(valeur))
    except ValueError:
        return None


def filter_health_sources(items: Iterable[Any]) -> Dict[str, Any]:
    """
    Applique le plancher de sources à une réponse de santé.

    Returns:
        Les éléments retenus et ceux écartés **avec leur catégorie** : une
        réponse vide sans explication ferait croire à une base vide, alors que
        le problème est la qualité des sources trouvées.
    """
    retenus, ecartes = [], []
    for element in items:
        categorie = _categorie(element)
        if categorie in PLANCHER_DE_SOURCES:
            retenus.append(element)
        else:
            ecartes.append({
                "id": element.get("id") if isinstance(element, dict) else getattr(element, "id", None),
                "category": categorie.value if categorie else None,
            })

    return {
        "allowed": bool(retenus),
        "items": retenus,
        "dropped": ecartes,
        "floor": sorted(categorie.value for categorie in PLANCHER_DE_SOURCES),
        "reason": (
            f"{len(retenus)} source(s) au niveau exigé." if retenus else
            "Aucune source officielle, gouvernementale ou évaluée par les pairs sur "
            "cette question. Le seuil général de fiabilité ne suffit pas en santé, et "
            "répondre avec une source de moindre niveau serait pire que ne pas répondre."
        ),
    }


def check_answer(texte: str) -> Dict[str, Any]:
    """
    Refuse une réponse de santé qui prend la forme d'un acte médical.

    Le filtre s'applique **après** la génération, sur le texte réellement
    produit : un modèle qui a lu la bonne notice peut quand même écrire
    « 500 mg toutes les six heures », et une consigne d'invite est un vœu, pas
    une garantie.

    Returns:
        `allowed`, et les formes repérées avec ce que chacune produirait.
    """
    trouvees = [
        {"kind": nom, "why": raison, "match": motif.search(texte or "").group(0).strip()}
        for nom, motif, raison in MOTIFS_INTERDITS
        if motif.search(texte or "")
    ]

    return {
        "allowed": not trouvees,
        "refused": trouvees,
        "reason": (
            "" if not trouvees else
            "Cette réponse prend la forme d'un acte médical : "
            + " ; ".join(entree["why"] for entree in trouvees)
            + ". La réponse est refusée, quoi que disent les sources."
        ),
        "method": "patterns",
        "not_detected": list(NON_DETECTE),
    }


def apply_health_policy(items: Iterable[Any], answer: str = "") -> Dict[str, Any]:
    """
    Applique les trois règles à une réponse de santé.

    Returns:
        Le verdict complet : sources retenues, refus éventuel, et
        **l'avertissement, présent dans tous les cas où une réponse sort**.
    """
    sources = filter_health_sources(items)
    if not sources["allowed"]:
        return {
            "status": "no_qualified_source",
            "allowed": False,
            "reason": sources["reason"],
            "dropped": sources["dropped"],
            "floor": sources["floor"],
            "safety_notice": AVERTISSEMENT,
            "what_would_settle_it": [
                "Ingérer une source du niveau exigé — ministère de la Santé, OMS, "
                "publication évaluée par les pairs (`corpus/sources/senegal.yaml`)",
            ],
        }

    verdict = check_answer(answer)
    if not verdict["allowed"]:
        return {
            "status": "refused_form",
            "allowed": False,
            "reason": verdict["reason"],
            "refused": verdict["refused"],
            "safety_notice": AVERTISSEMENT,
            "not_detected": verdict["not_detected"],
        }

    return {
        "status": "allowed",
        "allowed": True,
        "items": sources["items"],
        "dropped": sources["dropped"],
        "floor": sources["floor"],
        # Sur **chaque** réponse, pas « quand c'est utile » : la personne qui lit
        # doit voir dans la même réponse qu'un professionnel reste nécessaire.
        "safety_notice": AVERTISSEMENT,
        "not_detected": verdict["not_detected"],
    }


def health_policy_report() -> Dict[str, Any]:
    """Décrit la politique appliquée, pour qui veut la vérifier sans lire le code."""
    return {
        "subjects": sorted(sujet.value for sujet in SAFETY_CRITICAL_SUBJECTS),
        "source_floor": sorted(categorie.value for categorie in PLANCHER_DE_SOURCES),
        "refused_forms": [nom for nom, _, _ in MOTIFS_INTERDITS],
        "safety_notice": AVERTISSEMENT,
        "method": "patterns",
        "not_detected": list(NON_DETECTE),
        "note": (
            "Le refus est dans le code, pas dans une invite : un modèle qui a lu le "
            "bon document peut quand même produire une phrase dangereuse."
        ),
    }


def known_health_subjects() -> List[str]:
    """Retourne les sujets soumis à cette politique."""
    return sorted(sujet.value for sujet in SAFETY_CRITICAL_SUBJECTS if isinstance(sujet, KnowledgeSubject))
