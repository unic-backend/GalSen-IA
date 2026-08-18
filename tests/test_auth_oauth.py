"""
Tests unitaires pour les providers OAuth et le UserManager.

Couvre : configuration OAuth (Google, GitHub, Microsoft), création d'URL
d'autorisation, échange de code, gestion des utilisateurs (création,
authentification, rôle, activation/désactivation).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.auth.oauth_providers import (
    OAuthUserInfo,
    GitHubOAuthProvider,
    GoogleOAuthProvider,
    MicrosoftOAuthProvider,
)
from src.auth.user_manager import UserManager
from src.storage.sqlite_user_store import SQLiteUserStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store():
    """Store SQLite en mémoire isolé."""
    return SQLiteUserStore(db_path=":memory:")


@pytest.fixture
def user_manager(store):
    """UserManager avec un store en mémoire."""
    return UserManager(store=store)


@pytest.fixture
def google_provider():
    """Provider Google avec variables d'environnement simulées."""
    with patch.dict(os.environ, {
        "GALSEN_GOOGLE_CLIENT_ID": "google-client-id-123",
        "GALSEN_GOOGLE_CLIENT_SECRET": "google-client-secret-abc",
    }):
        yield GoogleOAuthProvider()


@pytest.fixture
def github_provider():
    """Provider GitHub avec variables d'environnement simulées."""
    with patch.dict(os.environ, {
        "GALSEN_GITHUB_CLIENT_ID": "github-client-id-456",
        "GALSEN_GITHUB_CLIENT_SECRET": "github-client-secret-def",
    }):
        yield GitHubOAuthProvider()


@pytest.fixture
def microsoft_provider():
    """Provider Microsoft avec variables d'environnement simulées."""
    with patch.dict(os.environ, {
        "GALSEN_MICROSOFT_CLIENT_ID": "ms-client-id-789",
        "GALSEN_MICROSOFT_CLIENT_SECRET": "ms-client-secret-ghi",
    }):
        yield MicrosoftOAuthProvider()


# ============================================================================
# Tests OAuthUserInfo
# ============================================================================


class TestOAuthUserInfo:
    """Tests du dataclass OAuthUserInfo."""

    def test_create_oauth_user_info(self):
        """Création basique d'un OAuthUserInfo."""
        info = OAuthUserInfo(
            provider="google",
            oauth_id="12345",
            email="user@gmail.com",
            name="Test User",
        )
        assert info.provider == "google"
        assert info.oauth_id == "12345"
        assert info.email == "user@gmail.com"
        assert info.name == "Test User"
        assert info.avatar_url is None

    def test_create_oauth_user_info_with_avatar(self):
        """OAuthUserInfo avec URL d'avatar."""
        info = OAuthUserInfo(
            provider="github",
            oauth_id="67890",
            email="dev@github.com",
            name="Dev",
            avatar_url="https://avatars.example.com/1.png",
        )
        assert info.avatar_url == "https://avatars.example.com/1.png"


# ============================================================================
# Tests Provider — Configuration
# ============================================================================


class TestOAuthConfiguration:
    """Tests de vérification de configuration des providers."""

    def test_google_is_configured_when_env_set(self, google_provider):
        """Google est configuré si CLIENT_ID et CLIENT_SECRET sont définis."""
        assert google_provider.is_configured is True

    def test_google_is_not_configured_when_env_missing(self):
        """Google n'est pas configuré si les variables d'environnement manquent."""
        provider = GoogleOAuthProvider()
        # Les variables n'ont pas été patchées, donc None
        assert provider.is_configured is False

    def test_github_is_configured_when_env_set(self, github_provider):
        """GitHub est configuré si les variables sont définies."""
        assert github_provider.is_configured is True

    def test_github_is_not_configured_when_env_missing(self):
        """GitHub n'est pas configuré sans variables d'environnement."""
        with patch.dict(os.environ, {}, clear=True):
            provider = GitHubOAuthProvider()
            assert provider.is_configured is False

    def test_microsoft_is_configured_when_env_set(self, microsoft_provider):
        """Microsoft est configuré si les variables sont définies."""
        assert microsoft_provider.is_configured is True

    def test_microsoft_is_not_configured_when_env_missing(self):
        """Microsoft n'est pas configuré sans variables d'environnement."""
        with patch.dict(os.environ, {}, clear=True):
            provider = MicrosoftOAuthProvider()
            assert provider.is_configured is False


