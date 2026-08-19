"""
Router une demande de recherche, et refuser quand aucun fournisseur ne peut la
servir (R05, STEP 5).

## Ce que STEP 5 demande, et ce qui est réellement décidable ici

La directive énumère dix critères : type de requête, source, fraîcheur,
fiabilité, latence, santé du fournisseur, authentification, disponibilité, coût,
permissions de l'utilisateur.

**Trois de ces dix ne sont mesurables sur aucun fournisseur aujourd'hui** :
latence, coût et fiabilité. Aucun `typical_latency_ms` n'est renseigné (R04),
aucun tarif n'est déclaré, et aucune campagne n'a mesuré un taux d'échec. Ce
module les traite donc comme `routing.py` traite déjà ses quatorze dimensions :
il rend un verdict séparé par critère, et **`UNKNOWN` n'est pas `UNMET`**.

Un critère non vérifiable n'écarte pas un fournisseur — il est **rapporté comme
non vérifiable**, et le demandeur décide. Fondre les deux ferait deux erreurs
opposées selon le sens du pli : écarter ce qui marche, ou retenir ce qui ne
marche pas.

## Les trois refus, et pourquoi ils ne se ressemblent pas

- **`NO_PROVIDER`** — personne ne déclare cette capacité. C'est une absence.
- **`ALL_BLOCKED`** — quelqu'un la déclare, mais rien ne peut tourner ici. C'est
  une installation manquante, et le refus nomme les conditions.
- **`REFUSED`** — un fournisseur pourrait servir, et une règle l'interdit :
  droit commercial non établi, données personnelles vers une destination non
  vérifiée, service hébergé alors que l'appelant l'a exclu.

Les fondre en un seul « pas de résultat » ferait chercher au mauvais endroit :
installer un paquet ne lève pas un refus juridique, et lire des conditions ne
remplace pas une installation.

## Ce que ce module ne fait pas

**Il ne substitue jamais une capacité par une autre.** Une demande de recherche
académique à laquelle aucun fournisseur ne répond ne se rabat pas sur une
recherche web « proche » : c'est ce que `creative/routing.py` refuse déjà, et
pour la même raison — servir autre chose que ce qui a été demandé, sans le dire,
est pire que ne rien servir.

**Il ne classe pas.** L'ordre du plan de repli est l'ordre de déclaration, et le
module le dit explicitement plutôt que de laisser croire à un ordre de qualité.
Le jour où une latence sera mesurée sur **tous** les candidats, le classement
deviendra possible ; pas avant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..creative.canvas.privacy import may_send_personal_reference, unknown_policy
from .providers import (
    CAPACITES,
    DISPONIBLE,
    SERVICE_HEBERGE,
    ResearchProvider,
    ResearchProviderRefused,
    health,
    providers_serving,
)

#: L'issue d'un routage. Quatre, et chacune se corrige autrement.
CHOISI = "SELECTED"
AUCUN_FOURNISSEUR = "NO_PROVIDER"
TOUS_BLOQUES = "ALL_BLOCKED"
REFUSE = "REFUSED"
ISSUES = (CHOISI, AUCUN_FOURNISSEUR, TOUS_BLOQUES, REFUSE)

#: Le verdict d'un critère pris isolément.
SATISFAIT = "MET"
NON_SATISFAIT = "UNMET"
NON_VERIFIABLE = "UNKNOWN"

#: Ce que rend une recherche qu'aucun fournisseur n'a pu vérifier (STEP 5).
INCONNU = "UNKNOWN"


class RoutingRefused(ValueError):
    """Une demande de routage impossible telle quelle."""


@dataclass(frozen=True)
class ResearchNeed:
    """
    Ce qu'une demande de recherche exige réellement.

    Attributes:
        capability: La capacité demandée, parmi `CAPACITES`.
        commercial: Si le résultat sera exploité commercialement. Un droit
            **non établi** n'est pas une permission.
        carries_personal_data: Si la requête emporte la donnée d'une personne
            réelle. La porte de `privacy.py` s'applique alors.
        allow_hosted_services: Si l'appelant accepte qu'un service tiers soit
            appelé. `False` exclut tout fournisseur `HOSTED_SERVICE` **et** tout
            fournisseur dont la destination est un hôte tiers.
        max_latency_ms: Une latence maximale souhaitée. Aucun fournisseur n'en
            déclare aujourd'hui, donc ce critère rend `UNKNOWN` — jamais
            `UNMET`.
    """

    capability: str
    commercial: bool = False
    carries_personal_data: bool = False
    allow_hosted_services: bool = True
    max_latency_ms: Optional[float] = None

    def __post_init__(self) -> None:
        if self.capability not in CAPACITES:
            raise RoutingRefused(
                f"Capacité « {self.capability} » non déclarée. Déclarées : "
                f"{list(CAPACITES)}. Router une capacité inventée rendrait "
                "« aucun fournisseur » là où la faute est dans la demande."
            )
        if self.max_latency_ms is not None and self.max_latency_ms <= 0:
            raise RoutingRefused(
                f"Latence maximale {self.max_latency_ms} ms impossible."
            )


def _examiner(provider: ResearchProvider,
              need: ResearchNeed) -> Dict[str, Any]:
    """
    Confronte un fournisseur à une demande, critère par critère.

    Returns:
        `admitted`, les `refusals` qui l'écartent, et les `unverifiable` qui ne
        l'écartent pas. Les deux listes sont **séparées** : un refus se lève par
        une décision, un critère non vérifiable par une mesure.
    """
    refus: List[Dict[str, str]] = []
    non_verifiables: List[Dict[str, str]] = []

    etat = health(provider)
    if etat["state"] != DISPONIBLE:
        refus.append({
            "criterion": "availability",
            "verdict": NON_SATISFAIT,
            "reason": (f"« {provider.provider_id} » ne peut pas tourner ici : "
                       f"{len(etat['missing'])} condition(s) manquante(s)."),
        })

    if need.commercial and not provider.licence.usable_commercially:
        refus.append({
            "criterion": "commercial",
            "verdict": NON_SATISFAIT,
            "reason": (f"Le droit commercial de « {provider.provider_id} » est "
                       f"« {provider.licence.commercial} ». Non établi n'est "
                       "pas permis."),
        })

    politique = provider.privacy or unknown_policy(provider.provider_id)
    if need.carries_personal_data:
        porte = may_send_personal_reference(politique)
        if not porte["allowed"]:
            refus.append({
                "criterion": "personal_data",
                "verdict": NON_SATISFAIT,
                "reason": porte["reason"],
            })

    if not need.allow_hosted_services:
        if provider.execution == SERVICE_HEBERGE:
            refus.append({
                "criterion": "hosted_service",
                "verdict": NON_SATISFAIT,
                "reason": (f"« {provider.provider_id} » est un service hébergé "
                           "et l'appelant les a exclus."),
            })
        elif politique.data_destination != "LOCAL_ONLY":
            refus.append({
                "criterion": "hosted_service",
                "verdict": NON_SATISFAIT,
                "reason": (f"« {provider.provider_id} » envoie la donnée hors "
                           f"de cette machine ({politique.data_destination}) et "
                           "l'appelant l'a exclu."),
            })

    if need.max_latency_ms is not None:
        if provider.typical_latency_ms is None:
            non_verifiables.append({
                "criterion": "latency",
                "verdict": NON_VERIFIABLE,
                "reason": (f"Aucune latence n'a été mesurée pour "
                           f"« {provider.provider_id} ». Non mesuré n'est pas "
                           "lent : le critère est rapporté, pas appliqué."),
            })
        elif provider.typical_latency_ms > need.max_latency_ms:
            refus.append({
                "criterion": "latency",
                "verdict": NON_SATISFAIT,
                "reason": (f"{provider.typical_latency_ms} ms dépasse "
                           f"{need.max_latency_ms} ms."),
            })

    return {
        "provider_id": provider.provider_id,
        "admitted": not refus,
        "refusals": refus,
        "unverifiable": non_verifiables,
        "health_state": etat["state"],
    }


def route(need: ResearchNeed) -> Dict[str, Any]:
    """
    Choisit un fournisseur pour une demande, ou dit pourquoi aucun ne convient.

    Args:
        need: La demande.

    Returns:
        `decision` parmi `ISSUES`, le `provider_id` retenu le cas échéant, le
        `plan` de repli, et `considered` — l'examen de **chaque** candidat, y
        compris ceux écartés. Un routage qui ne rendrait que le gagnant
        empêcherait de comprendre pourquoi les autres ont perdu.

    Note:
        **L'ordre du plan est l'ordre de déclaration, pas un ordre de qualité.**
        Aucune latence n'est mesurée sur aucun fournisseur, et classer sur un
        chiffre absent est ce que `creative/routing.py` refuse déjà. Le champ
        `ordering` le dit dans le résultat, pour que personne ne lise le premier
        élément comme « le meilleur ».
    """
    candidats = providers_serving(need.capability)
    if not candidats:
        return {
            "decision": AUCUN_FOURNISSEUR,
            "capability": need.capability,
            "provider_id": None,
            "plan": [],
            "considered": [],
            "ordering": "declaration",
            "reason": (f"Aucun fournisseur ne déclare « {need.capability} ». "
                       "Aucune capacité voisine n'est proposée à la place."),
        }

    examens = [_examiner(f, need) for f in candidats]
    admis = [e for e in examens if e["admitted"]]

    if admis:
        return {
            "decision": CHOISI,
            "capability": need.capability,
            "provider_id": admis[0]["provider_id"],
            "plan": [e["provider_id"] for e in admis],
            "considered": examens,
            "ordering": "declaration",
            "reason": "",
        }

    joignables = [e for e in examens if e["health_state"] == DISPONIBLE]
    if not joignables:
        return {
            "decision": TOUS_BLOQUES,
            "capability": need.capability,
            "provider_id": None,
            "plan": [],
            "considered": examens,
            "ordering": "declaration",
            "reason": (f"{len(examens)} fournisseur(s) déclarent "
                       f"« {need.capability} », aucun ne peut tourner ici. "
                       "Chaque condition manquante est nommée dans `health`."),
        }

    return {
        "decision": REFUSE,
        "capability": need.capability,
        "provider_id": None,
        "plan": [],
        "considered": examens,
        "ordering": "declaration",
        "reason": ("Un fournisseur pourrait servir, une règle l'interdit. "
                   "Installer quelque chose ne lèvera pas ce refus."),
    }


def execute_with_fallback(need: ResearchNeed,
                          attempt: Callable[[ResearchProvider], Any]
                          ) -> Dict[str, Any]:
    """
    Essaie les fournisseurs admis dans l'ordre, et rend `UNKNOWN` si tous
    échouent.

    Args:
        need: La demande.
        attempt: Ce qu'on tente avec un fournisseur. Une exception vaut échec.

    Returns:
        `status` — `SELECTED` avec le `result` et le `served_by`, ou `UNKNOWN`.
        `attempts` liste chaque essai avec son échec, **y compris quand un
        essai suivant a réussi** : savoir que le premier fournisseur est tombé
        est ce qui permet de le réparer.

    Note:
        **`UNKNOWN` est rendu quand aucun fournisseur n'a pu vérifier**, comme
        STEP 5 l'exige — jamais un résultat approchant, jamais le contenu du
        dernier essai partiellement abouti. Le repli change de **fournisseur**,
        jamais de **capacité**.
    """
    routage = route(need)
    essais: List[Dict[str, Any]] = []

    if routage["decision"] != CHOISI:
        return {
            "status": INCONNU,
            "capability": need.capability,
            "result": None,
            "served_by": None,
            "attempts": essais,
            "routing": routage,
            "reason": routage["reason"],
        }

    from .providers import provider as _provider

    for identifiant in routage["plan"]:
        fournisseur = _provider(identifiant)
        try:
            resultat = attempt(fournisseur)
        except Exception as erreur:                    # noqa: BLE001 - un échec
            essais.append({"provider_id": identifiant, "ok": False,
                           "error": f"{type(erreur).__name__}: {erreur}"})
            continue
        essais.append({"provider_id": identifiant, "ok": True, "error": ""})
        return {
            "status": CHOISI,
            "capability": need.capability,
            "result": resultat,
            "served_by": identifiant,
            "attempts": essais,
            "routing": routage,
            "reason": "",
        }

    return {
        "status": INCONNU,
        "capability": need.capability,
        "result": None,
        "served_by": None,
        "attempts": essais,
        "routing": routage,
        "reason": (f"{len(essais)} fournisseur(s) essayé(s), tous en échec. "
                   "Aucun résultat approchant n'est rendu à la place."),
    }


def routing_report() -> Dict[str, Any]:
    """
    Ce que le routeur décide, et ce qu'il refuse de décider.

    Returns:
        Le vocabulaire, l'état mesuré par capacité, et les règles tenues.
    """
    par_capacite = {}
    for capacite in CAPACITES:
        decision = route(ResearchNeed(capability=capacite))
        par_capacite[capacite] = {
            "decision": decision["decision"],
            "provider_id": decision["provider_id"],
            "candidates": len(decision["considered"]),
        }
    return {
        "outcomes": list(ISSUES),
        "verdicts": [SATISFAIT, NON_SATISFAIT, NON_VERIFIABLE],
        "unverified_result": INCONNU,
        "by_capability": par_capacite,
        "ordering": "declaration",
        "rankable_criteria": [],
        "rules": [
            "UNKNOWN n'est pas UNMET : un critère non vérifiable est rapporté, "
            "pas appliqué.",
            "Trois refus distincts — NO_PROVIDER, ALL_BLOCKED, REFUSED — parce "
            "qu'ils ne se corrigent pas de la même façon.",
            "Aucune substitution de capacité : le repli change de fournisseur, "
            "jamais de capacité.",
            "L'ordre est celui de la déclaration, pas un ordre de qualité : "
            "aucune latence n'est mesurée.",
            "Quand tous les fournisseurs échouent, le résultat est UNKNOWN, "
            "jamais un résultat approchant.",
            "Chaque candidat examiné est rendu, y compris ceux écartés.",
        ],
    }


def declared_capabilities() -> Tuple[str, ...]:
    """Les capacités routables."""
    return tuple(CAPACITES)


__all__ = [
    "AUCUN_FOURNISSEUR", "CHOISI", "INCONNU", "ISSUES", "NON_SATISFAIT",
    "NON_VERIFIABLE", "REFUSE", "SATISFAIT", "TOUS_BLOQUES", "ResearchNeed",
    "ResearchProviderRefused", "RoutingRefused", "declared_capabilities",
    "execute_with_fallback", "route", "routing_report",
]
