"""
Explaining an official record without becoming its author.

Directive XIII asks for five levels of explanation. The interesting part is not
the five levels — it is the sentence that follows them: *the underlying
curriculum fact must remain identical.* A pedagogical layer that can reach the
official title is a pedagogical layer that will eventually improve it, and an
improved official title is no longer official.

So the contract here is narrow on purpose:

- **The explanation function receives a copy and returns prose.** It cannot
  return fields. There is no shape in which it could hand back a modified
  `official_title`, because the only thing it is allowed to produce is text.
- **The canonical fact is re-attached afterwards, from the original**, not from
  whatever came back. Even a model that tried to restate the record cannot get
  its version into the answer.
- **An explanation that failed is an absence, not a fallback.** If the callable
  raises, the answer keeps the official fact and says the explanation is
  unavailable. Substituting a generic lesson would be the invention this whole
  layer exists to prevent.

The five levels are declared, not free-form: a caller asking for level 9 is asking
for something nobody defined, and guessing what they meant would produce
inconsistent teaching across a country.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

#: Les cinq niveaux (directive XIII). Le contenu du curriculum est le même aux
#: cinq ; seule la présentation change.
NIVEAUX: Dict[int, Dict[str, str]] = {
    1: {"name": "very_simple",
        "audience": "Un élève qui découvre, ou qui a décroché.",
        "instruction": "Explique en phrases courtes, avec un exemple concret "
                       "du quotidien. Aucun terme technique non défini."},
    2: {"name": "classroom",
        "audience": "L'explication de classe, celle du manuel.",
        "instruction": "Explique comme en cours : la notion, un exemple, une "
                       "application. Le vocabulaire officiel est utilisé et "
                       "défini."},
    3: {"name": "detailed",
        "audience": "Un élève qui veut comprendre pourquoi, pas seulement "
                    "comment.",
        "instruction": "Détaille le raisonnement, les cas particuliers et les "
                       "erreurs fréquentes."},
    4: {"name": "advanced",
        "audience": "Un élève en avance, ou en préparation d'examen.",
        "instruction": "Relie la notion à ce qui la précède et à ce qui la "
                       "suit, avec des exercices exigeants."},
    5: {"name": "expert",
        "audience": "Un enseignant, ou un élève très avancé.",
        "instruction": "Explique la structure mathématique ou conceptuelle "
                       "sous-jacente, et les choix didactiques possibles."},
}

#: Les champs qu'une explication ne doit jamais toucher. Ils ne lui sont pas
#: seulement interdits : ils lui sont **inaccessibles**, puisqu'elle ne rend que
#: du texte. La liste sert au rapport et au contrôle, pas à filtrer une sortie.
CHAMPS_INTOUCHABLES = (
    "official_title", "official_description", "competencies", "objectives",
    "prerequisites", "activities", "evaluation_requirements", "content_hash",
)


class PedagogyRefused(ValueError):
    """Une demande d'explication qui ne peut pas être servie telle quelle."""


def describe_level(level: int) -> Dict[str, str]:
    """
    Ce qu'un niveau demande à l'explication.

    Args:
        level: Le niveau, de 1 à 5.

    Returns:
        Son nom, son public et son instruction.

    Raises:
        PedagogyRefused: Pour un niveau non déclaré. Deviner ce qu'un « niveau
            9 » voudrait dire produirait un enseignement différent d'une classe
            à l'autre.
    """
    if level not in NIVEAUX:
        raise PedagogyRefused(
            f"Niveau {level} non déclaré. Les niveaux sont "
            f"{sorted(NIVEAUX)} : en deviner un produirait un enseignement "
            "différent d'une école à l'autre."
        )
    return dict(NIVEAUX[level])


def explain(
    canonical: Dict[str, Any],
    level: int = 2,
    generator: Optional[Callable[[Dict[str, Any]], str]] = None,
    language: str = "fr",
) -> Dict[str, Any]:
    """
    Produit une explication **à côté** du fait officiel, jamais à sa place.

    Args:
        canonical: Le fait canonique, tel que le pare-feu l'a rendu.
        level: Le niveau demandé, de 1 à 5.
        generator: L'explication elle-même, injectée. Elle reçoit une **copie**
            du fait et rend du texte : c'est la seule forme qu'elle peut rendre,
            donc elle ne peut pas renvoyer un titre officiel modifié.
        language: La langue de l'explication. Le fait, lui, garde la sienne.

    Returns:
        Le fait officiel repris **de l'original**, l'explication, son niveau, et
        ce qui manque quand elle n'a pas pu être produite.

    Raises:
        PedagogyRefused: Niveau inconnu, ou fait canonique absent — expliquer
            sans fait est exactement ce que le pare-feu interdit.
    """
    if not canonical:
        raise PedagogyRefused(
            "Aucun fait canonique à expliquer. Une explication sans fait est "
            "une leçon inventée, et c'est ce que le pare-feu (VOLET 6) refuse."
        )
    consigne = describe_level(level)

    if generator is None:
        return _sans_explication(
            canonical, level, consigne["name"], language,
            "Aucun moteur d'explication fourni : le fait officiel reste "
            "consultable, ce qui est la garantie de la directive XXXV.",
        )

    debut = time.perf_counter()
    try:
        # Une **copie** : si le générateur modifiait le dictionnaire reçu, il
        # modifierait le fait de l'appelant. Passer l'original serait laisser
        # une porte ouverte sans raison.
        texte = generator({
            "canonical": dict(canonical),
            "level": level,
            "level_name": consigne["name"],
            "instruction": consigne["instruction"],
            "language": language,
        })
    except Exception as erreur:
        return _sans_explication(
            canonical, level, consigne["name"], language,
            f"L'explication a échoué ({type(erreur).__name__}). Le fait "
            "officiel est rendu sans elle : lui substituer une leçon générique "
            "serait l'invention que cette couche existe pour empêcher.",
        )

    return {
        # Repris de l'original, jamais de ce que le générateur a rendu.
        "canonical": dict(canonical),
        "explanation": str(texte or ""),
        "level": level,
        "level_name": consigne["name"],
        "language": language,
        "explanation_available": bool(str(texte or "").strip()),
        "elapsed_ms": round((time.perf_counter() - debut) * 1000, 2),
        "note": (
            "L'explication est produite à partir du fait officiel et rendue à "
            "côté de lui. Le fait n'est pas relu depuis la sortie du modèle."
        ),
    }