# ============================================================================
# Tests Provider — URL d'autorisation
# ============================================================================


class TestOAuthAuthorizationURL:
    """Tests de génération d'URL d'autorisation OAuth."""

    def test_google_authorization_url_contains_required_params(self, google_provider):
        """L'URL Google contient client_id, redirect_uri, response_type, scope."""
        url = google_provider.get_authorization_url(state="random-state")
        assert "accounts.google.com" in url
        assert "client_id=google-client-id-123" in url
        assert "response_type=code" in url
        assert "state=random-state" in url
        assert "scope=" in url

    def test_google_authorization_url_includes_redirect_uri(self):
        """L'URL Google encode le redirect_uri configuré au constructeur."""
        # Le redirect_uri est stocké au constructeur, pas passé à get_authorization_url
        from src.auth.oauth_providers import GoogleOAuthProvider
        provider = GoogleOAuthProvider(
            client_id="test-id",
            client_secret="test-secret",
            redirect_uri="http://localhost/callback",
        )
        url = provider.get_authorization_url(state="s1")
        assert "redirect_uri=http%3A%2F%2Flocalhost%2Fcallback" in url

    def test_github_authorization_url_contains_required_params(self, github_provider):
        """L'URL GitHub contient client_id, state, scope."""
        url = github_provider.get_authorization_url(state="gh-state")
        assert "github.com/login/oauth/authorize" in url
        assert "client_id=github-client-id-456" in url
        assert "state=gh-state" in url
        assert "scope=" in url

    def test_microsoft_authorization_url_contains_required_params(self, microsoft_provider):
        """L'URL Microsoft contient client_id, response_type, scope."""
        url = microsoft_provider.get_authorization_url(state="ms-state")
        assert "microsoftonline.com" in url or "live.com" in url or "microsoft.com" in url
        assert "client_id=ms-client-id-789" in url
        assert "response_type=code" in url
        assert "state=ms-state" in url


# ============================================================================
# Tests Provider — Échange de code (mocked HTTP)
# ============================================================================


