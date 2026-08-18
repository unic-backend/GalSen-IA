"""
Answering a student — without grading them, and without handing them the key.

A student is the reader the rest of this package was built for, and also the one
with the most to lose from a confident wrong answer: they have no way to check
it. So student mode adds nothing to the firewall's guarantees — it inherits all
of them — and adds two of its own.

**A quiz shown to a student carries no marking key.** This is a projection, not
a promise: `student_quiz()` builds the student's view from scratch and copies
only the fields a student needs. A field added to `QuizItem` later cannot leak
through it by default, because nothing here forwards unknown fields. That is the
difference between stripping a key and never carrying one.

**A student is never told what they are.** They get their own measurements —
what they answered, what was not marked, which objectives have too little
evidence to say anything — and no appraisal, no rank, no grade. The platform
does not have a grade to give: a grade is a teacher's decision (VOLET 10), and
`INSUFFICIENT_EVIDENCE` is a real answer here too.

Everything a student sees about themselves goes through `access.require_own`.
Not because a student is likely to ask for another's work, but because the
function that forgets to ask is the one that hands it over.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from .access import require_own
from .assessment import QuizItem, evidence_by_objective
from .firewall import CANONIQUE, answer
from .pedagogy import catch_up_plan, explain
from .registry import CurriculumRegistry
from .resolution import CurriculumQuery

#: Le niveau d'explication par défaut pour un élève : celui de la classe. Les
#: cinq niveaux restent disponibles — c'est le niveau qui change, jamais le fait
#: (VOLET 8).
NIVEAU_ELEVE = 2

#: Les champs qu'un élève voit d'un item. La liste est **positive** : un champ
#: ajouté plus tard à `QuizItem` ne passe pas ici tout seul.
CHAMPS_VISIBLES_ELEVE = ("index", "prompt", "objective", "item_type")


def student_answer(
    query: CurriculumQuery,
    registry: CurriculumRegistry,
    generator: Optional[Callable[[Dict[str, Any]], str]] = None,
    level: int = NIVEAU_ELEVE,
) -> Dict[str, Any]:
    """
    Répond à un élève : le fait officiel, expliqué, ou un refus assumé.

    Args:
        query: La question de l'élève.
        registry: Le registre des versions officielles.
        generator: L'explication pédagogique, injectée.
        level: Le niveau d'explication (1 à 5).

    Returns:
        Le fait officiel tel quel et son explication à côté. Sans
        enregistrement, le refus du pare-feu est rendu **avec sa raison et sans
        substitut** : un élève n'a aucun moyen de vérifier une réponse fausse,
        ce qui est précisément pourquoi on ne lui en donne pas.
    """
    reponse = answer(query, registry, explain=None, level=level)
    if reponse.get("answer_type") != CANONIQUE:
        return {
            "answer_type": reponse.get("answer_type"),
            "canonical": None,
            "explanation": None,
            "reason": reponse.get("reason"),
            "missing": reponse.get("missing", []),
            "note": (
                "Aucun substitut n'est proposé. Un élève n'a pas les moyens de "
                "vérifier une réponse fausse — c'est ce qui rend l'invention "
                "plus grave ici qu'ailleurs."
            ),
        }

    pedagogie = explain(reponse["canonical"], level=level, generator=generator)
    return {
        "answer_type": CANONIQUE,
        "canonical": reponse["canonical"],
        "explanation": pedagogie["explanation"],
        "explanation_available": pedagogie["explanation_available"],
        "level": level,
        "level_name": pedagogie["level_name"],
        "unit_id": reponse["unit_id"],
        "provenance": reponse["provenance"],
        "grade": None,
        "note": (
            "Le fait officiel est repris tel quel ; l'explication est à côté. "
            "Aucune note n'accompagne une réponse : la plateforme n'en a pas."
        ),
    }


def student_quiz(items: Sequence[QuizItem]) -> Dict[str, Any]:
    """
    La vue élève d'un quiz : les énoncés, jamais les clés.

    Args:
        items: Les items du quiz.

    Returns:
        Une projection **construite champ par champ**. Rien n'est retiré d'un
        dictionnaire existant : la vue est bâtie à partir d'une liste positive,
        donc un champ ajouté plus tard à `QuizItem` ne fuit pas par défaut.
    """
    vue = [
        {
            "index": index,
            "prompt": item.prompt,
            "objective": item.objective,
            "item_type": item.item_type,
        }
        for index, item in enumerate(items)
    ]
    return {
        "items": vue,
        "count": len(vue),
        "visible_fields": list(CHAMPS_VISIBLES_ELEVE),
        "note": (
            "Aucune clé de correction n'est portée par cette vue : elle est "
            "construite à partir des champs visibles, pas obtenue en retirant "
            "les autres."
        ),
    }


def own_results(
    scoring: Dict[str, Any], subject_ref: str, viewer_ref: str,
) -> Dict[str, Any]:
    """
    Rend à un élève ses propres mesures, et rien sur personne d'autre.

    Args:
        scoring: Le résultat de `assessment.score_attempt`.
        subject_ref: L'élève concerné.
        viewer_ref: Qui demande.

    Returns:
        Le décompte, les objectifs trop peu mesurés, et **aucune note**.

    Raises:
        AccessRefused: Si le lecteur n'est pas l'élève concerné.
    """
    require_own(viewer_ref, subject_ref)
    preuve = evidence_by_objective(scoring)

    return {
        "subject_ref": subject_ref,
        "scored_count": scoring.get("scored_count", 0),
        "correct_count": scoring.get("correct_count", 0),
        "unanswered_count": scoring.get("unanswered_count", 0),
        "not_scored_count": len(scoring.get("not_scored", [])),
        "objectives_measured": preuve["objectives_measured"],
        "objectives_not_measured": [
            objectif for objectif, agrege in preuve["by_objective"].items()
            if objectif not in preuve["objectives_measured"]
        ],
        "grade": None,
        "rank": None,
        "appraisal": None,
        "note": (
            "Des mesures, pas un jugement. Aucune note, aucun rang, aucune "
            "appréciation : un objectif trop peu mesuré est dit tel quel, et "
            "ce n'est pas un échec."
        ),
    }


def study_plan(
    missed_units: List[Dict[str, Any]],
    subject_ref: str,
    viewer_ref: str,
    available_hours: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Un ordre de reprise, dans la séquence officielle.

    Args:
        missed_units: Les unités manquées, telles que le registre les rend.
        subject_ref: L'élève concerné.
        viewer_ref: Qui demande.
        available_hours: Le temps dont l'élève dispose, s'il est connu.

    Returns:
        Le plan de `pedagogy.catch_up_plan`, rattaché à son élève. Il reste
        marqué `AI_GENERATED` et n'estime aucune durée.

    Raises:
        AccessRefused: Si le lecteur n'est pas l'élève concerné.
    """
    require_own(viewer_ref, subject_ref)
    plan = catch_up_plan(missed_units, available_hours=available_hours)
    return {"subject_ref": subject_ref, **plan}


