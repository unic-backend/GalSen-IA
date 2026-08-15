"""
Saying what a learner has demonstrated — and refusing to say more than that.

Directive XXX asks for mastery per competency, with *insufficient evidence* as a
first-class state. That second half is the whole design. Every mastery model
ever built has a quiet failure: it produces a level for everyone, because a
level is what it was asked for, and "not enough data" gets rounded into the
lowest level. A child who answered two questions then appears as *weak* rather
than *unmeasured*, and that label follows them.

So the states here are not a scale with a floor. `NOT_MEASURED` and
`INSUFFICIENT_EVIDENCE` are outside the scale entirely — they describe the
measurement, not the learner — and no arithmetic can turn one into `EMERGING`.
Only crossing a declared evidence floor puts a learner on the scale at all.

Three further refusals:

**The thresholds are declared, so they can be argued with.** An implicit
threshold is a policy nobody can contest. These are module constants with the
reasoning attached, and a caller may pass their own.

**Mastery is never a grade, a rank, or a comparison.** It states what was
demonstrated against one official objective. Turning that into a number for a
report card is a teacher's decision (VOLET 10), and the platform does not take
it.

**A level whose prerequisites were never measured says so.** This is where the
graph (VOLET 14) earns its place: `SECURE` on fractions while nothing was ever
measured on the division it officially requires is a fragile claim, and the
report carries `unverified_prerequisites` rather than a confident level alone.
It is not downgraded — inventing a penalty would be as made-up as inventing the
level — it is qualified.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Sequence

from .assessment import PREUVES_MINIMALES, evidence_by_objective
from .graph import EducationalGraph

#: Hors de l'échelle : ces deux états décrivent la **mesure**, pas l'élève.
#: Aucun calcul ne les transforme en un niveau — c'est ce qui empêche un enfant
#: ayant répondu à deux questions d'apparaître « faible » plutôt que « non
#: mesuré ».
NON_MESURE = "NOT_MEASURED"
PREUVE_INSUFFISANTE = "INSUFFICIENT_EVIDENCE"

#: L'échelle, atteignable seulement une fois le plancher de preuve franchi.
EMERGENT = "EMERGING"
EN_COURS = "DEVELOPING"
ACQUIS = "SECURE"

#: Les états hors échelle, nommés pour qu'une interface puisse les distinguer
#: d'un niveau faible.
ETATS_HORS_ECHELLE = (NON_MESURE, PREUVE_INSUFFISANTE)

#: L'échelle, du plus bas au plus haut.
ECHELLE = (EMERGENT, EN_COURS, ACQUIS)

#: Les seuils, **déclarés donc contestables**. Un seuil implicite est une
#: politique que personne ne peut discuter.
SEUIL_ACQUIS = 0.8
SEUIL_EN_COURS = 0.5


class MasteryRefused(ValueError):
    """Une demande de maîtrise qui ne peut pas être servie telle quelle."""


def level_for(
    scored: int, correct: int, minimum: int = PREUVES_MINIMALES,
) -> Dict[str, Any]:
    """
    Dit ce qu'un décompte permet d'affirmer — souvent : rien.

    Args:
        scored: Le nombre d'items corrigés.
        correct: Le nombre de réponses justes.
        minimum: Le plancher de preuve.

    Returns:
        L'état, le ratio quand il a un sens, et la raison. En dessous du
        plancher, l'état est `INSUFFICIENT_EVIDENCE` **quel que soit** le ratio :
        trois réponses justes sur trois ne disent rien de plus que trois
        réponses justes sur trois.

    Raises:
        MasteryRefused: Pour un décompte impossible — plus de réponses justes
            que d'items corrigés est une erreur d'appel, pas une maîtrise
            exceptionnelle.
    """
    if scored < 0 or correct < 0 or correct > scored:
        raise MasteryRefused(
            f"Décompte impossible : {correct} justes pour {scored} corrigés. "
            "C'est une erreur d'appel, et l'arrondir cacherait un défaut de "
            "correction."
        )

    if scored == 0:
        return {
            "state": NON_MESURE, "scored": 0, "correct": 0, "ratio": None,
            "on_scale": False,
            "reason": "Aucun item corrigé : rien n'a été mesuré.",
        }

    if scored < minimum:
        return {
            "state": PREUVE_INSUFFISANTE, "scored": scored, "correct": correct,
            "ratio": None, "on_scale": False,
            "reason": (
                f"{scored} items corrigés sur {minimum} requis. Le ratio n'est "
                "pas rendu : le calculer inviterait à le lire comme un niveau, "
                "et un enfant ayant répondu deux fois apparaîtrait « faible » "
                "plutôt que « non mesuré »."
            ),
        }

    ratio = correct / scored
    if ratio >= SEUIL_ACQUIS:
        etat = ACQUIS
    elif ratio >= SEUIL_EN_COURS:
        etat = EN_COURS
    else:
        etat = EMERGENT

    return {
        "state": etat, "scored": scored, "correct": correct,
        "ratio": round(ratio, 3), "on_scale": True,
        "reason": (
            f"{correct} justes sur {scored} corrigés, seuils déclarés "
            f"{SEUIL_EN_COURS} et {SEUIL_ACQUIS}."
        ),
    }


def mastery_by_objective(
    scorings: Sequence[Dict[str, Any]], minimum: int = PREUVES_MINIMALES,
) -> Dict[str, Any]:
    """
    L'état de maîtrise, objectif officiel par objectif officiel.

    Args:
        scorings: Les résultats de `assessment.score_attempt`.
        minimum: Le plancher de preuve.

    Returns:
        Un état par objectif, et **aucun total**. Une moyenne sur des objectifs
        de natures différentes produirait un nombre qui se lirait comme une
        note, ce que la plateforme n'a pas à donner.
    """
    cumuls: Dict[str, Dict[str, int]] = {}
    for scoring in scorings:
        for objectif, agrege in evidence_by_objective(
            scoring, minimum=minimum,
        )["by_objective"].items():
            courant = cumuls.setdefault(objectif, {"scored": 0, "correct": 0})
            courant["scored"] += agrege["scored"]
            courant["correct"] += agrege["correct"]

    etats = {
        objectif: level_for(cumul["scored"], cumul["correct"], minimum=minimum)
        for objectif, cumul in cumuls.items()
    }

    return {
        "minimum_items": minimum,
        "by_objective": etats,
        "on_scale": sorted(o for o, e in etats.items() if e["on_scale"]),
        "not_on_scale": sorted(o for o, e in etats.items() if not e["on_scale"]),
        "overall": None,
        "grade": None,
        "rank": None,
        "note": (
            "Aucun total : une moyenne sur des objectifs de natures "
            "différentes produirait un nombre qui se lirait comme une note. "
            "`NOT_MEASURED` et `INSUFFICIENT_EVIDENCE` sont **hors échelle** — "
            "ils décrivent la mesure, pas l'élève."
        ),
    }


def qualify_with_prerequisites(
    mastery: Dict[str, Any],
    unit_id: str,
    graph: EducationalGraph,
    measured_units: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    Qualifie un état de maîtrise par ce qui n'a jamais été mesuré en amont.

    Args:
        mastery: L'état rendu par `level_for`.
        unit_id: L'unité concernée.
        graph: Le graphe éducatif (VOLET 14).
        measured_units: Les unités sur lesquelles quelque chose a été mesuré.

    Returns:
        L'état **inchangé**, accompagné des prérequis officiels jamais mesurés.
        Il n'est pas abaissé : inventer une pénalité serait aussi fabriqué
        qu'inventer le niveau. Il est qualifié — `SECURE` sur les fractions
        alors que rien n'a été mesuré sur la division qu'elles exigent
        officiellement est une affirmation fragile, et le dire est le travail
        de cette fonction.
    """
    mesurees = set(measured_units or [])
    chaine = graph.chain_to(unit_id)
    non_mesures = [
        prerequis for prerequis in chaine["before"] if prerequis not in mesurees
    ]

    return {
        **mastery,
        "unit_id": unit_id,
        "prerequisite_chain": chaine["before"],
        "unverified_prerequisites": non_mesures,
        "prerequisite_cycles": chaine["cycles"],
        "qualified": bool(non_mesures),
        "qualification": (
            None if not non_mesures else
            f"{len(non_mesures)} prérequis officiel(s) jamais mesuré(s). "
            "L'état n'est pas abaissé — inventer une pénalité serait aussi "
            "fabriqué qu'inventer le niveau — mais il repose sur moins que ce "
            "que le programme suppose acquis."
        ),
    }


