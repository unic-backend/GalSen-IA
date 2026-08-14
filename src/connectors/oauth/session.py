"""
The OAuth session: the three pieces held together, and withdrawal that works.

Phase 43.1 built the flow, 43.2 the encrypted store. This is what a connector
actually holds: one provider, the pending authorizations, and the tokens. It
turns `SubjectBoundConnector` — five states and a `revoke()` — into something a
Gmail or Calendar connector inherits rather than reimplements.

The one decision worth arguing about is the order inside `revoke()`.

**Local deletion happens first, and never depends on the provider answering.**
The tempting order is the opposite: tell Google to revoke, and delete locally
once it confirms. That order fails in the way that matters — the network is
down, the provider returns 500, the token was already invalid — and the platform
keeps a credential for someone who asked it to stop. Deleting first can leave a
token live *at the provider*, which the person can also kill from their Google
account page; keeping one *here* is a promise broken by us, and only we can fix
it. So: forget first, then hand back the request that asks the provider to
forget too, and say plainly whether it was sent.

Nothing in this module performs a network call. The exchange and the revocation
are **built** here and executed by whoever holds the credentials — which, in
this environment, is nobody.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..lifecycle import AuthorizationState, SubjectBinding, SubjectBoundConnector
from .config import Provider
from .flow import (
    AuthorizationStart,
    FlowRefused,
    PendingStore,
    start_authorization,
    token_request,
)
from .tokens import StoredToken, TokenStorageUnavailable, TokenStore


class ExchangeRefused(ValueError):
    """Une réponse de jetons inutilisable. Rien n'est conservé dans ce cas."""


