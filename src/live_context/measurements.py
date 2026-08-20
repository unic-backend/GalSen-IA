"""
Ce qui est mesuré, et ce qui ne peut pas l'être (L15.1, ADR-033, §33 et §45).

## §33 nomme sept latences. Aucune n'est mesurable ici, et une seule chose l'est

*« Ne jamais prétendre au temps réel sans mesure. »* La conséquence honnête de
cette phrase est que **la colonne des latences live reste vide**, et qu'elle le
dit :

| Mesure demandée | État | Pourquoi |
|---|---|---|
| Latence de capture | `NOT_MEASURED` | aucun périphérique n'existe ici |
| Latence de transcription | `NOT_MEASURED` | `faster_whisper` n'est pas importable |
| Latence d'identification de locuteur | `NOT_MEASURED` | aucune diarisation |
| Latence d'identification de langue | `NOT_MEASURED` | rien n'identifie sur l'audio |
| Latence de lecture d'écran | `NOT_MEASURED` | `DISPLAY` vide |
| Latence de bout en bout | `NOT_MEASURED` | la chaîne ne tourne pas |
| **Coût de la représentation** | **mesuré** | fusion, sondes, décisions |

Le dernier est le seul honnête, et il faut dire précisément ce qu'il est : le
coût de **décider**, pas celui de percevoir. Il ne dit rien de la vitesse d'une
session live et tout du prix que coûte la couche écrite dans ce volet.

## Pourquoi `None` et pas zéro

Une latence non mesurée vaut `None`. Zéro voudrait dire « instantané », ce qui
est une affirmation sur la performance ; `None` dit « personne n'a mesuré », ce
qui est une affirmation sur nous. La distinction est celle que tout le volet
tient depuis `state.py`.

## Ce qu'un chiffre mesuré ici ne prouve pas

Une fusion de dix observations en une fraction de milliseconde ne dit **pas**
que le contexte live est rapide. Elle dit que l'assemblage n'est pas le
goulot — ce qui est utile, et beaucoup moins impressionnant.
"""

from __future__ import annotations

import os
import platform
import time
from typing import Any, Callable, Dict, List

NON_MESURE = "NOT_MEASURED"

#: Les latences que §33 demande et que cette machine ne peut pas produire, avec
#: la raison mesurée de chacune. Écrites une fois, lues par le rapport.
LATENCES_IMPOSSIBLES: Dict[str, str] = {
    "capture_latency_ms": "aucun périphérique de capture n'existe ici",
    "transcription_latency_ms": "aucun moteur de transcription n'est importable",
    "speaker_identification_latency_ms": "aucune diarisation n'existe",
    "language_identification_latency_ms": ("rien n'identifie la langue d'un "
                                           "signal audio"),
    "screen_reading_latency_ms": "aucune session graphique",
    "end_to_end_latency_ms": ("la chaîne de perception ne tourne pas : "
                              "voir `readiness()`"),
}


def _chronometre(operation: Callable[[], Any], repetitions: int = 100) -> float:
    """
    Mesure une opération, en millisecondes par appel.

    Args:
        operation: Ce qui est mesuré.
        repetitions: Le nombre d'appels. Le premier est fait à part, pour ne pas
            mesurer l'import du module en même temps que l'opération.

    Returns:
        La durée moyenne, en millisecondes.
    """
    operation()
    debut = time.perf_counter()
    for _ in range(repetitions):
        operation()
    return round((time.perf_counter() - debut) / repetitions * 1000, 4)


def representation_cost() -> Dict[str, float]:
    """
    Le coût de la couche de représentation, sans aucune perception.

    Returns:
        Une durée par opération, en millisecondes. **C'est le coût de décider,
        pas celui de percevoir** : ces chiffres ne disent rien de la vitesse
        d'une session live.
    """
    from src.creative.reference.consent import ConsentScope

    from .capture import capture_surface, probe
    from .fusion import corroboration, fuse
    from .retention import authorize_act
    from .state import MESURE, LiveContextState, Observation

    def _o(valeur: str, fournisseur: str) -> Observation:
        return Observation(subject="speaker", status=MESURE, modality="audio",
                           value=valeur, provider=fournisseur)

    dix = [_o(f"SPEAKER_{i:02}", f"p{i}") for i in range(10)]
    etat = LiveContextState("mesure").add(*dix)
    accord = ConsentScope(granted_by="Awa Diop", subject="Awa Diop",
                          permitted_uses=("record", "retain", "index"),
                          evidence="mesure")

    return {
        "observation_build_ms": _chronometre(
            lambda: _o("SPEAKER_01", "p1"), 2000),
        "state_add_ms": _chronometre(lambda: etat.add(_o("A", "p")), 1000),
        "conflicts_10_observations_ms": _chronometre(etat.conflicts, 500),
        "corroboration_10_observations_ms": _chronometre(
            lambda: corroboration(etat, "speaker"), 500),
        "fuse_one_stream_ms": _chronometre(
            lambda: fuse("mesure", {"speakers": dix}), 200),
        "probe_one_input_ms": _chronometre(lambda: probe("microphone"), 500),
        "capture_surface_ms": _chronometre(capture_surface, 100),
        "authorize_act_ms": _chronometre(
            lambda: authorize_act("record", accord, modality="audio"), 500),
    }


