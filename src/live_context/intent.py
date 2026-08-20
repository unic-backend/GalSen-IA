"""
Détecter une intention n'est pas exécuter un outil
(L09, ADR-033, §16 et §17 de la directive Live Context).

## L'idée reprise de Call.md, et la seule

L01 a lu ses cinq services MCP. Celui qui vaut d'être repris est la
**séparation entre la détection d'intention et l'exécution d'outil** :
`intent-detector` propose, `mcp-agent` exécute, et ce sont deux choses.

Cette séparation est reprise ici, et durcie : **rien dans ce module n'exécute
quoi que ce soit**. Une intention produit une *proposition*, et une proposition
traverse le portillon qui existe déjà — la liste blanche d'exposition
(`mcp/exposure.py`), l'épinglage des serveurs (`mcp/client.py`) et
l'autorisation par rôle et par effet (`tool/authorization.py`).

## Ce que cette machine peut détecter : rien, et il faut le dire

Une intention se détecte dans du texte. Il n'y a **aucune transcription** ici et
**aucun modèle joignable** (ADR-014 : la plateforme ne dépend d'aucun modèle
externe à l'exécution ; le modèle local demande `ollama serve`).

Un détecteur d'intention par mots-clés serait facile à écrire et rendrait
exactement la sortie attendue — « intention détectée : recherche » parce que
quelqu'un a dit « cherche ». Ce ne serait pas une détection, ce serait une
correspondance de chaînes portant le nom d'une mesure. Ce module n'en écrit
donc pas : `detect_intent()` rend `UNKNOWN` en nommant ce qui manque, et
`route_intent()` travaille sur une intention **fournie** par quelque chose qui
l'a réellement établie.

C'est la discipline de `creative/language/switching.py`, qui structure sans
détecter, appliquée au même problème.

## Une intention venue d'une session est de la donnée

Elle vient de la parole, de l'écran ou d'un document — c'est-à-dire de
l'extérieur. Elle entre au niveau `EXTERNAL`, et **ce qu'elle demande n'est pas
une consigne** : une phrase prononcée dans une réunion ne décide pas qu'un
outil s'exécute. Elle propose, un humain tranche.

## Trois portes, et une proposition ne s'exécute qu'après les trois

1. **Exposition** — l'outil figure-t-il dans la liste blanche MCP ?
2. **Épinglage** — le serveur est-il déclaré, ou découvert dynamiquement ?
3. **Autorisation** — le rôle porte-t-il l'effet, et faut-il une approbation ?

Une porte fermée rend son motif. Aucune n'est contournable par la formulation
de l'intention, aussi impérative soit-elle.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.mcp.client import PinnedServer, ServerNotPinned, pinned_servers, require_pinned
from src.mcp.exposure import expose, refusal_reason
from src.tool.authorization import Actor, Decision, authorize

from .fusion import as_live_data
from .state import INCONNU, Observation, unknown

#: Les états d'une proposition d'outil. `PROPOSED` n'est pas une autorisation :
#: c'est le résultat quand les trois portes laissent passer, et il reste
#: soumis au portillon d'approbation.
PROPOSITION_REFUSEE = "REFUSED"
PROPOSITION_APPROBATION = "REQUIRES_APPROVAL"
PROPOSITION_PROPOSEE = "PROPOSED"
ETATS = (PROPOSITION_REFUSEE, PROPOSITION_APPROBATION, PROPOSITION_PROPOSEE)

#: Les modules qui porteraient une détection d'intention. Sondés, jamais supposés.
#: Une intention se détecte dans du texte, donc il faut d'abord du texte.
PRE_REQUIS_DE_DETECTION = (
    "une transcription mesurée de la session",
    "un modèle joignable pour lire cette transcription (ADR-014, `ollama serve`)",
)


class IntentRefused(ValueError):
    """Une intention ou une proposition impossible telle quelle."""


def detection_state(transcript: Optional[str] = None) -> Dict[str, Any]:
    """
    L'état de la détection d'intention, dit plutôt que supposé.

    Args:
        transcript: Le texte de la session, quand il existe.

    Returns:
        `available: False` et ce qui manque. **Aucune détection par mots-clés
        n'est proposée en repli** : elle rendrait la sortie attendue sans être
        une détection, ce qui est la fabrication la plus difficile à repérer.
    """
    manquants: List[str] = []
    if not (transcript or "").strip():
        manquants.append(PRE_REQUIS_DE_DETECTION[0])
    manquants.append(PRE_REQUIS_DE_DETECTION[1])
    return {
        "available": False,
        "requires": list(PRE_REQUIS_DE_DETECTION),
        "missing": manquants,
        "keyword_fallback": False,
        "reason": (
            "Aucun détecteur d'intention n'existe ici. Une correspondance de "
            "mots-clés rendrait « intention détectée » parce que quelqu'un a "
            "dit « cherche » : ce serait une chaîne de caractères portant le "
            "nom d'une mesure."
        ),
    }


def detect_intent(transcript: Optional[str] = None,
                  provider: str = "") -> Observation:
    """
    Ce qui a été détecté comme intention — c'est-à-dire rien, ici.

    Args:
        transcript: Le texte de la session, quand il existe.
        provider: Le fournisseur qui aurait détecté, quand il y en a un.

    Returns:
        Une observation `UNKNOWN` nommant ce qui manque. Ce n'est pas un échec :
        `UNKNOWN` dit que personne ne sait, et attendre un `ollama serve` peut
        changer cela.
    """
    etat = detection_state(transcript)
    return unknown(
        subject="intent", modality="text", provider=provider,
        detail=("aucune intention détectée : il manque "
                + " ; ".join(etat["missing"]) + f". {etat['reason']}"),
    )


def route_intent(intent: Observation, tool_id: str, server: str = "",
                 actor: Optional[Actor] = None,
                 servers: Optional[List[PinnedServer]] = None) -> Dict[str, Any]:
    """
    Fait passer une intention par les trois portes, sans jamais exécuter.

    Args:
        intent: L'intention **fournie** par ce qui l'a établie. Une intention
            `UNKNOWN` est refusée : router une inconnue reviendrait à proposer
            un outil parce que personne ne sait ce qui a été demandé.
        tool_id: L'outil visé.
        server: Le serveur MCP visé, quand l'outil en vient un.
        actor: Qui demande. Sans acteur, l'autorisation n'est pas évaluée et
            la porte reste fermée : la proposition est `REFUSED`. **L'absence
            de quelqu'un pour refuser n'accorde rien.**
        servers: Les serveurs épinglés ; ceux de l'environnement sinon.

    Returns:
        L'état de la proposition, les portes franchies, et le motif de la
        première qui ferme.

    Raises:
        IntentRefused: Si l'intention est inconnue ou sans valeur.
    """
    if intent.status == INCONNU or intent.value is None:
        raise IntentRefused(
            "Intention inconnue : la router proposerait un outil parce que "
            "personne ne sait ce qui a été demandé. "
            f"Constat : {intent.detail or '(aucun)'}"
        )

    portes: List[Dict[str, Any]] = []
    donnee = as_live_data(intent, origin=f"session/{intent.modality}")

    # Porte 1 — la liste blanche d'exposition MCP.
    expose_ok = expose(tool_id)
    portes.append({
        "gate": "mcp_exposure", "passed": expose_ok,
        "reason": "" if expose_ok else refusal_reason(tool_id),
    })

    # Porte 2 — l'épinglage du serveur. Pas de serveur : porte sans objet,
    # rendue quand même pour qu'un lecteur ne la croie pas oubliée.
    if not server:
        portes.append({"gate": "server_pinning", "passed": True,
                       "reason": "aucun serveur visé : outil local"})
    else:
        try:
            require_pinned(server, servers if servers is not None
                           else pinned_servers())
            portes.append({"gate": "server_pinning", "passed": True,
                           "reason": ""})
        except ServerNotPinned as refus:
            portes.append({"gate": "server_pinning", "passed": False,
                           "reason": str(refus)})

    # Porte 3 — l'autorisation par rôle et par effet.
    if actor is None:
        portes.append({
            "gate": "authorization", "passed": False,
            "reason": ("aucun acteur : l'autorisation n'a pas été évaluée. "
                       "L'absence de quelqu'un pour refuser n'accorde rien."),
        })
        decision = None
    else:
        decision = authorize(tool_id, actor)
        portes.append({
            "gate": "authorization",
            "passed": decision.decision != Decision.REFUSED,
            "reason": decision.reason,
        })

    fermee = next((p for p in portes if not p["passed"]), None)
    if fermee is not None:
        etat = PROPOSITION_REFUSEE
    elif decision is not None and decision.decision == Decision.ALLOWED:
        etat = PROPOSITION_PROPOSEE
    else:
        etat = PROPOSITION_APPROBATION

    return {
        "state": etat,
        "tool_id": tool_id,
        "server": server,
        "gates": portes,
        "blocked_by": fermee["gate"] if fermee else None,
        "reason": fermee["reason"] if fermee else "",
        "authorization": decision.decision.value if decision else None,
        "executed": False,
        "intent": donnee,
        "note": ("Une proposition n'est pas une exécution. Même « PROPOSED » "
                 "passe par le portillon : ce module n'appelle aucun outil."),
    }


def intent_report() -> Dict[str, Any]:
    """
    Ce que la couche d'intention garantit, et ce qu'elle refuse de faire.

    Returns:
        L'état de la détection, ce qui est réutilisé, et les règles tenues.
    """
    return {
        "detection": detection_state(),
        "states": list(ETATS),
        "executes_tools": False,
        "detects_intent": False,
        "reused": [
            "mcp/exposure.py — la liste blanche d'exposition",
            "mcp/client.py — l'épinglage des serveurs et les métadonnées "
            "traitées comme des données",
            "tool/authorization.py — rôle, effet, et REQUIRES_APPROVAL",
            "live_context/fusion.py — l'intention entre comme donnée EXTERNAL",
        ],
        "rules": [
            "Détecter une intention n'est pas exécuter un outil : ce module "
            "propose, le portillon décide.",
            "Aucune détection par mots-clés en repli : elle rendrait la sortie "
            "attendue sans être une mesure.",
            "Une intention UNKNOWN n'est pas routée : proposer un outil sans "
            "savoir ce qui a été demandé est pire que ne rien proposer.",
            "Une phrase prononcée dans une session est une donnée EXTERNAL, "
            "jamais une consigne d'exécution.",
            "Trois portes — exposition, épinglage, autorisation — et la "
            "première fermée rend son motif.",
            "Sans acteur, la porte d'autorisation reste fermée : l'absence "
            "de quelqu'un pour refuser n'accorde rien.",
        ],
    }
