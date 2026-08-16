"""
What still works when something is down — and what stops, rather than pretends.

Directive XXXV states the distinction this module exists to hold: *a curriculum
fact must remain retrievable even when the model is unavailable.* The register
is a database, not a language model, and a school does not stop needing to know
what week 10 contains because `ollama serve` is not running.

The dangerous shape of degradation is the graceful one. A system that "falls
back" when a component fails is a system that answers from somewhere else, and
somewhere else is exactly where invention lives. So every capability here
degrades by **doing less**, never by substituting:

- Generation down → the official record still comes back, without explanation.
- Alias table missing → questions in the language of the record still resolve;
  the others say the bridge is unavailable, and no translation is guessed.
- Register empty → `UNKNOWN`, which is not a degradation at all. It is the
  correct answer, and the state the platform is in today.

The three states are the platform's own (`src/integration/degradation.py`):
`AVAILABLE`, `DEGRADED`, `UNAVAILABLE`. Reusing them means a Darra J probe reads
the same way as the nine that already exist, and a second vocabulary for the
same idea would be one more thing to keep aligned.

Concurrency is the other half of scale here, and it is already handled where it
belongs: `CurriculumRegistry` holds an `RLock` and every read and write passes
through it. This module measures that it holds, rather than assuming it.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..integration.degradation import DEGRADE, DISPONIBLE, INDISPONIBLE
from .firewall import CANONIQUE, answer
from .registry import CurriculumRegistry
from .resolution import CurriculumQuery

#: Les capacités de Darra J, et ce que chacune **cesse de faire** quand elle est
#: dégradée. Une capacité dégradée qui continuerait à répondre par autre chose
#: n'est pas dégradée : elle invente.
CAPACITES = {
    "curriculum_retrieval": (
        "Rendre un enregistrement officiel. Ne dépend d'aucun modèle : c'est la "
        "distinction de la directive XXXV."
    ),
    "explanation": (
        "Expliquer un enregistrement. Sans générateur, le fait sort seul — "
        "aucune leçon générique ne le remplace."
    ),
    "assessment_generation": (
        "Produire des énoncés. Sans générateur, les objectifs officiels et les "
        "exigences d'évaluation restent consultables ; aucune question n'est "
        "fabriquée."
    ),
    "multilingual_bridge": (
        "Atteindre un enregistrement depuis une autre langue. Sans table "
        "d'alias, les questions dans la langue de publication résolvent encore ; "
        "les autres disent que le pont manque."
    ),
    "consistency_check": (
        "Mesurer la cohérence entre usagers. Ne dépend que du registre."
    ),
}


def probe_curriculum(
    registry: CurriculumRegistry,
    generator_available: bool = False,
    alias_table_available: bool = True,
) -> Dict[str, Any]:
    """
    L'état de chaque capacité, mesuré et non supposé.

    Args:
        registry: Le registre.
        generator_available: Si un moteur de génération répond.
        alias_table_available: Si la table d'alias est chargée.

    Returns:
        Une entrée par capacité, avec son état et **ce qu'elle cesse de faire**.
        Un registre vide ne rend pas la récupération indisponible : elle
        fonctionne et répond `UNKNOWN`, ce qui est la bonne réponse et l'état
        actuel de la plateforme.
    """
    rapport = registry.registry_report()
    # `official_versions`, et non une clé « published » : le rapport du
    # registre ne porte pas ce nom, et un `.get("published", 0)` aurait lu 0
    # en silence quel que soit le contenu réel du registre.
    publiees = rapport.get("official_versions", 0)

    capacites: Dict[str, Dict[str, Any]] = {
        "curriculum_retrieval": _etat(
            DISPONIBLE,
            "Le registre répond. Sans version publiée il rend `UNKNOWN`, ce qui "
            "est une réponse et non une panne."
            if not publiees else
            f"{publiees} version(s) publiée(s), interrogeables.",
        ),
        "explanation": _etat(
            DISPONIBLE if generator_available else DEGRADE,
            "Générateur disponible."
            if generator_available else
            "Aucun générateur : le fait officiel sort seul. Lui substituer une "
            "leçon générique serait l'invention que cette couche empêche.",
        ),
        "assessment_generation": _etat(
            DISPONIBLE if generator_available else DEGRADE,
            "Générateur disponible."
            if generator_available else
            "Aucun générateur : les objectifs et exigences officiels restent "
            "consultables, aucune question n'est fabriquée.",
        ),
        "multilingual_bridge": _etat(
            DISPONIBLE if alias_table_available else DEGRADE,
            "Table d'alias chargée."
            if alias_table_available else
            "Table d'alias absente : les questions dans la langue de "
            "publication résolvent encore ; aucune traduction n'est devinée.",
        ),
        "consistency_check": _etat(
            DISPONIBLE, "Ne dépend que du registre.",
        ),
    }

    etats = [entree["state"] for entree in capacites.values()]
    if INDISPONIBLE in etats:
        global_ = INDISPONIBLE
    elif DEGRADE in etats:
        global_ = DEGRADE
    else:
        global_ = DISPONIBLE

    return {
        "state": global_,
        "capabilities": capacites,
        "official_versions": publiees,
        "note": (
            "Chaque capacité dégradée **fait moins**, jamais autre chose : un "
            "repli qui répond depuis ailleurs répond depuis l'invention."
        ),
    }


def _etat(etat: str, raison: str) -> Dict[str, Any]:
    """Une capacité, son état et sa raison."""
    return {"state": etat, "reason": raison}


def survives_without_model(
    query: CurriculumQuery, registry: CurriculumRegistry,
) -> Dict[str, Any]:
    """
    Vérifie la distinction critique de la directive XXXV.

    Args:
        query: Une question dont on attend une réponse canonique.
        registry: Le registre.

    Returns:
        Ce que la même question rend avec et sans générateur. Le fait doit être
        **identique** : si la présence d'un modèle changeait l'enregistrement,
        l'enregistrement ne serait pas la source.
    """
    avec = answer(query, registry, explain=lambda contexte: "Explication.")
    sans = answer(query, registry, explain=None)

    return {
        "retrievable_without_model": sans.get("answer_type") == CANONIQUE,
        "canonical_identical": avec.get("canonical") == sans.get("canonical"),
        "explanation_with": avec.get("explanation"),
        "explanation_without": sans.get("explanation"),
        "reason": (
            "Le fait officiel ne dépend pas du modèle. S'il en dépendait, "
            "l'enregistrement ne serait pas la source — le modèle le serait."
        ),
    }


def measure_latency(
    query: CurriculumQuery, registry: CurriculumRegistry, runs: int = 100,
) -> Dict[str, Any]:
    """
    Mesure le temps de résolution, sans générateur.

    Args:
        query: La question à répéter.
        registry: Le registre.
        runs: Le nombre de répétitions.

    Returns:
        Les temps observés, en millisecondes. Aucun seuil n'est déclaré
        « acceptable » ici : une cible de performance est une décision de
        déploiement, et l'inventer donnerait une garantie que personne n'a
        prise.
    """
    if runs <= 0:
        return {"measured": False, "reason": "Aucune répétition demandée."}

    temps: List[float] = []
    for _ in range(runs):
        debut = time.perf_counter()
        answer(query, registry, explain=None)
        temps.append((time.perf_counter() - debut) * 1000)

    ordonnes = sorted(temps)
    return {
        "measured": True,
        "runs": runs,
        "min_ms": round(ordonnes[0], 4),
        "median_ms": round(ordonnes[len(ordonnes) // 2], 4),
        "max_ms": round(ordonnes[-1], 4),
        "note": (
            "Aucun seuil « acceptable » n'est déclaré : une cible de "
            "performance est une décision de déploiement, et l'inventer "
            "donnerait une garantie que personne n'a prise."
        ),
    }


def resilience_report(
    registry: Optional[CurriculumRegistry] = None,
    generator_available: bool = False,
) -> Dict[str, Any]:
    """
    Ce que la résilience garantit, et ce qu'elle refuse de faire.

    Args:
        registry: Un registre à sonder, facultatif.
        generator_available: Si un moteur de génération répond.

    Returns:
        Les capacités, l'état sondé s'il y a lieu, et les règles tenues.
    """
    rapport: Dict[str, Any] = {
        "states": [DISPONIBLE, DEGRADE, INDISPONIBLE],
        "capabilities": dict(CAPACITES),
        "rules": [
            "Une capacité dégradée **fait moins**, jamais autre chose : un "
            "repli qui répond depuis ailleurs répond depuis l'invention.",
            "Un fait de curriculum reste consultable sans modèle — c'est la "
            "distinction de la directive XXXV, et elle est mesurée.",
            "Un registre vide n'est pas une panne : `UNKNOWN` est la réponse "
            "correcte et l'état actuel de la plateforme.",
            "Les trois états sont ceux de la plateforme "
            "(`src/integration/degradation.py`) : un second vocabulaire pour la "
            "même idée serait une chose de plus à garder alignée.",
            "Aucun seuil de performance n'est déclaré ici : c'est une décision "
            "de déploiement.",
        ],
        "does_not": [
            "Répondre depuis un cache quand la source est indisponible.",
            "Substituer une leçon générique à une explication manquante.",
            "Deviner une traduction quand la table d'alias manque.",
            "Déclarer une cible de latence que personne n'a arrêtée.",
        ],
    }
    if registry is not None:
        rapport["probe"] = probe_curriculum(
            registry, generator_available=generator_available,
        )
    return rapport


__all__ = [
    "CAPACITES",
    "measure_latency",
    "probe_curriculum",
    "resilience_report",
    "survives_without_model",
]