@dataclass
class RevocationOutcome:
    """
    Ce qu'un retrait a réellement fait.

    Attributes:
        forgotten_locally: L'accès a-t-il été effacé de ce côté. C'est la seule
            partie que la plateforme maîtrise, et elle a toujours lieu.
        had_access: Y avait-il quelque chose à effacer.
        provider_request: La requête à envoyer au fournisseur pour qu'il oublie
            aussi, ou `None` s'il n'y avait pas de jeton à révoquer chez lui.
        provider_notified: `False` tant que personne n'a envoyé cette requête.
            Le champ existe pour que « nous avons oublié » ne se lise jamais
            comme « le fournisseur a oublié ».
    """

    forgotten_locally: bool
    had_access: bool
    provider_request: Optional[Dict[str, Any]] = None
    provider_notified: bool = False

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, **sans le jeton à révoquer**."""
        return {
            "forgotten_locally": self.forgotten_locally,
            "had_access": self.had_access,
            "provider_notification_required": self.provider_request is not None,
            "provider_notified": self.provider_notified,
        }


class OAuthSession(SubjectBoundConnector):
    """
    Un fournisseur, ses demandes en attente, et ses jetons.

    À hériter par les connecteurs de la vague II. Ils apportent leur contrat de
    données et leurs portées ; tout ce qui touche à l'autorisation est ici, une
    fois.
    """

    def __init__(
        self,
        provider: Provider,
        scopes: List[str],
        tokens: Optional[TokenStore] = None,
        pending: Optional[PendingStore] = None,
    ) -> None:
        """
        Args:
            provider: Le fournisseur déclaré.
            scopes: Les portées que ce connecteur demande. Elles sont vérifiées
                contre celles que la configuration autorise, à chaque demande.
            tokens: Le magasin de jetons ; un magasin propre par défaut.
            pending: Les demandes en attente ; un magasin propre par défaut.
        """
        self.provider = provider
        self.scopes = list(scopes)
        self.tokens = tokens if tokens is not None else TokenStore()
        self.pending = pending if pending is not None else PendingStore()

    # ------------------------------------------------------------------
    # Le contrat `SubjectBoundConnector`
    # ------------------------------------------------------------------

    def authorization_state(self, subject: str) -> AuthorizationState:
        """
        L'état d'accès d'une personne.

        Ne contacte rien et ne déchiffre rien : la configuration d'abord, puis
        les métadonnées du magasin.
        """
        if not self.provider.is_configured():
            return AuthorizationState.NOT_CONFIGURED
        try:
            return self.tokens.state(self.provider.id, subject)
        except ValueError:
            # Sujet vide : personne n'a rien accordé.
            return AuthorizationState.NOT_AUTHORIZED

    def revoke(self, subject: str) -> bool:
        """
        Retire l'accès d'une personne.

        Réussit toujours de ce côté. Voir `revoke_detailed` pour savoir s'il
        reste une requête à envoyer au fournisseur.

        Args:
            subject: La personne.

        Returns:
            True si quelque chose a été effacé.
        """
        return self.revoke_detailed(subject).had_access

    def revoke_detailed(self, subject: str) -> RevocationOutcome:
        """
        Retire l'accès, et dit ce qu'il reste à faire chez le fournisseur.

        **L'effacement local est fait en premier et sans condition.** L'ordre
        inverse — prévenir le fournisseur puis effacer s'il confirme — échoue
        exactement quand il ne faut pas : réseau coupé, fournisseur en erreur,
        jeton déjà invalide, et la plateforme garde un accès que quelqu'un lui
        a demandé d'oublier.

        Args:
            subject: La personne.

        Returns:
            Ce qui a été fait, et la requête à envoyer au fournisseur.
        """
        jeton: Optional[StoredToken] = None
        try:
            jeton = self.tokens.get(self.provider.id, subject)
        except (TokenStorageUnavailable, ValueError):
            # La clé manque ou le sujet est vide : on ne peut pas lire le jeton
            # à révoquer chez le fournisseur, mais on peut — et on doit —
            # effacer quand même.
            jeton = None

        try:
            efface = self.tokens.delete(self.provider.id, subject)
        except ValueError:
            return RevocationOutcome(forgotten_locally=False, had_access=False)

        requete = None
        if jeton is not None and self.provider.revocation_endpoint:
            requete = {
                "method": "POST",
                "url": self.provider.revocation_endpoint,
                "headers": {"Content-Type": "application/x-www-form-urlencoded"},
                # Le jeton de rafraîchissement de préférence : le révoquer
                # invalide chez la plupart des fournisseurs toute la grappe de
                # jetons d'accès qui en descend.
                "data": {"token": jeton.refresh_token or jeton.access_token},
            }

        return RevocationOutcome(
            forgotten_locally=True, had_access=efface, provider_request=requete
        )

    # ------------------------------------------------------------------
    # Le flux
    # ------------------------------------------------------------------

    def begin(self, subject: str) -> AuthorizationStart:
        """
        Prépare l'envoi d'une personne vers l'écran de consentement.

        Args:
            subject: Pour qui.

        Returns:
            L'adresse et la demande en attente.

        Raises:
            OAuthNotConfigured: Si les identifiants manquent.
            ScopeRefused: Si une portée n'est pas déclarée.
            FlowRefused: Si le sujet est vide.
        """
        return start_authorization(self.provider, subject, self.scopes, self.pending)

    def complete(
        self,
        state: str,
        code: str,
        token_response: Optional[Dict[str, Any]] = None,
        now: Optional[float] = None,
    ) -> Any:
        """
        Termine le flux au retour de la personne.

        Deux usages, et la différence est volontairement visible :

        - sans `token_response`, la méthode **rend la requête à envoyer** au
          fournisseur. Aucun appel réseau n'est fait ici ;
        - avec `token_response`, elle valide et conserve ce que le fournisseur
          a répondu.

        Args:
            state: L'état renvoyé, consommé une seule fois.
            code: Le code d'autorisation.
            token_response: La réponse du fournisseur, si elle a été obtenue.
            now: Horodatage, pour les tests.

        Returns:
            La requête à envoyer, ou les jetons conservés.

        Raises:
            FlowRefused: Si l'état est inconnu, rejoué ou périmé.
            ExchangeRefused: Si la réponse du fournisseur est inutilisable.
            TokenStorageUnavailable: Si aucune clé de chiffrement n'existe.
        """
        demande = self.pending.consume(state, now=now)
        if token_response is None:
            return token_request(self.provider, code, demande)

        return self._conserver(demande.subject, demande.scopes, token_response, now)

    def _conserver(
        self,
        subject: str,
        demandees: List[str],
        reponse: Dict[str, Any],
        now: Optional[float] = None,
    ) -> StoredToken:
        """
        Valide la réponse du fournisseur et conserve les jetons.

        Les portées **accordées** priment sur celles demandées : une personne
        peut n'en cocher qu'une partie, et enregistrer ce qu'on a demandé
        laisserait croire à un accès qu'on n'a pas.
        """
        if not isinstance(reponse, dict):
            raise ExchangeRefused(
                f"Réponse de jetons inattendue : {type(reponse).__name__}."
            )

        acces = str(reponse.get("access_token") or "").strip()
        if not acces:
            # Le fournisseur nomme parfois la cause dans `error`. On la relaie
            # telle quelle, comme donnée, sans l'interpréter.
            motif = reponse.get("error") or "aucun `access_token`"
            raise ExchangeRefused(f"Échange refusé par le fournisseur : {motif}.")

        accordees = str(reponse.get("scope") or "").split()
        expiration = None
        duree = reponse.get("expires_in")
        if isinstance(duree, (int, float)) and duree > 0:
            expiration = (now or time.time()) + float(duree)

        jeton = StoredToken(
            provider_id=self.provider.id,
            subject=subject,
            access_token=acces,
            refresh_token=(str(reponse.get("refresh_token")).strip() or None)
            if reponse.get("refresh_token") else None,
            expires_at=expiration,
            scopes=sorted(accordees) if accordees else sorted(demandees),
            obtained_at=now or time.time(),
        )
        self.tokens.save(jeton)
        return jeton

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def binding(self, subject: str) -> SubjectBinding:
        """Le lien à une personne, seul objet par lequel les opérations passent."""
        return self.for_subject(subject)

    def granted_scopes(self, subject: str) -> List[str]:
        """
        Les portées réellement accordées par une personne.

        Returns:
            Les portées, ou une liste vide si aucun accès n'est conservé.

        Raises:
            TokenStorageUnavailable: Si la clé manque.
        """
        jeton = self.tokens.get(self.provider.id, subject)
        return list(jeton.scopes) if jeton else []

    def session_report(self, subject: Optional[str] = None) -> Dict[str, Any]:
        """
        L'état de cette session, sans aucun jeton.

        Args:
            subject: La personne, quand on veut son état.

        Returns:
            Le fournisseur, les portées demandées, et l'état de la personne.
        """
        rapport: Dict[str, Any] = {
            "provider": self.provider.as_dict(),
            "requested_scopes": list(self.scopes),
            "pending_authorizations": len(self.pending),
        }
        if subject:
            etat = self.authorization_state(subject)
            rapport["subject"] = subject
            rapport["state"] = etat.value
            rapport["usable"] = etat.usable
        return rapport


__all__ = [
    "ExchangeRefused",
    "FlowRefused",
    "OAuthSession",
    "RevocationOutcome",
]
