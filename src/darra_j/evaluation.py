"""
Measuring the guarantees, because the knowledge is not there yet.

Directive XXXII asks for an evaluation lab. The obvious version of it cannot be
built: a curriculum benchmark needs expected answers, expected answers must come
from the official register, and the register is empty. Writing the expected
answers from model memory would be the exact failure this whole package exists
to prevent — and `docs/evaluation/*.jsonl` already refuses entries written that
way, with zero verified entries and a note saying so.

So this lab measures the other thing, and it measures it today: **the refusals.**

Every guarantee upstream is a behaviour, and behaviours are testable without any
official data. Does the platform generate when there is no record? Does it answer
four roles identically? Does every canonical answer carry provenance? Does it
ever return a grade? Those questions have answers right now, and the answers are
the ones that matter before a ministry hands over a single file.

Two rules keep the numbers honest.

**A rate with no cases is `NOT_MEASURABLE`, never 100 %.** An empty suite that
reports a perfect score is worse than no suite: it manufactures confidence out
of an absence, which is the same move as answering a question with no record.

**A fixture never becomes evidence of correctness on real data.** Cases here are
built on `NON_OFFICIAL_TEST_DATA` fixtures, and the report says so in every
result. What is measured is that the machinery refuses, resolves and reports
correctly — not that the curriculum is right, which nobody can measure yet.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .consistency import COHERENT, check_group, same_coordinates
from .firewall import CANONIQUE, answer
from .registry import TROUVE, CurriculumRegistry
from .resolution import CurriculumQuery

#: L'état d'une mesure sans cas. Un taux calculé sur zéro cas fabriquerait de la
#: confiance à partir d'une absence — le même geste que répondre sans
#: enregistrement.
NON_MESURABLE = "NOT_MEASURABLE"

#: Les mesures que ce laboratoire sait faire **aujourd'hui**, registre vide.
MESURES = (
    "hallucination_rate",
    "refusal_correctness",
    "provenance_coverage",
    "cross_role_consistency",
    "grade_leakage",
)

#: Ce qu'il ne sait pas mesurer, et pourquoi. Une mesure absente doit être
#: nommée : une liste de métriques qui ne montre que le mesurable laisse croire
#: qu'elle est complète.
MESURES_INDISPONIBLES = {
    "curriculum_accuracy": (
        "Demande un jeu de référence officiel. Le registre est vide, et écrire "
        "les réponses attendues depuis la mémoire d'un modèle serait l'invention "
        "que ce paquet entier existe pour empêcher."
    ),
    "explanation_quality": (
        "Demande un modèle et un jugement humain. Interroger le modèle sur la "
        "qualité de sa propre explication ne mesurerait que sa confiance en lui."
    ),
    "learning_outcome": (
        "Demande une cohorte réelle et du temps. Aucune mesure de laboratoire "
        "ne peut en tenir lieu."
    ),
}


def _taux(reussis: int, total: int) -> Dict[str, Any]:
    """Un taux, ou `NOT_MEASURABLE` quand il n'y a rien à diviser."""
    if total <= 0:
        return {
            "status": NON_MESURABLE, "rate": None, "passed": 0, "cases": 0,
            "reason": (
                "Aucun cas. Un taux calculé sur zéro cas fabriquerait de la "
                "confiance à partir d'une absence."
            ),
        }
    return {
        "status": "MEASURED", "rate": round(reussis / total, 4),
        "passed": reussis, "cases": total,
    }


