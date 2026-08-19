"""
Les cinq interfaces du §31, auxquelles une seule est ajoutée
(L13.1, ADR-033 décision 5, §31 à §34 de la directive Live Context).

## Pourquoi une seule

§31 propose cinq interfaces de fournisseur. **Quatre en dupliquent une qui
existe** — ADR-032 avait dû défendre l'ajout d'une quatrième déclaration dans le
programme de recherche, et une cinquième demandait au moins autant.

| §31 propose | Décision |
|---|---|
| `RealtimeTranscriptionProvider` | **réutiliser** `multimodal.TranscriptionProvider` |
| `MediaContextProvider` | **réutiliser** `media/providers/` |
| `RealtimeContextProvider` | **n'est pas un fournisseur** — c'est le moteur |
| `ScreenUnderstandingProvider` | **différé**, et borné par ADR-018 |
| `LiveCaptureProvider` | **nouveau** — rien n'abstrait un périphérique de capture |

Seule la capture avait l'argument : aucun module de ce dépôt ne représente un
microphone, une caméra ou un écran comme une source qu'on interroge.

## Un fournisseur déclaré n'est pas un fournisseur disponible

C'est la règle que `research/providers.py` tient déjà et qui est reprise
telle quelle : une déclaration dit ce qu'un fournisseur *prétend* savoir faire,
et `health()` mesure ce qu'il peut faire **ici**. Les deux ne se confondent
jamais, et aucun des deux ne se déduit de l'autre.

Ici, la mesure est sévère et le restera : **aucun fournisseur de capture n'est
disponible sur cette machine**, parce qu'aucun périphérique n'existe. Un
fournisseur `BLOCKED` dit ce qui lui manque ; il ne rend pas un flux vide.

## Le mode dégradé n'est pas un repli silencieux

§34 demande un fonctionnement dégradé. Dégradé veut dire **moins de modalités,
dites comme telles** — jamais « ça marche » avec la moitié des entrées
manquantes. `degraded_mode()` nomme ce qui est perdu et ce qui reste, et ne
rend aucun booléen global.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .capture import ENTREES, module_present, probe
from .state import MESURE

#: Les capacités qu'un fournisseur de capture peut déclarer. Elles reprennent
#: les entrées de §7 : une capacité qui ne correspond à aucune entrée serait
#: routée vers quelque chose que rien ne sonde.
CAPACITES = tuple(ENTREES)

#: Comment un fournisseur tourne. Repris de `research/providers.py` : deux
#: vocabulaires pour la même idée finiraient par diverger.
DANS_LE_PROCESSUS = "IN_PROCESS"
SOUS_PROCESSUS = "SUBPROCESS"
SERVICE_HEBERGE = "HOSTED_SERVICE"
MODES_D_EXECUTION = (DANS_LE_PROCESSUS, SOUS_PROCESSUS, SERVICE_HEBERGE)

#: L'état mesuré d'un fournisseur.
DISPONIBLE = "AVAILABLE"
BLOQUE = "BLOCKED"
REFUSE = "REFUSED"
ETATS = (DISPONIBLE, BLOQUE, REFUSE)

#: Les interfaces du §31 qui sont servies par quelque chose d'existant, et par
#: quoi. Écrit ici pour qu'une relecture n'ajoute pas la cinquième déclaration
#: en croyant qu'elle manquait.
INTERFACES_REUTILISEES: Dict[str, str] = {
    "RealtimeTranscriptionProvider": "multimodal.TranscriptionProvider",
    "MediaContextProvider": "media/providers/ et le registre créatif",
    "RealtimeContextProvider": "n'est pas un fournisseur : c'est le moteur",
    "ScreenUnderstandingProvider": ("différé, et borné par ADR-018 — une "
                                    "capture d'écran ne quitte pas la machine"),
}


class LiveProviderRefused(ValueError):
    """Une déclaration de fournisseur impossible telle quelle."""


@dataclass(frozen=True)
class LiveCaptureProvider:
    """
    Ce qu'un fournisseur de capture déclare de lui-même.

    Attributes:
        provider_id: Son identifiant.
        capabilities: Les entrées de §7 qu'il prétend servir.
        execution: Comment il tourne, parmi `MODES_D_EXECUTION`.
        python_module: Le module à importer quand il est `IN_PROCESS`.
        requires: Ce qu'il faut hors Python — un périphérique, un service.
        sends_data_off_host: **Déclaré, jamais deviné.** Un fournisseur qui
            envoie hors de la machine est refusé pour l'écran, quoi qu'il
            promette par ailleurs (ADR-018).
        typical_latency_ms: `None` = **jamais mesuré**, jamais « rapide ».
        limitations: Ce qu'il ne sait pas faire, en clair.
    """

    provider_id: str
    capabilities: Tuple[str, ...] = ()
    execution: str = DANS_LE_PROCESSUS
    python_module: str = ""
    requires: Tuple[str, ...] = ()
    sends_data_off_host: bool = False
    typical_latency_ms: Optional[float] = None
    limitations: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not str(self.provider_id).strip():
            raise LiveProviderRefused(
                "Un fournisseur sans identifiant ne se route pas."
            )
        inconnues = [c for c in self.capabilities if c not in CAPACITES]
        if inconnues:
            raise LiveProviderRefused(
                f"Capacités non déclarées : {inconnues}. Déclarées : "
                f"{list(CAPACITES)}. Une capacité inventée serait routée vers "
                "un fournisseur que rien ne sonde."
            )
        if not self.capabilities:
            raise LiveProviderRefused(
                f"« {self.provider_id} » ne déclare aucune capacité : rien ne "
                "peut lui être confié."
            )
        if self.execution not in MODES_D_EXECUTION:
            raise LiveProviderRefused(
                f"Mode d'exécution « {self.execution} » non déclaré. "
                f"Déclarés : {list(MODES_D_EXECUTION)}."
            )
        if self.execution == DANS_LE_PROCESSUS and not self.python_module:
            raise LiveProviderRefused(
                f"« {self.provider_id} » est `IN_PROCESS` sans module à "
                "importer : sa disponibilité ne pourrait pas être mesurée."
            )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable de la déclaration."""
        return {
            "provider_id": self.provider_id,
            "capabilities": list(self.capabilities),
            "execution": self.execution,
            "python_module": self.python_module,
            "requires": list(self.requires),
            "sends_data_off_host": self.sends_data_off_host,
            "typical_latency_ms": self.typical_latency_ms,
            "limitations": list(self.limitations),
        }


