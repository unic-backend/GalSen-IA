"""
Asking in three languages without ever translating the record.

Directive XXVII wants a curriculum reachable in French, Wolof and English.
Directive XXVIII adds the part that makes it honest: Wolof capability must be
*measured*, not claimed. Both are already half-built — `expand_terms` and
`translate` (`src/services/senegal/multilingual_aliases.py`) carry a vocabulary
table where the Wolof terms are declared by a named speaker and marked
`reviewed: false`. This module reuses that table and adds one asymmetry.

**The question travels; the record does not.** A query is expanded through the
alias table until it reaches an official unit. The unit's official title,
objectives and competencies are returned in the language the authority published
them in, always. Translating them would produce a second official record — a
Wolof "official title" nobody ratified — and there is no way to mark that
harmless once it is on a page.

**An unreviewed term stays unreviewed all the way to the answer.** If a match
was reached through a Wolof alias that no dictionary has confirmed, the answer
says so. Dropping the reserve at the last step is how a measured capability
turns into a claimed one.

**Nothing is guessed.** A term absent from the table adds no candidate. The
question then resolves on what it does carry, or asks for clarification — the
same refusal `resolution.py` already makes, reached through a different door.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..services.senegal.multilingual_aliases import (
    LANGUES,
    alias_report,
    translate,
)
from .registry import TROUVE, CurriculumRegistry
from .resolution import CurriculumQuery, resolve

#: Les langues de la couche éducative. Ce sont celles de la table d'alias : en
#: déclarer une quatrième ici sans terme derrière annoncerait une capacité que
#: rien ne porte.
LANGUES_EDUCATIVES = LANGUES

#: Ce qu'une résolution multilingue peut rendre en plus des états habituels.
DIRECTE = "DIRECT"
PAR_ALIAS = "VIA_ALIAS"
AUCUN_ALIAS = "NO_ALIAS"


def subject_candidates(
    subject: str, path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Les termes par lesquels une matière peut être désignée.

    Args:
        subject: Le terme tel qu'il a été posé.
        path: Un autre fichier d'alias, pour les tests.

    Returns:
        Le terme d'origine, les termes équivalents trouvés dans la table, et
        **si l'un d'eux est non relu**. Un terme absent de la table n'ajoute
        aucun candidat : deviner une traduction plausible est le seul moyen de
        se tromper ici.
    """
    candidats: List[str] = [subject]
    concepts: List[str] = []
    non_relu = False

    for langue in LANGUES_EDUCATIVES:
        trouve = translate(subject, vers=langue, chemin=path)
        if not trouve["found"]:
            continue
        concepts = sorted(set(concepts) | set(trouve["concepts"]))
        for terme in trouve["terms"]:
            if terme not in candidats:
                candidats.append(terme)
        if not trouve["reviewed"]:
            non_relu = True

    return {
        "subject": subject,
        "candidates": candidats,
        "concepts": concepts,
        "expanded": len(candidats) > 1,
        "includes_unreviewed": non_relu,
        "reason": (
            "Termes équivalents tirés de la table d'alias."
            if len(candidats) > 1 else
            "Terme absent de la table : aucun candidat ajouté, aucune "
            "traduction devinée."
        ),
    }