def measure_hallucination(
    cases: Sequence[CurriculumQuery],
    registry: CurriculumRegistry,
) -> Dict[str, Any]:
    """
    Compte les réponses produites **sans** enregistrement canonique.

    Args:
        cases: Des questions dont aucune ne doit aboutir.
        registry: Le registre, typiquement vide ou non publié.

    Returns:
        Le taux d'hallucination. Il doit valoir 0 : le pare-feu n'appelle pas
        le modèle quand il n'y a rien à expliquer, et cette mesure le vérifie
        au lieu de le supposer.
    """
    appels: List[str] = []

    def _generateur(contexte: Dict[str, Any]) -> str:
        appels.append(contexte.get("canonical", {}).get("official_title", ""))
        return "Une explication qui n'aurait pas dû être demandée."

    fabriquees = 0
    for question in cases:
        reponse = answer(question, registry, explain=_generateur)
        if reponse.get("canonical") is not None or reponse.get("explanation"):
            fabriquees += 1

    resultat = _taux(len(cases) - fabriquees, len(cases))
    resultat.update({
        "fabricated": fabriquees,
        "generator_calls": len(appels),
        "note": (
            "Le générateur est instrumenté : on mesure qu'il n'est **pas "
            "appelé**, pas seulement que sa sortie est étiquetée."
        ),
    })
    return resultat


def measure_refusals(
    cases: Sequence[Dict[str, Any]], registry: CurriculumRegistry,
) -> Dict[str, Any]:
    """
    Vérifie que chaque refus est celui qui était attendu.

    Args:
        cases: Des dictionnaires `{"query": ..., "expected": <answer_type>}`.
        registry: Le registre.

    Returns:
        Le taux de refus corrects, et **quels cas** ont divergé. Un taux sans
        la liste des écarts ne se corrige pas.
    """
    ecarts: List[Dict[str, Any]] = []
    justes = 0

    for cas in cases:
        reponse = answer(cas["query"], registry)
        obtenu = reponse.get("answer_type")
        if obtenu == cas["expected"]:
            justes += 1
        else:
            ecarts.append({
                "expected": cas["expected"], "got": obtenu,
                "reason": reponse.get("reason", ""),
            })

    resultat = _taux(justes, len(cases))
    resultat["mismatches"] = ecarts
    return resultat


def measure_provenance(
    cases: Sequence[CurriculumQuery], registry: CurriculumRegistry,
) -> Dict[str, Any]:
    """
    Vérifie qu'aucune réponse canonique ne sort sans sa provenance.

    Args:
        cases: Des questions dont on attend des réponses canoniques.
        registry: Le registre.

    Returns:
        Le taux de couverture, et les réponses canoniques sans autorité. Une
        seule suffit à casser la garantie : un fait sans origine est un fait que
        personne ne peut contester.
    """
    sans_provenance: List[str] = []
    canoniques = 0

    for question in cases:
        reponse = answer(question, registry)
        if reponse.get("answer_type") != CANONIQUE:
            continue
        canoniques += 1
        provenance = reponse.get("provenance") or {}
        if provenance.get("status") != TROUVE or not provenance.get("authority"):
            sans_provenance.append(reponse.get("unit_id", "?"))

    resultat = _taux(canoniques - len(sans_provenance), canoniques)
    resultat["without_provenance"] = sans_provenance
    return resultat


def measure_consistency(
    coordinates: Sequence[Dict[str, Any]], registry: CurriculumRegistry,
) -> Dict[str, Any]:
    """
    Mesure la garantie de la directive VI sur un jeu de coordonnées.

    Args:
        coordinates: Des dictionnaires acceptés par `same_coordinates`.
        registry: Le registre.

    Returns:
        Le taux de groupes cohérents, et les groupes qui ne le sont pas.
    """
    incoherents: List[Dict[str, Any]] = []
    coherents = 0

    for jeu in coordinates:
        verdict = check_group(same_coordinates(**jeu), registry)
        if verdict["verdict"] == COHERENT:
            coherents += 1
        else:
            incoherents.append({"coordinates": jeu,
                                "diverging": verdict.get("diverging", [])})

    resultat = _taux(coherents, len(coordinates))
    resultat["inconsistent_groups"] = incoherents
    return resultat


