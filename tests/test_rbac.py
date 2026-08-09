"""
Tests unitaires pour le module RBAC (Role-Based Access Control).

Couvre : les rôles, les permissions, le mapping clé API → rôle,
l'authentification, la vérification des permissions, et l'intégration
avec FastAPI.
"""

import logging
import os
import sys
from typing import Any, Dict
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient


# =========================================================================
# Tests unitaires du module RBAC
# =========================================================================


class TestRolePermissions:
    """Vérifie que chaque rôle possède les bonnes permissions."""

    def test_admin_has_all_permissions(self):
        """L'administrateur doit avoir toutes les permissions."""
        from src.api.rbac import Role, Permission, get_permissions_for_role

        perms = get_permissions_for_role(Role.ADMIN)
        for perm in Permission:
            assert perm in perms, f"Admin devrait avoir la permission {perm.value}"

    def test_operator_permissions(self):
        """L'opérateur doit pouvoir voir et décider les approbations."""
        from src.api.rbac import Role, Permission, get_permissions_for_role

        perms = get_permissions_for_role(Role.OPERATOR)
        assert Permission.APPROVAL_VIEW in perms
        assert Permission.APPROVAL_DECIDE in perms
        assert Permission.TOOL_EXECUTE in perms
        assert Permission.MODEL_GENERATE not in perms
        assert Permission.ADMIN_MANAGE not in perms

    def test_user_permissions(self):
        """L'utilisateur standard doit pouvoir utiliser les fonctionnalités de base."""
        from src.api.rbac import Role, Permission, get_permissions_for_role

        perms = get_permissions_for_role(Role.USER)
        assert Permission.MEMORY_READ in perms
        assert Permission.MEMORY_WRITE in perms
        assert Permission.MODEL_GENERATE in perms
        assert Permission.TOOL_EXECUTE in perms
        assert Permission.KNOWLEDGE_SEARCH in perms
        assert Permission.APPROVAL_DECIDE not in perms
        assert Permission.ADMIN_MANAGE not in perms

    def test_readonly_permissions(self):
        """Le rôle readonly ne doit avoir que les permissions de consultation."""
        from src.api.rbac import Role, Permission, get_permissions_for_role

        perms = get_permissions_for_role(Role.READONLY)
        assert Permission.HEALTH_VIEW in perms
        assert Permission.KNOWLEDGE_SEARCH in perms
        assert Permission.APPROVAL_VIEW in perms
        assert Permission.MEMORY_WRITE not in perms
        assert Permission.MODEL_GENERATE not in perms
        assert Permission.TOOL_EXECUTE not in perms


class TestParseApiKeyMappings:
    """Vérifie le parsing des clés API depuis les variables d'environnement."""

    def test_empty_env(self):
        """Variable d'environnement vide → mapping vide."""
        with patch.dict(os.environ, {"GALSEN_API_KEYS": ""}, clear=False):
            from src.api.rbac import hash_api_key, parse_api_key_mappings
            assert parse_api_key_mappings() == {}

    def test_keys_without_role_default_to_user(self):
        """Clés sans rôle explicite → rôle 'user' par défaut."""
        with patch.dict(os.environ, {"GALSEN_API_KEYS": "key1,key2"}, clear=False):
            from src.api.rbac import hash_api_key, parse_api_key_mappings
            mappings = parse_api_key_mappings()
            assert mappings[hash_api_key("key1")].role.value == "user"
            assert mappings[hash_api_key("key2")].role.value == "user"

    def test_keys_with_explicit_roles(self):
        """Clés avec rôle explicite dans le format 'key:role'."""
        with patch.dict(
            os.environ,
            {"GALSEN_API_KEYS": "admin-key:admin,read-key:readonly"},
            clear=False,
        ):
            from src.api.rbac import hash_api_key, parse_api_key_mappings
            mappings = parse_api_key_mappings()
            assert mappings[hash_api_key("admin-key")].role.value == "admin"
            assert mappings[hash_api_key("read-key")].role.value == "readonly"
            assert len(mappings) == 2

    def test_mixed_format(self):
        """Mélange de clés avec et sans rôle."""
        with patch.dict(
            os.environ,
            {"GALSEN_API_KEYS": "admin-key:admin,plain-key,op-key:operator"},
            clear=False,
        ):
            from src.api.rbac import hash_api_key, parse_api_key_mappings
            mappings = parse_api_key_mappings()
            assert mappings[hash_api_key("admin-key")].role.value == "admin"
            assert mappings[hash_api_key("plain-key")].role.value == "user"
            assert mappings[hash_api_key("op-key")].role.value == "operator"

    def test_invalid_role_defaults_to_user(self):
        """Rôle invalide → 'user' par défaut avec un avertissement log."""
        with patch.dict(
            os.environ,
            {"GALSEN_API_KEYS": "key1:superadmin"},
            clear=False,
        ):
            from src.api.rbac import hash_api_key, parse_api_key_mappings
            mappings = parse_api_key_mappings()
            assert mappings[hash_api_key("key1")].role.value == "user"


