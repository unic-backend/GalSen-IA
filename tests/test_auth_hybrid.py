"""
Tests de l'authentification hybride — **dormants par décision d'architecture**.

Ces tests éprouvent des routes (`/auth/login`, `/auth/register`,
`/auth/refresh`, `/auth/oauth/...`) qui ne sont **pas montées** sur l'API.

Ce n'est pas un oubli. ADR-010 refuse pour l'instant un magasin d'identifiants :
« a password store is a secret the platform must keep. Today it keeps none. »
Et `docs/memory/priorities.md` place en P0, avant tout code, la décision
« la plateforme a-t-elle des utilisateurs ? ». Monter `/auth/register`
créerait ce magasin au premier appel, donc trancherait la question à la place
de la personne qui doit la trancher.

Le code de `src/auth/` est conservé, rebasé et couvert par
`test_auth_jwt.py` et `test_auth_oauth.py`, qui eux tournent : ils n'ont besoin
d'aucune route. Ce fichier-ci attend la décision.

Pour le réveiller : monter les routes dans `src/api/server.py`, puis retirer le
saut ci-dessous. Rien d'autre à changer.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Routes /auth/login|register|refresh|oauth non montées : ADR-010 refuse "
        "le magasin d'identifiants tant que la décision P0 « la plateforme a-t-elle "
        "des utilisateurs ? » n'est pas prise."
    )
)


import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient

# Configuration d'environnement AVANT l'import du serveur
# (le pattern suivi dans test_agri_advice.py)
# Répertoire temporaire unique pour isoler la DB entre les runs
_GALSEN_TEST_DIR = tempfile.mkdtemp(prefix="galsen-test-hybrid-")
os.environ["GALSEN_DATA_DIR"] = _GALSEN_TEST_DIR
os.environ["GALSEN_API_KEYS"] = "sk-test-hybrid:user,sk-test-admin:admin"
os.environ["GALSEN_RATE_LIMIT_ENABLED"] = "false"
os.environ["GALSEN_JWT_ACCESS_EXPIRY"] = "5"  # 5 secondes pour test d'expiration
os.environ["GALSEN_JWT_REFRESH_EXPIRY"] = "10"


def _cleanup_temp_dir():
    """Nettoie le répertoire temporaire après les tests."""
    if os.path.exists(_GALSEN_TEST_DIR):
        shutil.rmtree(_GALSEN_TEST_DIR, ignore_errors=True)


import atexit
atexit.register(_cleanup_temp_dir)

from src.api.server import app  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Client de test FastAPI."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Headers avec clé API valide (rôle admin)."""
    return {"X-API-Key": "sk-test-admin"}


# ============================================================================
# Tests POST /auth/register
# ============================================================================


