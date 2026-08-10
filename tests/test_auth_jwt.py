"""
Tests unitaires pour le gestionnaire JWT et le gestionnaire de sessions.

Couvre : création de tokens, vérification, expiration, types de tokens,
sessions utilisateur (création, expiration, nettoyage, rafraîchissement).
"""

from __future__ import annotations

import time

import pytest

from src.auth.jwt_handler import JWTHandler
from src.auth.session_manager import Session, SessionManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def jwt_handler():
    """JWT handler avec un secret de test et une expiration courte (2s)."""
    return JWTHandler(
        secret="test-secret-key-for-jwt-unit-tests-32ch",
        access_expiry=2,
        refresh_expiry=10,
    )


@pytest.fixture
def session_manager():
    """Session manager avec un TTL court (2s) pour les tests d'expiration."""
    return SessionManager(session_ttl=2)


# ============================================================================
# Tests JWTHandler — Création de tokens
# ============================================================================


class TestJWTCreation:
    """Tests de création d'access tokens et refresh tokens."""

    def test_create_access_token_returns_string(self, jwt_handler):
        """Un access token doit être une chaîne non vide."""
        token = jwt_handler.create_access_token(user_id="u1", role="user")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_encodes_user_id_in_sub(self, jwt_handler):
        """Le user_id doit être dans le claim 'sub' du token."""
        token = jwt_handler.create_access_token(user_id="alice", role="admin")
        payload = jwt_handler.verify_token(token)
        assert payload["sub"] == "alice"
        assert payload["role"] == "admin"

    def test_create_access_token_sets_token_type_access(self, jwt_handler):
        """Le type de token doit être 'access'."""
        token = jwt_handler.create_access_token(user_id="u1")
        payload = jwt_handler.verify_token(token)
        assert payload["type"] == "access"

    def test_create_access_token_role_defaults_to_user(self, jwt_handler):
        """Le rôle par défaut est 'user' si non spécifié."""
        token = jwt_handler.create_access_token(user_id="u1")
        payload = jwt_handler.verify_token(token)
        assert payload["role"] == "user"

    def test_create_access_token_with_extra_claims(self, jwt_handler):
        """Les claims supplémentaires sont inclus dans le payload."""
        token = jwt_handler.create_access_token(
            user_id="u1", role="operator", email="op@example.com", tenant="senegal"
        )
        payload = jwt_handler.verify_token(token)
        assert payload["email"] == "op@example.com"
        assert payload["tenant"] == "senegal"

    def test_create_refresh_token_returns_string(self, jwt_handler):
        """Un refresh token doit être une chaîne non vide."""
        token = jwt_handler.create_refresh_token(user_id="u1")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token_sets_token_type_refresh(self, jwt_handler):
        """Le type de token doit être 'refresh'."""
        token = jwt_handler.create_refresh_token(user_id="u1")
        payload = jwt_handler.verify_token(token)
        assert payload["type"] == "refresh"

    def test_create_refresh_token_has_no_role(self, jwt_handler):
        """Un refresh token ne contient pas de claim 'role' (pas nécessaire)."""
        token = jwt_handler.create_refresh_token(user_id="u1")
        payload = jwt_handler.verify_token(token)
        assert "role" not in payload


# ============================================================================
# Tests JWTHandler — Vérification de tokens
# ============================================================================


