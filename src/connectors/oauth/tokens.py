"""
OAuth token storage: encrypted, or refused.

The platform already has encryption at rest (`src/storage/encryption.py`), and
this module uses it rather than growing a second one. What it adds is a policy,
and the difference is the whole point:

**There, encryption is optional. Here it is mandatory.** `storage.encryption`
lets a value through unchanged when no key is configured, which is a reasonable
default for an audit line or a memory item — losing it is bad, but it is not a
live credential. An OAuth token *is* one. Stored in the clear it reads someone's
mail for whoever finds the file, so the absence of a key stops the write instead
of degrading it. A store that quietly writes plaintext while its name says
otherwise is worse than one that refuses.

Three more rules, each with a reason that is not obvious until it bites:

- **A token never appears in a repr, a dict, or a log.** A dataclass prints its
  fields by default; one uncaught exception in a request handler would put a
  refresh token in a traceback, and tracebacks travel.
- **Deletion works without the key.** Revoking is the moment consent matters
  most (VOLET 41), and destroying a ciphertext never required reading it. A
  store that could not forget you because its key was misconfigured would be
  the worst possible failure.
- **Only the ciphertext is held.** The plaintext exists inside `save()` and
  inside `get()`, and nowhere in between.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ...storage import encryption
from ..lifecycle import AuthorizationState

#: Marge avant expiration. Un jeton qui expire dans dix secondes est traité
#: comme expiré : le temps d'un appel réseau, il le sera.
MARGE_D_EXPIRATION_SECONDES = 60


class TokenStorageUnavailable(RuntimeError):
    """Aucune clé de chiffrement. L'écriture est refusée, jamais dégradée."""


def require_encryption() -> None:
    """
    Exige un chiffrement au repos utilisable.

    Raises:
        TokenStorageUnavailable: Si aucune clé n'est configurée ou si elle est
            invalide. Le message nomme la variable, jamais la clé.
    """
    if not encryption.is_enabled():
        raise TokenStorageUnavailable(
            f"Aucune clé de chiffrement ({encryption.KEY_VARIABLE}) : un jeton "
            "OAuth ne s'écrit pas en clair. Il lirait le courrier de quelqu'un "
            "pour qui trouverait le fichier."
        )
    try:
        encryption.verify_key()
    except Exception as erreur:
        raise TokenStorageUnavailable(
            f"{encryption.KEY_VARIABLE} inutilisable : {erreur}"
        ) from erreur


