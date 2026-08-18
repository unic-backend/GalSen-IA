"""
Asking a student questions without inventing what they were taught — or what
they scored.

Two fabrications are possible here and both are named in the directive's list of
things Darra J must never do: **fabricate curriculum content**, and **fabricate
grades**. A quiz is where they meet, because a generated question looks exactly
like an official one once it is on a page, and a computed number looks exactly
like a mark once it is in a report.

So this module holds two anchors.

**Every item is anchored to an official objective, verbatim.** An item is built
*for* an objective taken from the canonical record, and an item naming an
objective the record does not contain is refused — proposing one would be
writing curriculum with extra steps. The anchor carries the `content_hash` too:
a quiz built against a record that has since been rewritten is stale, and it can
say so instead of quietly testing last year's programme.

**A score is a measurement, never a grade.** The platform counts what a marking
key says; it does not decide what that count is worth. `grade` is always `None`
and says why. An item with no marking key is reported `NOT_SCORED` by name
rather than being counted wrong — counting an unmarkable item as a failure would
invent a result about a student.

And evidence has a floor: `INSUFFICIENT_EVIDENCE` is a first-class verdict, not
a low score. Two answers do not establish anything about an objective, and
saying so is the difference between a measurement and a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .firewall import CANONIQUE, GENERE_IA

#: Ce qu'un item est. La distinction est celle du pare-feu (VOLET 6) et elle
#: vaut ici pour la même raison : une question générée et une exigence
#: d'évaluation officielle se ressemblent une fois imprimées.
ITEM_GENERE = GENERE_IA
ITEM_OFFICIEL = CANONIQUE

#: Les issues d'une correction.
CORRIGE = "SCORED"
NON_CORRIGE = "NOT_SCORED"

#: Les verdicts de preuve. `INSUFFICIENT_EVIDENCE` n'est pas une mauvaise note :
#: c'est l'absence de mesure, et la confondre avec un échec ferait porter à un
#: élève le résultat d'un quiz trop court.
PREUVE_SUFFISANTE = "SUFFICIENT_EVIDENCE"
PREUVE_INSUFFISANTE = "INSUFFICIENT_EVIDENCE"

#: Le nombre d'items corrigés en dessous duquel aucune affirmation n'est faite
#: sur un objectif. Déclaré, donc contestable — un seuil implicite ne l'est pas.
PREUVES_MINIMALES = 3


class AssessmentRefused(ValueError):
    """Une évaluation qui ne peut pas être construite ou corrigée telle quelle."""


@dataclass(frozen=True)
class QuizItem:
    """
    Une question, et l'enregistrement officiel à laquelle elle est accrochée.

    Attributes:
        unit_id: L'unité de curriculum visée.
        content_hash: L'empreinte de cette unité **au moment de la construction**.
            Un quiz bâti sur un enregistrement réécrit depuis est périmé, et il
            peut le dire au lieu d'interroger silencieusement l'an dernier.
        objective: L'objectif officiel visé, repris **mot pour mot**.
        prompt: L'énoncé. Généré, sauf s'il vient du curriculum lui-même.
        item_type: `AI_GENERATED` ou `CANONICAL_OFFICIAL`.
        answer_key: La clé de correction, quand quelqu'un l'a fournie. Absente,
            l'item n'est pas corrigé — il n'est pas compté faux.
    """

    unit_id: str
    content_hash: str
    objective: str
    prompt: str
    item_type: str = ITEM_GENERE
    answer_key: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "unit_id": self.unit_id, "content_hash": self.content_hash,
            "objective": self.objective, "prompt": self.prompt,
            "item_type": self.item_type,
            "scorable": self.answer_key is not None,
        }


@dataclass
class Attempt:
    """
    Ce qu'un élève a rendu, avant toute interprétation.

    Attributes:
        answers: Une réponse par index d'item. Une absence est une absence :
            elle n'est pas comptée fausse.
        subject_ref: La référence de l'élève, telle que l'appelant la porte.
            Aucune donnée personnelle n'est requise ici — un identifiant
            opaque suffit à corriger.
    """

    answers: Dict[int, str] = field(default_factory=dict)
    subject_ref: str = ""


def build_quiz(
    answer: Dict[str, Any],
    generator: Optional[Callable[[Dict[str, Any]], str]] = None,
    max_items: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Construit un quiz **à partir** d'un fait officiel, jamais à sa place.

    Args:
        answer: La réponse du pare-feu (`firewall.answer`). Elle doit être
            `CANONICAL_OFFICIAL` : sans enregistrement, il n'y a rien à évaluer
            et générer des questions écrirait un programme.
        generator: L'énoncé, injecté. Il reçoit une **copie** du fait et
            l'objectif visé, et rend du texte — la seule forme qu'il peut rendre.
        max_items: Un plafond facultatif. Le plancher, lui, est structurel : il
            ne peut pas y avoir plus d'items que d'objectifs officiels.

    Returns:
        Les items, les exigences d'évaluation officielles reprises telles
        quelles, et ce qui manque.

    Raises:
        AssessmentRefused: Si la réponse n'est pas canonique. C'est la même
            règle que le pare-feu, appliquée un cran plus loin : une question
            inventée est aussi enseignable qu'une leçon inventée.
    """
    if answer.get("answer_type") != CANONIQUE or not answer.get("canonical"):
        raise AssessmentRefused(
            "Aucun fait canonique : un quiz construit ici poserait des questions "
            "sur un programme que personne n'a publié. `UNKNOWN` reste la "
            "réponse — voir le pare-feu (VOLET 6)."
        )

    canonique = answer["canonical"]
    objectifs = list(canonique.get("objectives") or [])
    if max_items is not None:
        objectifs = objectifs[:max_items]

    items: List[QuizItem] = []
    echecs: List[Dict[str, str]] = []
    for objectif in objectifs:
        if generator is None:
            continue
        try:
            # Une copie : le générateur ne doit pas pouvoir toucher le fait de
            # l'appelant, et il ne rend que du texte.
            enonce = str(generator({
                "canonical": dict(canonique),
                "objective": objectif,
            }) or "").strip()
        except Exception as erreur:
            echecs.append({"objective": objectif, "error": type(erreur).__name__})
            continue
        if not enonce:
            echecs.append({"objective": objectif, "error": "empty_prompt"})
            continue
        items.append(QuizItem(
            unit_id=answer["unit_id"],
            content_hash=canonique["content_hash"],
            objective=objectif,
            prompt=enonce,
        ))

    return {
        "unit_id": answer["unit_id"],
        "content_hash": canonique["content_hash"],
        "items": [item.as_dict() for item in items],
        "objects": items,
        "official_evaluation_requirements": list(
            canonique.get("evaluation_requirements") or []
        ),
        "official_objectives": list(canonique.get("objectives") or []),
        "generation_failures": echecs,
        "generation_available": generator is not None,
        "note": (
            "Chaque item est accroché à un objectif officiel repris mot pour "
            "mot. Les exigences d'évaluation officielles sont rendues telles "
            "quelles, à côté, et ne sont pas des items générés."
        ),
    }