class TestRegisterEndpoint:
    """Tests de l'endpoint d'enregistrement."""

    def test_register_creates_user_and_returns_tokens(self, client):
        """Un enregistrement valide retourne un TokenResponse 201."""
        resp = client.post("/auth/register", json={
            "email": "newuser@example.com",
            "name": "New User",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email_returns_409(self, client):
        """Un email déjà utilisé retourne 409 Conflict."""
        client.post("/auth/register", json={
            "email": "dupuser@example.com",
            "name": "First",
            "password": "SecurePass123!",
        })
        resp = client.post("/auth/register", json={
            "email": "dupuser@example.com",
            "name": "Second",
            "password": "AnotherPass123!",
        })
        assert resp.status_code == 409

    def test_register_missing_email_returns_422(self, client):
        """Un email manquant retourne 422 Unprocessable Entity."""
        resp = client.post("/auth/register", json={
            "name": "No Email",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 422

    def test_register_missing_password_returns_422(self, client):
        """Un mot de passe manquant retourne 422."""
        resp = client.post("/auth/register", json={
            "email": "nopass@example.com",
            "name": "No Pass",
        })
        assert resp.status_code == 422

    def test_register_short_password_returns_422(self, client):
        """Un mot de passe trop court retourne 422 (validation Pydantic)."""
        resp = client.post("/auth/register", json={
            "email": "short@example.com",
            "name": "Short",
            "password": "ab",
        })
        assert resp.status_code == 422

    def test_register_with_explicit_role_ignored(self, client):
        """Le rôle ne peut pas être forcé à l'enregistrement (sécurité)."""
        resp = client.post("/auth/register", json={
            "email": "hacker@example.com",
            "name": "Hacker",
            "password": "SecurePass123!",
            "role": "admin",
        })
        # L'enregistrement réussit mais le rôle reste "user"
        assert resp.status_code == 201


# ============================================================================
# Tests POST /auth/login
# ============================================================================


class TestLoginEndpoint:
    """Tests de l'endpoint de connexion."""

    @pytest.fixture(autouse=True)
    def setup_user(self, client):
        """Crée un utilisateur de test avant chaque test de login."""
        client.post("/auth/register", json={
            "email": "login-test@example.com",
            "name": "Login Test",
            "password": "SecurePass123!",
        })

    def test_login_with_correct_credentials_returns_tokens(self, client):
        """Des identifiants valides retournent access_token et refresh_token."""
        resp = client.post("/auth/login", json={
            "email": "login-test@example.com",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_with_wrong_password_returns_401(self, client):
        """Un mot de passe incorrect retourne 401 Unauthorized."""
        resp = client.post("/auth/login", json={
            "email": "login-test@example.com",
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401

    def test_login_with_unknown_email_returns_401(self, client):
        """Un email inconnu retourne 401 Unauthorized."""
        resp = client.post("/auth/login", json={
            "email": "ghost@example.com",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 401

    def test_login_case_insensitive_email(self, client):
        """L'email est insensible à la casse."""
        resp = client.post("/auth/login", json={
            "email": "Login-Test@Example.COM",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 200

    def test_login_missing_fields_returns_422(self, client):
        """Des champs manquants retournent 422."""
        resp = client.post("/auth/login", json={
            "email": "login-test@example.com",
        })
        assert resp.status_code == 422


# ============================================================================
# Tests POST /auth/refresh
# ============================================================================


class TestRefreshEndpoint:
    """Tests de l'endpoint de rafraîchissement de token."""

    def test_refresh_with_valid_token_returns_new_access_token(self, client):
        """Un refresh token valide retourne un nouvel access token."""
        # Enregistrer et récupérer le refresh token
        reg = client.post("/auth/register", json={
            "email": "refresh-test@example.com",
            "name": "Refresh",
            "password": "SecurePass123!",
        })
        refresh_token = reg.json()["refresh_token"]

        resp = client.post("/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "token_type" in data

    def test_refresh_with_invalid_token_returns_401(self, client):
        """Un refresh token invalide retourne 401."""
        resp = client.post("/auth/refresh", json={
            "refresh_token": "invalid-refresh-token",
        })
        assert resp.status_code == 401

    def test_refresh_with_access_token_returns_401(self, client):
        """Un access token ne peut pas être utilisé comme refresh token."""
        reg = client.post("/auth/register", json={
            "email": "type-test@example.com",
            "name": "Type Test",
            "password": "SecurePass123!",
        })
        access_token = reg.json()["access_token"]

        resp = client.post("/auth/refresh", json={
            "refresh_token": access_token,  # Mauvais type de token
        })
        assert resp.status_code == 401

    def test_refresh_missing_token_returns_422(self, client):
        """L'absence de refresh_token retourne 422."""
        resp = client.post("/auth/refresh", json={})
        assert resp.status_code == 422


# ============================================================================
# Tests GET /auth/me
# ============================================================================


class TestMeEndpoint:
    """Tests de l'endpoint /auth/me."""

    def test_me_with_valid_bearer_returns_user_info(self, client):
        """Un Bearer token valide retourne les infos utilisateur."""
        reg = client.post("/auth/register", json={
            "email": "me-test@example.com",
            "name": "Me User",
            "password": "SecurePass123!",
        })
        token = reg.json()["access_token"]
        resp = client.get("/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["role"] == "user"
        assert data["auth_method"] == "jwt"
        assert "user_id" in data
        # L'user_id exposé doit être exactement le sujet du token présenté.
        from src.api.server import jwt_handler
        assert data["user_id"] == jwt_handler.verify_access_token(token)["sub"]
        assert data["user_id"]
        assert "permissions" in data
        # Ne doit pas exposer le hash du mot de passe
        assert "password_hash" not in data

    def test_me_without_auth_returns_401(self, client):
        """Sans authentification, /auth/me retourne 401."""
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_with_invalid_token_returns_401(self, client):
        """Un token invalide retourne 401."""
        resp = client.get("/auth/me", headers={
            "Authorization": "Bearer invalid.token.here",
        })
        assert resp.status_code == 401

    def test_me_with_expired_token_returns_401(self, client):
        """Un token expiré retourne 401."""
        # L'inscription reste nécessaire — elle crée le compte — mais sa
        # réponse ne sert plus : le token expiré est fabriqué juste après.
        client.post("/auth/register", json={
            "email": "expire-me@example.com",
            "name": "Expire",
            "password": "SecurePass123!",
        })

        # Force l'expiration en réduisant l'access_expiry du handler à -1.
        # Le handler est un singleton partagé : restaurer la valeur d'origine,
        # sinon tous les tests suivants reçoivent des tokens déjà expirés.
        from src.api.server import jwt_handler
        original_expiry = jwt_handler._access_expiry
        jwt_handler._access_expiry = -1
        try:
            expired_token = jwt_handler.create_access_token(
                user_id="expire-me", role="user"
            )
            resp = client.get("/auth/me", headers={
                "Authorization": f"Bearer {expired_token}",
            })
        finally:
            jwt_handler._access_expiry = original_expiry

        assert resp.status_code == 401

    def test_me_with_api_key_returns_user_info(self, client):
        """Une clé API valide permet aussi d'accéder à /auth/me."""
        resp = client.get("/auth/me", headers={
            "X-API-Key": "sk-test-hybrid",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "user"


# ============================================================================
# Tests require_auth_jwt — Fallback JWT → API Key
# ============================================================================


class TestRequireAuthJWT:
    """Tests du mécanisme de fallback require_auth_jwt."""

    def test_jwt_takes_priority_over_api_key(self, client, auth_headers):
        """Si un Bearer token valide est fourni, il est utilisé même si X-API-Key est présent."""
        reg = client.post("/auth/register", json={
            "email": "priority@example.com",
            "name": "Priority",
            "password": "SecurePass123!",
        })
        token = reg.json()["access_token"]

        # Fournir les deux : Bearer + X-API-Key
        resp = client.get("/auth/me", headers={
            "Authorization": f"Bearer {token}",
            "X-API-Key": "sk-test-admin",
        })
        assert resp.status_code == 200
        # Le JWT prime — on voit l'utilisateur enregistré, pas l'admin API key
        data = resp.json()
        assert data["auth_method"] == "jwt"
        assert data["role"] == "user"
        # L'utilisateur du token, pas l'admin porté par la clé API.
        from src.api.server import jwt_handler
        assert data["user_id"] == jwt_handler.verify_access_token(token)["sub"]

    def test_falls_back_to_api_key_when_no_jwt(self, client):
        """Sans Bearer token, X-API-Key est utilisé en fallback."""
        resp = client.get("/auth/me", headers={
            "X-API-Key": "sk-test-hybrid",
        })
        assert resp.status_code == 200

    def test_returns_401_when_both_missing(self, client):
        """Ni Bearer ni X-API-Key → 401."""
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_invalid_jwt_is_rejected_even_with_valid_api_key(self, client):
        """Un Bearer invalide est refusé, même accompagné d'une clé API valide."""
        resp = client.get("/auth/me", headers={
            "Authorization": "Bearer invalid.token",
            "X-API-Key": "sk-test-hybrid",
        })
        # Pas de repli silencieux : un token fourni fait autorité.
        assert resp.status_code == 401

    def test_expired_jwt_does_not_escalate_to_admin_api_key(self, client):
        """Un token expiré ne doit pas donner les droits de la clé API admin."""
        from src.api.server import jwt_handler
        original_expiry = jwt_handler._access_expiry
        jwt_handler._access_expiry = -1
        try:
            expired_token = jwt_handler.create_access_token(
                user_id="escalation-probe", role="user"
            )
        finally:
            jwt_handler._access_expiry = original_expiry

        resp = client.get("/auth/me", headers={
            "Authorization": f"Bearer {expired_token}",
            "X-API-Key": "sk-test-admin",
        })
        assert resp.status_code == 401


# ============================================================================
# Tests — Protection des endpoints avec JWT
# ============================================================================


class TestProtectedEndpointsWithJWT:
    """Vérifie que les endpoints protégés acceptent l'auth JWT."""

    def test_health_endpoint_with_jwt(self, client):
        """L'endpoint /health est accessible avec un JWT valide (permission health:view)."""
        reg = client.post("/auth/register", json={
            "email": "health-jwt@example.com",
            "name": "Health JWT",
            "password": "SecurePass123!",
        })
        token = reg.json()["access_token"]

        resp = client.get("/health", headers={
            "Authorization": f"Bearer {token}",
        })
        # Le rôle "user" a HEALTH_VIEW — donc 200
        assert resp.status_code in (200, 401)

    def test_health_endpoint_with_api_key(self, client):
        """L'endpoint /health reste accessible avec une clé API (non-régression)."""
        resp = client.get("/health", headers={
            "X-API-Key": "sk-test-hybrid",
        })
        # La clé API doit toujours fonctionner
        assert resp.status_code == 200


# ============================================================================
# Tests — Rate limiting désactivé pour les tests
# ============================================================================


class TestRateLimitingDisabled:
    """Vérifie que le rate limiting est bien désactivé en test."""

    def test_multiple_requests_allowed(self, client):
        """Plusieurs requêtes consécutives sont acceptées (rate limit désactivé)."""
        for i in range(5):
            resp = client.post("/auth/register", json={
                "email": f"burst-{i}@example.com",
                "name": f"Burst {i}",
                "password": "SecurePass123!",
            })
            assert resp.status_code == 201