class TestOAuthCodeExchange:
    """Tests de l'échange du code d'autorisation contre un token."""

    def test_google_exchange_code_returns_user_info(self, google_provider):
        """Google exchange_code retourne un OAuthUserInfo avec les bons champs."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            # Réponse token
            {"access_token": "ya29.test-token"},
            # Réponse userinfo
            {
                "sub": "g-12345",
                "email": "user@gmail.com",
                "name": "Google User",
                "picture": "https://example.com/avatar.jpg",
            },
        ]

        with patch("requests.post", return_value=mock_response):
            with patch("requests.get", return_value=mock_response):
                user = google_provider.exchange_code(code="auth-code-xyz")

        assert isinstance(user, OAuthUserInfo)
        assert user.provider == "google"
        assert user.oauth_id == "g-12345"
        assert user.email == "user@gmail.com"
        assert user.name == "Google User"
        assert user.avatar_url == "https://example.com/avatar.jpg"

    def test_google_exchange_code_handles_missing_picture(self, google_provider):
        """Google exchange_code gère l'absence de photo de profil."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {"access_token": "ya29.test-token"},
            {"sub": "g-999", "email": "noavatar@gmail.com", "name": "No Avatar"},
        ]

        with patch("requests.post", return_value=mock_response):
            with patch("requests.get", return_value=mock_response):
                user = google_provider.exchange_code(code="auth-code-xyz")

        assert user.email == "noavatar@gmail.com"
        assert user.avatar_url is None

    def test_github_exchange_code_returns_user_info(self, github_provider):
        """GitHub exchange_code retourne un OAuthUserInfo."""
        mock_post = MagicMock()
        mock_post.status_code = 200
        mock_post.json.return_value = {"access_token": "gho-test-token"}

        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {
            "id": 42,
            "email": "dev@github.com",
            "login": "devuser",
            "avatar_url": "https://avatars.githubusercontent.com/u/42",
            "name": "Dev User",
        }

        with patch("requests.post", return_value=mock_post):
            with patch("requests.get", return_value=mock_get):
                user = github_provider.exchange_code(code="gh-code")

        assert user.provider == "github"
        assert user.oauth_id == "42"
        assert user.email == "dev@github.com"
        assert user.name == "Dev User"

    def test_github_exchange_code_uses_login_as_fallback_name(self, github_provider):
        """GitHub utilise 'login' comme nom si 'name' est absent."""
        mock_post = MagicMock()
        mock_post.status_code = 200
        mock_post.json.return_value = {"access_token": "gho-test-token"}

        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {
            "id": 99,
            "email": "anon@github.com",
            "login": "anonuser",
            "avatar_url": "",
        }

        with patch("requests.post", return_value=mock_post):
            with patch("requests.get", return_value=mock_get):
                user = github_provider.exchange_code(code="gh-code")

        assert user.name == "anonuser"

    def test_microsoft_exchange_code_returns_user_info(self, microsoft_provider):
        """Microsoft exchange_code retourne un OAuthUserInfo."""
        mock_post = MagicMock()
        mock_post.status_code = 200
        mock_post.json.return_value = {"access_token": "EwB...test-token"}

        mock_get = MagicMock()
        mock_get.status_code = 200
        mock_get.json.return_value = {
            "id": "ms-uuid-123",
            "mail": "user@outlook.com",
            "displayName": "MS User",
        }

        with patch("requests.post", return_value=mock_post):
            with patch("requests.get", return_value=mock_get):
                user = microsoft_provider.exchange_code(code="ms-code")

        assert user.provider == "microsoft"
        assert user.oauth_id == "ms-uuid-123"
        assert user.email == "user@outlook.com"
        assert user.name == "MS User"


# ============================================================================
# Tests UserManager — Création d'utilisateurs
# ============================================================================


class TestUserManagerCreation:
    """Tests de création d'utilisateurs via UserManager."""

    def test_create_user_returns_user_with_id(self, user_manager):
        """create_user retourne un utilisateur avec un ID généré."""
        user = user_manager.create_user(
            email="alice@example.com",
            name="Alice",
            password="SecurePass123!",
        )
        assert user.id is not None
        assert len(user.id) > 0
        assert user.email == "alice@example.com"
        assert user.name == "Alice"
        assert user.role == "user"  # rôle par défaut

    def test_create_user_with_explicit_role(self, user_manager):
        """Le rôle peut être spécifié à la création."""
        user = user_manager.create_user(
            email="admin@example.com",
            name="Admin",
            password="AdminPass123!",
            role="admin",
        )
        assert user.role == "admin"

    def test_create_user_hashes_password(self, user_manager):
        """Le mot de passe est haché (pas stocké en clair)."""
        user = user_manager.create_user(
            email="bob@example.com",
            name="Bob",
            password="MyPassword123!",
        )
        assert user.password_hash != "MyPassword123!"
        assert user.password_hash.startswith("$2b$")  # bcrypt

    def test_create_user_defaults_to_active(self, user_manager):
        """Un nouvel utilisateur est actif par défaut."""
        user = user_manager.create_user(
            email="carol@example.com",
            name="Carol",
            password="CarolPass123!",
        )
        assert user.is_active is True

    def test_create_user_lowers_email(self, user_manager):
        """L'email est normalisé en minuscules."""
        user = user_manager.create_user(
            email="Alice@Example.COM",
            name="Alice",
            password="Pass123!",
        )
        assert user.email == "alice@example.com"

    def test_create_user_strips_email_whitespace(self, user_manager):
        """Les espaces autour de l'email sont supprimés."""
        user = user_manager.create_user(
            email="  dave@example.com  ",
            name="Dave",
            password="DavePass123!",
        )
        assert user.email == "dave@example.com"

    def test_create_user_sets_timestamps(self, user_manager):
        """Les timestamps created_at et updated_at sont définis."""
        user = user_manager.create_user(
            email="eve@example.com",
            name="Eve",
            password="EvePass123!",
        )
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_create_duplicate_email_raises(self, user_manager):
        """Deux utilisateurs avec le même email lèvent ValueError."""
        user_manager.create_user(
            email="dup@example.com",
            name="First",
            password="FirstPass123!",
        )
        with pytest.raises(ValueError, match="déjà"):
            user_manager.create_user(
                email="dup@example.com",
                name="Second",
                password="SecondPass123!",
            )

    def test_create_user_with_invalid_role_raises(self, user_manager):
        """Un rôle invalide lève ValueError."""
        with pytest.raises(ValueError, match="Rôle"):
            user_manager.create_user(
                email="bad@example.com",
                name="Bad Role",
                password="Pass123!",
                role="superadmin",
            )

    def test_create_user_with_short_password(self, user_manager):
        """Un mot de passe court est accepté (la validation est côté API)."""
        # Le UserManager n'impose pas de longueur minimale — la validation
        # est faite par Pydantic au niveau de l'API
        user = user_manager.create_user(
            email="short@example.com",
            name="Short",
            password="ab",
        )
        assert user is not None


