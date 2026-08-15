"""
Showing a parent their child's programme — the same programme, and only theirs.

Parent mode is where two of this package's guarantees meet, and neither is
decorative.

**It is the same official fact the child receives.** Directive VI's four
questioners include the parent, and `consistency.check_group` measures it. A
parent view that "simplified" the record for a non-specialist would be a second
curriculum with a friendlier tone, and the moment a parent and a teacher read
different things, the argument is about which of them the platform lied to.

**The link to the child is declared, never inferred.** `access.require_declared_link`
holds this: the caller passes the children an enrolment source says this
guardian follows. Nothing here reads a surname, a household, or a previous
conversation. A platform that infers who a parent is will eventually infer
wrong, and that particular error hands one family another family's child.

What a parent does *not* get is anything resembling a judgement. No grade, no
rank, no appraisal — those are a teacher's decisions (VOLET 10) and the platform
has none to give. What it can give is measured: what was answered, what was not
marked, and which objectives carry too little evidence to say anything at all.
`INSUFFICIENT_EVIDENCE` reads badly to a worried parent, which is exactly why it
must not be rounded into a verdict.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional, Sequence

from .access import require_declared_link
from .assessment import (
    PREUVE_INSUFFISANTE,
    PREUVE_SUFFISANTE,
    PREUVES_MINIMALES,
    evidence_by_objective,
)
from .firewall import CANONIQUE, answer
from .pedagogy import explain
from .registry import CurriculumRegistry
from .resolution import CurriculumQuery

#: Le niveau d'explication par défaut pour un responsable : celui de la classe,
#: le même que pour l'élève. Un niveau plus bas « pour les parents » supposerait
#: quelque chose que personne n'a mesuré.
NIVEAU_PARENT = 2


def child_curriculum(
    query: CurriculumQuery,
    registry: CurriculumRegistry,
    child_ref: str,
    viewer_ref: str,
    authorized_children: Optional[Iterable[str]] = None,
    generator: Optional[Callable[[Dict[str, Any]], str]] = None,
    level: int = NIVEAU_PARENT,
) -> Dict[str, Any]:
    """
    Le programme officiel de l'enfant — le même que le sien.

    Args:
        query: La question de curriculum.
        registry: Le registre des versions officielles.
        child_ref: L'enfant concerné.
        viewer_ref: Le responsable qui demande.
        authorized_children: Les enfants que ce responsable est **déclaré**
            suivre. Vide ou absent n'accorde rien.
        generator: L'explication pédagogique, injectée.
        level: Le niveau d'explication (1 à 5).

    Returns:
        Le fait officiel tel quel, l'explication à côté, et aucune note.

    Raises:
        AccessRefused: Sans lien déclaré vers cet enfant.
    """
    require_declared_link(viewer_ref, child_ref, authorized_children)

    reponse = answer(query, registry, explain=None, level=level)
    if reponse.get("answer_type") != CANONIQUE:
        return {
            "child_ref": child_ref,
            "answer_type": reponse.get("answer_type"),
            "canonical": None,
            "explanation": None,
            "reason": reponse.get("reason"),
            "note": (
                "Aucun substitut n'est proposé. Inventer un programme pour "
                "rassurer un parent le tromperait sur ce que fait son enfant."
            ),
        }

    pedagogie = explain(reponse["canonical"], level=level, generator=generator)
    return {
        "child_ref": child_ref,
        "answer_type": CANONIQUE,
        # Repris tel quel : c'est **le même** enregistrement que l'élève et
        # l'enseignant reçoivent, et la directive VI le rend vérifiable.
        "canonical": reponse["canonical"],
        "explanation": pedagogie["explanation"],
        "explanation_available": pedagogie["explanation_available"],
        "level": level,
        "unit_id": reponse["unit_id"],
        "version_id": reponse["version_id"],
        "provenance": reponse["provenance"],
        "grade": None,
        "note": (
            "C'est le même enregistrement officiel que celui rendu à l'élève "
            "et à l'enseignant. Une version « simplifiée pour les parents » "
            "serait un second curriculum au ton plus aimable."
        ),
    }


def child_progress(
    scorings: Sequence[Dict[str, Any]],
    child_ref: str,
    viewer_ref: str,
    authorized_children: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    Ce qui a été mesuré chez l'enfant, sans conclusion sur lui.

    Args:
        scorings: Les résultats de `assessment.score_attempt`.
        child_ref: L'enfant concerné.
        viewer_ref: Le responsable qui demande.
        authorized_children: Les enfants déclarés de ce responsable.

    Returns:
        Les décomptes, les objectifs mesurés et ceux qui ne le sont pas assez,
        et **aucun** jugement. `INSUFFICIENT_EVIDENCE` se lit mal quand on
        s'inquiète pour son enfant, et c'est exactement pourquoi il ne doit pas
        être arrondi en verdict.

    Raises:
        AccessRefused: Sans lien déclaré vers cet enfant.
    """
    require_declared_link(viewer_ref, child_ref, authorized_children)

    mesures: Dict[str, Any] = {}
    for scoring in scorings:
        for objectif, agrege in evidence_by_objective(scoring)["by_objective"].items():
            courant = mesures.setdefault(objectif, {"scored": 0, "correct": 0})
            courant["scored"] += agrege["scored"]
            courant["correct"] += agrege["correct"]

    # Le verdict est **recalculé** sur le cumul, jamais recopié d'un devoir :
    # deux devoirs de deux items mesurent quatre items, et chacun pris seul
    # dirait « pas assez ». Et il est rendu : sans lui, « 1 sur 1 » se lit comme
    # une maîtrise là où il n'y a aucune mesure.
    for agrege in mesures.values():
        assez = agrege["scored"] >= PREUVES_MINIMALES
        agrege["verdict"] = PREUVE_SUFFISANTE if assez else PREUVE_INSUFFISANTE
        agrege["reason"] = (
            f"{agrege['scored']} items corrigés (minimum {PREUVES_MINIMALES})."
            if assez else
            f"{agrege['scored']} items corrigés sur {PREUVES_MINIMALES} requis : "
            "trop peu pour dire quoi que ce soit. Ce n'est pas un échec, c'est "
            "une absence de mesure."
        )

    return {
        "child_ref": child_ref,
        "attempts": len(scorings),
        "scored_count": sum(s.get("scored_count", 0) for s in scorings),
        "correct_count": sum(s.get("correct_count", 0) for s in scorings),
        "unanswered_count": sum(s.get("unanswered_count", 0) for s in scorings),
        "not_scored_count": sum(len(s.get("not_scored", [])) for s in scorings),
        "by_objective": mesures,
        "grade": None,
        "rank": None,
        "appraisal": None,
        "comparison_with_other_children": None,
        "note": (
            "Des mesures, pas un jugement. Ni note, ni rang, ni comparaison "
            "avec d'autres enfants : ce sont des décisions d'enseignant, et la "
            "plateforme n'en prend pas."
        ),
    }


def parent_report() -> Dict[str, Any]:
    """
    Ce que le mode parent montre, et ce qu'il ne montre jamais.

    Returns:
        Le niveau par défaut et les règles tenues.
    """
    return {
        "default_level": NIVEAU_PARENT,
        "rules": [
            "C'est **le même** enregistrement officiel que celui rendu à "
            "l'élève et à l'enseignant — la directive VI le rend vérifiable.",
            "Le lien vers l'enfant est **déclaré** par une source d'inscription, "
            "jamais déduit d'un nom ou d'un foyer.",
            "Aucune note, aucun rang, aucune comparaison avec d'autres enfants.",
            "`INSUFFICIENT_EVIDENCE` est rendu tel quel : il se lit mal quand "
            "on s'inquiète, et c'est pourquoi il ne doit pas être arrondi.",
        ],
        "does_not": [
            "Simplifier le programme officiel « pour les parents ».",
            "Montrer un autre enfant que ceux déclarés.",
            "Produire une appréciation, un classement ou une comparaison.",
            "Inventer un programme pour rassurer.",
        ],
    }