def resolve_multilingual(
    query: CurriculumQuery,
    registry: CurriculumRegistry,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Résout une question posée dans l'une des trois langues.

    Args:
        query: La question.
        registry: Le registre des versions officielles.
        path: Un autre fichier d'alias, pour les tests.

    Returns:
        La résolution habituelle, plus **par quel terme** elle a abouti et la
        réserve qui l'accompagne. Le terme déclaré est essayé en premier : un
        alias ne doit jamais l'emporter sur ce que quelqu'un a écrit
        explicitement.
    """
    directe = resolve(query, registry)
    if directe["status"] == TROUVE or not query.subject:
        return {
            **directe,
            "matched_by": DIRECTE if directe["status"] == TROUVE else AUCUN_ALIAS,
            "matched_term": query.subject,
            "unreviewed_terms_used": False,
        }

    expansion = subject_candidates(query.subject, path=path)
    for terme in expansion["candidates"][1:]:
        essai = resolve(
            CurriculumQuery(**{**query.as_dict(), "subject": terme}), registry,
        )
        if essai["status"] != TROUVE:
            continue
        # La réserve porte sur le **pont**, pas sur son arrivée. Une question
        # posée en wolof qui atteint un enregistrement par un terme français
        # repose entièrement sur la liste wolof non relue : ne regarder que le
        # terme d'arrivée déclarerait la correspondance sûre alors que c'est
        # justement le premier pas qui ne l'est pas.
        non_relu = _terme_non_relu(query.subject, path=path) or \
            _terme_non_relu(terme, path=path)
        return {
            **essai,
            "matched_by": PAR_ALIAS,
            "matched_term": terme,
            "asked_term": query.subject,
            "concepts": expansion["concepts"],
            "unreviewed_terms_used": non_relu,
            "reserve": (
                None if not non_relu else
                "Correspondance atteinte par un terme wolof déclaré par un "
                "locuteur nommé et **non confronté à un dictionnaire** "
                "(`wo_reviewed: false`). La réserve est portée jusqu'ici : la "
                "laisser tomber au dernier pas transformerait une capacité "
                "mesurée en capacité affirmée."
            ),
        }

    return {
        **directe,
        "matched_by": AUCUN_ALIAS,
        "matched_term": None,
        "asked_term": query.subject,
        "candidates_tried": expansion["candidates"][1:],
        "unreviewed_terms_used": False,
    }


def _terme_non_relu(terme: str, path: Optional[str] = None) -> bool:
    """
    Dit si un terme **est lui-même** un terme wolof non relu.

    La comparaison se fait sur les formes écrites rendues par `translate` : la
    table conserve `mbéy`, et c'est cette forme qu'une réponse montrera.
    """
    en_wolof = translate(terme, vers="wo", chemin=path)
    return bool(en_wolof["found"]) and not en_wolof["reviewed"] and \
        terme in en_wolof["terms"]


def official_language_of(
    registry: CurriculumRegistry, version_id: str,
) -> Dict[str, Any]:
    """
    La langue dans laquelle une version a été publiée.

    Args:
        registry: Le registre.
        version_id: La version.

    Returns:
        La langue officielle et la règle qui s'y attache. Elle vient du système
        éducatif importé, jamais d'une supposition sur le pays.
    """
    version = registry.get_version(version_id)
    if version is None:
        return {
            "known": False, "language": None,
            "reason": "Version inconnue du registre : aucune langue supposée.",
        }
    return {
        "known": True,
        "language": version.education_system.language,
        "rule": (
            "Les champs officiels sont rendus dans cette langue, toujours. Les "
            "traduire produirait un second enregistrement officiel que personne "
            "n'a ratifié."
        ),
    }


def explanation_language(
    requested: str, official_language: str,
) -> Dict[str, Any]:
    """
    Dit ce qui peut changer de langue, et ce qui ne le peut pas.

    Args:
        requested: La langue demandée pour l'explication.
        official_language: La langue de l'enregistrement officiel.

    Returns:
        La langue de l'explication, celle du fait, et leur statut respectif.
        L'explication est **générée** ; le fait ne l'est pas, et il ne change
        pas de langue.
    """
    return {
        "explanation_language": requested,
        "explanation_type": "AI_GENERATED",
        "canonical_language": official_language,
        "canonical_translated": False,
        "note": (
            "L'explication peut être produite dans une autre langue ; le fait "
            "officiel reste dans la sienne. Une réponse où les deux auraient "
            "été traduites ensemble ne permettrait plus de savoir ce que "
            "l'autorité a écrit."
        ),
    }


def multilingual_report(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Ce que la couche multilingue peut faire — **mesuré**, pas affirmé.

    Args:
        path: Un autre fichier d'alias, pour les tests.

    Returns:
        L'état de la table d'alias, les langues, et les règles tenues.
    """
    table = alias_report(path)
    return {
        "languages": list(LANGUES_EDUCATIVES),
        "alias_table": table,
        "wolof_reviewed": table.get("wo_reviewed", False),
        "match_kinds": [DIRECTE, PAR_ALIAS, AUCUN_ALIAS],
        "rules": [
            "La question voyage, l'enregistrement non : les champs officiels "
            "sont rendus dans la langue de publication, toujours.",
            "Traduire un champ officiel produirait un second enregistrement "
            "officiel que personne n'a ratifié.",
            "Le terme déclaré est essayé en premier : un alias ne l'emporte "
            "jamais sur ce que quelqu'un a écrit explicitement.",
            "Un terme absent de la table n'ajoute aucun candidat — aucune "
            "traduction n'est devinée.",
            "La réserve « wolof non relu » est portée **jusqu'à la réponse** : "
            "la laisser tomber au dernier pas transformerait une capacité "
            "mesurée en capacité affirmée.",
        ],
        "does_not": [
            "Traduire un titre, un objectif ou une compétence officielle.",
            "Deviner un équivalent absent de la table d'alias.",
            "Rapprocher deux termes par ressemblance.",
            "Affirmer une couverture wolof que la table ne porte pas.",
        ],
    }
