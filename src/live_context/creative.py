"""
Ce qu'une session peut proposer au moteur créatif — et rien de plus
(L12, ADR-033, §23, §24 et §37 de la directive Live Context).

## La phrase que ce module existe pour tenir

**Rien de ce qui est observé dans une session n'est une demande.** Quelqu'un
qui parle wolof en réunion n'a pas demandé une vidéo en wolof. Quelqu'un dont le
nom est prononcé n'a pas demandé à figurer dans un plan.

Traiter une observation comme une intention serait l'erreur la plus coûteuse du
programme, parce qu'elle est invisible : le résultat aurait exactement la forme
de ce qu'on attendait, et personne ne pourrait dire lequel des éléments avait
été demandé.

## Une seule porte, et ce module n'y touche pas

`creative/intent.py` a déjà la bonne forme. `offer()` propose **sans jamais
appliquer** et rend `intent_unchanged: True` ; `accept()` est la seule porte
d'entrée, elle demande un appel séparé et un `stated_as` qui atteste
l'acceptation.

Ce module s'arrête à `offer()`. **Il n'expose aucune fonction qui accepte**, et
un test le vérifie sur les noms publics plutôt que sur une promesse.

## La table de correspondance est courte, et ce qui n'y est pas est dit

Deux sujets d'observation seulement deviennent des éléments d'intention. Ce
n'est pas une limitation temporaire : c'est le résultat de se demander, pour
chaque sujet, *est-ce que l'observer revient à le demander ?*

Le contenu d'un écran ne devient pas un texte incrusté, une transcription ne
devient pas un dialogue, et une application ouverte ne devient rien du tout.
Chaque exclusion porte sa raison, pour qu'une relecture dans six mois ne les
prenne pas pour un oubli.

## §24 : une langue proposée est une langue déclarée

Proposer « wolof » là où le registre dit `wo` ferait qu'un interdit posé sur
l'un ne couvrirait pas l'autre. Une langue non déclarée est donc refusée, avec
le rappel que l'ajouter est une ligne dans `corpus/creative/languages.yaml`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from src.creative.intent import CreativeIntent, offer
from src.creative.voice.scene import known_codes

from .state import LiveContextState, Observation

#: Les sujets d'observation qui deviennent des éléments d'intention, et la
#: nature qu'ils prennent. Deux, et chacun reste une **proposition**.
CORRESPONDANCES: Dict[str, str] = {
    "language": "language",
    "speaker": "entity",
}

#: Ce qui ne devient pas un élément d'intention, et pourquoi. Une exclusion sans
#: raison se relit comme un oubli.
EXCLUSIONS: Dict[str, str] = {
    "transcript": (
        "Une transcription est ce qui a été dit, pas ce qui est demandé. En "
        "faire un dialogue mettrait dans un plan des phrases que personne n'a "
        "écrites pour lui."
    ),
    "screen_text": (
        "Un texte affiché pendant une réunion n'est pas un texte incrusté "
        "demandé. Le convertir ferait entrer dans une production le contenu "
        "d'une diapositive que personne n'a choisie."
    ),
    "screen_app": (
        "Une application ouverte ne dit rien d'une intention créative."
    ),
    "intent": (
        "Une intention détectée reste une intention d'outil (§16), pas un "
        "élément de plan. Les confondre ferait exécuter une demande créative "
        "à partir d'une phrase prononcée."
    ),
    "diarization": (
        "L'état d'une capacité technique n'est pas un élément de plan."
    ),
}


class CreativeLinkRefused(ValueError):
    """Une proposition impossible telle quelle."""


def suggestible(observation: Observation) -> Dict[str, Any]:
    """
    Dit si une observation peut devenir une proposition, et sinon pourquoi.

    Args:
        observation: L'observation examinée.

    Returns:
        `eligible`, la nature d'intention le cas échéant, et la raison du refus
        sinon. Les raisons sont distinctes : « inconnue », « exclue par nature »
        et « sujet non rattaché » n'appellent pas la même suite.
    """
    if not observation.is_known:
        return {"eligible": False, "kind": None, "reason": (
            f"Observation de statut {observation.status} : proposer à partir "
            "d'une inconnue mettrait dans un plan ce que personne n'a mesuré.")}
    if observation.subject in EXCLUSIONS:
        return {"eligible": False, "kind": None,
                "reason": EXCLUSIONS[observation.subject]}
    if observation.subject not in CORRESPONDANCES:
        return {"eligible": False, "kind": None, "reason": (
            f"Sujet « {observation.subject} » sans correspondance déclarée. "
            "L'ajouter est une décision : observer quelque chose ne revient "
            "pas à le demander.")}
    nature = CORRESPONDANCES[observation.subject]
    if nature == "language" and str(observation.value) not in known_codes():
        return {"eligible": False, "kind": None, "reason": (
            f"Langue « {observation.value} » non déclarée. Déclarées : "
            f"{known_codes()}. Proposer « wolof » là où le registre dit « wo » "
            "ferait qu'un interdit posé sur l'un ne couvrirait pas l'autre ; "
            "l'ajouter est une ligne dans `corpus/creative/languages.yaml`.")}
    return {"eligible": True, "kind": nature, "reason": ""}


def to_suggestions(state: LiveContextState) -> List[Dict[str, Any]]:
    """
    Ce qu'une session pourrait proposer, sujet par sujet.

    Args:
        state: L'état de la session.

    Returns:
        Une entrée par observation, éligible ou non, **avec sa provenance**
        (§37) : le fournisseur, la modalité et la session. Une proposition
        anonyme ne peut pas être pesée par la personne qui la reçoit.
    """
    resultats: List[Dict[str, Any]] = []
    for observation in state.observations:
        verdict = suggestible(observation)
        resultats.append({
            "observation_subject": observation.subject,
            "kind": verdict["kind"],
            "value": observation.value if verdict["eligible"] else None,
            "eligible": verdict["eligible"],
            "reason": verdict["reason"],
            "provenance": {
                "session_id": state.session_id,
                "provider": observation.provider or "inconnu",
                "modality": observation.modality,
                "status": observation.status,
                "observed_at": observation.at,
            },
        })
    return resultats


def eligible_couples(state: LiveContextState) -> List[Tuple[str, str]]:
    """
    Les couples `(nature, valeur)` qu'une session pourrait proposer.

    Args:
        state: L'état de la session.

    Returns:
        Les couples, sans doublon, dans l'ordre d'apparition.
    """
    couples: List[Tuple[str, str]] = []
    for entree in to_suggestions(state):
        if not entree["eligible"]:
            continue
        couple = (entree["kind"], str(entree["value"]))
        if couple not in couples:
            couples.append(couple)
    return couples


def offer_from_session(intent: CreativeIntent,
                       state: LiveContextState) -> Dict[str, Any]:
    """
    Propose au moteur créatif ce qu'une session a observé, sans rien appliquer.

    Args:
        intent: L'intention en cours. **Elle n'est pas modifiée** — le retour de
            `creative.intent.offer()` est rendu tel quel.
        state: L'état de la session.

    Returns:
        Le résultat de `offer()`, plus ce qui n'a pas été proposé et pourquoi.
        `applied_count` vaut zéro et `intent_unchanged` vaut vrai, parce que
        c'est `offer()` qui répond, pas ce module.

    Note:
        Il n'existe ici **aucun chemin vers `accept()`**. Accepter est un acte
        d'une personne, avec son `stated_as` ; le faire à sa place au motif
        qu'une session l'a suggéré est exactement ce que §23 refuse.
    """
    entrees = to_suggestions(state)
    couples = eligible_couples(state)
    resultat = offer(intent, couples,
                     source=f"live_context/session:{state.session_id}")
    resultat["not_offered"] = [
        {"observation_subject": e["observation_subject"], "reason": e["reason"]}
        for e in entrees if not e["eligible"]
    ]
    resultat["provenance"] = [e["provenance"] for e in entrees if e["eligible"]]
    resultat["accepted"] = False
    resultat["session_note"] = (
        "Rien de ce qui est observé dans une session n'est une demande. "
        "Ces éléments sont proposés ; seule une personne les accepte."
    )
    return resultat


def creative_link_report() -> Dict[str, Any]:
    """
    Ce que la liaison au moteur créatif garantit, et ce qu'elle refuse.

    Returns:
        La table de correspondance, les exclusions, et les règles tenues.
    """
    return {
        "mappings": dict(CORRESPONDANCES),
        "exclusions": dict(EXCLUSIONS),
        "accepts_anything": False,
        "modifies_intent": False,
        "reused": [
            "creative/intent.py — offer() propose sans appliquer, accept() est "
            "la seule porte",
            "creative/voice/scene.py — les codes de langue déclarés (§24)",
        ],
        "rules": [
            "Rien de ce qui est observé dans une session n'est une demande.",
            "Ce module s'arrête à offer() et n'expose aucune fonction qui "
            "accepte.",
            "Une observation inconnue ne propose rien : elle mettrait dans un "
            "plan ce que personne n'a mesuré.",
            "Chaque exclusion porte sa raison, pour qu'elle ne se relise pas "
            "comme un oubli.",
            "Une langue proposée est une langue déclarée : « wolof » et « wo » "
            "ne doivent pas devenir deux choses.",
            "Chaque proposition porte sa provenance : une proposition anonyme "
            "ne peut pas être pesée.",
        ],
    }
