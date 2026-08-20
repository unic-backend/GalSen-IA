"""
Les cinq choses qui ne se font jamais en silence
(L11.1, ADR-033, §14 et §28 de la directive Live Context).

## La phrase du §28, transformée en code plutôt qu'en promesse

*« Ne pas enregistrer en silence. Ne pas conserver en silence. Ne pas
téléverser en silence. Ne pas indexer en silence. Ne pas partager en
silence. »*

Cinq actes, et le mot qui compte est **en silence**. Aucun des cinq n'est
interdit par nature : enregistrer une réunion est légitime, et l'indexer aussi.
Ce qui est interdit, c'est de le faire sans que quelqu'un l'ait décidé et sans
qu'il en reste une trace.

Chaque acte passe donc par `authorize_act()`, qui **rend toujours une décision
écrite** — autorisée ou refusée. Il n'existe aucun chemin qui autorise sans
produire la trace : la décision *est* la valeur de retour.

## Le consentement est nécessaire, jamais suffisant

C'est la règle propre à ce volet, et elle est la seule qui puisse surprendre.

`creative/reference/consent.py` décide déjà si un usage est couvert : liste
blanche d'usages, portée qui ne s'élargit pas, révocation terminale, et
**l'absence de portée vaut l'absence de permission**. Tout cela est appelé, pas
réécrit.

Mais ADR-018 refuse **inconditionnellement** que trois catégories quittent la
machine — mémoires et fichiers de l'utilisateur, **captures d'écran**, export de
données d'entraînement — et l'ADR ne prévoit pas d'exception pour une personne
qui accepterait. Une plateforme qui laisserait un consentement lever cet
interdit reviendrait à demander à quelqu'un de renoncer à une garantie qu'elle
lui a donnée par ailleurs.

Les refus inconditionnels sont donc évalués **avant** le consentement, pour
qu'une portée valide n'apparaisse jamais comme une autorisation.

## « Pour toujours » n'est pas une politique de conservation

Une durée illimitée non dite est une durée que personne n'a acceptée. La règle
vit déjà dans `ConsentScope` — une conservation par durée sans instant
d'expiration y est refusée à la construction — et `retain` la fait valoir au
moment de l'acte plutôt qu'au moment de la promesse.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from src.creative.reference.consent import (
    ACTIF,
    CONSERVATION_DUREE,
    CONSERVATION_JUSQU_A_REVOCATION,
    CONSERVATION_USAGE_UNIQUE,
    PORTEE_PROJET,
    ConsentScope,
)
from src.creative.reference.consent import authorize as consent_authorize

#: Les cinq actes de §28. Aucun n'est interdit par nature ; aucun ne se fait en
#: silence.
ACTES = ("record", "retain", "upload", "index", "share")

#: Ce que chaque acte fait, écrit pour qu'un refus soit lisible par quelqu'un
#: qui ne connaît pas la directive.
DESCRIPTION_DES_ACTES: Dict[str, str] = {
    "record": "capter et écrire ce qui se dit ou s'affiche pendant la session",
    "retain": "garder cet enregistrement au-delà de la session",
    "upload": "envoyer le contenu hors de cette machine",
    "index": "rendre le contenu retrouvable par une recherche ultérieure",
    "share": "donner accès au contenu à quelqu'un d'autre que le sujet",
}

#: Les actes qui font sortir le contenu de la machine, seuls concernés par les
#: refus inconditionnels d'ADR-018.
ACTES_SORTANTS = ("upload", "share")

#: Les modalités qu'ADR-018 refuse de laisser sortir, **quelle que soit** la
#: configuration et **quel que soit** le consentement. La liste est nominative
#: plutôt que déduite : une modalité ajoutée doit être classée explicitement.
MODALITES_SANS_SORTIE: Dict[str, str] = {
    "screen": (
        "ADR-018 range les captures d'écran parmi les charges qu'aucune "
        "dérogation ne couvre. Une image de l'écran de quelqu'un est la charge "
        "la plus révélatrice que cette plateforme manipulera jamais."
    ),
}

#: Les politiques de conservation qui bornent réellement la durée.
CONSERVATIONS_BORNEES = (CONSERVATION_DUREE, CONSERVATION_USAGE_UNIQUE,
                         CONSERVATION_JUSQU_A_REVOCATION)


class RetentionRefused(ValueError):
    """Un acte impossible tel quel."""


def _decision(act: str, allowed: bool, reason: str, basis: str,
              scope: Optional[ConsentScope], unconditional: bool,
              modality: str, now: float) -> Dict[str, Any]:
    """Construit la décision écrite d'un acte."""
    return {
        "act": act,
        "act_means": DESCRIPTION_DES_ACTES[act],
        "modality": modality,
        "allowed": allowed,
        "reason": reason,
        "basis": basis,
        "unconditional_refusal": unconditional,
        "consent": scope.as_dict() if scope is not None else None,
        "decided_at": now,
        "silent": False,
        "note": ("Aucun de ces actes ne se fait en silence : cette décision "
                 "est la trace, et il n'existe aucun chemin qui autorise sans "
                 "la produire."),
    }


