"""
The authorization code flow, with PKCE — the only flow this platform performs.

Nothing here is a network call, and nothing here holds a token. This module
builds the two halves of the flow that can be got wrong silently: the URL a
person is sent to, and the request that turns a returned code into tokens. Both
are pure functions of configuration and randomness, so both are testable without
credentials — which is exactly the situation this environment is in.

Four refusals, each closing a documented way this flow is broken in the wild:

**PKCE is mandatory, and only S256.** The `plain` method is in the RFC and
protects against nothing an attacker who reads the request cannot see. It is
refused rather than offered.

**`state` is single use and expires.** Reusing one is a replay; keeping one
forever means a code intercepted last month is still worth something.

**The redirect URI comes from the environment, never from a request.** A
redirect URI chosen by the caller is an open redirect — the authorization code
delivered to whoever asked for it.

**No password, anywhere.** The whole point of this flow is that the platform
never sees one. There is no field for it, no parameter, and a test reads this
package's source to keep it that way.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from .config import Provider

#: Durée de validité d'une demande en attente. Dix minutes suffisent largement à
#: un consentement humain, et rien ne justifie qu'un code intercepté hier vaille
#: encore quelque chose demain.
DUREE_DE_VIE_SECONDES = 600

#: Longueur du vérificateur PKCE, en octets avant encodage. La RFC 7636 impose
#: entre 43 et 128 caractères ; 32 octets donnent 43 caractères, le minimum
#: conforme, avec 256 bits d'entropie.
OCTETS_DE_VERIFICATEUR = 32

#: La seule méthode de défi acceptée. `plain` ne protège de rien.
METHODE_DE_DEFI = "S256"


class FlowRefused(ValueError):
    """Une étape du flux refusée : état inconnu, rejoué, ou périmé."""


def _b64url(donnees: bytes) -> str:
    """Encode en base64 URL, sans remplissage, comme l'exige la RFC 7636."""
    return base64.urlsafe_b64encode(donnees).decode("ascii").rstrip("=")


def generate_verifier() -> str:
    """
    Produit un vérificateur PKCE.

    Returns:
        Une chaîne aléatoire conforme à la RFC 7636.
    """
    return _b64url(secrets.token_bytes(OCTETS_DE_VERIFICATEUR))


def challenge_for(verifier: str) -> str:
    """
    Calcule le défi `S256` d'un vérificateur.

    Args:
        verifier: Le vérificateur.

    Returns:
        Le défi, base64 URL sans remplissage.

    Raises:
        FlowRefused: Si le vérificateur est vide ou trop court pour la RFC.
    """
    if len(verifier or "") < 43:
        raise FlowRefused(
            "Vérificateur PKCE trop court : la RFC 7636 exige au moins 43 "
            "caractères, faute de quoi le défi se force."
        )
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def generate_state() -> str:
    """
    Produit un `state` — le jeton anti-rejeu du flux.

    Returns:
        Une chaîne aléatoire imprévisible.
    """
    return _b64url(secrets.token_bytes(32))


@dataclass
class PendingAuthorization:
    """
    Une demande d'autorisation en attente du retour de la personne.

    Elle porte le vérificateur PKCE, qui **ne quitte jamais la plateforme** :
    seul son défi part chez le fournisseur, et c'est ce qui rend un code
    intercepté inutilisable.

    Attributes:
        state: Le jeton anti-rejeu, retrouvé au retour.
        verifier: Le vérificateur PKCE, gardé ici.
        subject: Pour qui l'autorisation est demandée.
        provider_id: Chez quel fournisseur.
        scopes: Ce qui est demandé.
        created_at: Quand, en secondes depuis l'époque.
    """

    state: str
    verifier: str
    subject: str
    provider_id: str
    scopes: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def expired(self, now: Optional[float] = None) -> bool:
        """Indique si la demande a dépassé sa durée de vie."""
        return (now or time.time()) - self.created_at > DUREE_DE_VIE_SECONDES

    def as_dict(self) -> Dict[str, Any]:
        """
        Représentation sérialisable, **sans le vérificateur**.

        Le publier reviendrait à annuler PKCE : quiconque le lit peut échanger
        un code intercepté.
        """
        return {
            "state": self.state,
            "subject": self.subject,
            "provider_id": self.provider_id,
            "scopes": list(self.scopes),
            "created_at": self.created_at,
        }


class PendingStore:
    """
    Les demandes en attente, en mémoire.

    Volontairement non persistant : une demande d'autorisation vit dix minutes,
    et la faire survivre à un redémarrage n'apporterait qu'une fenêtre de rejeu
    plus large. Un redémarrage pendant un consentement se solde par un
    recommencement, ce qui est le bon comportement.
    """

    def __init__(self) -> None:
        self._demandes: Dict[str, PendingAuthorization] = {}

    def put(self, demande: PendingAuthorization) -> None:
        """Enregistre une demande."""
        self._demandes[demande.state] = demande

    def consume(self, state: str, now: Optional[float] = None) -> PendingAuthorization:
        """
        Retire et retourne la demande correspondant à cet état.

        **Usage unique** : la demande est retirée avant toute vérification, de
        sorte qu'un `state` rejoué ne retrouve rien — y compris si la première
        tentative a échoué.

        Args:
            state: L'état renvoyé par le fournisseur.
            now: Horodatage, pour les tests.

        Returns:
            La demande.

        Raises:
            FlowRefused: Si l'état est inconnu, déjà consommé, ou périmé. Les
                trois cas rendent le même message : distinguer « inconnu » de
                « périmé » renseignerait qui essaie.
        """
        demande = self._demandes.pop(state, None)
        if demande is None or demande.expired(now):
            raise FlowRefused(
                "État d'autorisation inconnu, déjà utilisé ou périmé. "
                "Recommencer la demande."
            )
        return demande

    def purge(self, now: Optional[float] = None) -> int:
        """
        Retire les demandes périmées.

        Returns:
            Le nombre de demandes retirées.
        """
        perimes = [
            state for state, demande in self._demandes.items() if demande.expired(now)
        ]
        for state in perimes:
            self._demandes.pop(state, None)
        return len(perimes)

    def __len__(self) -> int:
        return len(self._demandes)