def check_anchor(item: QuizItem, canonical: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dit si un item porte encore sur l'enregistrement qu'il visait.

    Args:
        item: L'item.
        canonical: Le fait canonique actuel.

    Returns:
        `valid` faux quand l'objectif a disparu du programme ou quand
        l'empreinte a changé — un quiz bâti sur un enregistrement réécrit
        interroge un contenu que l'élève n'a plus.
    """
    objectifs = list(canonical.get("objectives") or [])
    dans_le_programme = item.objective in objectifs
    meme_empreinte = item.content_hash == canonical.get("content_hash")
    return {
        "valid": dans_le_programme and meme_empreinte,
        "objective_still_official": dans_le_programme,
        "content_unchanged": meme_empreinte,
        "reason": (
            "L'item porte sur l'enregistrement en vigueur."
            if dans_le_programme and meme_empreinte else
            "L'enregistrement a changé depuis la construction du quiz : "
            "interroger dessus testerait un contenu que l'élève n'a plus."
        ),
    }


def score_attempt(
    items: Sequence[QuizItem], attempt: Attempt,
) -> Dict[str, Any]:
    """
    Compte ce qu'une clé de correction dit, et **rien d'autre**.

    Args:
        items: Les items du quiz.
        attempt: Ce que l'élève a rendu.

    Returns:
        Le décompte, les items non corrigeables **nommés**, et `grade: None`.
        Une note est une décision institutionnelle : la fabriquer ici serait
        exactement l'invention que la directive interdit.
    """
    corriges: List[Dict[str, Any]] = []
    non_corriges: List[Dict[str, Any]] = []

    for index, item in enumerate(items):
        rendu = attempt.answers.get(index)
        if item.answer_key is None:
            non_corriges.append({
                "index": index, "objective": item.objective,
                "reason": "Aucune clé de correction : compter faux inventerait "
                          "un résultat sur cet élève.",
            })
            continue
        corriges.append({
            "index": index,
            "objective": item.objective,
            "answered": rendu is not None,
            "correct": rendu is not None
            and _replie(rendu) == _replie(item.answer_key),
        })

    justes = sum(1 for entree in corriges if entree["correct"])
    return {
        "status": CORRIGE if corriges else NON_CORRIGE,
        "scored_count": len(corriges),
        "correct_count": justes,
        "unanswered_count": sum(1 for e in corriges if not e["answered"]),
        "not_scored": non_corriges,
        "details": corriges,
        "grade": None,
        "is_official_grade": False,
        "note": (
            "Ceci est un **décompte**, pas une note. Une note est une décision "
            "institutionnelle prise par un enseignant ; la produire ici "
            "fabriquerait un résultat scolaire."
        ),
    }


def evidence_by_objective(
    scoring: Dict[str, Any], minimum: int = PREUVES_MINIMALES,
) -> Dict[str, Any]:
    """
    Dit, objectif par objectif, si la mesure suffit à affirmer quoi que ce soit.

    Args:
        scoring: Le résultat de `score_attempt`.
        minimum: Le nombre d'items corrigés requis. Déclaré, donc contestable.

    Returns:
        Par objectif, le décompte et son verdict de preuve.
        `INSUFFICIENT_EVIDENCE` n'est **pas** une mauvaise note : c'est
        l'absence de mesure, et les confondre ferait porter à un élève le
        résultat d'un quiz trop court.
    """
    par_objectif: Dict[str, Dict[str, Any]] = {}
    for entree in scoring.get("details", []):
        agrege = par_objectif.setdefault(
            entree["objective"], {"scored": 0, "correct": 0},
        )
        agrege["scored"] += 1
        agrege["correct"] += 1 if entree["correct"] else 0

    for agrege in par_objectif.values():
        assez = agrege["scored"] >= minimum
        agrege["verdict"] = PREUVE_SUFFISANTE if assez else PREUVE_INSUFFISANTE
        agrege["reason"] = (
            f"{agrege['scored']} items corrigés (minimum {minimum})."
            if assez else
            f"{agrege['scored']} items corrigés sur {minimum} requis : trop peu "
            "pour affirmer quoi que ce soit. Ce n'est pas un échec, c'est une "
            "absence de mesure."
        )

    return {
        "minimum_items": minimum,
        "by_objective": par_objectif,
        "objectives_measured": [
            objectif for objectif, agrege in par_objectif.items()
            if agrege["verdict"] == PREUVE_SUFFISANTE
        ],
    }


def _replie(valeur: str) -> str:
    """Ramène une réponse à sa forme comparable : sans casse, sans marges."""
    return " ".join(str(valeur or "").casefold().split())


def assessment_report() -> Dict[str, Any]:
    """
    Ce que l'évaluation garantit, et ce qu'elle refuse.

    Returns:
        Les types d'item, les verdicts, et les règles tenues.
    """
    return {
        "item_types": [ITEM_OFFICIEL, ITEM_GENERE],
        "evidence_verdicts": [PREUVE_SUFFISANTE, PREUVE_INSUFFISANTE],
        "minimum_items_per_objective": PREUVES_MINIMALES,
        "rules": [
            "Aucun quiz sans fait canonique : une question inventée est aussi "
            "enseignable qu'une leçon inventée.",
            "Chaque item est accroché à un objectif officiel repris mot pour "
            "mot, et porte l'empreinte de l'enregistrement visé.",
            "Un item sans clé de correction est **nommé** non corrigé : le "
            "compter faux inventerait un résultat sur un élève.",
            "Un décompte n'est pas une note : `grade` vaut toujours `None`.",
            "`INSUFFICIENT_EVIDENCE` est un verdict à part entière, pas un "
            "score bas.",
        ],
        "does_not": [
            "Produire une note, un rang ou une appréciation scolaire.",
            "Générer une question sur un objectif absent du programme officiel.",
            "Compter une absence de réponse comme une erreur sans clé.",
            "Décider qu'un élève maîtrise un objectif sur une seule réponse.",
        ],
    }