def live_latencies() -> Dict[str, Any]:
    """
    Les latences que §33 demande, avec l'état réel de chacune.

    Returns:
        Chaque latence à `None` avec sa raison mesurée. **`None`, jamais zéro** :
        zéro affirmerait l'instantanéité.
    """
    return {
        nom: {"value": None, "state": NON_MESURE, "reason": raison}
        for nom, raison in LATENCES_IMPOSSIBLES.items()
    }


def machine() -> Dict[str, Any]:
    """
    La machine sur laquelle ces chiffres ont été pris.

    Returns:
        Le système, la version de Python et le nombre de cœurs. Un chiffre sans
        la machine qui l'a produit ne se compare à rien.
    """
    return {
        "system": platform.system(),
        "release": platform.release(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "measured_at": time.time(),
    }


def realtime_claim() -> Dict[str, Any]:
    """
    Ce que la plateforme a le droit d'affirmer sur le temps réel.

    Returns:
        `is_realtime: None` — ni oui ni non. Répondre « oui » serait la
        prétention que §33 interdit ; répondre « non » affirmerait une mesure
        qui n'a pas eu lieu non plus.
    """
    from .readiness import readiness

    mesure = readiness()
    return {
        "is_realtime": None,
        "state": NON_MESURE,
        "reason": ("Aucune latence de bout en bout n'a été mesurée, parce que "
                   "la chaîne de perception ne tourne pas ici."),
        "readiness_verdict": mesure["state"],
        "what_would_settle_it": [
            "un périphérique de capture et un `LiveCaptureProvider` "
            "implémenté",
            "un moteur de transcription importable",
            "une session mesurée de bout en bout, chronométrée",
        ],
        "note": ("Ni oui ni non : « oui » serait la prétention que §33 "
                 "interdit, « non » affirmerait une mesure qui n'a pas eu "
                 "lieu non plus."),
    }


def measurements_report() -> Dict[str, Any]:
    """
    Tout ce qui est mesurable, et tout ce qui ne l'est pas.

    Returns:
        Les coûts mesurés, les latences absentes avec leurs raisons, la
        machine, et les règles tenues.
    """
    latences = live_latencies()
    return {
        "machine": machine(),
        "representation_cost_ms": representation_cost(),
        "live_latencies": latences,
        "measured_count": len(representation_cost()),
        "not_measured_count": len(latences),
        "realtime": realtime_claim(),
        "rules": [
            "Une latence non mesurée vaut None : zéro affirmerait "
            "l'instantanéité.",
            "Le coût rendu est celui de décider, pas celui de percevoir.",
            "Une fusion rapide ne dit pas que le contexte live est rapide ; "
            "elle dit que l'assemblage n'est pas le goulot.",
            "Aucune prétention au temps réel : ni oui ni non, et ce qui "
            "trancherait est nommé.",
            "Chaque chiffre porte la machine qui l'a produit.",
        ],
    }


def measured_summary() -> List[str]:
    """
    Le résumé en trois lignes, pour un rapport qui n'a pas la place du reste.

    Returns:
        Les phrases, prêtes à être lues telles quelles.
    """
    couts = representation_cost()
    plus_cher = max(couts.items(), key=lambda item: item[1])
    return [
        f"{len(couts)} opérations de représentation mesurées ; la plus chère "
        f"est {plus_cher[0]} à {plus_cher[1]} ms.",
        f"{len(LATENCES_IMPOSSIBLES)} latences de §33 rendues NOT_MEASURED, "
        "chacune avec sa raison.",
        "Aucune prétention au temps réel : la chaîne de perception ne tourne "
        "pas sur cette machine.",
    ]
