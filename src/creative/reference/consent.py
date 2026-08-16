"""
What someone agreed to, and why "yes" is not an answer on its own.

Directive §12 is short and its consequence is large: *uploading a person's image
MUST NOT automatically imply unlimited rights to use it.* ADR-025 turns that into
a structure, and the structure exists because of two failures that are ordinary
rather than exotic.

**Scope creep is silent.** A photo uploaded for one project is reused in another
six months later, by a system that has no idea the permission was narrower than
the storage. Nothing in a file path remembers what someone agreed to. So consent
here is a **scope**: who granted it, for what uses, over what reach, until when.
A use that is not listed is refused, and the refusal names the missing
permission — the shape `src/tool/authorization.py` already uses for tool
ceilings.

**Absence is not permission.** A reference with no consent scope cannot be used.
Not "used with a warning", not "used because nobody objected": refused. This is
the Darra J rule restated — there is no permission for an unlinked learner
because none was created — and it is the only reading of §12 that survives
contact with a busy pipeline.

Revocation is terminal for **use** and permanent for the **record**. The
revocation itself is kept, because erasing the trace of a privacy decision
destroys the evidence that it was honoured.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

#: La portée d'un consentement : jusqu'où la référence a le droit d'aller.
#: Elles sont ordonnées, du plus étroit au plus large — un consentement de
#: projet ne couvre pas un compte, et l'inverse serait une extension que
#: personne n'a accordée.
PORTEE_PROJET = "PROJECT"
PORTEE_COMPTE = "ACCOUNT"
PORTEE_ORGANISATION = "ORGANISATION"
PORTEES = (PORTEE_PROJET, PORTEE_COMPTE, PORTEE_ORGANISATION)

#: Les politiques de conservation déclarables. « Pour toujours » n'en est pas
#: une : une durée illimitée non dite est une durée que personne n'a acceptée.
CONSERVATION_DUREE = "DURATION"
CONSERVATION_JUSQU_A_REVOCATION = "UNTIL_REVOKED"
CONSERVATION_USAGE_UNIQUE = "SINGLE_USE"
CONSERVATIONS = (CONSERVATION_DUREE, CONSERVATION_JUSQU_A_REVOCATION,
                 CONSERVATION_USAGE_UNIQUE)

#: L'état d'une référence vis-à-vis de son consentement.
ACTIF = "ACTIVE"
REVOQUE = "REVOKED"
EXPIRE = "EXPIRED"
ETATS = (ACTIF, REVOQUE, EXPIRE)

#: Les identités qui ne peuvent pas accorder un consentement au nom d'un tiers.
#: La plateforme ne consent pas pour quelqu'un ; c'est le même refus que Darra J
#: oppose à une plateforme qui publierait son propre curriculum.
IDENTITES_DE_PLATEFORME = ("galsen", "ia", "galsen-ia", "galsenia", "system",
                           "plateforme", "platform", "bot", "agent")


class ConsentRefused(ValueError):
    """Un consentement impossible ou une utilisation hors de sa portée."""


def is_platform_identity(name: str) -> bool:
    """
    Indique si un nom désigne la plateforme plutôt qu'une personne.

    La comparaison porte sur des **mots entiers** : « ia » est à l'intérieur de
    « Mariama », et une comparaison par sous-chaîne refuserait le consentement
    d'une personne réelle tout en laissant passer « galsen_ia_v2 ».

    Args:
        name: Le nom examiné.

    Returns:
        True si le nom est celui de la plateforme.
    """
    mots = [m for m in "".join(
        c.lower() if c.isalnum() else " " for c in str(name or "")
    ).split() if m]
    return any(mot in IDENTITES_DE_PLATEFORME for mot in mots)


@dataclass(frozen=True)
class ConsentScope:
    """
    Ce à quoi une personne a consenti — pas seulement qu'elle a consenti.

    Attributes:
        granted_by: Qui accorde. Une personne nommée, jamais la plateforme.
        subject: Qui la référence représente.
        permitted_uses: Les usages autorisés, en liste blanche. Un usage absent
            est refusé.
        scope: Jusqu'où la référence peut aller, parmi `PORTEES`.
        retention: La politique de conservation.
        expires_at: L'instant d'expiration, pour `DURATION`.
        may_share: Si la référence peut sortir de sa portée. Faux par défaut.
        granted_on: Quand.
        evidence: Comment le consentement a été recueilli. Sans cela, personne
            ne peut vérifier qu'il a existé.
    """

    granted_by: str
    subject: str
    permitted_uses: Tuple[str, ...]
    scope: str = PORTEE_PROJET
    retention: str = CONSERVATION_JUSQU_A_REVOCATION
    expires_at: Optional[float] = None
    may_share: bool = False
    granted_on: float = field(default_factory=time.time)
    evidence: str = ""

    def __post_init__(self) -> None:
        if not str(self.granted_by or "").strip():
            raise ConsentRefused(
                "Un consentement sans auteur n'en est pas un : personne ne "
                "peut le révoquer, et personne ne peut dire qui l'a donné."
            )
        if is_platform_identity(self.granted_by):
            raise ConsentRefused(
                f"« {self.granted_by} » désigne la plateforme. Elle ne consent "
                "pas à la place de quelqu'un : un consentement que nul humain "
                "n'assume n'est pas un consentement."
            )
        if not str(self.subject or "").strip():
            raise ConsentRefused(
                "Un consentement doit nommer **qui** la référence représente : "
                "sans sujet, « il a accepté » ne dit pas de quoi."
            )
        if not self.permitted_uses:
            raise ConsentRefused(
                "Aucun usage autorisé. Une liste vide n'ouvre rien — et c'est "
                "voulu : un consentement sans usage nommé serait une "
                "autorisation générale que personne n'a accordée."
            )
        if self.scope not in PORTEES:
            raise ConsentRefused(
                f"Portée « {self.scope} » non déclarée. Déclarées : {list(PORTEES)}."
            )
        if self.retention not in CONSERVATIONS:
            raise ConsentRefused(
                f"Conservation « {self.retention} » non déclarée. Déclarées : "
                f"{list(CONSERVATIONS)}. « Pour toujours » n'en est pas une."
            )
        if self.retention == CONSERVATION_DUREE and self.expires_at is None:
            raise ConsentRefused(
                "Une conservation par durée sans instant d'expiration est une "
                "durée illimitée déguisée."
            )

    def covers(self, use: str, scope: str = PORTEE_PROJET) -> bool:
        """
        Indique si cet usage, à cette portée, est couvert.

        Args:
            use: L'usage demandé.
            scope: La portée où il aurait lieu.

        Returns:
            True seulement si l'usage est **nommé** et si la portée demandée
            ne dépasse pas celle accordée.
        """
        if use not in self.permitted_uses:
            return False
        if scope not in PORTEES:
            return False
        return PORTEES.index(scope) <= PORTEES.index(self.scope)

    def expired(self, now: Optional[float] = None) -> bool:
        """Vrai quand la durée accordée est passée."""
        if self.expires_at is None:
            return False
        return (now if now is not None else time.time()) >= self.expires_at

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "granted_by": self.granted_by, "subject": self.subject,
            "permitted_uses": list(self.permitted_uses), "scope": self.scope,
            "retention": self.retention, "expires_at": self.expires_at,
            "may_share": self.may_share, "granted_on": self.granted_on,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class Revocation:
    """
    Le fait qu'un consentement a été retiré, conservé pour toujours.

    Attributes:
        revoked_by: Qui a retiré.
        revoked_on: Quand.
        reason: Pourquoi, si la personne l'a dit.
        propagated_to: Les artefacts marqués comme dérivant de cette référence.
    """

    revoked_by: str
    revoked_on: float = field(default_factory=time.time)
    reason: str = ""
    propagated_to: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "revoked_by": self.revoked_by, "revoked_on": self.revoked_on,
            "reason": self.reason, "propagated_to": list(self.propagated_to),
        }


def authorize(
    scope: Optional[ConsentScope], use: str,
    at_scope: str = PORTEE_PROJET, state: str = ACTIF,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Décide si une référence peut être employée, et dit pourquoi quand elle ne peut pas.

    Args:
        scope: Le consentement accordé. `None` signifie **aucun**.
        use: L'usage demandé.
        at_scope: La portée où l'usage aurait lieu.
        state: L'état de la référence.
        now: L'instant de référence, pour l'expiration.

    Returns:
        L'autorisation et sa raison. Un refus **nomme** ce qui manque : un refus
        muet fait chercher un bogue là où il y a une décision.
    """
    if scope is None:
        return {
            "allowed": False, "reason": (
                "Aucune portée de consentement. L'absence de portée est "
                "l'absence de permission : rien n'a été accordé, donc rien "
                "n'est permis."
            ),
        }
    if state == REVOQUE:
        return {"allowed": False, "reason": (
            "Consentement révoqué. Quelqu'un a retiré son accord, et une "
            "réutilisation après coup le contredirait."
        )}
    if state == EXPIRE or scope.expired(now):
        return {"allowed": False, "reason": (
            "Consentement expiré. Une durée écoulée ne se prolonge pas parce "
            "que la référence est encore sur le disque."
        )}
    if not scope.covers(use, at_scope):
        if use not in scope.permitted_uses:
            return {"allowed": False, "reason": (
                f"L'usage « {use} » n'est pas dans la liste accordée "
                f"({list(scope.permitted_uses)}). La liste est blanche : ce qui "
                "n'y est pas est refusé."
            )}
        return {"allowed": False, "reason": (
            f"Portée « {at_scope} » plus large que celle accordée "
            f"(« {scope.scope} »). Un accord de projet ne devient pas un accord "
            "de compte parce que c'est pratique."
        )}
    return {"allowed": True, "reason": (
        f"Usage « {use} » accordé par {scope.granted_by} à la portée "
        f"{scope.scope}."
    )}