class TestJWTVerification:
    """Tests de vérification des tokens (valides, invalides, expirés)."""

    def test_verify_valid_token(self, jwt_handler):
        """Un token valide est décodé sans erreur."""
        token = jwt_handler.create_access_token(user_id="u1")
        payload = jwt_handler.verify_token(token)
        assert payload["sub"] == "u1"

    def test_verify_token_without_expected_type(self, jwt_handler):
        """Sans expected_type, tout token valide est accepté."""
        token = jwt_handler.create_refresh_token(user_id="u1")
        payload = jwt_handler.verify_token(token)
        assert payload["type"] == "refresh"

    def test_verify_token_with_correct_expected_type(self, jwt_handler):
        """Avec expected_type='access', un access token passe."""
        token = jwt_handler.create_access_token(user_id="u1")
        payload = jwt_handler.verify_token(token, expected_type="access")
        assert payload["type"] == "access"

    def test_verify_token_with_wrong_expected_type_raises(self, jwt_handler):
        """Avec expected_type='access', un refresh token lève ValueError."""
        token = jwt_handler.create_refresh_token(user_id="u1")
        with pytest.raises(ValueError, match="Type de token inattendu"):
            jwt_handler.verify_token(token, expected_type="access")

    def test_verify_empty_token_raises(self, jwt_handler):
        """Un token vide lève ValueError."""
        with pytest.raises(ValueError, match="Token JWT manquant"):
            jwt_handler.verify_token("")

    def test_verify_none_token_raises(self, jwt_handler):
        """Un token None lève ValueError."""
        with pytest.raises(ValueError, match="Token JWT manquant"):
            jwt_handler.verify_token(None)

    def test_verify_tampered_token_raises(self, jwt_handler):
        """Un token modifié (payload altéré) lève ValueError."""
        token = jwt_handler.create_access_token(user_id="u1")
        # Modifier les 5 derniers caractères du token
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(ValueError, match="Token JWT invalide"):
            jwt_handler.verify_token(tampered)

    def test_verify_token_with_wrong_secret_raises(self, jwt_handler):
        """Un token signé avec un secret différent lève ValueError."""
        other_handler = JWTHandler(
            secret="other-secret-key-for-testing-only---"
        )
        token = other_handler.create_access_token(user_id="u1")
        with pytest.raises(ValueError, match="Token JWT invalide"):
            jwt_handler.verify_token(token)

    def test_verify_access_token_method(self, jwt_handler):
        """verify_access_token vérifie un access token."""
        token = jwt_handler.create_access_token(user_id="u1")
        payload = jwt_handler.verify_access_token(token)
        assert payload["sub"] == "u1"

    def test_verify_access_token_rejects_refresh(self, jwt_handler):
        """verify_access_token rejette un refresh token."""
        token = jwt_handler.create_refresh_token(user_id="u1")
        with pytest.raises(ValueError):
            jwt_handler.verify_access_token(token)

    def test_verify_refresh_token_method(self, jwt_handler):
        """verify_refresh_token vérifie un refresh token."""
        token = jwt_handler.create_refresh_token(user_id="u1")
        payload = jwt_handler.verify_refresh_token(token)
        assert payload["sub"] == "u1"

    def test_verify_refresh_token_rejects_access(self, jwt_handler):
        """verify_refresh_token rejette un access token."""
        token = jwt_handler.create_access_token(user_id="u1")
        with pytest.raises(ValueError):
            jwt_handler.verify_refresh_token(token)


# ============================================================================
# Tests JWTHandler — Expiration
# ============================================================================


class TestJWTExpiration:
    """Tests de comportement à l'expiration des tokens."""

    def test_verify_expired_token_raises(self, jwt_handler):
        """Un token expiré lève ValueError."""
        token = jwt_handler.create_access_token(user_id="u1")
        # Avance le temps au-delà de l'expiration (2s)
        time.sleep(2.1)
        with pytest.raises(ValueError, match="Token JWT expiré"):
            jwt_handler.verify_token(token)

    def test_refresh_token_has_longer_expiry(self, jwt_handler):
        """Le refresh token a une expiration plus longue que l'access token."""
        access = jwt_handler.create_access_token(user_id="u1")
        refresh = jwt_handler.create_refresh_token(user_id="u1")

        access_payload = jwt_handler.verify_token(access)
        refresh_payload = jwt_handler.verify_token(refresh)

        assert refresh_payload["exp"] > access_payload["exp"]


# ============================================================================
# Tests JWTHandler — Utilitaires
# ============================================================================