# ============================================================================
# Tests UserManager — Authentification
# ============================================================================


class TestUserManagerAuthentication:
    """Tests d'authentification via UserManager."""

    def test_authenticate_user_returns_user_on_success(self, user_manager):
        """authenticate_user retourne l'utilisateur si le mot de passe est correct."""
        user_manager.create_user(
            email="auth@example.com",
            name="Auth User",
            password="CorrectPass123!",
        )
        user = user_manager.authenticate_user("auth@example.com", "CorrectPass123!")
        assert user is not None
        assert user.email == "auth@example.com"

    def test_authenticate_user_returns_none_on_wrong_password(self, user_manager):
        """authenticate_user retourne None si le mot de passe est incorrect."""
        user_manager.create_user(
            email="auth@example.com",
            name="Auth User",
            password="CorrectPass123!",
        )
        assert user_manager.authenticate_user("auth@example.com", "WrongPass!") is None

    def test_authenticate_user_returns_none_for_unknown_email(self, user_manager):
        """authenticate_user retourne None pour un email inexistant."""
        assert user_manager.authenticate_user("nobody@example.com", "AnyPass") is None

    def test_authenticate_user_returns_none_for_inactive_user(self, user_manager):
        """authenticate_user retourne None pour un utilisateur désactivé."""
        user = user_manager.create_user(
            email="inactive@example.com",
            name="Inactive",
            password="Pass123!",
        )
        user_manager.deactivate_user(user.id)
        assert (
            user_manager.authenticate_user("inactive@example.com", "Pass123!")
            is None
        )

    def test_authenticate_user_normalizes_email(self, user_manager):
        """L'email est normalisé avant la recherche (minuscules)."""
        user_manager.create_user(
            email="Mixed@Example.COM",
            name="Mixed",
            password="Pass123!",
        )
        user = user_manager.authenticate_user("mixed@example.com", "Pass123!")
        assert user is not None

    def test_authenticate_user_with_spaces_in_email(self, user_manager):
        """Les espaces autour de l'email sont ignorés."""
        user_manager.create_user(
            email="space@example.com",
            name="Space",
            password="Pass123!",
        )
        user = user_manager.authenticate_user("  space@example.com  ", "Pass123!")
        assert user is not None


# ============================================================================
# Tests UserManager — Recherche
# ============================================================================


class TestUserManagerLookup:
    """Tests de recherche d'utilisateurs."""

    def test_get_user_returns_user_by_id(self, user_manager):
        """get_user retourne l'utilisateur correspondant à l'ID."""
        created = user_manager.create_user(
            email="lookup@example.com",
            name="Lookup",
            password="Pass123!",
        )
        found = user_manager.get_user(created.id)
        assert found is not None
        assert found.id == created.id

    def test_get_user_returns_none_for_unknown_id(self, user_manager):
        """get_user retourne None pour un ID inexistant."""
        assert user_manager.get_user("nonexistent-id-12345") is None

    def test_get_user_by_email_returns_user(self, user_manager):
        """get_user_by_email retourne l'utilisateur correspondant."""
        user_manager.create_user(
            email="search@example.com",
            name="Search",
            password="Pass123!",
        )
        found = user_manager.get_user_by_email("search@example.com")
        assert found is not None
        assert found.name == "Search"

    def test_get_user_by_email_case_insensitive(self, user_manager):
        """get_user_by_email est insensible à la casse."""
        user_manager.create_user(
            email="Case@Example.COM",
            name="Case",
            password="Pass123!",
        )
        found = user_manager.get_user_by_email("CASE@example.com")
        assert found is not None

    def test_get_user_by_email_returns_none_for_unknown(self, user_manager):
        """get_user_by_email retourne None pour un email inconnu."""
        assert user_manager.get_user_by_email("ghost@example.com") is None