def health(provider: LiveCaptureProvider) -> Dict[str, Any]:
    """
    Mesure ce qu'un fournisseur peut faire **ici**, pas ce qu'il déclare.

    Args:
        provider: La déclaration examinée.

    Returns:
        L'état mesuré, capacité par capacité : le module est-il importable, et
        l'entrée correspondante existe-t-elle ? Un fournisseur dont le module
        est présent mais dont le périphérique manque reste `BLOCKED`, et le
        rapport dit lequel des deux manque.

    Note:
        `latency_ms` vaut `None` tant que rien n'a été mesuré. « Rapide » n'est
        pas une mesure, et zéro non plus.
    """
    manques: List[str] = []
    if provider.execution == DANS_LE_PROCESSUS and provider.python_module:
        if not module_present(provider.python_module):
            manques.append(f"module « {provider.python_module} » non importable")

    entrees: Dict[str, Any] = {}
    for capacite in provider.capabilities:
        observation = probe(capacite)
        entrees[capacite] = {
            "present": observation.status == MESURE,
            "detail": observation.detail,
        }
        if observation.status != MESURE:
            manques.append(f"entrée « {capacite} » : {observation.detail}")

    return {
        "provider_id": provider.provider_id,
        "state": BLOQUE if manques else DISPONIBLE,
        "missing": manques,
        "inputs": entrees,
        "latency_ms": provider.typical_latency_ms,
        "measured_latency": False,
        "note": ("Un fournisseur déclaré n'est pas un fournisseur disponible. "
                 "Ce qui manque est nommé ; rien n'est rendu à sa place."),
    }