def authorize_act(act: str, scope: Optional[ConsentScope] = None,
                  modality: str = "", at_scope: str = PORTEE_PROJET,
                  state: str = ACTIF,
                  now: Optional[float] = None) -> Dict[str, Any]:
    """
    Décide si un acte peut avoir lieu, et écrit la décision dans tous les cas.

    Args:
        act: Un acte de `ACTES`.
        scope: Le consentement accordé. `None` signifie **aucun**, ce qui vaut
            refus : l'absence de portée est l'absence de permission.
        modality: La modalité du contenu concerné, quand elle est connue. Elle
            décide des refus inconditionnels.
        at_scope: La portée où l'acte aurait lieu.
        state: L'état du consentement.
        now: L'instant de référence.

    Returns:
        La décision écrite : autorisée ou non, sa raison, et sur quoi elle
        s'appuie.

    Raises:
        RetentionRefused: Si l'acte n'est pas déclaré. Un acte inconnu n'est pas
            refusé silencieusement — il n'a pas de sens à évaluer.
    """
    if act not in ACTES:
        raise RetentionRefused(
            f"Acte « {act} » non déclaré. Déclarés : {list(ACTES)}."
        )
    instant = now if now is not None else time.time()

    # Les refus inconditionnels d'abord : une portée valide ne doit jamais
    # apparaître comme une autorisation de ce qu'une ADR interdit.
    if act in ACTES_SORTANTS and modality in MODALITES_SANS_SORTIE:
        return _decision(
            act, False,
            (f"L'acte « {act} » ferait sortir un contenu de modalité "
             f"« {modality} » de la machine. {MODALITES_SANS_SORTIE[modality]}"),
            basis="ADR-018 — refus inconditionnel",
            scope=scope, unconditional=True, modality=modality, now=instant,
        )

    verdict = consent_authorize(scope, use=act, at_scope=at_scope,
                                state=state, now=instant)
    if not verdict["allowed"]:
        return _decision(act, False, verdict["reason"],
                         basis="creative/reference/consent.py",
                         scope=scope, unconditional=False, modality=modality,
                         now=instant)

    if act == "retain":
        borne = retention_bound(scope, now=instant)
        if not borne["bounded"]:
            return _decision(act, False, borne["reason"],
                             basis="politique de conservation",
                             scope=scope, unconditional=False,
                             modality=modality, now=instant)

    return _decision(act, True, verdict["reason"],
                     basis="creative/reference/consent.py",
                     scope=scope, unconditional=False, modality=modality,
                     now=instant)