def student_report() -> Dict[str, Any]:
    """
    Ce que le mode élève donne, et ce qu'il ne donne jamais.

    Returns:
        Les champs visibles, le niveau par défaut, et les règles tenues.
    """
    return {
        "default_level": NIVEAU_ELEVE,
        "visible_quiz_fields": list(CHAMPS_VISIBLES_ELEVE),
        "rules": [
            "La vue élève d'un quiz est **construite** à partir des champs "
            "visibles, pas obtenue en retirant les clés : un champ ajouté plus "
            "tard ne fuit pas par défaut.",
            "Un élève ne reçoit ni note, ni rang, ni appréciation — la "
            "plateforme n'en a pas à donner.",
            "Un objectif trop peu mesuré est dit tel quel : "
            "`INSUFFICIENT_EVIDENCE` n'est pas un échec.",
            "Toute lecture de ses propres données passe par une vérification "
            "explicite du lecteur ; une référence absente ne montre rien.",
            "Sans enregistrement officiel, le refus est rendu sans substitut : "
            "un élève n'a pas les moyens de vérifier une réponse fausse.",
        ],
        "does_not": [
            "Montrer une clé de correction.",
            "Montrer le travail d'un autre élève.",
            "Produire une note, un classement ou une appréciation.",
            "Répondre depuis la mémoire d'un modèle quand le registre est vide.",
        ],
    }
