"""
Ce qui d'une session a le droit d'entrer en mémoire
(L11.2, ADR-033, §14 de la directive Live Context).

## Écrire en mémoire est un acte de rétention, pas un détail d'implémentation

Une mémoire survit à la session. C'est exactement ce que §28 appelle
« conserver », et c'est souvent aussi « indexer », puisqu'une mémoire qu'on ne
retrouve pas ne sert à rien. Ce module ne réinvente donc aucune règle : il
appelle `retention.authorize_act()` pour les deux actes, et une écriture est
refusée dès que l'un des deux l'est.

## Trois refus, et le premier est le moins évident

**1. Une inconnue n'entre pas en mémoire.** Écrire une observation `UNKNOWN` ou
`ABSENT` stockerait « personne ne sait » sous une forme qui, relue dans six
mois, ressemblera à ce qui a été appris. Une mémoire ne contient que ce qui a
été observé.

**2. Sans lien déclaré, il n'y a pas de permission.** C'est la règle de Darra J,
et elle vaut ici mot pour mot : *il n'existe aucune permission pour un
apprenant non rattaché, parce qu'aucune n'a été créée.* Une observation de
session doit nommer **à qui** elle se rattache, et ce sujet doit être celui du
consentement. Écrire au nom de quelqu'un d'autre est le défaut que rien ne
rattrape ensuite.

**3. Le consentement doit couvrir la conservation ET l'indexation.** Deux actes
distincts : accepter qu'une réunion soit gardée n'est pas accepter qu'elle
devienne cherchable par toute une organisation.

## Rien n'est écrit par défaut

Sans magasin de mémoire fourni, ce module rend la décision et la charge qui
*serait* écrite, avec `written: False` et sa raison. Il ne prétend pas avoir
écrit là où il n'y avait rien pour écrire.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.creative.reference.consent import ACTIF, PORTEE_PROJET, ConsentScope

from .retention import authorize_act
from .state import Observation

#: Les actes qu'une écriture en mémoire déclenche. Les deux, jamais un seul :
#: garder et rendre cherchable sont deux décisions différentes.
ACTES_D_ECRITURE = ("retain", "index")


class MemoryWriteRefused(ValueError):
    """Une écriture en mémoire impossible telle quelle."""


def _refus(raison: str, observation: Observation, subject: str,
           decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Construit le refus écrit d'une écriture."""
    return {
        "allowed": False,
        "written": False,
        "reason": raison,
        "subject": subject,
        "observation": observation.as_dict(),
        "acts": decisions,
        "payload": None,
        "note": ("Un refus d'écriture nomme ce qui manque : un refus muet fait "
                 "chercher un bogue là où il y a une décision."),
    }


def may_write(observation: Observation, subject: str,
              scope: Optional[ConsentScope] = None,
              at_scope: str = PORTEE_PROJET, state: str = ACTIF,
              now: Optional[float] = None) -> Dict[str, Any]:
    """
    Décide si une observation de session peut entrer en mémoire.

    Args:
        observation: L'observation concernée.
        subject: À qui elle se rattache. **Requis** : sans lien déclaré, il n'y
            a pas de permission, parce qu'aucune n'a été créée.
        scope: Le consentement accordé. `None` vaut refus.
        at_scope: La portée où la mémoire vivrait.
        state: L'état du consentement.
        now: L'instant de référence.

    Returns:
        La décision écrite, avec la décision de chacun des deux actes.
    """
    if not str(subject or "").strip():
        return _refus(
            ("Aucun sujet déclaré. Une observation qui ne dit pas à qui elle se "
             "rattache ne peut être couverte par aucune permission : il n'en "
             "existe pas pour un lien qui n'a pas été créé."),
            observation, subject, [])

    if not observation.is_known:
        return _refus(
            (f"Observation « {observation.subject} » de statut "
             f"{observation.status} : une inconnue relue dans six mois "
             "ressemblera à ce qui a été appris. Une mémoire ne contient que "
             "ce qui a été observé."),
            observation, subject, [])

    if scope is not None and scope.subject != subject:
        return _refus(
            (f"Le consentement porte sur « {scope.subject} » et l'écriture se "
             f"rattache à « {subject} ». Écrire au nom de quelqu'un d'autre "
             "est le défaut que rien ne rattrape ensuite."),
            observation, subject, [])

    decisions = [authorize_act(acte, scope=scope, modality=observation.modality,
                               at_scope=at_scope, state=state, now=now)
                 for acte in ACTES_D_ECRITURE]
    refusee = next((d for d in decisions if not d["allowed"]), None)
    if refusee is not None:
        return _refus(
            (f"L'acte « {refusee['act']} » est refusé : {refusee['reason']}"),
            observation, subject, decisions)

    return {
        "allowed": True,
        "written": False,
        "reason": "",
        "subject": subject,
        "observation": observation.as_dict(),
        "acts": decisions,
        "payload": {
            "content": observation.value,
            "subject": subject,
            "observation_subject": observation.subject,
            "modality": observation.modality,
            "status": observation.status,
            "provider": observation.provider,
            "observed_at": observation.at,
            "consent": scope.as_dict() if scope is not None else None,
        },
        "note": ("Autorisée, et pas encore écrite : la décision et l'écriture "
                 "sont deux étapes, pour qu'un appelant puisse montrer la "
                 "première avant de faire la seconde."),
    }


