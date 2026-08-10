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

# ---------------------------------------------------------------------------
# Configuration — variables d'environnement
# ---------------------------------------------------------------------------

_JWT_SECRET = os.environ.get("GALSEN_JWT_SECRET", "gal-sen-ia-dev-secret-change-me-32b")
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
        self._secret = secret or _JWT_SECRET
        self._algorithm = algorithm
        self._access_expiry = access_expiry
        self._refresh_expiry = refresh_expiry
        if self._secret == "gal-sen-ia-dev-secret-change-me-32b":
            logger.warning(
                "JWT secret par défaut utilisé. "
                "Définissez GALSEN_JWT_SECRET en production."
            )

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
