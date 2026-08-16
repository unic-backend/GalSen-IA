"""
Saying what state this actually is in, in the words the directive chose.

Directive L asks for a production-readiness report, and names the answer that
must be given while the register is empty:

    ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING.

This module refuses to say anything stronger. Not as a caution, as a
measurement: `readiness()` counts published versions and official units in a
real register, and there is exactly one state in which it can report the
platform ready to serve curriculum — the one where an authority has provided
data. No argument, flag or override reaches that state without the data.

The failure this closes is small and extremely common. A readiness check that
takes a boolean, or that returns "ready" when its checks pass and its checks
happen to run on fixtures, produces a green report for an empty system. Someone
then reads that report and plans a rollout. The fixtures are marked
`NON_OFFICIAL_TEST_DATA` precisely so that this function can tell them apart,
and it does: a register holding only fixtures is reported as empty of official
data, because it is.

What is genuinely ready is the machinery, and that is worth stating plainly
rather than hedging: the resolution, the refusals, the provenance chain, the
roles and the audit trail all work, are measured, and will not need rewriting
when a ministry hands over a file.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .evaluation import MESURES, MESURES_INDISPONIBLES
from .registry import CurriculumRegistry
from .resilience import probe_curriculum

#: L'état déclaré par la directive tant qu'aucune donnée officielle n'existe.
#: Il est écrit ici une seule fois, et rendu tel quel : le reformuler en
#: « presque prêt » serait précisément la nuance qu'un lecteur pressé retient.
ARCHITECTURE_PRETE = "ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING"

#: L'état atteignable seulement avec des données officielles publiées.
PRET_A_SERVIR = "READY TO SERVE OFFICIAL CURRICULUM"

#: Ce qui doit être vrai pour quitter le premier état. Un seul élément, et il ne
#: dépend pas de nous : c'est le sens même de « GalSen IA n'est pas l'autorité ».
CONDITIONS_DE_SERVICE = (
    "Au moins une version de curriculum publiée par une autorité de rang "
    "TIER_A, provenance vérifiée et non marquée NON_OFFICIAL_TEST_DATA.",
)


def readiness(
    registry: Optional[CurriculumRegistry] = None,
    generator_available: bool = False,
) -> Dict[str, Any]:
    """
    L'état réel, mesuré sur un registre réel.

    Args:
        registry: Le registre à mesurer. Absent, l'état est celui d'un registre
            vide — ce qui est l'état actuel du dépôt.
        generator_available: Si un moteur de génération répond.

    Returns:
        L'état déclaré, ce qui est prêt, ce qui manque, et **qui** doit le
        fournir. Aucun argument ne permet d'atteindre `READY TO SERVE` sans
        données officielles publiées : un rapport vert sur un système vide se
        lit comme un feu vert de déploiement.
    """
    depot = registry or CurriculumRegistry()
    rapport = depot.registry_report()
    officielles = rapport.get("official_versions", 0)
    unites = rapport.get("units", 0)

    pret = officielles > 0
    sonde = probe_curriculum(depot, generator_available=generator_available)

    return {
        "state": PRET_A_SERVIR if pret else ARCHITECTURE_PRETE,
        "official_versions": officielles,
        "units": unites,
        "serving_conditions": list(CONDITIONS_DE_SERVICE),
        "conditions_met": pret,
        "blocked_by": [] if pret else [
            "Aucune version officielle publiée. La fournir n'appartient pas à "
            "cette plateforme : GalSen IA n'est pas l'autorité qui définit le "
            "curriculum.",
        ],
        "capabilities": sonde["capabilities"],
        "capability_state": sonde["state"],
        "ready_now": _ce_qui_est_pret(),
        "measurable_now": list(MESURES),
        "not_measurable_yet": dict(MESURES_INDISPONIBLES),
        "note": (
            "L'état est **mesuré** sur le registre, pas déclaré. Aucun "
            "argument n'atteint « prêt à servir » sans données officielles : un "
            "rapport vert sur un système vide se lit comme un feu vert."
        ),
    }


def _ce_qui_est_pret() -> List[str]:
    """La machinerie qui fonctionne et qui n'aura pas à être réécrite."""
    return [
        "Modèle canonique : identité déterministe, empreinte de contenu "
        "distincte de l'identité, fixtures marquées et refusées comme "
        "officielles.",
        "Registre de versions : append-only, publication exigeant un décideur "
        "nommé, version remplacée conservée en `SUPERSEDED`.",
        "Résolution déterministe : par coordonnées, jamais par similarité, avec "
        "`CLARIFICATION_REQUIRED` quand elles manquent.",
        "Pare-feu : aucune génération sans fait canonique — le modèle n'est pas "
        "appelé, et c'est mesuré.",
        "Cohérence entre usagers : mesurée sur `unit_id:content_hash`.",
        "Ingestion : contrôles de qualité, frontière de confiance, propositions "
        "en `VALIDATION_REQUIRED` — rien ne se publie seul.",
        "Rôles éducatifs, garde à deux verrous et empreintes d'apprenant.",
        "Graphe éducatif dérivé, prérequis pendants nommés, cycles rendus.",
        "Maîtrise avec `INSUFFICIENT_EVIDENCE` hors échelle.",
        "Couche multilingue : la question voyage, l'enregistrement non.",
        "Laboratoire d'évaluation des garanties, et `NOT_MEASURABLE` sans cas.",
        "Piste institutionnelle remontant à la personne qui a publié.",
    ]


def readiness_report(
    registry: Optional[CurriculumRegistry] = None,
) -> Dict[str, Any]:
    """
    Ce que l'aptitude à la production affirme, et ce qu'elle refuse d'affirmer.

    Args:
        registry: Le registre à mesurer, facultatif.

    Returns:
        L'état mesuré et les règles tenues.
    """
    return {
        "states": [ARCHITECTURE_PRETE, PRET_A_SERVIR],
        "measured": readiness(registry),
        "rules": [
            "L'état est mesuré sur le registre : aucun drapeau, aucun argument "
            "ne fait passer un système vide pour prêt.",
            "Un registre ne contenant que des fixtures est un registre sans "
            "données officielles — la marque `NON_OFFICIAL_TEST_DATA` existe "
            "pour que cette fonction puisse les distinguer.",
            "La condition de sortie ne dépend pas de nous : elle demande qu'une "
            "autorité publie. C'est le sens de « GalSen IA n'est pas "
            "l'autorité ».",
            "Ce qui est prêt est dit **plainement** : la machinerie fonctionne, "
            "elle est mesurée, et elle n'aura pas à être réécrite.",
        ],
        "does_not": [
            "Déclarer une intégration du curriculum sénégalais.",
            "Reformuler l'état en « presque prêt ».",
            "Compter une fixture comme une donnée officielle.",
            "Promettre une date que personne ne tient.",
        ],
    }