def consent_report() -> Dict[str, Any]:
    """
    Ce que le consentement garantit, et ce qu'il refuse.

    Returns:
        Le vocabulaire déclaré et les règles tenues.
    """
    return {
        "scopes": list(PORTEES),
        "retentions": list(CONSERVATIONS),
        "states": list(ETATS),
        "rules": [
            "**L'absence de portée est l'absence de permission.** Une "
            "référence sans consentement ne s'utilise pas — pas même avec un "
            "avertissement.",
            "Les usages forment une **liste blanche** : ce qui n'y est pas est "
            "refusé, et le refus nomme l'usage manquant.",
            "Une portée ne s'élargit pas : un accord de projet ne devient pas "
            "un accord de compte parce que c'est pratique.",
            "La plateforme ne consent pas à la place de quelqu'un, et "
            "l'identité est comparée **par mots entiers** — « ia » est à "
            "l'intérieur de « Mariama ».",
            "« Pour toujours » n'est pas une politique de conservation.",
            "Une révocation est **terminale pour l'usage** et **permanente "
            "pour le registre** : effacer la trace d'une décision de "
            "confidentialité détruit la preuve qu'elle a été honorée.",
        ],
        "does_not": [
            "Traiter un téléversement comme un consentement.",
            "Élargir une portée accordée.",
            "Prolonger une durée expirée.",
            "Oublier qu'une révocation a eu lieu.",
        ],
    }