class TestRBACManager:
    """Vérifie le gestionnaire RBAC."""

    @pytest.fixture(autouse=True)
    def _setup_env(self):
        """Configure les clés de test avant chaque test."""
        with patch.dict(
            os.environ,
            {"GALSEN_API_KEYS": "admin-key:admin,user-key:user,ro-key:readonly"},
            clear=False,
        ):
            yield

    def test_authenticate_valid_keys(self):
        """L'authentification doit réussir pour des clés valides."""
        from src.api.rbac import RBACManager, hash_api_key

        manager = RBACManager()
        ctx = manager.authenticate("admin-key")
        assert ctx.role.value == "admin"
        # Le contexte porte une empreinte, jamais la clé : il peut finir en journal
        assert ctx.key_fingerprint == hash_api_key("admin-key")[:12]
        assert "admin-key" not in str(ctx)

        ctx2 = manager.authenticate("user-key")
        assert ctx2.role.value == "user"

    def test_authenticate_missing_key(self):
        """Clé manquante → PermissionError."""
        from src.api.rbac import RBACManager

        manager = RBACManager()
        with pytest.raises(PermissionError, match="Clé API manquante"):
            manager.authenticate(None)

    def test_authenticate_invalid_key(self):
        """Clé invalide → PermissionError."""
        from src.api.rbac import RBACManager

        manager = RBACManager()
        with pytest.raises(PermissionError, match="Clé API invalide"):
            manager.authenticate("fake-key")

    def test_get_valid_key_digests(self):
        """Le gestionnaire ne publie que des condensés, jamais les clés."""
        from src.api.rbac import RBACManager, hash_api_key

        manager = RBACManager()
        digests = manager.get_valid_key_digests()
        assert hash_api_key("admin-key") in digests
        assert hash_api_key("user-key") in digests
        assert hash_api_key("ro-key") in digests
        assert len(digests) == 3
        # La clé en clair ne doit apparaître nulle part
        assert "admin-key" not in digests

    def test_reload(self):
        """reload() met à jour le mapping clé → rôle."""
        from src.api.rbac import RBACManager

        manager = RBACManager()
        with patch.dict(
            os.environ,
            {"GALSEN_API_KEYS": "new-key:admin"},
            clear=False,
        ):
            manager.reload()
            ctx = manager.authenticate("new-key")
            assert ctx.role.value == "admin"

    def test_has_keys_property(self):
        """has_keys retourne True quand des clés sont configurées."""
        from src.api.rbac import RBACManager

        manager = RBACManager()
        assert manager.has_keys

    def test_has_keys_empty(self):
        """has_keys retourne False quand aucune clé n'est configurée."""
        with patch.dict(os.environ, {"GALSEN_API_KEYS": ""}, clear=False):
            from src.api.rbac import RBACManager

            manager = RBACManager()
            assert not manager.has_keys


class TestRBACContext:
    """Vérifie le contexte RBAC."""

    def test_has_permission(self):
        """has_permission retourne True pour les permissions du rôle."""
        from src.api.rbac import RBACContext, Role, Permission

        ctx = RBACContext(key_fingerprint="empreinte", role=Role.ADMIN)
        assert ctx.has_permission(Permission.ADMIN_MANAGE)
        assert ctx.has_permission(Permission.MEMORY_READ)

    def test_missing_permission(self):
        """has_permission retourne False pour les permissions absentes."""
        from src.api.rbac import RBACContext, Role, Permission

        ctx = RBACContext(key_fingerprint="empreinte", role=Role.READONLY)
        assert not ctx.has_permission(Permission.MEMORY_WRITE)
        assert not ctx.has_permission(Permission.MODEL_GENERATE)

    def test_has_any_permission(self):
        """has_any_permission retourne True si au moins une permission est présente."""
        from src.api.rbac import RBACContext, Role, Permission

        ctx = RBACContext(key_fingerprint="empreinte", role=Role.USER)
        assert ctx.has_any_permission(Permission.MEMORY_READ, Permission.ADMIN_MANAGE)
        assert not ctx.has_any_permission(Permission.ADMIN_MANAGE, Permission.ADMIN_AUDIT)

    def test_require_permission_ok(self):
        """require_permission ne lève pas pour une permission valide."""
        from src.api.rbac import RBACContext, Role, Permission

        ctx = RBACContext(key_fingerprint="empreinte", role=Role.ADMIN)
        ctx.require_permission(Permission.ADMIN_MANAGE)  # ne doit pas lever

    def test_require_permission_fail(self):
        """require_permission lève PermissionError pour une permission absente."""
        from src.api.rbac import RBACContext, Role, Permission

        ctx = RBACContext(key_fingerprint="empreinte", role=Role.READONLY)
        with pytest.raises(PermissionError):
            ctx.require_permission(Permission.TOOL_EXECUTE)

    def test_permissions_set_at_init(self):
        """Les permissions sont calculées à l'initialisation du contexte."""
        from src.api.rbac import RBACContext, Role, Permission

        ctx = RBACContext(key_fingerprint="empreinte", role=Role.OPERATOR)
        assert isinstance(ctx.permissions, frozenset)
        assert Permission.APPROVAL_DECIDE in ctx.permissions


