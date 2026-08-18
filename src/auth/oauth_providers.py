"""
Fournisseurs OAuth2 pour GalSen IA.

Implémente le flux Authorization Code pour Google, GitHub et Microsoft.
Chaque fournisseur expose deux méthodes :
- get_authorization_url() → URL de redirection vers le fournisseur
- exchange_code(code) → dict avec les informations utilisateur
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration de base — variables d'environnement
# ---------------------------------------------------------------------------

_BASE_URL = os.environ.get("GALSEN_BASE_URL", "http://localhost:8000")
_REDIRECT_PATH = "/auth/oauth/callback"


@dataclass
class OAuthUserInfo:
    """Informations utilisateur normalisées extraites d'un fournisseur OAuth."""

    provider: str
    oauth_id: str
    email: str
    name: str
    avatar_url: Optional[str] = None


def _default_redirect_uri() -> str:
    """Construit l'URI de redirection OAuth à partir de la configuration."""
    return f"{_BASE_URL.rstrip('/')}{_REDIRECT_PATH}"


# ======================================================================
# Fournisseur Google
# ======================================================================


class GoogleOAuthProvider:
    """Flux OAuth2 Google.

    Variables d'environnement requises :
    - GALSEN_GOOGLE_CLIENT_ID
    - GALSEN_GOOGLE_CLIENT_SECRET
    """

    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    SCOPE = "openid email profile"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ) -> None:
        self.client_id = client_id or os.environ.get("GALSEN_GOOGLE_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("GALSEN_GOOGLE_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or _default_redirect_uri()

    @property
    def is_configured(self) -> bool:
        """Vérifie que les credentials OAuth sont configurés."""
        return bool(self.client_id and self.client_secret)

    def get_authorization_url(self, state: str = "") -> str:
        """Retourne l'URL d'autorisation Google.

        Args:
            state: Jeton anti-CSRF à inclure dans l'URL.

        Returns:
            URL complète vers la page de consentement Google.

        Raises:
            ValueError: Si le fournisseur n'est pas configuré.
        """
        if not self.is_configured:
            raise ValueError("Google OAuth non configuré (client_id ou client_secret manquant).")

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.SCOPE,
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> OAuthUserInfo:
        """Échange un code d'autorisation contre des informations utilisateur.

        Args:
            code: Code d'autorisation reçu du callback Google.

        Returns:
            OAuthUserInfo normalisé.

        Raises:
            ValueError: Si l'échange échoue.
        """
        if not self.is_configured:
            raise ValueError("Google OAuth non configuré.")

        # Échange du code contre un token
        token_resp = requests.post(
            self.TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
            },
            timeout=15,
        )
        if token_resp.status_code != 200:
            logger.error("Échec échange token Google : %s", token_resp.text)
            raise ValueError(f"Échange token Google échoué (HTTP {token_resp.status_code}).")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("Access token absent de la réponse Google.")

        # Récupération des infos utilisateur
        user_resp = requests.get(
            self.USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if user_resp.status_code != 200:
            logger.error("Échec userinfo Google : %s", user_resp.text)
            raise ValueError(f"Userinfo Google échoué (HTTP {user_resp.status_code}).")

        user_data = user_resp.json()
        return OAuthUserInfo(
            provider="google",
            oauth_id=user_data.get("sub", ""),
            email=user_data.get("email", ""),
            name=user_data.get("name", ""),
            avatar_url=user_data.get("picture"),
        )


# ======================================================================
# Fournisseur GitHub
# ======================================================================


class GitHubOAuthProvider:
    """Flux OAuth2 GitHub.

    Variables d'environnement requises :
    - GALSEN_GITHUB_CLIENT_ID
    - GALSEN_GITHUB_CLIENT_SECRET
    """

    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USERINFO_URL = "https://api.github.com/user"
    EMAILS_URL = "https://api.github.com/user/emails"
    SCOPE = "user:email"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ) -> None:
        self.client_id = client_id or os.environ.get("GALSEN_GITHUB_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("GALSEN_GITHUB_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or _default_redirect_uri()

    @property
    def is_configured(self) -> bool:
        """Vérifie que les credentials OAuth sont configurés."""
        return bool(self.client_id and self.client_secret)

    def get_authorization_url(self, state: str = "") -> str:
        """Retourne l'URL d'autorisation GitHub.

        Args:
            state: Jeton anti-CSRF à inclure dans l'URL.

        Returns:
            URL complète vers la page de consentement GitHub.

        Raises:
            ValueError: Si le fournisseur n'est pas configuré.
        """
        if not self.is_configured:
            raise ValueError("GitHub OAuth non configuré (client_id ou client_secret manquant).")

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.SCOPE,
        }
        if state:
            params["state"] = state
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> OAuthUserInfo:
        """Échange un code d'autorisation contre des informations utilisateur.

        Args:
            code: Code d'autorisation reçu du callback GitHub.

        Returns:
            OAuthUserInfo normalisé.

        Raises:
            ValueError: Si l'échange échoue.
        """
        if not self.is_configured:
            raise ValueError("GitHub OAuth non configuré.")

        # Échange du code contre un token
        token_resp = requests.post(
            self.TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=15,
        )
        if token_resp.status_code != 200:
            logger.error("Échec échange token GitHub : %s", token_resp.text)
            raise ValueError(f"Échange token GitHub échoué (HTTP {token_resp.status_code}).")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("Access token absent de la réponse GitHub.")

        # Récupération des infos utilisateur
        user_resp = requests.get(
            self.USERINFO_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=15,
        )
        if user_resp.status_code != 200:
            logger.error("Échec userinfo GitHub : %s", user_resp.text)
            raise ValueError(f"Userinfo GitHub échoué (HTTP {user_resp.status_code}).")

        user_data = user_resp.json()
        email = user_data.get("email", "")

        # Si l'email est privé, le récupérer via l'API emails
        if not email:
            email = self._fetch_primary_email(access_token)

        return OAuthUserInfo(
            provider="github",
            oauth_id=str(user_data.get("id", "")),
            email=email,
            name=user_data.get("name") or user_data.get("login", ""),
            avatar_url=user_data.get("avatar_url"),
        )

    def _fetch_primary_email(self, access_token: str) -> str:
        """Récupère l'email primaire GitHub quand il est privé."""
        try:
            resp = requests.get(
                self.EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                emails = resp.json()
                for entry in emails:
                    if entry.get("primary") and entry.get("verified"):
                        return entry.get("email", "")
        except Exception:
            logger.warning("Impossible de récupérer les emails GitHub.", exc_info=True)
        return ""


# ======================================================================
# Fournisseur Microsoft (Azure AD)
# ======================================================================


class MicrosoftOAuthProvider:
    """Flux OAuth2 Microsoft (Azure AD / Entra ID).

    Variables d'environnement requises :
    - GALSEN_MICROSOFT_CLIENT_ID
    - GALSEN_MICROSOFT_CLIENT_SECRET
    - GALSEN_MICROSOFT_TENANT (optionnel, défaut : 'common')
    """

    SCOPE = "openid email profile User.Read"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        tenant: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ) -> None:
        self.client_id = client_id or os.environ.get("GALSEN_MICROSOFT_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("GALSEN_MICROSOFT_CLIENT_SECRET", "")
        self.tenant = tenant or os.environ.get("GALSEN_MICROSOFT_TENANT", "common")
        self.redirect_uri = redirect_uri or _default_redirect_uri()

    @property
    def is_configured(self) -> bool:
        """Vérifie que les credentials OAuth sont configurés."""
        return bool(self.client_id and self.client_secret)

    @property
    def _base_url(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant}"

    @property
    def authorize_url(self) -> str:
        return f"{self._base_url}/oauth2/v2.0/authorize"

    @property
    def token_url(self) -> str:
        return f"{self._base_url}/oauth2/v2.0/token"

    @property
    def userinfo_url(self) -> str:
        return "https://graph.microsoft.com/v1.0/me"

    def get_authorization_url(self, state: str = "") -> str:
        """Retourne l'URL d'autorisation Microsoft.

        Args:
            state: Jeton anti-CSRF à inclure dans l'URL.

        Returns:
            URL complète vers la page de consentement Microsoft.

        Raises:
            ValueError: Si le fournisseur n'est pas configuré.
        """
        if not self.is_configured:
            raise ValueError(
                "Microsoft OAuth non configuré (client_id ou client_secret manquant)."
            )

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.SCOPE,
            "response_mode": "query",
        }
        if state:
            params["state"] = state
        return f"{self.authorize_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> OAuthUserInfo:
        """Échange un code d'autorisation contre des informations utilisateur.

        Args:
            code: Code d'autorisation reçu du callback Microsoft.

        Returns:
            OAuthUserInfo normalisé.

        Raises:
            ValueError: Si l'échange échoue.
        """
        if not self.is_configured:
            raise ValueError("Microsoft OAuth non configuré.")

        # Échange du code contre un token
        token_resp = requests.post(
            self.token_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "scope": self.SCOPE,
            },
            timeout=15,
        )
        if token_resp.status_code != 200:
            logger.error("Échec échange token Microsoft : %s", token_resp.text)
            raise ValueError(f"Échange token Microsoft échoué (HTTP {token_resp.status_code}).")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("Access token absent de la réponse Microsoft.")

        # Récupération des infos utilisateur via Microsoft Graph
        user_resp = requests.get(
            self.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if user_resp.status_code != 200:
            logger.error("Échec userinfo Microsoft Graph : %s", user_resp.text)
            raise ValueError(f"Userinfo Microsoft échoué (HTTP {user_resp.status_code}).")

        user_data = user_resp.json()
        return OAuthUserInfo(
            provider="microsoft",
            oauth_id=user_data.get("id", ""),
            email=user_data.get("mail") or user_data.get("userPrincipalName", ""),
            name=user_data.get("displayName", ""),
        )


# ======================================================================
# Registre des fournisseurs
# ======================================================================


_OAUTH_PROVIDER_CLASSES: Dict[str, type] = {
    "google": GoogleOAuthProvider,
    "github": GitHubOAuthProvider,
    "microsoft": MicrosoftOAuthProvider,
}


def get_oauth_provider(name: str) -> Optional[object]:
    """Retourne une instance du fournisseur OAuth demandé, ou None si non configuré.

    Args:
        name: Nom du fournisseur ('google', 'github', 'microsoft').

    Returns:
        Instance du fournisseur, ou None si la classe est inconnue.
    """
    cls = _OAUTH_PROVIDER_CLASSES.get(name.lower())
    if cls is None:
        return None
    return cls()


def get_configured_providers() -> Dict[str, object]:
    """Retourne tous les fournisseurs OAuth qui sont configurés.

    Returns:
        Dictionnaire {nom: instance} des fournisseurs prêts à l'emploi.
    """
    configured: Dict[str, object] = {}
    for name, cls in _OAUTH_PROVIDER_CLASSES.items():
        instance = cls()
        if instance.is_configured:
            configured[name] = instance
    return configured