def mastery_report() -> Dict[str, Any]:
    """
    Ce que le modèle de maîtrise affirme, et ce qu'il refuse d'affirmer.

    Returns:
        Les états, les seuils déclarés, et les règles tenues.
    """
    return {
        "off_scale_states": list(ETATS_HORS_ECHELLE),
        "scale": list(ECHELLE),
        "thresholds": {"developing": SEUIL_EN_COURS, "secure": SEUIL_ACQUIS},
        "minimum_items": PREUVES_MINIMALES,
        "rules": [
            "`NOT_MEASURED` et `INSUFFICIENT_EVIDENCE` sont **hors échelle** : "
            "ils décrivent la mesure, pas l'élève, et aucun calcul ne les "
            "transforme en niveau.",
            "En dessous du plancher, le ratio n'est pas rendu : le calculer "
            "inviterait à le lire comme un niveau.",
            "Les seuils sont déclarés, donc contestables — un seuil implicite "
            "est une politique que personne ne peut discuter.",
            "Aucun total, aucune moyenne : un nombre unique se lirait comme une "
            "note.",
            "Un état dont les prérequis n'ont jamais été mesurés est **qualifié**, "
            "pas abaissé : inventer une pénalité serait aussi fabriqué "
            "qu'inventer le niveau.",
        ],
        "does_not": [
            "Produire une note, un rang ou une moyenne.",
            "Comparer un élève à un autre.",
            "Arrondir une absence de mesure en un niveau faible.",
            "Prédire ce qu'un élève réussira.",
        ],
    }


__all__ = [
    "ACQUIS",
    "ECHELLE",
    "EMERGENT",
    "EN_COURS",
    "ETATS_HORS_ECHELLE",
    "MasteryRefused",
    "NON_MESURE",
    "PREUVE_INSUFFISANTE",
    "SEUIL_ACQUIS",
    "SEUIL_EN_COURS",
    "level_for",
    "mastery_by_objective",
    "mastery_report",
    "qualify_with_prerequisites",
]