def _sans_explication(
    canonical: Dict[str, Any], level: int, level_name: str, language: str,
    raison: str,
) -> Dict[str, Any]:
    """
    Le fait officiel, sans explication, et pourquoi.

    La forme rendue est **la même** que celle du cas nominal : un appelant qui
    lirait `language` ou `level_name` échouerait sinon exactement au moment où
    l'explication a manqué, c'est-à-dire au pire moment.
    """
    return {
        "canonical": dict(canonical),
        "explanation": None,
        "level": level,
        "level_name": level_name,
        "language": language,
        "explanation_available": False,
        "reason": raison,
    }


def catch_up_plan(
    missed_units: List[Dict[str, Any]],
    available_hours: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Ordonne des unités manquées selon la séquence officielle (directive XIV).

    L'ordre vient du curriculum — période, puis prérequis — et non d'une
    estimation de difficulté que personne n'a mesurée. Ce plan est **généré**,
    et il le dit : il ne remplace ni la classe ni l'enseignant.

    Args:
        missed_units: Les unités manquées, telles que le registre les rend.
        available_hours: Le temps dont l'élève dispose, s'il est connu.

    Returns:
        L'ordre de reprise, ce qui bloque quoi, et la nature du plan.
    """
    def _rang(unite: Dict[str, Any]) -> tuple:
        periode = unite.get("period", {})
        return (
            periode.get("term") or 0, periode.get("month") or 0,
            periode.get("week") or 0, periode.get("sequence") or 0,
        )

    ordonnees = sorted(missed_units, key=_rang)
    titres = {u.get("official_title", "") for u in ordonnees}
    bloquantes = [
        {
            "unit_id": unite.get("unit_id"),
            "blocked_by": [
                prerequis for prerequis in unite.get("prerequisites", [])
                if prerequis in titres
            ],
        }
        for unite in ordonnees
    ]

    return {
        "content_type": "AI_GENERATED",
        "order": [unite.get("unit_id") for unite in ordonnees],
        "sequence_source": "official_curriculum_period_then_prerequisites",
        "blocking": [b for b in bloquantes if b["blocked_by"]],
        "available_hours": available_hours,
        "hours_estimate": None,
        "note": (
            "Plan **généré**. Il suit la séquence officielle ; il ne remplace "
            "ni la classe ni l'enseignant, et aucune durée n'est estimée — une "
            "estimation que personne n'a mesurée se lirait comme une promesse."
        ),
    }


def pedagogy_report() -> Dict[str, Any]:
    """
    Ce que la couche pédagogique peut faire, et ce qu'elle ne peut pas.

    Returns:
        Les niveaux, les champs intouchables, et les règles tenues.
    """
    return {
        "levels": {
            niveau: {"name": details["name"], "audience": details["audience"]}
            for niveau, details in NIVEAUX.items()
        },
        "untouchable_fields": list(CHAMPS_INTOUCHABLES),
        "rules": [
            "L'explication ne rend que du **texte** : il n'existe aucune forme "
            "dans laquelle elle pourrait renvoyer un champ officiel modifié.",
            "Le fait est réattaché depuis l'original, jamais depuis la sortie "
            "du modèle.",
            "Une explication qui échoue est une **absence**, pas un repli : le "
            "fait officiel sort seul, avec la raison.",
            "Les cinq niveaux sont déclarés : deviner un niveau non défini "
            "produirait un enseignement différent d'une école à l'autre.",
            "Un plan de rattrapage est **généré** et le dit ; il suit la "
            "séquence officielle et ne remplace ni la classe ni l'enseignant.",
        ],
        "does_not": [
            "Reformuler un champ officiel, même pour le rendre plus clair.",
            "Estimer une durée de rattrapage que personne n'a mesurée.",
            "Expliquer sans fait canonique : le pare-feu l'interdit en amont.",
        ],
    }