def route(capability: str,
          providers: Tuple[LiveCaptureProvider, ...] = ()) -> Dict[str, Any]:
    """
    Choisit un fournisseur pour une capacité, ou dit pourquoi il n'y en a pas.

    Args:
        capability: L'entrée de §7 demandée.
        providers: Les fournisseurs déclarés.

    Returns:
        Le fournisseur retenu et l'état de chaque candidat. `chosen` vaut `None`
        quand aucun n'est disponible — et la liste des raisons est rendue, parce
        que « aucun fournisseur » n'apprend rien.

    Raises:
        LiveProviderRefused: Si la capacité n'est pas déclarée.
    """
    if capability not in CAPACITES:
        raise LiveProviderRefused(
            f"Capacité « {capability} » non déclarée. Déclarées : "
            f"{list(CAPACITES)}."
        )
    candidats = [p for p in providers if capability in p.capabilities]
    etats = [health(p) for p in candidats]
    retenu = next((e for e in etats if e["state"] == DISPONIBLE), None)
    return {
        "capability": capability,
        "chosen": retenu["provider_id"] if retenu else None,
        "candidates": etats,
        "candidate_count": len(candidats),
        "reason": "" if retenu else (
            "aucun candidat déclaré pour cette capacité" if not candidats
            else "tous les candidats sont bloqués ; voir `candidates`"),
        "fallback_used": False,
        "note": ("Aucun repli silencieux : un fournisseur bloqué n'est pas "
                 "remplacé par un autre qui ne sert pas la même capacité."),
    }


def degraded_mode(providers: Tuple[LiveCaptureProvider, ...] = ()) -> Dict[str, Any]:
    """
    Ce qui reste possible quand des modalités manquent (§34).

    Args:
        providers: Les fournisseurs déclarés.

    Returns:
        Les capacités servies, celles qui ne le sont pas avec leur raison, et
        **aucun booléen global**. « Dégradé » ne veut rien dire tout seul :
        ce qui compte est quelle entrée est perdue.
    """
    routes = {c: route(c, providers) for c in CAPACITES}
    servies = sorted(c for c, r in routes.items() if r["chosen"])
    perdues = sorted(c for c, r in routes.items() if not r["chosen"])
    return {
        "served": servies,
        "lost": perdues,
        "reasons": {c: routes[c]["reason"] for c in perdues},
        "served_count": len(servies),
        "declared_count": len(CAPACITES),
        "operational": None,
        "note": ("Dégradé veut dire moins de modalités, dites comme telles — "
                 "jamais « ça marche » avec la moitié des entrées manquantes. "
                 "Aucun verdict global : ce qui compte est quelle entrée "
                 "manque."),
    }


def providers_report(providers: Tuple[LiveCaptureProvider, ...] = ()) -> Dict[str, Any]:
    """
    Ce que la couche fournisseurs déclare, et ce qu'elle refuse.

    Returns:
        Les interfaces réutilisées, l'état mesuré, et les règles tenues.
    """
    return {
        "new_interfaces": ["LiveCaptureProvider"],
        "reused_interfaces": dict(INTERFACES_REUTILISEES),
        "capabilities": list(CAPACITES),
        "declared_providers": [p.as_dict() for p in providers],
        "degraded": degraded_mode(providers),
        "rules": [
            "Une seule interface nouvelle sur les cinq proposées : quatre "
            "dupliquent quelque chose qui existe.",
            "Un fournisseur déclaré n'est pas un fournisseur disponible ; "
            "`health()` mesure, la déclaration affirme.",
            "Un fournisseur bloqué dit ce qui lui manque et ne rend pas un "
            "flux vide.",
            "Aucun repli silencieux vers un fournisseur qui ne sert pas la "
            "même capacité.",
            "La latence vaut None tant que rien n'a été mesuré : « rapide » "
            "n'est pas une mesure, et zéro non plus.",
            "Aucun booléen global de mode dégradé : ce qui compte est quelle "
            "entrée manque.",
        ],
    }