@dataclass
class StoredToken:
    """
    Les jetons d'une personne chez un fournisseur.

    `repr` est réécrit et `as_dict` ne porte aucun jeton : une exception non
    rattrapée dans un gestionnaire de requête suffirait sinon à écrire un jeton
    de rafraîchissement dans une trace, et les traces voyagent.

    Attributes:
        provider_id: Le fournisseur.
        subject: La personne.
        access_token: Le jeton d'accès, en clair **en mémoire seulement**.
        refresh_token: Le jeton de rafraîchissement, s'il y en a un.
        expires_at: Quand l'accès périme, en secondes depuis l'époque.
        scopes: Les portées réellement accordées — elles peuvent être plus
            étroites que celles demandées, et c'est celles-là qui comptent.
        obtained_at: Quand l'accès a été obtenu.
    """

    provider_id: str
    subject: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    scopes: List[str] = field(default_factory=list)
    obtained_at: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        """Rend l'objet sans ses jetons. `dataclass` les imprimerait tous."""
        return (
            f"StoredToken(provider_id={self.provider_id!r}, "
            f"subject={self.subject!r}, expires_at={self.expires_at!r}, "
            f"scopes={self.scopes!r})"
        )

    def expired(self, now: Optional[float] = None) -> bool:
        """
        Indique si l'accès est périmé, marge comprise.

        Un jeton sans date d'expiration n'est **pas** supposé éternel : il est
        traité comme utilisable, parce que c'est ce que le fournisseur dit, mais
        c'est le seul cas où la plateforme fait confiance sans date.
        """
        if self.expires_at is None:
            return False
        return (now or time.time()) + MARGE_D_EXPIRATION_SECONDES >= self.expires_at

    def state(self, now: Optional[float] = None) -> AuthorizationState:
        """L'état d'autorisation que ce jeton représente."""
        if self.expired(now):
            return AuthorizationState.EXPIRED
        return AuthorizationState.AUTHORIZED

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, **sans aucun jeton**."""
        return {
            "provider_id": self.provider_id,
            "subject": self.subject,
            "expires_at": self.expires_at,
            "obtained_at": self.obtained_at,
            "scopes": list(self.scopes),
            "has_refresh_token": self.refresh_token is not None,
            "state": self.state().value,
        }


class TokenStore:
    """
    Les jetons, chiffrés en mémoire.

    Ne détient que du chiffré : le clair n'existe que dans `save()` et `get()`.
    La persistance sur disque suivra la même règle et le même chiffreur — ce
    magasin est délibérément le plus simple possible, parce qu'un magasin de
    jetons est le mauvais endroit où être malin.
    """

    def __init__(self) -> None:
        self._verrou = threading.RLock()
        # (fournisseur, sujet) → (métadonnées, chiffré)
        self._entrees: Dict[Tuple[str, str], Tuple[Dict[str, Any], str]] = {}

    @staticmethod
    def _cle(provider_id: str, subject: str) -> Tuple[str, str]:
        """Construit la clé d'entrée, en refusant un sujet vide."""
        if not (subject or "").strip():
            raise ValueError(
                "Un jeton appartient à quelqu'un : le sujet est obligatoire."
            )
        return (provider_id, subject.strip())

    def save(self, token: StoredToken) -> None:
        """
        Enregistre les jetons d'une personne, chiffrés.

        Args:
            token: Les jetons à conserver.

        Raises:
            TokenStorageUnavailable: Si aucune clé n'est configurée. **Rien
                n'est écrit** dans ce cas ; c'est le sens du refus.
            ValueError: Si le sujet est vide ou le jeton d'accès absent.
        """
        require_encryption()
        if not (token.access_token or "").strip():
            raise ValueError("Jeton d'accès vide : rien à conserver.")

        cle = self._cle(token.provider_id, token.subject)
        secret = "\n".join([token.access_token, token.refresh_token or ""])
        chiffre = encryption.encrypt(secret)

        metadonnees = {
            "expires_at": token.expires_at,
            "obtained_at": token.obtained_at,
            "scopes": list(token.scopes),
        }
        with self._verrou:
            self._entrees[cle] = (metadonnees, chiffre)

    def get(self, provider_id: str, subject: str) -> Optional[StoredToken]:
        """
        Retourne les jetons d'une personne.

        Args:
            provider_id: Le fournisseur.
            subject: La personne.

        Returns:
            Les jetons, ou `None` s'il n'y en a pas.

        Raises:
            TokenStorageUnavailable: Si la clé est absente — le chiffré est là,
                mais il n'est pas lisible, et rendre `None` ferait croire que la
                personne n'a jamais accordé l'accès.
        """
        cle = self._cle(provider_id, subject)
        with self._verrou:
            entree = self._entrees.get(cle)
        if entree is None:
            return None

        require_encryption()
        metadonnees, chiffre = entree
        clair = encryption.decrypt(chiffre) or ""
        acces, _, rafraichissement = clair.partition("\n")

        return StoredToken(
            provider_id=provider_id,
            subject=cle[1],
            access_token=acces,
            refresh_token=rafraichissement or None,
            expires_at=metadonnees["expires_at"],
            scopes=list(metadonnees["scopes"]),
            obtained_at=metadonnees["obtained_at"],
        )

    def delete(self, provider_id: str, subject: str) -> bool:
        """
        Efface les jetons d'une personne.

        **Ne demande aucune clé.** Détruire un chiffré n'a jamais exigé de le
        lire, et un magasin incapable de vous oublier parce que sa clé est mal
        configurée serait la pire panne possible (VOLET 41).

        Args:
            provider_id: Le fournisseur.
            subject: La personne.

        Returns:
            True si quelque chose a été effacé.
        """
        cle = self._cle(provider_id, subject)
        with self._verrou:
            return self._entrees.pop(cle, None) is not None

    def state(
        self, provider_id: str, subject: str, now: Optional[float] = None
    ) -> AuthorizationState:
        """
        L'état d'autorisation d'une personne, sans déchiffrer.

        Les métadonnées suffisent à répondre, ce qui permet à une interface de
        montrer l'état sans jamais toucher au secret.

        Args:
            provider_id: Le fournisseur.
            subject: La personne.
            now: Horodatage, pour les tests.

        Returns:
            `NOT_AUTHORIZED`, `EXPIRED` ou `AUTHORIZED`.
        """
        cle = self._cle(provider_id, subject)
        with self._verrou:
            entree = self._entrees.get(cle)
        if entree is None:
            return AuthorizationState.NOT_AUTHORIZED

        expiration = entree[0]["expires_at"]
        if expiration is None:
            return AuthorizationState.AUTHORIZED
        instant = now or time.time()
        if instant + MARGE_D_EXPIRATION_SECONDES >= expiration:
            return AuthorizationState.EXPIRED
        return AuthorizationState.AUTHORIZED

    def subjects(self, provider_id: str) -> List[str]:
        """Les personnes ayant un accès conservé chez ce fournisseur, triées."""
        with self._verrou:
            return sorted(
                sujet for (fournisseur, sujet) in self._entrees
                if fournisseur == provider_id
            )

    def raw_entry(self, provider_id: str, subject: str) -> Optional[str]:
        """
        Retourne ce qui est **réellement conservé**, tel quel.

        Existe pour que les tests puissent vérifier qu'aucun jeton en clair ne
        traîne, sans avoir à croire le reste de ce module sur parole.
        """
        with self._verrou:
            entree = self._entrees.get(self._cle(provider_id, subject))
        return entree[1] if entree else None

    def report(self) -> Dict[str, Any]:
        """
        L'état du magasin, sans aucun jeton.

        Returns:
            Le décompte par fournisseur et l'état du chiffrement.
        """
        with self._verrou:
            fournisseurs: Dict[str, int] = {}
            for fournisseur, _ in self._entrees:
                fournisseurs[fournisseur] = fournisseurs.get(fournisseur, 0) + 1

        return {
            "entries": sum(fournisseurs.values()),
            "by_provider": fournisseurs,
            "encryption": {
                "variable": encryption.KEY_VARIABLE,
                "enabled": encryption.is_enabled(),
                "policy": (
                    "Obligatoire. Sans clé, l'écriture est refusée — jamais "
                    "dégradée en clair."
                ),
            },
        }