# ============================================================================
# Tests UserManager — OAuth
# ============================================================================


class TestUserManagerOAuth:
    """Tests de gestion des utilisateurs OAuth."""

    def test_create_oauth_user_creates_without_password(self, user_manager):
        """create_oauth_user crée un utilisateur sans mot de passe."""
        oauth_info = OAuthUserInfo(
            provider="google",
            oauth_id="g-123",
            email="oauth@example.com",
            name="OAuth User",
        )
        user = user_manager.create_oauth_user(
            email=oauth_info.email,
            provider=oauth_info.provider,
            oauth_id=oauth_info.oauth_id,
            name=oauth_info.name,
        )
        assert user.email == "oauth@example.com"
        assert user.oauth_provider == "google"
        assert user.oauth_id == "g-123"
        assert user.password_hash is None  # pas de mot de passe pour OAuth

    def test_create_oauth_user_sets_all_fields(self, user_manager):
        """create_oauth_user définit provider, oauth_id, nom, email."""
        oauth_info = OAuthUserInfo(
            provider="github",
            oauth_id="gh-456",
            email="ghuser@example.com",
            name="GitHub User",
            avatar_url="https://avatars.example.com/gh.png",
        )
        user = user_manager.create_oauth_user(
            email=oauth_info.email,
            provider=oauth_info.provider,
            oauth_id=oauth_info.oauth_id,
            name=oauth_info.name,
        )
        assert user.oauth_provider == "github"
        assert user.oauth_id == "gh-456"
        assert user.name == "GitHub User"

    def test_get_user_by_oauth_finds_existing(self, user_manager):
        """get_user_by_oauth retrouve un utilisateur par provider + oauth_id."""
        oauth_info = OAuthUserInfo(
            provider="microsoft",
            oauth_id="ms-789",
            email="msuser@example.com",
            name="MS User",
        )
        user_manager.create_oauth_user(
            email=oauth_info.email,
            provider=oauth_info.provider,
            oauth_id=oauth_info.oauth_id,
            name=oauth_info.name,
        )
        found = user_manager.get_user_by_oauth("microsoft", "ms-789")
        assert found is not None
        assert found.email == "msuser@example.com"

    def test_get_user_by_oauth_returns_none_for_unknown(self, user_manager):
        """get_user_by_oauth retourne None pour une combinaison inconnue."""
        assert user_manager.get_user_by_oauth("google", "unknown-id") is None

    def test_create_oauth_user_links_to_existing_email(self, user_manager):
        """create_oauth_user rattache l'identité OAuth à un compte email existant."""
        existing = user_manager.create_user(
            email="existing@example.com",
            name="Existing",
            password="Pass123!",
        )
        oauth_info = OAuthUserInfo(
            provider="google",
            oauth_id="g-new",
            email="existing@example.com",
            name="New OAuth",
        )
        linked = user_manager.create_oauth_user(
            email=oauth_info.email,
            provider=oauth_info.provider,
            oauth_id=oauth_info.oauth_id,
            name=oauth_info.name,
        )
        # Aucun doublon : le compte existant est enrichi, pas remplacé.
        assert linked.id == existing.id
        assert linked.oauth_provider == "google"
        assert linked.oauth_id == "g-new"
        assert len(user_manager.list_users()) == 1


# ============================================================================
# Tests UserManager — Gestion du compte
# ============================================================================