def retention_bound(scope: Optional[ConsentScope],
                    now: Optional[float] = None) -> Dict[str, Any]:
    """
    Dit si la conservation accordée est réellement bornée.

    Args:
        scope: Le consentement accordé.
        now: L'instant de référence.

    Returns:
        `bounded`, la politique, et l'instant d'expiration quand il existe.
        `expires_at` vaut `None` pour `UNTIL_REVOKED` : ce n'est pas une durée
        infinie mais une durée **inconnue**, qui se termine quand quelqu'un le
        décide.
    """
    if scope is None:
        return {"bounded": False, "policy": None, "expires_at": None,
                "reason": ("Aucun consentement : il n'y a pas de politique de "
                           "conservation à faire valoir.")}
    if scope.retention not in CONSERVATIONS_BORNEES:
        return {"bounded": False, "policy": scope.retention, "expires_at": None,
                "reason": (f"Conservation « {scope.retention} » non bornée. "
                           "« Pour toujours » n'est pas une politique : une "
                           "durée illimitée non dite est une durée que "
                           "personne n'a acceptée.")}
    if scope.retention == CONSERVATION_DUREE and scope.expired(now):
        return {"bounded": True, "policy": scope.retention,
                "expires_at": scope.expires_at,
                "reason": ("Durée écoulée : ce qui est encore sur le disque "
                           "n'est pas pour autant encore autorisé.")}
    return {
        "bounded": True,
        "policy": scope.retention,
        "expires_at": scope.expires_at,
        "reason": "",
        "ends_when": ("une révocation" if scope.retention
                      == CONSERVATION_JUSQU_A_REVOCATION else
                      "l'instant déclaré" if scope.retention
                      == CONSERVATION_DUREE else "le premier usage"),
    }


def session_policy(scope: Optional[ConsentScope] = None,
                   modality: str = "", at_scope: str = PORTEE_PROJET,
                   state: str = ACTIF,
                   now: Optional[float] = None) -> Dict[str, Any]:
    """
    L'état des cinq actes pour une session, d'un seul coup d'œil.

    Args:
        scope: Le consentement accordé.
        modality: La modalité du contenu.
        at_scope: La portée où les actes auraient lieu.
        state: L'état du consentement.
        now: L'instant de référence.

    Returns:
        Une décision par acte, et les comptes. **Aucun booléen global** : « la
        session est conforme » ne dit pas ce qui est permis, et c'est ce qu'un
        opérateur a besoin de savoir.
    """
    decisions = {act: authorize_act(act, scope=scope, modality=modality,
                                    at_scope=at_scope, state=state, now=now)
                 for act in ACTES}
    return {
        "acts": decisions,
        "allowed": sorted(a for a, d in decisions.items() if d["allowed"]),
        "refused": sorted(a for a, d in decisions.items() if not d["allowed"]),
        "unconditionally_refused": sorted(
            a for a, d in decisions.items() if d["unconditional_refusal"]),
        "retention": retention_bound(scope, now=now),
        "compliant": None,
        "note": ("Aucun verdict global : « conforme » ne dit pas quel acte est "
                 "permis, et c'est cela qu'un opérateur doit lire."),
    }


def retention_report() -> Dict[str, Any]:
    """
    Ce que la couche de rétention garantit, et ce qu'elle refuse.

    Returns:
        Le vocabulaire, ce qui est réutilisé, et les règles tenues.
    """
    return {
        "acts": list(ACTES),
        "act_means": dict(DESCRIPTION_DES_ACTES),
        "outbound_acts": list(ACTES_SORTANTS),
        "modalities_without_exit": list(MODALITES_SANS_SORTIE),
        "consent_can_lift_adr": False,
        "silent_paths": 0,
        "reused": [
            "creative/reference/consent.py — la portée, la liste blanche "
            "d'usages, la révocation, et l'absence de portée qui vaut refus",
            "ADR-018 — les catégories qui ne sortent pas, quelle que soit la "
            "configuration",
        ],
        "rules": [
            "Aucun des cinq actes n'est interdit par nature ; aucun ne se fait "
            "en silence.",
            "La décision est la valeur de retour : il n'existe aucun chemin "
            "qui autorise sans produire la trace.",
            "Le consentement est nécessaire, jamais suffisant : les refus "
            "inconditionnels sont évalués avant lui.",
            "Un consentement ne lève pas ADR-018 : demander à quelqu'un de "
            "renoncer à une garantie donnée par ailleurs n'est pas un choix.",
            "L'absence de consentement vaut refus — ce n'est pas un défaut de "
            "configuration.",
            "« Pour toujours » n'est pas une politique de conservation.",
            "Aucun verdict global de conformité : ce qui aide est de savoir "
            "quel acte est permis.",
        ],
    }
