"""
Gestionnaire JWT (JSON Web Token) pour GalSen IA.

Génération et vérification de tokens HS256 avec expiration configurable.
Supporte les access tokens (courte durée) et refresh tokens (longue durée).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

logger = logging.getLogger(__name__)


class SecretAbsent(RuntimeError):
    """Le secret de signature manque ou est trop faible pour être utilisé."""


def _secret_configure() -> str:
    """
    Lit le secret de signature **au moment de la construction**.

    Le lire une fois à l'import serait un piège : un exploitant qui charge son
    `.env` après l'import de ce module — ce que fait tout lanceur qui importe
    l'application avant de configurer l'environnement — obtiendrait un 503
    inexplicable, la variable étant pourtant posée.

    Returns:
        Le secret courant, ou la valeur lue à l'import si l'environnement n'en
        porte plus (chemin emprunté par les tests qui la remplacent).
    """
    return os.environ.get("GALSEN_JWT_SECRET") or _JWT_SECRET

# ---------------------------------------------------------------------------
# Configuration — variables d'environnement
# ---------------------------------------------------------------------------

# **Aucun secret par défaut.** La version précédente en portait un, écrit dans
# le dépôt, et se contentait d'avertir : un déploiement qui oubliait la variable
# signait donc ses jetons avec une valeur publique, et n'importe qui pouvait
# forger un jeton d'administrateur. Un avertissement dans un journal n'arrête
# personne. La règle du dépôt est explicite — « NEVER hardcode credentials in
# the source code » — et ADR-004 veut les identifiants dans l'environnement.
#
# Sans secret, aucun jeton n'est émis ni accepté : les routes d'authentification
# rapportent leur indisponibilité, ce qui est le comportement que la plateforme
# applique partout ailleurs à une capacité non configurée.
#: Valeur de repli, lue à l'import. Elle existe pour être **remplacée dans un
#: test** (`monkeypatch.setattr`) ; le chemin normal relit l'environnement à
#: chaque construction, voir `_secret_configure()`.
_JWT_SECRET = os.environ.get("GALSEN_JWT_SECRET") or ""

#: Longueur minimale du secret. HS256 signe avec une clé arbitraire : un secret
#: court est devinable, et la bibliothèque ne s'y oppose pas.
LONGUEUR_MINIMALE_DU_SECRET = 32
_JWT_ALGORITHM = "HS256"
_JWT_ACCESS_EXPIRY = int(os.environ.get("GALSEN_JWT_ACCESS_EXPIRY", "3600"))  # 1 heure
_JWT_REFRESH_EXPIRY = int(os.environ.get("GALSEN_JWT_REFRESH_EXPIRY", "604800"))  # 7 jours


class JWTHandler:
    """Générateur et vérificateur de tokens JWT HS256.

    Usage :
        handler = JWTHandler()
        token = handler.create_access_token(user_id="u1", role="user")
        payload = handler.verify_token(token)   # → {"user_id": "u1", "role": "user"}
    """

    def __init__(
        self,
        secret: Optional[str] = None,
        algorithm: str = _JWT_ALGORITHM,
        access_expiry: int = _JWT_ACCESS_EXPIRY,
        refresh_expiry: int = _JWT_REFRESH_EXPIRY,
    ) -> None:
        self._secret = secret or _secret_configure()
        self._algorithm = algorithm
        self._access_expiry = access_expiry
        self._refresh_expiry = refresh_expiry
        if not self._secret:
            raise SecretAbsent(
                "Aucun secret de signature. Renseignez GALSEN_JWT_SECRET avec "
                "au moins "
                f"{LONGUEUR_MINIMALE_DU_SECRET} caractères aléatoires "
                "(`python -c \"import secrets; print(secrets.token_urlsafe(48))\"`). "
                "Aucune valeur par défaut n'est fournie : elle serait publique."
            )
        if len(self._secret) < LONGUEUR_MINIMALE_DU_SECRET:
            raise SecretAbsent(
                f"Secret de signature trop court ({len(self._secret)} caractères) : "
                f"{LONGUEUR_MINIMALE_DU_SECRET} au minimum. Un secret devinable "
                f"laisse forger des jetons d'administrateur."
            )

    @property
    def access_expiry(self) -> int:
        """Durée de validité d'un jeton d'accès, en secondes.

        Exposée parce que l'API la rend dans `expires_in` : sans elle,
        l'appelant lirait un attribut privé, et un renommage interne casserait
        le contrat de la route sans que rien ne le signale.
        """
        return self._access_expiry

    # ------------------------------------------------------------------
    # Création de tokens
    # ------------------------------------------------------------------

    def create_access_token(
        self, user_id: str, role: str = "user", **extra_claims: Any
    ) -> str:
        """Crée un access token JWT avec expiration courte.

        Args:
            user_id: Identifiant unique de l'utilisateur.
            role: Rôle RBAC (user, operator, admin, readonly).
            **extra_claims: Claims supplémentaires à inclure dans le payload.

        Returns:
            Token JWT encodé (str).
        """
        now = int(time.time())
        payload = {
            "sub": user_id,
            "role": role,
            "iat": now,
            "exp": now + self._access_expiry,
            "type": "access",
            **extra_claims,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        """Crée un refresh token JWT avec expiration longue.

        Args:
            user_id: Identifiant unique de l'utilisateur.

        Returns:
            Refresh token JWT encodé (str).
        """
        now = int(time.time())
        payload = {
            "sub": user_id,
            "iat": now,
            "exp": now + self._refresh_expiry,
            "type": "refresh",
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    # ------------------------------------------------------------------
    # Vérification
    # ------------------------------------------------------------------

    def verify_token(self, token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
        """Vérifie un token JWT et retourne son payload décodé.

        Args:
            token: Token JWT à vérifier.
            expected_type: Si fourni, vérifie que le champ 'type' correspond.

        Returns:
            Payload décodé du token.

        Raises:
            ValueError: Token invalide, expiré ou type inattendu.
        """
        if not token:
            raise ValueError("Token JWT manquant.")

        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except ExpiredSignatureError:
            raise ValueError("Token JWT expiré.")
        except InvalidTokenError as e:
            raise ValueError(f"Token JWT invalide : {e}")

        if expected_type and payload.get("type") != expected_type:
            raise ValueError(
                f"Type de token inattendu : attendu '{expected_type}', "
                f"reçu '{payload.get('type')}'"
            )

        return payload

    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """Vérifie un access token et retourne son payload."""
        return self.verify_token(token, expected_type="access")

    def verify_refresh_token(self, token: str) -> Dict[str, Any]:
        """Vérifie un refresh token et retourne son payload."""
        return self.verify_token(token, expected_type="refresh")

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def token_user_id(self, payload: Dict[str, Any]) -> str:
        """Extrait l'identifiant utilisateur du payload décodé."""
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Payload sans champ 'sub' (user_id).")
        return user_id

    def token_role(self, payload: Dict[str, Any]) -> str:
        """Extrait le rôle du payload décodé (défaut : 'user')."""
        return payload.get("role", "user")
