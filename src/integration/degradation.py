"""
What still works when something is missing — measured, not promised.

`EngineRegistry` already isolates the fourteen engines of the early volets: one
that cannot be built is recorded as unavailable and never propagates its
exception. That guarantee was never extended to anything built afterwards. By
VOLET 64 the platform carries ten more subsystems — routines, checkpoints,
delivery channels, world knowledge, routing, plugins, memory layers, the
sandbox, the source registry, orchestration — and none of them appeared in any
availability report. An operator could read a healthy platform while half of it
was unusable.

This module probes them, and the probing itself follows the rule it is
measuring: **a subsystem that fails while being probed is reported, never
propagated.** A degradation report that can be taken down by the thing it
observes would be the exact failure it exists to prevent.

Three states, and the middle one is the point:

- `AVAILABLE` — it answered, and it has what it needs.
- `DEGRADED` — it answered, and it says what it is missing. The platform keeps
  working; that subsystem does less. This is not a failure and must not be
  reported as one.
- `UNAVAILABLE` — the probe raised. The exception is carried as the reason.

Every subsystem also carries **what still works without it**, because
"degraded" alone tells an operator nothing about whether to act tonight or on
Monday.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

#: Les trois états d'un sous-système.
DISPONIBLE = "AVAILABLE"
DEGRADE = "DEGRADED"
INDISPONIBLE = "UNAVAILABLE"

_journal = logging.getLogger(__name__)


def _sonde_routines() -> Dict[str, Any]:
    """Le moteur de routines : déclarées, actives, et de quoi il dépend."""
    from ..routines import RoutineRegistry

    comptes = RoutineRegistry().counts()

    # La dépendance mesurée est celle du planificateur réel : le moteur
    # d'outils, pris au registre partagé. Construire ici un planificateur neuf
    # pour l'interroger mesurerait un objet que personne n'utilise, et
    # rapporterait « dégradé » sur une plateforme qui va très bien.
    from .engine_registry import get_shared_registry

    if get_shared_registry().try_get("tool") is None:
        return {
            "state": DEGRADE,
            "reason": (
                "Moteur d'outils indisponible : une routine rapporterait son "
                "indisponibilité au lieu d'agir."
            ),
            "detail": comptes,
        }
    return {"state": DISPONIBLE, "detail": comptes}


def _sonde_points_de_reprise() -> Dict[str, Any]:
    """Les points de reprise des workflows longs."""
    from ..router.workflow_checkpoint import EXECUTIONS_CONSERVEES, WorkflowCheckpoints

    rapport = WorkflowCheckpoints().checkpoint_report()
    return {
        "state": DISPONIBLE,
        "detail": {
            "runs_kept": EXECUTIONS_CONSERVEES,
            "runs": rapport["runs"],
            "resumable": len(rapport["resumable"]),
        },
    }


def _sonde_canaux() -> Dict[str, Any]:
    """Les canaux de livraison des notifications."""
    from ..services.notification.channels import ChannelRegistry

    rapport = ChannelRegistry().channels_report()
    if not rapport["channels"]:
        return {
            "state": DEGRADE,
            "reason": rapport.get("declaration") or "Aucun canal déclaré.",
            "detail": {"channels": 0},
        }
    if not rapport["available"]:
        return {
            "state": DEGRADE,
            "reason": (
                f"{len(rapport['not_configured'])} canaux déclarés, aucun "
                "configuré : rien ne peut partir vers l'extérieur, et rien ne "
                "prétend le contraire."
            ),
            "detail": {"channels": len(rapport["channels"])},
        }
    return {"state": DISPONIBLE, "detail": {"available": len(rapport["available"])}}


def _sonde_connaissance_mondiale() -> Dict[str, Any]:
    """La référence mondiale dérivée."""
    from ..knowledge_engine.world import load_world

    monde = load_world()
    if not monde.get("built", True):
        return {
            "state": DEGRADE,
            "reason": monde.get("reason", "Jamais construite."),
            "detail": {"countries": 0},
        }
    return {
        "state": DISPONIBLE,
        "detail": {"countries": len(monde.get("countries") or [])},
    }


def _sonde_routage() -> Dict[str, Any]:
    """Le routage entre profondeur sénégalaise et largeur mondiale."""
    from ..knowledge_engine.routing import COUCHE_SENEGAL, layer_comparison

    couches = layer_comparison()
    if not couches[COUCHE_SENEGAL].get("available"):
        return {
            "state": DEGRADE,
            "reason": (
                "La couche sénégalaise ne répond pas : les questions "
                "nationales resteront UNKNOWN, et la référence mondiale n'est "
                "pas un repli pour elles."
            ),
            "detail": {},
        }
    return {
        "state": DISPONIBLE,
        "detail": {"departments": couches[COUCHE_SENEGAL].get("departments", 0)},
    }


def _sonde_greffons() -> Dict[str, Any]:
    """Les greffons installés, et le bac à sable qui les exécute."""
    from ..plugins.registry import PluginRegistry, discover
    from ..sandbox import describe

    trouve = discover(PluginRegistry())
    bac = describe()
    if not bac.get("available"):
        return {
            "state": DEGRADE,
            "reason": (
                f"Bac à sable indisponible ({bac.get('reason')}) : aucun "
                "greffon ne peut être exécuté. L'installation reste possible, "
                "l'exécution non."
            ),
            "detail": {"installed": len(trouve["installed"])},
        }
    return {
        "state": DISPONIBLE,
        "detail": {
            "installed": len(trouve["installed"]),
            "refused": len(trouve["refused"]),
        },
    }


def _sonde_couches_de_memoire() -> Dict[str, Any]:
    """Les couches de mémoire et leurs durées de vie."""
    from ..memory_engine.layers import COUCHES, layers_report

    layers_report()
    return {"state": DISPONIBLE, "detail": {"layers": len(COUCHES)}}


def _sonde_registre_de_sources() -> Dict[str, Any]:
    """Le registre des sources déclarées."""
    from ..knowledge_engine.source_registry import registry_report

    rapport = registry_report()
    if not rapport.get("sources"):
        return {
            "state": DEGRADE,
            "reason": "Aucune source déclarée : rien ne peut être acquis.",
            "detail": {"sources": 0},
        }
    return {
        "state": DISPONIBLE,
        "detail": {
            "sources": rapport["sources"],
            "enabled": rapport.get("enabled", 0),
        },
    }


def _sonde_orchestration() -> Dict[str, Any]:
    """Les deux chemins d'entrée de l'orchestrateur."""
    from ..router.orchestration_paths import orchestration_paths
    from ..router.workflow_loader import WorkflowLoader
    from ..router.agent_loader import AgentLoader
    import os

    racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    chargeur = WorkflowLoader(os.path.join(racine, "workflows", "workflows.yaml"))
    chargeur.validate(
        AgentLoader(os.path.join(racine, "agents", "registry.yaml")).get_all_agents().keys(),
        journaliser=False,
    )
    mesures = orchestration_paths(workflow_loader=chargeur)["measured"]
    if not mesures["workflows_executable"]:
        return {
            "state": DEGRADE,
            "reason": "Aucun workflow exécutable : toute demande serait refusée.",
            "detail": mesures,
        }
    return {"state": DISPONIBLE, "detail": mesures}


#: Les sous-systèmes construits après le registre des moteurs, et ce qui
#: continue de fonctionner sans chacun. « Dégradé » seul ne dit pas à un
#: exploitant s'il doit agir ce soir ou lundi.
SOUS_SYSTEMES: Dict[str, Dict[str, Any]] = {
    "routines": {
        "volet": 47,
        "probe": _sonde_routines,
        "still_works_without": (
            "Tout le reste : les routines sont du travail répété, aucune "
            "requête n'en dépend."
        ),
    },
    "workflow_checkpoints": {
        "volet": 49,
        "probe": _sonde_points_de_reprise,
        "still_works_without": (
            "Les workflows tournent ; une exécution interrompue devrait être "
            "relancée depuis le début."
        ),
    },
    "notification_channels": {
        "volet": 50,
        "probe": _sonde_canaux,
        "still_works_without": (
            "Tout, sauf prévenir quelqu'un au-dehors. Les événements restent "
            "dans l'audit."
        ),
    },
    "world_knowledge": {
        "volet": 52,
        "probe": _sonde_connaissance_mondiale,
        "still_works_without": (
            "La couche sénégalaise répond toujours ; les questions mondiales "
            "rendent UNKNOWN au lieu du moins mauvais fragment."
        ),
    },
    "knowledge_routing": {
        "volet": 57,
        "probe": _sonde_routage,
        "still_works_without": (
            "Chaque couche reste interrogeable directement ; c'est le choix "
            "automatique entre elles qui manque."
        ),
    },
    "plugins": {
        "volet": 58,
        "probe": _sonde_greffons,
        "still_works_without": (
            "La plateforme entière : un greffon est une extension par un "
            "tiers, rien du cœur n'en dépend."
        ),
    },
    "memory_layers": {
        "volet": 60,
        "probe": _sonde_couches_de_memoire,
        "still_works_without": (
            "La mémoire s'écrit et se lit ; les durées de vie ne seraient plus "
            "appliquées."
        ),
    },
    "source_registry": {
        "volet": 51,
        "probe": _sonde_registre_de_sources,
        "still_works_without": (
            "La connaissance déjà acquise reste lisible ; plus rien de nouveau "
            "ne peut entrer."
        ),
    },
    "orchestration": {
        "volet": 64,
        "probe": _sonde_orchestration,
        "still_works_without": (
            "Rien de ce qui passe par des agents. C'est le seul sous-système "
            "de cette liste dont l'absence arrête le travail principal."
        ),
    },
}


def probe(name: str) -> Dict[str, Any]:
    """
    Interroge un sous-système, sans jamais se laisser renverser par lui.

    Args:
        name: Le sous-système, tel que déclaré dans `SOUS_SYSTEMES`.

    Returns:
        Son état, la raison quand il y en a une, et ce qui fonctionne sans lui.

    Raises:
        KeyError: Si le sous-système n'est pas déclaré. Deviner serait pire :
            un nom mal écrit rendrait « disponible » pour toujours.
    """
    declare = SOUS_SYSTEMES[name]
    try:
        resultat = declare["probe"]()
    except Exception as erreur:
        # La sonde qui tombe est **le** cas que ce module existe pour tenir :
        # un rapport de dégradation renversé par ce qu'il observe serait
        # exactement la panne qu'il doit empêcher.
        _journal.warning("Sonde '%s' en échec : %s", name, erreur)
        resultat = {
            "state": INDISPONIBLE,
            "reason": f"{type(erreur).__name__}: {erreur}",
            "detail": {},
        }

    return {
        "subsystem": name,
        "volet": declare["volet"],
        "state": resultat["state"],
        "reason": resultat.get("reason"),
        "detail": resultat.get("detail", {}),
        "still_works_without": declare["still_works_without"],
    }


def degradation_report(names: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    L'état de tous les sous-systèmes construits après le registre des moteurs.

    Args:
        names: Les sous-systèmes à interroger. Tous par défaut.

    Returns:
        Chaque sous-système, le décompte par état, et les règles tenues.
    """
    demandes = names if names is not None else list(SOUS_SYSTEMES)
    etats = [probe(nom) for nom in demandes]

    return {
        "subsystems": {etat["subsystem"]: etat for etat in etats},
        "counts": {
            DISPONIBLE: sum(1 for e in etats if e["state"] == DISPONIBLE),
            DEGRADE: sum(1 for e in etats if e["state"] == DEGRADE),
            INDISPONIBLE: sum(1 for e in etats if e["state"] == INDISPONIBLE),
        },
        "degraded": [e["subsystem"] for e in etats if e["state"] == DEGRADE],
        "unavailable": [e["subsystem"] for e in etats if e["state"] == INDISPONIBLE],
        "rules": [
            "Un sous-système absent n'en fait tomber aucun autre : chaque "
            "sonde est isolée, et celle qui lève est rapportée, pas propagée.",
            "**Dégradé n'est pas en panne.** Un sous-système qui dit ce qui lui "
            "manque fonctionne comme prévu ; le compter comme une panne "
            "déclencherait des alertes que personne ne lirait plus.",
            "Chaque état dit **ce qui fonctionne encore sans lui** : « dégradé "
            "» seul ne dit pas s'il faut agir ce soir ou lundi.",
        ],
        "does_not": [
            "Réparer quoi que ce soit : ce module observe, il n'agit pas.",
            "Construire un sous-système pour le mesurer : une sonde qui "
            "réveillerait ce qu'elle observe changerait ce qu'elle mesure.",
        ],
    }


def probes() -> List[Callable[[], Dict[str, Any]]]:
    """Les sondes déclarées, dans l'ordre du registre."""
    return [declare["probe"] for declare in SOUS_SYSTEMES.values()]
