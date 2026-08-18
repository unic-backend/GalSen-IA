"""
Connector lifecycle: authorization, binding to a subject, and withdrawal.

Phase 41.1 made a connector declare *what* it touches and *on whose behalf*.
This phase gives the per-subject connectors the shape their life actually has,
because a connector bound to a person has states the platform's own integrations
never had: nobody has granted access yet, the grant expired, the person took it
back.

Two decisions carry this module.

**A per-subject connector cannot be called without a subject.** Its operations
are reached through a binding that carries the subject, so no call site can omit
it. This is the same lesson as the memory engine's optional `user_id`, which
meant "everyone" when it was left out — that design never fails through an
attack, it fails through an omission.

**Withdrawal works when nothing else does.** `revoke()` must succeed even when
the connector is unconfigured, unreachable, or already expired. A person taking
back access is not asking the platform for a favour, and making that path depend
on a credential being present would mean the one moment consent matters most is
the one moment the button does not work.

No credential is ever fabricated here, and nothing in this module authenticates:
it describes states and refuses transitions. The Google OAuth flow that fills
these states in is VOLET 43.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

from ..security.isolation import Owner
from .contract import DataContract, contract_of


class AuthorizationState(str, Enum):
    """Où en est l'accès d'une personne à travers un connecteur."""

    #: La plateforme n'a pas les identifiants d'application. Rien ne peut être
    #: demandé à personne tant que c'est le cas.
    NOT_CONFIGURED = "not_configured"

    #: Configuré, mais cette personne n'a jamais accordé l'accès.
    NOT_AUTHORIZED = "not_authorized"

    #: Accès accordé et utilisable.
    AUTHORIZED = "authorized"

    #: Accordé puis périmé. Un rafraîchissement peut le rétablir sans redemander
    #: son consentement à la personne — ce n'est pas un refus.
    EXPIRED = "expired"

    #: Retiré, par la personne ou par le fournisseur. **Se redemande**, ne se
    #: rafraîchit pas : un consentement repris n'est pas un jeton périmé.
    REVOKED = "revoked"

    @property
    def usable(self) -> bool:
        """Vrai seulement si un appel peut avoir lieu maintenant."""
        return self is AuthorizationState.AUTHORIZED


class AuthorizationRefused(PermissionError):
    """Un appel tenté sans autorisation utilisable."""


@dataclass(frozen=True)
class SubjectBinding:
    """
    Un connecteur, lié à une personne.

    C'est le seul objet par lequel les opérations d'un connecteur par sujet sont
    atteintes. Il porte le sujet, donc aucun site d'appel ne peut l'oublier, et
    il sait dire le propriétaire de tout ce qui en sort.

    Attributes:
        connector: Le connecteur lié.
        subject: L'identifiant stable de la personne (ADR-010).
    """

    connector: Any
    subject: str

    @property
    def contract(self) -> Optional[DataContract]:
        """Le contrat de données du connecteur lié."""
        return contract_of(self.connector)

    def owner(self) -> Owner:
        """
        Le propriétaire de ce que ce connecteur rend pour cette personne.

        Returns:
            Le propriétaire, déduit du contrat — jamais choisi par l'appelant.

        Raises:
            ContractError: Si le connecteur ne déclare pas de contrat.
        """
        contrat = self.contract
        if contrat is None:
            from .contract import ContractError

            raise ContractError(
                f"Connecteur '{getattr(self.connector, 'connector_id', '?')}' : "
                "aucun contrat, donc rien ne peut être attribué."
            )
        return contrat.owner_of(self.subject)

    def state(self) -> AuthorizationState:
        """L'état d'autorisation de cette personne."""
        return self.connector.authorization_state(self.subject)

    def call(self, operation: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Exécute une opération, si et seulement si l'accès est utilisable.

        Args:
            operation: L'opération du connecteur à appeler.
            *args: Arguments positionnels.
            **kwargs: Arguments nommés.

        Returns:
            Le résultat de l'opération.

        Raises:
            AuthorizationRefused: Si l'accès n'est pas utilisable, avec l'état
                réel dans le message — « périmé » et « retiré » demandent deux
                actions différentes, et un message commun les confondrait.
        """
        etat = self.state()
        if not etat.usable:
            raise AuthorizationRefused(
                f"Accès '{etat.value}' pour '{self.subject}' sur "
                f"'{getattr(self.connector, 'connector_id', '?')}'. "
                f"{EXPLICATIONS[etat]}"
            )
        return operation(*args, **kwargs)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, sans aucun jeton."""
        return {
            "connector_id": getattr(self.connector, "connector_id", None),
            "subject": self.subject,
            "state": self.state().value,
        }


#: Ce que chaque état demande comme suite. Un refus qui ne dit pas quoi faire
#: oblige son destinataire à deviner.
EXPLICATIONS: Dict[AuthorizationState, str] = {
    AuthorizationState.NOT_CONFIGURED: (
        "La plateforme n'a pas les identifiants d'application : rien ne peut "
        "être demandé à cette personne tant que c'est le cas."
    ),
    AuthorizationState.NOT_AUTHORIZED: (
        "Cette personne n'a jamais accordé l'accès ; il faut le lui demander."
    ),
    AuthorizationState.AUTHORIZED: "Accès utilisable.",
    AuthorizationState.EXPIRED: (
        "L'accès est périmé : un rafraîchissement le rétablit sans redemander "
        "son consentement."
    ),
    AuthorizationState.REVOKED: (
        "L'accès a été retiré : il se **redemande**, il ne se rafraîchit pas."
    ),
}


class SubjectBoundConnector(ABC):
    """
    Contrat d'un connecteur agissant pour le compte d'une personne.

    À implémenter **en plus** de `Connector`, jamais à sa place : les trois
    questions d'ADR-007 — qui es-tu, es-tu configuré, réponds-tu — restent
    valables et portent sur la machine, pas sur la personne.
    """

    @abstractmethod
    def authorization_state(self, subject: str) -> AuthorizationState:
        """
        L'état d'accès de cette personne.

        Ne lève jamais et ne contacte rien : un état se lit hors ligne, comme
        `is_configured`.
        """

    @abstractmethod
    def revoke(self, subject: str) -> bool:
        """
        Retire l'accès de cette personne, et efface ce qui la concerne.

        **Doit réussir même non configuré, injoignable ou déjà périmé.** Une
        personne qui reprend son accès ne demande pas une faveur ; faire
        dépendre ce chemin d'un identifiant présent reviendrait à ce que le seul
        moment où le consentement compte vraiment soit celui où le bouton ne
        marche pas.

        Returns:
            True si quelque chose a été retiré, False s'il n'y avait rien.
        """

    def for_subject(self, subject: str) -> SubjectBinding:
        """
        Lie ce connecteur à une personne.

        Args:
            subject: L'identifiant stable de la personne.

        Returns:
            Le lien, seul objet par lequel les opérations sont atteintes.

        Raises:
            ValueError: Si le sujet est vide. Un connecteur par sujet appelé
                pour personne ne saurait ni à qui demander l'accès, ni à qui
                attribuer ce qu'il rend.
        """
        if not (subject or "").strip():
            raise ValueError(
                "Un connecteur par sujet ne s'appelle pas sans sujet : il ne "
                "saurait ni à qui demander l'accès, ni à qui attribuer ce "
                "qu'il rend."
            )
        return SubjectBinding(connector=self, subject=subject.strip())


def is_subject_bound(connector: Any) -> bool:
    """
    Indique si un connecteur agit pour le compte de personnes.

    Lu sur le **contrat**, pas sur la classe : c'est la déclaration qui fait
    foi, et un connecteur qui hériterait du contrat sans se déclarer par sujet
    serait justement l'incohérence que `verify_contract` refuse.

    Args:
        connector: Le connecteur.

    Returns:
        True s'il est déclaré par sujet.
    """
    contrat = contract_of(connector)
    return bool(contrat and contrat.per_subject)


def lifecycle_report(connector: Any, subject: Optional[str] = None) -> Dict[str, Any]:
    """
    L'état de cycle de vie d'un connecteur, pour une personne s'il y a lieu.

    Args:
        connector: Le connecteur.
        subject: La personne, quand le connecteur est par sujet.

    Returns:
        L'état, et ce qu'il demande comme suite. Aucun jeton n'y figure.
    """
    par_sujet = is_subject_bound(connector)
    rapport: Dict[str, Any] = {
        "connector_id": getattr(connector, "connector_id", None),
        "per_subject": par_sujet,
    }

    if not par_sujet:
        rapport["state"] = (
            AuthorizationState.AUTHORIZED.value
            if getattr(connector, "is_configured", lambda: False)()
            else AuthorizationState.NOT_CONFIGURED.value
        )
        rapport["detail"] = (
            "Connecteur de la plateforme : son accès ne dépend d'aucune personne."
        )
        return rapport

    if not (subject or "").strip():
        rapport["state"] = None
        rapport["detail"] = (
            "Connecteur par sujet : l'état n'a de sens que pour une personne "
            "nommée. Aucun état global n'est publié."
        )
        return rapport

    etat = connector.authorization_state(subject)
    rapport["subject"] = subject
    rapport["state"] = etat.value
    rapport["usable"] = etat.usable
    rapport["detail"] = EXPLICATIONS[etat]
    return rapport