class TestJWTUtilities:
    """Tests des méthodes utilitaires du JWTHandler."""

    def test_token_user_id_extracts_sub(self, jwt_handler):
        """token_user_id extrait le 'sub' du payload."""
        token = jwt_handler.create_access_token(user_id="bob")
        payload = jwt_handler.verify_token(token)
        assert jwt_handler.token_user_id(payload) == "bob"

    def test_token_user_id_raises_if_no_sub(self, jwt_handler):
        """token_user_id lève ValueError si 'sub' est absent."""
        with pytest.raises(ValueError, match="Payload sans champ 'sub'"):
            jwt_handler.token_user_id({})

    def test_token_role_extracts_role(self, jwt_handler):
        """token_role extrait le 'role' du payload."""
        token = jwt_handler.create_access_token(user_id="u1", role="admin")
        payload = jwt_handler.verify_token(token)
        assert jwt_handler.token_role(payload) == "admin"

    def test_token_role_defaults_to_user_if_missing(self, jwt_handler):
        """token_role retourne 'user' si le claim 'role' est absent."""
        assert jwt_handler.token_role({"sub": "u1"}) == "user"


# ============================================================================
# Tests SessionManager — Création de sessions
# ============================================================================


class TestSessionCreation:
    """Tests de création de sessions utilisateur."""

    def test_create_session_returns_session_object(self, session_manager):
        """create_session retourne un objet Session valide."""
        session = session_manager.create_session(user_id="u1")
        assert isinstance(session, Session)
        assert session.user_id == "u1"
        assert len(session.session_id) == 64  # 32 bytes hex = 64 chars

    def test_create_session_default_role_is_user(self, session_manager):
        """Le rôle par défaut est 'user'."""
        session = session_manager.create_session(user_id="u1")
        assert session.role == "user"

    def test_create_session_with_explicit_role(self, session_manager):
        """Le rôle est correctement stocké quand spécifié."""
        session = session_manager.create_session(user_id="u1", role="admin")
        assert session.role == "admin"

    def test_create_session_stores_metadata(self, session_manager):
        """Les métadonnées sont stockées dans la session."""
        session = session_manager.create_session(
            user_id="u1", metadata={"ip": "127.0.0.1", "agent": "pytest"}
        )
        assert session.metadata["ip"] == "127.0.0.1"
        assert session.metadata["agent"] == "pytest"

    def test_create_session_generates_unique_ids(self, session_manager):
        """Deux sessions ont des IDs différents."""
        s1 = session_manager.create_session(user_id="u1")
        s2 = session_manager.create_session(user_id="u2")
        assert s1.session_id != s2.session_id

    def test_create_session_sets_expires_at(self, session_manager):
        """La session a une date d'expiration dans le futur."""
        session = session_manager.create_session(user_id="u1")
        assert session.expires_at > time.time()

    def test_create_session_not_expired_immediately(self, session_manager):
        """Une session fraîchement créée n'est pas expirée."""
        session = session_manager.create_session(user_id="u1")
        assert not session.is_expired


# ============================================================================
# Tests SessionManager — Récupération et validation
# ============================================================================