def measure_grade_leakage(
    outputs: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Vérifie qu'aucune sortie ne porte une note.

    Args:
        outputs: Les sorties à examiner — vues élève, parent, corrections.

    Returns:
        Le taux de sorties propres, et celles qui portent une note. La
        vérification est **positive** : une note absente doit valoir `None`, pas
        manquer, car une clé manquante se lit comme « pas encore implémenté ».
    """
    fuites: List[Dict[str, Any]] = []
    for index, sortie in enumerate(outputs):
        portees = {
            cle: sortie[cle] for cle in ("grade", "rank", "appraisal")
            if sortie.get(cle) is not None
        }
        if portees:
            fuites.append({"index": index, "fields": portees})

    resultat = _taux(len(outputs) - len(fuites), len(outputs))
    resultat["leaks"] = fuites
    return resultat


def run_lab(
    registry: CurriculumRegistry,
    empty_cases: Optional[Sequence[CurriculumQuery]] = None,
    refusal_cases: Optional[Sequence[Dict[str, Any]]] = None,
    canonical_cases: Optional[Sequence[CurriculumQuery]] = None,
    consistency_cases: Optional[Sequence[Dict[str, Any]]] = None,
    outputs: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Exécute les mesures disponibles et rapporte ce qui ne l'est pas.

    Args:
        registry: Le registre à mesurer.
        empty_cases: Questions sans enregistrement attendu.
        refusal_cases: Questions avec le refus attendu.
        canonical_cases: Questions avec une réponse canonique attendue.
        consistency_cases: Coordonnées à poser sous quatre rôles.
        outputs: Sorties à examiner pour une fuite de note.

    Returns:
        Chaque mesure avec son état, et **la liste de ce qui n'est pas
        mesurable** avec la raison. Une liste de métriques qui ne montre que le
        mesurable laisse croire qu'elle est complète.
    """
    return {
        "hallucination_rate": measure_hallucination(empty_cases or [], registry),
        "refusal_correctness": measure_refusals(refusal_cases or [], registry),
        "provenance_coverage": measure_provenance(canonical_cases or [], registry),
        "cross_role_consistency": measure_consistency(
            consistency_cases or [], registry,
        ),
        "grade_leakage": measure_grade_leakage(outputs or []),
        "unavailable": dict(MESURES_INDISPONIBLES),
        "data_basis": "NON_OFFICIAL_TEST_DATA",
        "note": (
            "Ce laboratoire mesure les **garanties**, pas la connaissance : le "
            "registre est vide et écrire les réponses attendues depuis la "
            "mémoire d'un modèle serait l'invention que ce paquet existe pour "
            "empêcher. Ce qui est mesuré ici l'est sur des fixtures marquées "
            "`NON_OFFICIAL_TEST_DATA`."
        ),
    }


def evaluation_report() -> Dict[str, Any]:
    """
    Ce que le laboratoire mesure, et ce qu'il refuse de mesurer.

    Returns:
        Les mesures disponibles, les indisponibles avec leur raison, et les
        règles tenues.
    """
    return {
        "available": list(MESURES),
        "unavailable": dict(MESURES_INDISPONIBLES),
        "rules": [
            "Un taux sans cas est `NOT_MEASURABLE`, jamais 100 % : une suite "
            "vide qui affiche un score parfait fabrique de la confiance à "
            "partir d'une absence.",
            "L'hallucination se mesure sur un générateur **instrumenté** : on "
            "vérifie qu'il n'est pas appelé, pas que sa sortie est étiquetée.",
            "Un taux est rendu avec la liste de ses écarts — un taux seul ne se "
            "corrige pas.",
            "Ce qui est mesuré l'est sur des fixtures `NON_OFFICIAL_TEST_DATA` "
            "et le rapport le dit à chaque exécution.",
            "Les mesures indisponibles sont **nommées** avec leur raison : une "
            "liste qui ne montre que le mesurable se lit comme complète.",
        ],
        "does_not": [
            "Écrire des réponses attendues depuis la mémoire d'un modèle.",
            "Mesurer la justesse d'un curriculum que personne n'a fourni.",
            "Demander à un modèle s'il a bien répondu.",
            "Rendre un score sur zéro cas.",
        ],
    }