# =========================================================================
# Tests d'intégration avec FastAPI
# =========================================================================
# Les tests d'intégration HTTP sont dans test_rbac_integration.py.
# Ce fichier contient uniquement les tests unitaires purs du module RBAC.

# =========================================================================
# Les clés API ne subsistent jamais en clair (VOLET 02 ch. 08)
# =========================================================================


class TestSecretsJamaisEnClair:
    """Vérifie qu'aucune clé rejouable ne subsiste après le démarrage.

    Une clé API est un secret porteur : qui l'obtient agit à la place de son
    porteur. La conserver en clair en mémoire, la journaliser même partiellement
    ou la promener dans un contexte de requête sont trois façons de la perdre.
    """

    def test_le_mapping_ne_contient_aucune_cle_en_clair(self):
        """Après lecture de l'environnement, seules des empreintes subsistent."""
        with patch.dict(os.environ, {"GALSEN_API_KEYS": "cle-secrete:admin"}, clear=False):
            from src.api.rbac import RBACManager

            manager = RBACManager()
            assert "cle-secrete" not in str(manager._key_role_map)

    def test_le_contexte_ne_porte_pas_la_cle(self):
        """Le contexte de requête ne doit rien contenir de rejouable."""
        with patch.dict(os.environ, {"GALSEN_API_KEYS": "cle-secrete:admin"}, clear=False):
            from src.api.rbac import RBACManager

            contexte = RBACManager().authenticate("cle-secrete")
            assert "cle-secrete" not in str(vars(contexte))

    def test_un_role_inconnu_ne_journalise_pas_la_cle(self, caplog):
        """Un rôle mal orthographié ne doit pas faire fuiter le début de la clé.

        L'ancienne version écrivait `key[:8]` : huit caractères d'un secret
        journalisés restent huit caractères de secret divulgués.
        """
        with patch.dict(
            os.environ, {"GALSEN_API_KEYS": "cle-secrete:roi-du-monde"}, clear=False
        ):
            from src.api.rbac import parse_api_key_mappings

            with caplog.at_level(logging.WARNING):
                parse_api_key_mappings()

        assert "cle-secr" not in caplog.text
        assert "roi-du-monde" in caplog.text

    def test_condensat_stable_et_non_reversible(self):
        """Le condensé doit être déterministe et ne pas contenir la clé."""
        from src.api.rbac import hash_api_key

        assert hash_api_key("cle-secrete") == hash_api_key("cle-secrete")
        assert hash_api_key("cle-secrete") != hash_api_key("cle-secrete2")
        assert len(hash_api_key("cle-secrete")) == 64
        assert "cle-secrete" not in hash_api_key("cle-secrete")

    def test_empreinte_courte_et_distinctive(self):
        """L'empreinte doit rester courte tout en distinguant deux clés."""
        from src.api.rbac import hash_api_key, key_fingerprint

        premiere = key_fingerprint(hash_api_key("cle-a"))
        seconde = key_fingerprint(hash_api_key("cle-b"))
        assert len(premiere) == 12
        assert premiere != seconde

    def test_le_limiteur_ne_recoit_que_des_condensats(self):
        """Le limiteur de taux doit reconnaître un client sans détenir sa clé."""
        with patch.dict(os.environ, {"GALSEN_API_KEYS": "cle-secrete:admin"}, clear=False):
            from src.api import rate_limiter
            from src.api.rbac import RBACManager

            rate_limiter.set_valid_api_key_digests(RBACManager().get_valid_key_digests())
            try:
                assert "cle-secrete" not in str(rate_limiter._valid_key_digests)
            finally:
                rate_limiter.set_valid_api_key_digests(set())