class TestSessionRetrieval:
    """Tests de récupération et validation des sessions."""

    def test_get_session_returns_session_by_id(self, session_manager):
        """get_session retourne la session correspondante."""
        created = session_manager.create_session(user_id="u1")
        retrieved = session_manager.get_session(created.session_id)
        assert retrieved is not None
        assert retrieved.user_id == "u1"
        assert retrieved.session_id == created.session_id

    def test_get_session_returns_none_for_unknown_id(self, session_manager):
        """get_session retourne None pour un ID inexistant."""
        assert session_manager.get_session("unknown-session-id") is None

    def test_get_session_returns_none_for_empty_id(self, session_manager):
        """get_session retourne None pour une chaîne vide."""
        assert session_manager.get_session("") is None

    def test_get_session_after_expiry_returns_none(self, session_manager):
        """Une session expirée n'est pas retournée (nettoyage automatique)."""
        session = session_manager.create_session(user_id="u1")
        time.sleep(2.1)  # TTL = 2s
        assert session_manager.get_session(session.session_id) is None

    def test_is_expired_detects_expired_session(self, session_manager):
        """La propriété is_expired détecte une session expirée."""
        session = session_manager.create_session(user_id="u1")
        time.sleep(2.1)
        assert session.is_expired

    def test_ttl_seconds_returns_positive_before_expiry(self, session_manager):
        """ttl_seconds est positif avant expiration."""
        session = session_manager.create_session(user_id="u1")
        assert session.ttl_seconds > 0

    def test_ttl_seconds_returns_zero_after_expiry(self, session_manager):
        """ttl_seconds est 0 après expiration."""
        session = session_manager.create_session(user_id="u1")
        time.sleep(2.1)
        assert session.ttl_seconds == 0.0


# ============================================================================
# Tests SessionManager — Suppression et gestion
# ============================================================================


class TestSessionDeletion:
    """Tests de suppression de sessions."""

    def test_delete_session_removes_session(self, session_manager):
        """delete_session supprime la session et retourne True."""
        session = session_manager.create_session(user_id="u1")
        assert session_manager.delete_session(session.session_id) is True
        assert session_manager.get_session(session.session_id) is None

    def test_delete_session_returns_false_for_unknown_id(self, session_manager):
        """delete_session retourne False pour un ID inexistant."""
        assert session_manager.delete_session("unknown-id") is False

    def test_delete_user_sessions_removes_all_for_user(self, session_manager):
        """delete_user_sessions supprime toutes les sessions d'un utilisateur."""
        session_manager.create_session(user_id="alice")
        session_manager.create_session(user_id="alice")
        session_manager.create_session(user_id="bob")

        deleted = session_manager.delete_user_sessions("alice")
        assert deleted == 2

        # Les sessions d'alice sont supprimées
        # La session de bob existe toujours
        assert session_manager.active_count == 1

    def test_delete_user_sessions_returns_zero_for_unknown_user(self, session_manager):
        """delete_user_sessions retourne 0 pour un utilisateur sans sessions."""
        assert session_manager.delete_user_sessions("ghost") == 0

    def test_refresh_session_extends_expiry(self, session_manager):
        """refresh_session prolonge la date d'expiration."""
        session = session_manager.create_session(user_id="u1")
        original_expiry = session.expires_at
        time.sleep(0.5)
        refreshed = session_manager.refresh_session(session.session_id)
        assert refreshed is not None
        assert refreshed.expires_at > original_expiry

    def test_refresh_session_returns_none_for_expired(self, session_manager):
        """refresh_session retourne None pour une session déjà expirée."""
        session = session_manager.create_session(user_id="u1")
        time.sleep(2.1)
        assert session_manager.refresh_session(session.session_id) is None

    def test_refresh_session_returns_none_for_unknown_id(self, session_manager):
        """refresh_session retourne None pour un ID inexistant."""
        assert session_manager.refresh_session("unknown-id") is None


# ============================================================================
# Tests SessionManager — Comptage et état
# ============================================================================


class TestSessionCount:
    """Tests de comptage des sessions."""

    def test_active_count_initial_zero(self, session_manager):
        """Aucune session active au départ."""
        assert session_manager.active_count == 0

    def test_active_count_after_creation(self, session_manager):
        """active_count reflète le nombre de sessions actives."""
        session_manager.create_session(user_id="u1")
        session_manager.create_session(user_id="u2")
        assert session_manager.active_count == 2

    def test_active_count_excludes_expired(self, session_manager):
        """Les sessions expirées ne sont pas comptées comme actives."""
        session_manager.create_session(user_id="u1")
        time.sleep(2.1)
        assert session_manager.active_count == 0