def write_observation(observation: Observation, subject: str,
                      scope: Optional[ConsentScope] = None,
                      memory: Any = None, session_id: str = "",
                      at_scope: str = PORTEE_PROJET, state: str = ACTIF,
                      now: Optional[float] = None) -> Dict[str, Any]:
    """
    Écrit une observation en mémoire, quand tout l'autorise et qu'un magasin existe.

    Args:
        observation: L'observation concernée.
        subject: À qui elle se rattache.
        scope: Le consentement accordé.
        memory: Le gestionnaire de mémoire. **Aucun par défaut** : sans lui,
            rien n'est écrit et la décision le dit.
        session_id: La session d'origine.
        at_scope: La portée où la mémoire vivrait.
        state: L'état du consentement.
        now: L'instant de référence.

    Returns:
        La décision, et `written` avec l'identifiant quand l'écriture a eu lieu.

    Note:
        Ce module ne prétend jamais avoir écrit là où il n'y avait rien pour
        écrire. `written: False` avec sa raison vaut mieux qu'un identifiant
        fabriqué.
    """
    decision = may_write(observation, subject, scope=scope,
                         at_scope=at_scope, state=state, now=now)
    if not decision["allowed"]:
        return decision
    if memory is None:
        decision["reason"] = ("Autorisée, non écrite : aucun magasin de "
                              "mémoire n'a été fourni.")
        return decision

    from src.memory_engine.types import MemoryItem

    item = MemoryItem(
        content=decision["payload"]["content"],
        user_id=subject,
        session_id=session_id or None,
        metadata={k: v for k, v in decision["payload"].items()
                  if k != "content"},
    )
    decision["written"] = True
    decision["memory_id"] = memory.save_memory(item)
    decision["reason"] = "Écrite avec la permission et le lien déclarés."
    return decision


def memory_report() -> Dict[str, Any]:
    """
    Ce que l'écriture en mémoire garantit, et ce qu'elle refuse.

    Returns:
        Les actes déclenchés, ce qui est réutilisé, et les règles tenues.
    """
    return {
        "acts_triggered": list(ACTES_D_ECRITURE),
        "writes_by_default": False,
        "reused": [
            "live_context/retention.py — les cinq actes et leurs refus",
            "creative/reference/consent.py — la portée et l'absence qui vaut "
            "refus",
            "memory_engine/ — le magasin, quand un appelant en fournit un",
        ],
        "rules": [
            "Une écriture en mémoire déclenche deux actes : conserver et "
            "indexer. Accepter l'un n'est pas accepter l'autre.",
            "Une observation UNKNOWN ou ABSENT n'entre pas : relue dans six "
            "mois, elle ressemblerait à ce qui a été appris.",
            "Sans lien déclaré, il n'y a pas de permission — aucune n'a été "
            "créée.",
            "Un consentement qui porte sur quelqu'un d'autre ne couvre pas "
            "cette écriture.",
            "Rien n'est écrit sans magasin fourni, et la décision le dit "
            "plutôt que de rendre un identifiant fabriqué.",
        ],
    }