@dataclass(frozen=True)
class AuthorizationStart:
    """
    Ce qu'il faut pour envoyer une personne consentir.

    Attributes:
        url: L'adresse vers laquelle la rediriger.
        pending: La demande à conserver jusqu'à son retour.
    """

    url: str
    pending: PendingAuthorization


def start_authorization(
    provider: Provider, subject: str, scopes: List[str], store: PendingStore
) -> AuthorizationStart:
    """
    Prépare l'envoi d'une personne vers l'écran de consentement.

    Args:
        provider: Le fournisseur.
        subject: Pour qui l'accès est demandé.
        scopes: Les portées voulues ; elles sont vérifiées contre celles que la
            configuration déclare.
        store: Où conserver la demande en attente.

    Returns:
        L'adresse et la demande.

    Raises:
        OAuthNotConfigured: Si les identifiants manquent — c'est l'état de cet
            environnement, et il est rapporté, pas contourné.
        ScopeRefused: Si une portée n'est pas déclarée.
        FlowRefused: Si le sujet est vide : un consentement appartient à
            quelqu'un.
    """
    if not (subject or "").strip():
        raise FlowRefused(
            "Autorisation demandée sans sujet : un consentement appartient à "
            "quelqu'un, et sans nom rien ne pourrait lui être attribué."
        )

    portees = provider.check_scopes(scopes)
    # `client_id` et `redirect_uri` lèvent si la configuration manque. C'est
    # voulu : mieux vaut ne pas construire d'URL du tout que d'en construire une
    # incomplète, qu'une personne suivrait quand même.
    identifiant_client = provider.client_id()
    retour = provider.redirect_uri()

    verificateur = generate_verifier()
    demande = PendingAuthorization(
        state=generate_state(),
        verifier=verificateur,
        subject=subject.strip(),
        provider_id=provider.id,
        scopes=portees,
    )
    store.put(demande)

    parametres = {
        "response_type": "code",
        "client_id": identifiant_client,
        "redirect_uri": retour,
        "scope": " ".join(portees),
        "state": demande.state,
        "code_challenge": challenge_for(verificateur),
        "code_challenge_method": METHODE_DE_DEFI,
        # Un accès qui ne se rafraîchit pas obligerait à redemander son
        # consentement à la personne toutes les heures, ce qui apprend à cliquer
        # « oui » sans lire.
        "access_type": "offline",
    }
    return AuthorizationStart(
        url=f"{provider.authorization_endpoint}?{urlencode(parametres)}",
        pending=demande,
    )


def token_request(
    provider: Provider, code: str, pending: PendingAuthorization
) -> Dict[str, Any]:
    """
    Construit la requête d'échange du code contre des jetons.

    Elle est **construite, pas envoyée**. L'envoi appartient au connecteur qui
    détient les identifiants ; ici, aucun appel réseau n'est fait — cet
    environnement n'a ni identifiants ni accès à `oauth2.googleapis.com`.

    Args:
        provider: Le fournisseur.
        code: Le code d'autorisation retourné.
        pending: La demande conservée, porteuse du vérificateur.

    Returns:
        L'URL, la méthode, les en-têtes et le corps à poster.

    Raises:
        FlowRefused: Si le code est vide.
        OAuthNotConfigured: Si les identifiants manquent.
    """
    if not (code or "").strip():
        raise FlowRefused("Code d'autorisation vide : rien à échanger.")

    return {
        "method": "POST",
        "url": provider.token_endpoint,
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        "data": {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": provider.client_id(),
            "client_secret": provider.client_secret(),
            "redirect_uri": provider.redirect_uri(),
            # Le vérificateur, révélé seulement maintenant : c'est lui qui
            # prouve que celui qui échange le code est celui qui l'a demandé.
            "code_verifier": pending.verifier,
        },
    }


def flow_report() -> Dict[str, Any]:
    """
    Ce que ce flux fait, et ce qu'il refuse de faire.

    Returns:
        Les paramètres du flux et la liste des refus.
    """
    return {
        "flow": "authorization_code",
        "pkce": METHODE_DE_DEFI,
        "state_ttl_seconds": DUREE_DE_VIE_SECONDES,
        "refuses": [
            "PKCE `plain` — il ne protège de rien qu'un lecteur de la requête "
            "ne voie déjà.",
            "Un `state` rejoué ou périmé.",
            "Une URI de retour venue d'une requête (redirection ouverte).",
            "Une portée non déclarée dans `config/oauth/providers.yaml`.",
            "Un consentement sans sujet nommé.",
        ],
        "never": [
            "Demander ou stocker un mot de passe — le flux existe pour que la "
            "plateforme n'en voie jamais.",
            "Fabriquer un identifiant client absent.",
            "Faire un appel réseau depuis ce module.",
        ],
    }