class TestUserManagerAccount:
    """Tests de gestion du compte utilisateur."""

    def test_change_password_changes_hash(self, user_manager):
        """change_password change le hash du mot de passe."""
        user = user_manager.create_user(
            email="pwd@example.com",
            name="Pwd User",
            password="OldPass123!",
        )
        original_hash = user.password_hash
        user_manager.change_password(user.id, "OldPass123!", "NewPass456!")
        updated = user_manager.get_user(user.id)
        assert updated.password_hash != original_hash

    def test_change_password_old_password_stops_working(self, user_manager):
        """L'ancien mot de passe ne fonctionne plus après changement."""
        user = user_manager.create_user(
            email="pwd2@example.com",
            name="Pwd2",
            password="OldPass123!",
        )
        user_manager.change_password(user.id, "OldPass123!", "NewPass456!")
        assert (
            user_manager.authenticate_user("pwd2@example.com", "OldPass123!")
            is None
        )
        assert (
            user_manager.authenticate_user("pwd2@example.com", "NewPass456!")
            is not None
        )

    def test_change_role_changes_role(self, user_manager):
        """change_role change le rôle de l'utilisateur."""
        user = user_manager.create_user(
            email="role@example.com",
            name="Role User",
            password="Pass123!",
            role="user",
        )
        user_manager.change_role(user.id, "admin")
        updated = user_manager.get_user(user.id)
        assert updated.role == "admin"

    def test_change_role_with_invalid_role_raises(self, user_manager):
        """change_role lève ValueError pour un rôle invalide."""
        user = user_manager.create_user(
            email="badrole@example.com",
            name="Bad Role",
            password="Pass123!",
        )
        with pytest.raises(ValueError, match="Rôle"):
            user_manager.change_role(user.id, "superadmin")

    def test_change_role_for_unknown_user_raises(self, user_manager):
        """change_role lève ValueError pour un utilisateur inexistant."""
        with pytest.raises(ValueError, match="introuvable"):
            user_manager.change_role("ghost-id", "admin")

    def test_update_user_modifies_fields(self, user_manager):
        """update_user modifie les champs de l'utilisateur."""
        user = user_manager.create_user(
            email="update@example.com",
            name="Before",
            password="Pass123!",
        )
        user.name = "After"
        user_manager.update_user(user)
        updated = user_manager.get_user(user.id)
        assert updated.name == "After"

    def test_deactivate_user_flags_as_inactive(self, user_manager):
        """deactivate_user passe is_active à False."""
        user = user_manager.create_user(
            email="deact@example.com",
            name="Deact",
            password="Pass123!",
        )
        user_manager.deactivate_user(user.id)
        updated = user_manager.get_user(user.id)
        assert updated.is_active is False

    def test_reactivate_user_restores_active_flag(self, user_manager):
        """reactivate_user peut réactiver un utilisateur désactivé."""
        user = user_manager.create_user(
            email="react@example.com",
            name="React",
            password="Pass123!",
        )
        user_manager.deactivate_user(user.id)
        user_manager.reactivate_user(user.id)
        updated = user_manager.get_user(user.id)
        assert updated.is_active is True

    def test_delete_user_removes_from_store(self, user_manager):
        """delete_user supprime l'utilisateur du store."""
        user = user_manager.create_user(
            email="del@example.com",
            name="Delete Me",
            password="Pass123!",
        )
        user_manager.delete_user(user.id)
        assert user_manager.get_user(user.id) is None

    def test_list_users_returns_all(self, user_manager):
        """list_users retourne tous les utilisateurs."""
        user_manager.create_user(email="a@ex.com", name="A", password="Pa$$w0rd1!")
        user_manager.create_user(email="b@ex.com", name="B", password="Pa$$w0rd2!")
        users = user_manager.list_users()
        assert len(users) == 2

    def test_list_users_empty_initial(self, user_manager):
        """list_users retourne une liste vide au départ."""
        assert user_manager.list_users() == []

    def test_change_password_for_unknown_user_raises(self, user_manager):
        """change_password lève ValueError pour un utilisateur inexistant."""
        with pytest.raises(ValueError, match="introuvable"):
            user_manager.change_password("ghost-id", "OldPass123!", "NewPass!")
