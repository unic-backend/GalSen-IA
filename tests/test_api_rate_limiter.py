"""
Tests unitaires pour le limiteur de taux de l'API GalSen IA.

Couvre :
- L'implémentation InMemoryRateLimiter (token bucket)
- La dépendance FastAPI rate_limit_dependency
- Les limites authentifiées vs non authentifiées
- La réponse HTTP 429 avec les bons en-têtes
- La compatibilité avec l'authentification API Key
- La configuration via variables d'environnement
- La désactivation du limiteur
"""

import os
import sys
import time
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

# S'assurer que le chemin d'importation est correct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.rbac import hash_api_key
from src.api.rate_limiter import (
    APIRateLimiter,
    InMemoryRateLimiter,
    RateLimitConfig,
    RateLimitInfo,
    get_rate_limiter,
    set_valid_api_key_digests,
    rate_limit_dependency,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def default_config():
    """Configuration par défaut pour les tests."""
    return RateLimitConfig(
        enabled=True,
        authenticated_rpm=60,
        unauthenticated_rpm=10,
        burst_multiplier=1.0,  # Pas de rafale pour des tests déterministes
    )


@pytest.fixture
def limiter(default_config):
    """Crée un limiteur de taux en mémoire avec configuration de test."""
    return InMemoryRateLimiter(default_config)


@pytest.fixture
def disabled_limiter():
    """Crée un limiteur de taux désactivé."""
    config = RateLimitConfig(enabled=False)
    return InMemoryRateLimiter(config)


@pytest.fixture
def test_app():
    """Crée une application FastAPI minimale pour les tests d'intégration."""
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/protected")
    async def protected():
        return {"data": "secret"}

    return app


# ---------------------------------------------------------------------------
# Tests de RateLimitConfig
# ---------------------------------------------------------------------------


class TestRateLimitConfig:
    """Tests pour la configuration du limiteur de taux."""

    def test_default_values(self):
        """Vérifie les valeurs par défaut de la configuration."""
        config = RateLimitConfig()
        assert config.enabled is True
        assert config.authenticated_rpm == 60
        assert config.unauthenticated_rpm == 30
        assert config.burst_multiplier == 2.0

    def test_custom_values(self):
        """Vérifie qu'on peut définir des valeurs personnalisées."""
        config = RateLimitConfig(
            enabled=False,
            authenticated_rpm=120,
            unauthenticated_rpm=5,
            burst_multiplier=3.0,
        )
        assert config.enabled is False
        assert config.authenticated_rpm == 120
        assert config.unauthenticated_rpm == 5
        assert config.burst_multiplier == 3.0

    @patch.dict(os.environ, {
        "GALSEN_RATE_LIMIT_ENABLED": "false",
        "GALSEN_RATE_LIMIT_AUTHENTICATED_RPM": "100",
        "GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM": "5",
        "GALSEN_RATE_LIMIT_BURST_MULTIPLIER": "3.5",
    })
    def test_from_env_sets_all_values(self):
        """Vérifie que from_env lit correctement toutes les variables."""
        config = RateLimitConfig.from_env()
        assert config.enabled is False
        assert config.authenticated_rpm == 100
        assert config.unauthenticated_rpm == 5
        assert config.burst_multiplier == 3.5

    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_returns_defaults_when_no_env_vars(self):
        """Vérifie que from_env utilise les valeurs par défaut si aucune variable n'est définie."""
        config = RateLimitConfig.from_env()
        assert config.enabled is True
        assert config.authenticated_rpm == 60
        assert config.unauthenticated_rpm == 30
        assert config.burst_multiplier == 2.0

    @patch.dict(os.environ, {
        "GALSEN_RATE_LIMIT_ENABLED": "1",
    })
    def test_from_env_parses_true_variants(self):
        """Vérifie que les variantes de 'true' sont correctement interprétées."""
        config = RateLimitConfig.from_env()
        assert config.enabled is True

    @patch.dict(os.environ, {
        "GALSEN_RATE_LIMIT_AUTHENTICATED_RPM": "invalid",
    })
    def test_from_env_handles_invalid_int_gracefully(self):
        """Vérifie qu'une valeur entière invalide ne casse pas la config."""
        config = RateLimitConfig.from_env()
        assert config.authenticated_rpm == 60  # Valeur par défaut


# ---------------------------------------------------------------------------
# Tests de InMemoryRateLimiter
# ---------------------------------------------------------------------------


class TestInMemoryRateLimiter:
    """Tests pour l'implémentation en mémoire du limiteur de taux."""

    # --- Tests de base ---

    def test_initial_state_allows_request(self, limiter):
        """Un nouveau client doit être autorisé à faire sa première requête."""
        allowed, info = limiter.is_allowed("client-1", is_authenticated=True)
        assert allowed is True
        assert info.limit > 0
        assert info.remaining >= 0
        assert info.retry_after == 0.0

    def test_disabled_limiter_allows_all(self, disabled_limiter):
        """Un limiteur désactivé doit autoriser toutes les requêtes."""
        for _ in range(1000):
            allowed, info = disabled_limiter.is_allowed("client-1", is_authenticated=False)
            assert allowed is True
            assert info.limit == 0

    def test_rate_limit_exceeded_unauthenticated(self, limiter):
        """Un client non authentifié doit être bloqué après avoir dépassé sa limite."""
        rpm = limiter._config.unauthenticated_rpm
        client_id = "unauthenticated-client"

        # Consommer tous les jetons disponibles (rafale initiale = rpm * burst_multiplier = rpm * 1.0)
        for i in range(rpm):
            allowed, _ = limiter.is_allowed(client_id, is_authenticated=False)
            assert allowed is True, f"Requête {i + 1} aurait dû être autorisée"

        # La requête suivante doit être refusée (seau vide)
        allowed, info = limiter.is_allowed(client_id, is_authenticated=False)
        assert allowed is False
        assert info.remaining == 0
        assert info.retry_after > 0.0

    def test_rate_limit_exceeded_authenticated(self, limiter):
        """Un client authentifié doit avoir une limite plus élevée."""
        rpm = limiter._config.authenticated_rpm
        client_id = "authenticated-client"

        # Consommer tous les jetons
        for i in range(rpm):
            allowed, _ = limiter.is_allowed(client_id, is_authenticated=True)
            assert allowed is True, f"Requête {i + 1} aurait dû être autorisée"

        # La requête suivante doit être refusée
        allowed, info = limiter.is_allowed(client_id, is_authenticated=True)
        assert allowed is False

    def test_authenticated_has_higher_limit_than_unauthenticated(self, limiter):
        """Vérifie que la limite authentifiée est supérieure à la limite non authentifiée."""
        assert limiter._config.authenticated_rpm > limiter._config.unauthenticated_rpm

    def test_different_clients_have_independent_limits(self, limiter):
        """Deux clients différents ne doivent pas partager le même seau."""
        unauthenticated_rpm = limiter._config.unauthenticated_rpm

        # Épuiser le client 1
        for _ in range(unauthenticated_rpm):
            limiter.is_allowed("client-1", is_authenticated=False)

        # Le client 2 doit encore pouvoir faire des requêtes
        allowed, _ = limiter.is_allowed("client-2", is_authenticated=False)
        assert allowed is True

    # --- Tests de rafale (burst) ---

    def test_burst_allows_extra_requests_initially(self):
        """Avec un burst_multiplier > 1, un client peut faire plus de requêtes au début."""
        config = RateLimitConfig(
            enabled=True,
            authenticated_rpm=10,
            unauthenticated_rpm=10,
            burst_multiplier=3.0,  # Capacité = 30 jetons
        )
        limiter = InMemoryRateLimiter(config)

        # Les 30 premières requêtes doivent passer (burst)
        for i in range(30):
            allowed, _ = limiter.is_allowed("burst-client", is_authenticated=True)
            assert allowed is True, f"Requête {i + 1} en rafale aurait dû être autorisée"

        # La 31e doit être refusée
        allowed, _ = limiter.is_allowed("burst-client", is_authenticated=True)
        assert allowed is False

    # --- Tests de reconstitution des jetons ---

    def test_tokens_refill_over_time(self, limiter):
        """Les jetons doivent se reconstituer avec le temps."""
        # Configuration : burst_multiplier = 1.0, donc capacité = rpm
        rpm = limiter._config.authenticated_rpm
        client_id = "refill-client"

        # Épuiser tous les jetons
        for _ in range(rpm):
            limiter.is_allowed(client_id, is_authenticated=True)

        # Vérifier que plus rien n'est autorisé
        allowed, _ = limiter.is_allowed(client_id, is_authenticated=True)
        assert allowed is False

        # Attendre assez longtemps pour qu'un jeton se reconstitue
        # fill_rate = rpm / 60 jetons par seconde
        # Pour 1 jeton avec rpm=60 → 1 seconde
        wait_time = 60.0 / rpm + 0.1  # Un peu plus d'un cycle de remplissage
        time.sleep(wait_time)

        # Maintenant une requête devrait passer
        allowed, info = limiter.is_allowed(client_id, is_authenticated=True)
        assert allowed is True

    # --- Tests de reset ---

    def test_reset_clears_client_state(self, limiter):
        """Réinitialiser un client doit lui rendre sa capacité complète."""
        rpm = limiter._config.authenticated_rpm
        client_id = "reset-client"

        # Épuiser les jetons
        for _ in range(rpm):
            limiter.is_allowed(client_id, is_authenticated=True)

        # Vérifier que c'est bloqué
        allowed, _ = limiter.is_allowed(client_id, is_authenticated=True)
        assert allowed is False

        # Réinitialiser
        limiter.reset(client_id)

        # Maintenant les requêtes doivent passer à nouveau
        for i in range(rpm):
            allowed, _ = limiter.is_allowed(client_id, is_authenticated=True)
            assert allowed is True, f"Requête {i + 1} après reset aurait dû être autorisée"

    def test_reset_unknown_client_does_not_crash(self, limiter):
        """Réinitialiser un client inconnu ne doit pas lever d'exception."""
        limiter.reset("client-inexistant")
        # Pas d'exception = succès

    # --- Tests de retour d'information ---

    def test_info_contains_correct_limit(self, limiter):
        """RateLimitInfo doit contenir la limite correcte selon l'authentification."""
        _, info_auth = limiter.is_allowed("info-1", is_authenticated=True)
        assert info_auth.limit == limiter._config.authenticated_rpm

        _, info_unauth = limiter.is_allowed("info-2", is_authenticated=False)
        assert info_unauth.limit == limiter._config.unauthenticated_rpm

    def test_info_remaining_decreases(self, limiter):
        """Le nombre de requêtes restantes doit diminuer à chaque appel."""
        client_id = "remaining-client"
        initial_allowed, initial_info = limiter.is_allowed(client_id, is_authenticated=True)
        assert initial_allowed is True

        second_allowed, second_info = limiter.is_allowed(client_id, is_authenticated=True)
        assert second_allowed is True
        assert second_info.remaining < initial_info.remaining

    def test_info_retry_after_is_zero_when_allowed(self, limiter):
        """retry_after doit être 0 quand la requête est autorisée."""
        allowed, info = limiter.is_allowed("retry-client", is_authenticated=True)
        assert allowed is True
        assert info.retry_after == 0.0

    def test_info_retry_after_positive_when_denied(self, limiter):
        """retry_after doit être > 0 quand la requête est refusée."""
        rpm = limiter._config.authenticated_rpm
        client_id = "denied-client"
        for _ in range(rpm):
            limiter.is_allowed(client_id, is_authenticated=True)

        allowed, info = limiter.is_allowed(client_id, is_authenticated=True)
        assert allowed is False
        assert info.retry_after > 0.0

    # --- Tests de concurrence simple ---

    def test_different_auth_levels_for_same_client(self, limiter):
        """Un même client_id avec des niveaux d'auth différents utilise des limites différentes."""
        client_id = "same-id-different-auth"

        # Avec authentification : limite élevée
        _, info_auth = limiter.is_allowed(client_id, is_authenticated=True)
        assert info_auth.limit == limiter._config.authenticated_rpm

        # Sans authentification : limite basse
        # Note: le même client_id est réutilisé, donc le seau existant est mis à jour
        # avec la nouvelle capacité. C'est le comportement attendu car un client
        # ne peut pas être à la fois authentifié et non authentifié dans la même requête.
        _, info_unauth = limiter.is_allowed(client_id, is_authenticated=False)
        assert info_unauth.limit == limiter._config.unauthenticated_rpm


# ---------------------------------------------------------------------------
# Tests de l'interface abstraite
# ---------------------------------------------------------------------------


class TestAPIRateLimiterInterface:
    """Vérifie que l'interface abstraite est correctement définie."""

    def test_in_memory_limiter_is_an_api_rate_limiter(self, limiter):
        """InMemoryRateLimiter doit implémenter APIRateLimiter."""
        assert isinstance(limiter, APIRateLimiter)

    def test_abstract_methods_are_defined(self):
        """Vérifie que les méthodes abstraites sont bien définies dans l'interface."""
        assert hasattr(APIRateLimiter, "is_allowed")
        assert hasattr(APIRateLimiter, "reset")


# ---------------------------------------------------------------------------
# Tests de la dépendance FastAPI
# ---------------------------------------------------------------------------


class TestRateLimitDependency:
    """Tests d'intégration de la dépendance rate_limit_dependency avec FastAPI."""

    @pytest.fixture
    def client_with_rate_limit(self):
        """Crée un client de test avec rate limiting configuré."""
        # Configurer les clés API
        os.environ["GALSEN_API_KEYS"] = "valid-test-key"
        set_valid_api_key_digests({hash_api_key("valid-test-key")})

        # S'assurer que le limiteur est activé avec une config de test
        os.environ["GALSEN_RATE_LIMIT_ENABLED"] = "true"
        os.environ["GALSEN_RATE_LIMIT_AUTHENTICATED_RPM"] = "60"
        os.environ["GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM"] = "10"
        os.environ["GALSEN_RATE_LIMIT_BURST_MULTIPLIER"] = "1.0"

        # Recréer le limiteur avec la nouvelle config
        import src.api.rate_limiter as rl_module
        rl_module._rate_limiter = None

        app = FastAPI()

        @app.get("/health", dependencies=[Depends(rate_limit_dependency)])
        async def health():
            return {"status": "ok"}

        @app.get("/protected", dependencies=[Depends(rate_limit_dependency)])
        async def protected():
            return {"data": "secret"}

        return TestClient(app)

    def test_request_within_limit_succeeds(self, client_with_rate_limit):
        """Une requête dans la limite doit retourner 200."""
        response = client_with_rate_limit.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_unauthenticated_rate_limit_exceeded_returns_429(self, client_with_rate_limit):
        """Un client non authentifié qui dépasse la limite doit recevoir 429."""
        # Faire 10 requêtes (limite non authentifiée = 10, burst = 1.0)
        for i in range(10):
            response = client_with_rate_limit.get("/health")
            assert response.status_code == 200, f"Requête {i + 1} aurait dû être 200, reçu {response.status_code}"

        # La 11e doit être refusée
        response = client_with_rate_limit.get("/health")
        assert response.status_code == 429
        assert "Trop de requêtes" in response.json()["detail"]

    def test_429_response_has_retry_after_header(self, client_with_rate_limit):
        """La réponse 429 doit inclure l'en-tête Retry-After."""
        # Épuiser la limite
        for _ in range(10):
            client_with_rate_limit.get("/health")

        response = client_with_rate_limit.get("/health")
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0

    def test_429_response_has_rate_limit_headers(self, client_with_rate_limit):
        """La réponse 429 doit inclure les en-têtes X-RateLimit-*."""
        # Épuiser la limite
        for _ in range(10):
            client_with_rate_limit.get("/health")

        response = client_with_rate_limit.get("/health")
        assert response.status_code == 429
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "10"  # Limite non authentifiée
        assert response.headers["X-RateLimit-Remaining"] == "0"

    def test_authenticated_requests_have_higher_limit(self):
        """Les requêtes authentifiées doivent avoir une limite plus élevée."""
        import src.api.rate_limiter as rl_module

        os.environ["GALSEN_API_KEYS"] = "high-limit-key"
        os.environ["GALSEN_RATE_LIMIT_ENABLED"] = "true"
        os.environ["GALSEN_RATE_LIMIT_AUTHENTICATED_RPM"] = "60"
        os.environ["GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM"] = "5"
        os.environ["GALSEN_RATE_LIMIT_BURST_MULTIPLIER"] = "1.0"

        set_valid_api_key_digests({hash_api_key("high-limit-key")})
        rl_module._rate_limiter = None

        app = FastAPI()

        @app.get("/data", dependencies=[Depends(rate_limit_dependency)])
        async def data():
            return {"ok": True}

        client = TestClient(app)

        # Sans clé API : limité à 5 requêtes
        for i in range(5):
            response = client.get("/data")
            assert response.status_code == 200, f"Requête non auth {i + 1} échouée"

        # La 6e sans clé doit échouer
        response = client.get("/data")
        assert response.status_code == 429, "Le client non auth aurait dû être limité"

        # Avec clé API : le client est identifié par sa clé, donc nouvelle limite
        # (le client TestClient réutilise la même IP, mais avec une clé différente
        # l'identifiant change, donc nouveau seau)
        for i in range(60):
            response = client.get("/data", headers={"X-API-Key": "high-limit-key"})
            assert response.status_code == 200, f"Requête auth {i + 1} échouée: {response.status_code}"

    def test_different_api_keys_have_separate_limits(self):
        """Deux clés API différentes doivent avoir des seaux indépendants."""
        import src.api.rate_limiter as rl_module

        os.environ["GALSEN_API_KEYS"] = "key-a,key-b"
        os.environ["GALSEN_RATE_LIMIT_ENABLED"] = "true"
        os.environ["GALSEN_RATE_LIMIT_AUTHENTICATED_RPM"] = "5"
        os.environ["GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM"] = "2"
        os.environ["GALSEN_RATE_LIMIT_BURST_MULTIPLIER"] = "1.0"

        set_valid_api_key_digests({hash_api_key("key-a"), hash_api_key("key-b")})
        rl_module._rate_limiter = None

        app = FastAPI()

        @app.get("/data", dependencies=[Depends(rate_limit_dependency)])
        async def data():
            return {"ok": True}

        client = TestClient(app)

        # Épuiser key-a (5 requêtes)
        for i in range(5):
            response = client.get("/data", headers={"X-API-Key": "key-a"})
            assert response.status_code == 200, f"key-a requête {i + 1} échouée"

        # key-a est épuisée
        response = client.get("/data", headers={"X-API-Key": "key-a"})
        assert response.status_code == 429, "key-a aurait dû être limitée"

        # key-b doit encore fonctionner
        response = client.get("/data", headers={"X-API-Key": "key-b"})
        assert response.status_code == 200, "key-b devrait encore fonctionner"


# ---------------------------------------------------------------------------
# Tests de manipulation d'IP
# ---------------------------------------------------------------------------


class TestClientIPExtraction:
    """Tests pour l'extraction de l'adresse IP du client."""

    def test_different_ips_have_separate_limits(self, limiter):
        """Deux IPs différentes doivent avoir des limites indépendantes."""
        unauthenticated_rpm = limiter._config.unauthenticated_rpm

        # Épuiser l'IP 1
        for _ in range(unauthenticated_rpm):
            limiter.is_allowed("192.168.1.1", is_authenticated=False)

        # L'IP 1 est bloquée
        allowed, _ = limiter.is_allowed("192.168.1.1", is_authenticated=False)
        assert allowed is False

        # L'IP 2 peut encore faire des requêtes
        allowed, _ = limiter.is_allowed("192.168.1.2", is_authenticated=False)
        assert allowed is True


# ---------------------------------------------------------------------------
# Tests de compatibilité avec l'authentification
# ---------------------------------------------------------------------------


class TestRateLimitAuthCompatibility:
    """Vérifie que le rate limiting et l'authentification API Key fonctionnent ensemble."""

    def test_rate_limit_runs_before_auth(self):
        """Le rate limiting doit s'exécuter avant la vérification d'authentification."""
        import src.api.rate_limiter as rl_module

        os.environ["GALSEN_API_KEYS"] = "my-key"
        os.environ["GALSEN_RATE_LIMIT_ENABLED"] = "true"
        os.environ["GALSEN_RATE_LIMIT_AUTHENTICATED_RPM"] = "60"
        os.environ["GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM"] = "3"
        os.environ["GALSEN_RATE_LIMIT_BURST_MULTIPLIER"] = "1.0"

        set_valid_api_key_digests({hash_api_key("my-key")})
        rl_module._rate_limiter = None

        from fastapi.security.api_key import APIKeyHeader

        API_KEY_NAME = "X-API-Key"
        api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
        valid_keys = {"my-key"}

        def get_api_key(api_key: str = Depends(api_key_header)):
            if not api_key or api_key not in valid_keys:
                from fastapi import HTTPException
                raise HTTPException(status_code=401, detail="Invalid or missing API Key")
            return api_key

        app = FastAPI()

        @app.get("/secure", dependencies=[Depends(rate_limit_dependency), Depends(get_api_key)])
        async def secure():
            return {"secure": True}

        client = TestClient(app)

        # Sans clé API : limité à 3 requêtes non authentifiées
        for i in range(3):
            response = client.get("/secure")
            # Sans clé valide, c'est l'auth qui bloque (401), pas le rate limit
            # Le rate limit vérifie d'abord, mais le client n'est pas identifié par clé
            # donc il utilise l'IP. Après 3 requêtes, il devrait recevoir 429.
            if i < 3:
                # Soit 401 (auth) soit 200 (si pas d'auth check) - mais pas 429
                assert response.status_code != 429, f"Requête {i + 1}: ne devrait pas être 429"

        # La 4e requête sans clé = rate limit dépassé → 429
        response = client.get("/secure")
        assert response.status_code == 429, f"Attendu 429, reçu {response.status_code}"

    def test_invalid_api_key_treated_as_unauthenticated(self, monkeypatch):
        """Une clé API invalide doit être traitée comme non authentifiée pour le rate limiting.

        `monkeypatch` et non `os.environ` : la variable était laissée modifiée
        pour tout le processus, et une suite exécutée ensuite recevait des 401
        sur ses propres clés — un échec qui ne dépendait que de l'ordre.
        """
        import src.api.rate_limiter as rl_module

        monkeypatch.setenv("GALSEN_API_KEYS", "only-valid-key")
        monkeypatch.setenv("GALSEN_RATE_LIMIT_ENABLED", "true")
        monkeypatch.setenv("GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM", "2")
        monkeypatch.setenv("GALSEN_RATE_LIMIT_BURST_MULTIPLIER", "1.0")

        set_valid_api_key_digests({hash_api_key("only-valid-key")})
        rl_module._rate_limiter = None

        app = FastAPI()

        @app.get("/test", dependencies=[Depends(rate_limit_dependency)])
        async def test():
            return {"ok": True}

        client = TestClient(app)

        # Avec une clé invalide : traité comme non authentifié (identifié par IP)
        for i in range(2):
            response = client.get("/test", headers={"X-API-Key": "invalid-key"})
            assert response.status_code == 200, f"Requête {i + 1} avec clé invalide échouée"

        # La 3e doit être refusée
        response = client.get("/test", headers={"X-API-Key": "invalid-key"})
        assert response.status_code == 429


# ---------------------------------------------------------------------------
# Tests du singleton
# ---------------------------------------------------------------------------


class TestRateLimiterSingleton:
    """Tests pour la gestion du singleton du limiteur de taux."""

    def test_get_rate_limiter_returns_same_instance(self):
        """get_rate_limiter doit retourner la même instance à chaque appel."""
        import src.api.rate_limiter as rl_module
        rl_module._rate_limiter = None

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    @patch.dict(os.environ, {"GALSEN_RATE_LIMIT_ENABLED": "false"})
    def test_get_rate_limiter_respects_env_config(self):
        """Le singleton doit utiliser la configuration d'environnement."""
        import src.api.rate_limiter as rl_module
        rl_module._rate_limiter = None

        limiter = get_rate_limiter()
        # Même désactivé, le limiteur doit autoriser les requêtes
        allowed, _ = limiter.is_allowed("test", is_authenticated=False)
        assert allowed is True


# ---------------------------------------------------------------------------
# Point d'entrée pour exécution directe
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
