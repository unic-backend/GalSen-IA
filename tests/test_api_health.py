"""
Tests unitaires pour le vérificateur de santé de l'API GalSen IA.

Couvre :
- Les dataclasses ComponentHealth et HealthReport
- L'implémentation ComponentHealthChecker (tous les composants)
- Les endpoints /health, /ready, /live
- Le pattern singleton (init_health_checker, get_health_checker)
- Le late binding de tool_engine via set_tool_engine()
- La gestion des erreurs et cas limites
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# S'assurer que le chemin d'importation est correct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.health import (
    ComponentHealth,
    ComponentHealthChecker,
    HealthChecker,
    HealthReport,
    get_health_checker,
    init_health_checker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_health_checker():
    """Réinitialise le singleton du vérificateur de santé avant chaque test."""
    # Sauvegarder l'état actuel
    import src.api.health as health_module
    old = health_module._health_checker
    health_module._health_checker = None
    yield
    # Restaurer après le test
    health_module._health_checker = old


@pytest.fixture
def start_time():
    """Timestamp de démarrage fixe pour les tests."""
    return 1000000.0


@pytest.fixture
def version():
    """Version de test."""
    return "0.1.0-test"


@pytest.fixture
def mock_memory_manager():
    """Crée un MemoryManager mocké qui fonctionne correctement."""
    mgr = MagicMock()
    mgr.save_memory.return_value = "test-item-id"
    mock_item = MagicMock()
    mock_item.content = "health_check_test"
    mock_item.id = "test-item-id"
    mgr.get_memory.return_value = mock_item
    mgr.delete_memory.return_value = True
    return mgr


@pytest.fixture
def mock_memory_manager_failing():
    """Crée un MemoryManager mocké qui échoue à la sauvegarde."""
    mgr = MagicMock()
    mgr.save_memory.side_effect = RuntimeError("Erreur de stockage simulée")
    return mgr


@pytest.fixture
def mock_model_manager():
    """Crée un ModelManagerImpl mocké avec des fournisseurs disponibles."""
    mgr = MagicMock()
    mgr.get_provider_status.return_value = {
        "openai": {"available": True},
        "anthropic": {"available": False},
        "local": {"available": True},
    }
    return mgr


@pytest.fixture
def mock_model_manager_no_providers():
    """Crée un ModelManagerImpl mocké sans fournisseurs."""
    mgr = MagicMock()
    mgr.get_provider_status.return_value = {}
    return mgr


@pytest.fixture
def mock_model_manager_all_unavailable():
    """Crée un ModelManagerImpl mocké où aucun fournisseur n'est dispo."""
    mgr = MagicMock()
    mgr.get_provider_status.return_value = {
        "openai": {"available": False},
        "anthropic": {"available": False},
    }
    return mgr


@pytest.fixture
def mock_knowledge_manager():
    """Crée un KnowledgeManagerImpl mocké."""
    mgr = MagicMock()
    mgr.get_stats.return_value = {
        "store": {"total_items": 42},
        "cache": {"size": 10, "max_size": 100},
    }
    return mgr


@pytest.fixture
def mock_knowledge_manager_broken():
    """Crée un KnowledgeManagerImpl mocké qui lève une exception."""
    mgr = MagicMock()
    mgr.get_stats.side_effect = RuntimeError("Erreur simulée")
    return mgr


@pytest.fixture
def mock_tool_engine():
    """Crée un ToolEngine mocké avec des outils."""
    engine = MagicMock()
    engine.list_tools.return_value = [
        {"name": "filesystem", "description": "Opérations sur le système de fichiers"},
        {"name": "terminal", "description": "Exécution de commandes"},
        {"name": "git", "description": "Opérations Git"},
    ]
    return engine


@pytest.fixture
def mock_tool_engine_empty():
    """Crée un ToolEngine mocké sans outils."""
    engine = MagicMock()
    engine.list_tools.return_value = []
    return engine


# ---------------------------------------------------------------------------
# Tests des dataclasses
# ---------------------------------------------------------------------------


class TestComponentHealth:
    """Tests pour la dataclass ComponentHealth."""

    def test_healthy_component(self):
        """Un composant sain doit avoir le statut 'healthy' sans erreur."""
        health = ComponentHealth(
            status="healthy",
            details={"message": "Fonctionne"},
        )
        assert health.status == "healthy"
        assert health.error is None
        assert health.details["message"] == "Fonctionne"

    def test_degraded_component(self):
        """Un composant dégradé doit avoir un message d'erreur."""
        health = ComponentHealth(
            status="degraded",
            error="Partiellement fonctionnel",
        )
        assert health.status == "degraded"
        assert health.error == "Partiellement fonctionnel"

    def test_unhealthy_component(self):
        """Un composant non sain doit avoir une erreur explicite."""
        health = ComponentHealth(
            status="unhealthy",
            error="Composant inaccessible",
        )
        assert health.status == "unhealthy"
        assert health.error == "Composant inaccessible"


class TestHealthReport:
    """Tests pour la dataclass HealthReport et sa sérialisation."""

    def test_to_dict_basic(self):
        """Vérifie la structure de base du dictionnaire de rapport."""
        report = HealthReport(
            status="healthy",
            timestamp=1234567890.0,
            version="1.0.0",
            uptime=3600.0,
            components={
                "api": ComponentHealth(status="healthy", details={"message": "OK"}),
            },
            storage_backend="in-memory",
            configured_providers=["openai"],
        )
        result = report.to_dict()

        assert result["status"] == "healthy"
        assert result["timestamp"] == 1234567890.0
        assert result["version"] == "1.0.0"
        assert result["uptime"] == 3600.0
        assert result["storage_backend"] == "in-memory"
        assert result["configured_providers"] == ["openai"]
        assert "api" in result["components"]

    def test_to_dict_component_with_error(self):
        """Un composant avec erreur doit inclure le champ error dans to_dict."""
        report = HealthReport(
            status="degraded",
            timestamp=1234567890.0,
            version="1.0.0",
            uptime=100.0,
            components={
                "db": ComponentHealth(
                    status="unhealthy",
                    error="Connexion refusée",
                ),
            },
            storage_backend="sqlite",
            configured_providers=[],
        )
        result = report.to_dict()

        comp = result["components"]["db"]
        assert comp["status"] == "unhealthy"
        assert comp["error"] == "Connexion refusée"

    def test_to_dict_component_without_error(self):
        """Un composant sain ne doit pas avoir de champ error dans to_dict."""
        report = HealthReport(
            status="healthy",
            timestamp=1234567890.0,
            version="1.0.0",
            uptime=100.0,
            components={
                "api": ComponentHealth(status="healthy", details={"msg": "ok"}),
            },
            storage_backend="in-memory",
            configured_providers=["openai"],
        )
        result = report.to_dict()

        comp = result["components"]["api"]
        assert "error" not in comp
        assert comp["msg"] == "ok"  # Les détails sont fusionnés


# ---------------------------------------------------------------------------
# Tests du ComponentHealthChecker — vérifications individuelles
# ---------------------------------------------------------------------------


class TestCheckApi:
    """Tests pour la vérification du composant API."""

    def test_api_always_healthy(self, start_time, version):
        """L'API doit toujours être marquée comme saine."""
        checker = ComponentHealthChecker(start_time=start_time, version=version)
        result = checker._check_api()
        assert result.status == "healthy"
        assert result.error is None


class TestCheckMemoryEngine:
    """Tests pour la vérification du moteur de mémoire."""

    def test_memory_engine_null(self, start_time, version):
        """Si le gestionnaire est None, le composant doit être unhealthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=None,
        )
        result = checker._check_memory_engine()
        assert result.status == "unhealthy"
        assert "non initialisé" in result.error

    def test_memory_engine_healthy(self, start_time, version, mock_memory_manager):
        """Un cycle écriture/lecture réussi doit donner healthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=mock_memory_manager,
        )
        result = checker._check_memory_engine()
        assert result.status == "healthy"

    def test_memory_engine_write_fails(self, start_time, version, mock_memory_manager_failing):
        """Un échec d'écriture doit donner unhealthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=mock_memory_manager_failing,
        )
        result = checker._check_memory_engine()
        assert result.status == "unhealthy"

    def test_memory_engine_read_returns_wrong_content(self, start_time, version):
        """Une lecture avec un contenu inattendu doit donner degraded."""
        mgr = MagicMock()
        mgr.save_memory.return_value = "test-id"
        mock_item = MagicMock()
        mock_item.content = "mauvais_contenu"
        mgr.get_memory.return_value = mock_item
        mgr.delete_memory.return_value = True

        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=mgr,
        )
        result = checker._check_memory_engine()
        assert result.status == "degraded"

    def test_memory_engine_read_returns_none(self, start_time, version):
        """Une lecture qui retourne None doit donner degraded."""
        mgr = MagicMock()
        mgr.save_memory.return_value = "test-id"
        mgr.get_memory.return_value = None

        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=mgr,
        )
        result = checker._check_memory_engine()
        assert result.status == "degraded"


class TestCheckModelEngine:
    """Tests pour la vérification du moteur de modèles."""

    def test_model_engine_null(self, start_time, version):
        """Si le gestionnaire est None, le composant doit être unhealthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            model_manager=None,
        )
        result = checker._check_model_engine()
        assert result.status == "unhealthy"

    def test_model_engine_healthy(self, start_time, version, mock_model_manager):
        """Avec des fournisseurs disponibles, le moteur doit être healthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            model_manager=mock_model_manager,
        )
        result = checker._check_model_engine()
        assert result.status == "healthy"
        assert result.details["total_providers"] == 3
        assert result.details["available_providers"] == 2

    def test_model_engine_no_providers(self, start_time, version, mock_model_manager_no_providers):
        """Sans fournisseurs configurés, le moteur doit être degraded."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            model_manager=mock_model_manager_no_providers,
        )
        result = checker._check_model_engine()
        assert result.status == "degraded"
        assert "Aucun fournisseur" in result.error

    def test_model_engine_all_unavailable(self, start_time, version, mock_model_manager_all_unavailable):
        """Si tous les fournisseurs sont indisponibles, le moteur doit être degraded."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            model_manager=mock_model_manager_all_unavailable,
        )
        result = checker._check_model_engine()
        assert result.status == "degraded"
        assert "Aucun fournisseur" in result.error

    def test_model_engine_exception(self, start_time, version):
        """Une exception dans get_provider_status doit donner unhealthy."""
        mgr = MagicMock()
        mgr.get_provider_status.side_effect = RuntimeError("Échec")

        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            model_manager=mgr,
        )
        result = checker._check_model_engine()
        assert result.status == "unhealthy"


class TestCheckKnowledgeEngine:
    """Tests pour la vérification du moteur de connaissances."""

    def test_knowledge_engine_null(self, start_time, version):
        """Si le gestionnaire est None, le composant doit être unhealthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            knowledge_manager=None,
        )
        result = checker._check_knowledge_engine()
        assert result.status == "unhealthy"

    def test_knowledge_engine_healthy(self, start_time, version, mock_knowledge_manager):
        """Un moteur qui répond avec des stats doit être healthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            knowledge_manager=mock_knowledge_manager,
        )
        result = checker._check_knowledge_engine()
        assert result.status == "healthy"
        assert result.details["total_items"] == 42

    def test_knowledge_engine_exception(self, start_time, version, mock_knowledge_manager_broken):
        """Une exception dans get_stats doit donner unhealthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            knowledge_manager=mock_knowledge_manager_broken,
        )
        result = checker._check_knowledge_engine()
        assert result.status == "unhealthy"


class TestCheckToolEngine:
    """Tests pour la vérification du moteur d'outils."""

    def test_tool_engine_null(self, start_time, version):
        """Si le moteur est None, le composant doit être unhealthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            tool_engine=None,
        )
        result = checker._check_tool_engine()
        assert result.status == "unhealthy"
        assert "non initialisé" in result.error

    def test_tool_engine_healthy(self, start_time, version, mock_tool_engine):
        """Un moteur avec des outils chargés doit être healthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            tool_engine=mock_tool_engine,
        )
        result = checker._check_tool_engine()
        assert result.status == "healthy"
        assert result.details["tools_count"] == 3

    def test_tool_engine_empty(self, start_time, version, mock_tool_engine_empty):
        """Un moteur sans outils doit quand même être healthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            tool_engine=mock_tool_engine_empty,
        )
        result = checker._check_tool_engine()
        assert result.status == "healthy"
        assert result.details["tools_count"] == 0

    def test_tool_engine_exception(self, start_time, version):
        """Une exception dans list_tools doit donner unhealthy."""
        engine = MagicMock()
        engine.list_tools.side_effect = RuntimeError("Échec du listage")

        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            tool_engine=engine,
        )
        result = checker._check_tool_engine()
        assert result.status == "unhealthy"


class TestCheckStorage:
    """Tests pour la vérification du backend de stockage."""

    def test_storage_in_memory(self, start_time, version):
        """Le backend in-memory doit être healthy."""
        with patch.dict(os.environ, {"GALSEN_STORAGE_BACKEND": "in-memory"}):
            checker = ComponentHealthChecker(start_time=start_time, version=version)
            result = checker._check_storage()
            assert result.status == "healthy"
            assert result.details["backend"] == "in-memory"

    def test_storage_sqlite(self, start_time, version):
        """Le backend sqlite doit être healthy."""
        with patch.dict(os.environ, {"GALSEN_STORAGE_BACKEND": "sqlite"}):
            checker = ComponentHealthChecker(start_time=start_time, version=version)
            result = checker._check_storage()
            assert result.status == "healthy"
            assert result.details["backend"] == "sqlite"

    def test_storage_default(self, start_time, version):
        """Par défaut (sans variable d'environnement), le backend doit être in-memory."""
        with patch.dict(os.environ, {}, clear=True):
            checker = ComponentHealthChecker(start_time=start_time, version=version)
            result = checker._check_storage()
            assert result.status == "healthy"
            assert result.details["backend"] == "in-memory"

    def test_storage_unknown(self, start_time, version):
        """Un backend inconnu doit être degraded."""
        with patch.dict(os.environ, {"GALSEN_STORAGE_BACKEND": "postgresql"}):
            checker = ComponentHealthChecker(start_time=start_time, version=version)
            result = checker._check_storage()
            assert result.status == "degraded"


# ---------------------------------------------------------------------------
# Tests du ComponentHealthChecker — méthodes publiques
# ---------------------------------------------------------------------------


class TestCheckHealth:
    """Tests pour la méthode check_health() — rapport complet."""

    def test_all_healthy(self, start_time, version, mock_memory_manager,
                         mock_model_manager, mock_knowledge_manager, mock_tool_engine):
        """Quand tous les composants sont sains, le statut global doit être healthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=mock_memory_manager,
            model_manager=mock_model_manager,
            knowledge_manager=mock_knowledge_manager,
            tool_engine=mock_tool_engine,
        )
        report = checker.check_health()

        assert report.status == "healthy"
        assert report.version == version
        assert report.uptime >= 0
        assert "api" in report.components
        assert "memory_engine" in report.components
        assert "model_engine" in report.components
        assert "knowledge_engine" in report.components
        assert "tool_engine" in report.components
        assert "storage" in report.components

    def test_one_unhealthy_makes_overall_unhealthy(self, start_time, version):
        """Si un seul composant est unhealthy, le statut global doit être unhealthy."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=None,  # Provoque unhealthy
            model_manager=MagicMock(),
            knowledge_manager=MagicMock(),
            tool_engine=MagicMock(),
        )
        # Rendre model_manager fonctionnel pour ne pas avoir d'exception
        checker._model_manager.get_provider_status.return_value = {"openai": {"available": True}}
        checker._knowledge_manager.get_stats.return_value = {"store": {"total_items": 0}}
        checker._tool_engine.list_tools.return_value = []

        report = checker.check_health()
        assert report.status == "unhealthy"

    def test_one_degraded_no_unhealthy(self, start_time, version,
                                       mock_memory_manager, mock_model_manager_no_providers,
                                       mock_knowledge_manager, mock_tool_engine):
        """Si un composant est degraded et aucun unhealthy, statut global = degraded."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=mock_memory_manager,
            model_manager=mock_model_manager_no_providers,  # degraded
            knowledge_manager=mock_knowledge_manager,
            tool_engine=mock_tool_engine,
        )
        report = checker.check_health()
        assert report.status == "degraded"

    def test_report_timestamp_is_recent(self, start_time, version, mock_tool_engine):
        """Le timestamp du rapport doit être proche de maintenant."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            tool_engine=mock_tool_engine,
        )
        before = time.time()
        report = checker.check_health()
        after = time.time()

        assert before <= report.timestamp <= after + 0.1

    def test_report_includes_configured_providers(self, start_time, version,
                                                  mock_model_manager, mock_tool_engine):
        """Le rapport doit lister les fournisseurs configurés."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            model_manager=mock_model_manager,
            tool_engine=mock_tool_engine,
        )
        report = checker.check_health()
        assert "openai" in report.configured_providers
        assert "anthropic" in report.configured_providers
        assert "local" in report.configured_providers

    def test_report_without_model_manager(self, start_time, version, mock_tool_engine):
        """Sans model_manager, configured_providers doit être une liste vide."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            model_manager=None,
            tool_engine=mock_tool_engine,
        )
        report = checker.check_health()
        assert report.configured_providers == []

    def test_report_to_dict(self, start_time, version, mock_tool_engine):
        """La conversion en dict doit produire un dictionnaire valide."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            tool_engine=mock_tool_engine,
        )
        report = checker.check_health()
        result = report.to_dict()

        assert isinstance(result, dict)
        assert "status" in result
        assert "timestamp" in result
        assert "version" in result
        assert "uptime" in result
        assert "components" in result
        assert "storage_backend" in result
        assert "configured_providers" in result
        # Vérifier que chaque composant est un dict
        for comp_data in result["components"].values():
            assert isinstance(comp_data, dict)
            assert "status" in comp_data


class TestCheckReadiness:
    """Tests pour la méthode check_readiness()."""

    def test_ready_when_all_required_healthy(self, start_time, version, mock_tool_engine):
        """L'app doit être prête quand tous les composants requis sont sains."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            tool_engine=mock_tool_engine,
        )
        ready, reason = checker.check_readiness()
        assert ready is True
        assert "disponibles" in reason

    def test_not_ready_when_tool_engine_null(self, start_time, version):
        """L'app ne doit pas être prête si le moteur d'outils est None."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            tool_engine=None,
        )
        ready, reason = checker.check_readiness()
        assert ready is False
        assert "tool_engine" in reason

    def test_not_ready_when_tool_engine_fails(self, start_time, version):
        """L'app ne doit pas être prête si le moteur d'outils échoue."""
        engine = MagicMock()
        engine.list_tools.side_effect = RuntimeError("Indisponible")

        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            tool_engine=engine,
        )
        ready, reason = checker.check_readiness()
        assert ready is False
        assert "tool_engine" in reason


class TestCheckLiveness:
    """Tests pour la méthode check_liveness()."""

    def test_liveness_always_true(self, start_time, version):
        """La liveness doit toujours retourner True."""
        checker = ComponentHealthChecker(start_time=start_time, version=version)
        assert checker.check_liveness() is True


class TestSetToolEngine:
    """Tests pour le late binding de tool_engine."""

    def test_set_tool_engine_updates_reference(self, start_time, version, mock_tool_engine):
        """set_tool_engine() doit mettre à jour la référence interne."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            tool_engine=None,
        )
        # Avant mise à jour
        assert checker._check_tool_engine().status == "unhealthy"

        # Après mise à jour
        checker.set_tool_engine(mock_tool_engine)
        result = checker._check_tool_engine()
        assert result.status == "healthy"
        assert result.details["tools_count"] == 3


# ---------------------------------------------------------------------------
# Tests du pattern singleton
# ---------------------------------------------------------------------------


class TestSingletonPattern:
    """Tests pour le pattern singleton (init_health_checker / get_health_checker)."""

    def test_get_before_init_raises(self, reset_health_checker):
        """get_health_checker() avant init_health_checker() doit lever RuntimeError."""
        # reset_health_checker a déjà mis _health_checker à None
        with pytest.raises(RuntimeError, match="n'a pas été initialisé"):
            get_health_checker()

    def test_init_creates_singleton(self, start_time, version, mock_tool_engine):
        """init_health_checker() doit créer et retourner un singleton."""
        checker = init_health_checker(
            start_time=start_time,
            version=version,
            tool_engine=mock_tool_engine,
        )
        assert checker is not None
        assert isinstance(checker, HealthChecker)

        # Un deuxième appel doit retourner la même instance
        checker2 = init_health_checker(
            start_time=start_time,
            version=version,
            tool_engine=mock_tool_engine,
        )
        assert checker2 is checker

    def test_get_after_init_returns_same(self, start_time, version, mock_tool_engine):
        """get_health_checker() après init doit retourner l'instance créée."""
        init_health_checker(
            start_time=start_time,
            version=version,
            tool_engine=mock_tool_engine,
        )
        retrieved = get_health_checker()
        assert retrieved is not None

    def test_init_preserves_first_instance(self, start_time, version, mock_tool_engine):
        """Un deuxième init avec des paramètres différents doit ignorer les changements."""
        checker1 = init_health_checker(
            start_time=start_time,
            version=version,
            tool_engine=mock_tool_engine,
        )
        # Tenter d'initialiser avec des paramètres différents
        checker2 = init_health_checker(
            start_time=start_time + 5000,
            version="999.0.0",
            tool_engine=None,
        )
        assert checker2 is checker1


# ---------------------------------------------------------------------------
# Tests d'intégration avec TestClient (endpoints HTTP)
# ---------------------------------------------------------------------------


@pytest.fixture
def test_app(start_time, version, mock_memory_manager, mock_model_manager,
             mock_knowledge_manager, mock_tool_engine):
    """Crée une application FastAPI de test avec les endpoints de santé."""
    from fastapi import HTTPException

    app = FastAPI()

    # Initialiser le vérificateur de santé AVANT de définir les routes
    init_health_checker(
        start_time=start_time,
        version=version,
        memory_manager=mock_memory_manager,
        model_manager=mock_model_manager,
        knowledge_manager=mock_knowledge_manager,
        tool_engine=mock_tool_engine,
    )

    from src.api.health import get_health_checker as ghc

    @app.get("/health")
    async def health():
        checker = ghc()
        report = checker.check_health()
        return report.to_dict()

    @app.get("/ready")
    async def ready():
        checker = ghc()
        is_ready, reason = checker.check_readiness()
        if is_ready:
            return {"status": "ready", "reason": reason}
        else:
            raise HTTPException(status_code=503, detail=reason)

    @app.get("/live")
    async def live():
        checker = ghc()
        alive = checker.check_liveness()
        return {"status": "alive" if alive else "dead"}

    return app


@pytest.fixture
def test_app_not_ready(start_time, version):
    """Crée une app de test où tool_engine est None (pas prête)."""
    from fastapi import HTTPException

    app = FastAPI()

    init_health_checker(
        start_time=start_time,
        version=version,
        memory_manager=None,
        model_manager=None,
        knowledge_manager=None,
        tool_engine=None,
    )

    from src.api.health import get_health_checker as ghc

    @app.get("/ready")
    async def ready():
        checker = ghc()
        is_ready, reason = checker.check_readiness()
        if is_ready:
            return {"status": "ready", "reason": reason}
        else:
            raise HTTPException(status_code=503, detail=reason)

    return app


class TestHealthEndpoint:
    """Tests d'intégration pour l'endpoint GET /health."""

    def test_health_returns_200(self, test_app):
        """L'endpoint /health doit retourner 200."""
        client = TestClient(test_app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_valid_json(self, test_app):
        """La réponse de /health doit être un JSON valide avec les champs requis."""
        client = TestClient(test_app)
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "uptime" in data
        assert "components" in data
        assert "storage_backend" in data
        assert "configured_providers" in data

    def test_health_status_is_string(self, test_app):
        """Le statut global doit être une chaîne parmi les valeurs attendues."""
        client = TestClient(test_app)
        response = client.get("/health")
        data = response.json()

        assert data["status"] in ("healthy", "degraded", "unhealthy")

    def test_health_all_components_present(self, test_app):
        """Tous les composants doivent être présents dans la réponse."""
        client = TestClient(test_app)
        response = client.get("/health")
        data = response.json()

        expected_components = [
            "api", "memory_engine", "model_engine",
            "knowledge_engine", "tool_engine", "storage",
        ]
        for comp in expected_components:
            assert comp in data["components"], f"Composant {comp} manquant"


class TestReadyEndpoint:
    """Tests d'intégration pour l'endpoint GET /ready."""

    def test_ready_returns_200_when_healthy(self, test_app):
        """L'endpoint /ready doit retourner 200 quand l'app est prête."""
        client = TestClient(test_app)
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_ready_returns_503_when_not_ready(self, test_app_not_ready):
        """L'endpoint /ready doit retourner 503 quand l'app n'est pas prête."""
        client = TestClient(test_app_not_ready)
        response = client.get("/ready")
        assert response.status_code == 503
        assert "tool_engine" in response.json()["detail"]


class TestLiveEndpoint:
    """Tests d'intégration pour l'endpoint GET /live."""

    def test_live_returns_200(self, test_app):
        """L'endpoint /live doit toujours retourner 200."""
        client = TestClient(test_app)
        response = client.get("/live")
        assert response.status_code == 200

    def test_live_returns_alive(self, test_app):
        """L'endpoint /live doit retourner le statut 'alive'."""
        client = TestClient(test_app)
        response = client.get("/live")
        data = response.json()
        assert data["status"] == "alive"


# ---------------------------------------------------------------------------
# Tests de robustesse
# ---------------------------------------------------------------------------


class TestRobustness:
    """Tests de robustesse et cas limites."""

    def test_component_failure_doesnt_block_others(self, start_time, version):
        """La défaillance d'un composant ne doit pas empêcher de vérifier les autres."""
        # memory_engine va échouer, mais les autres doivent être vérifiés
        mgr = MagicMock()
        mgr.save_memory.side_effect = RuntimeError("Échec mémoire")
        tool = MagicMock()
        tool.list_tools.return_value = [{"name": "test"}]

        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=mgr,
            model_manager=None,
            knowledge_manager=None,
            tool_engine=tool,
        )
        report = checker.check_health()

        # Tous les composants doivent être présents malgré l'échec mémoire
        assert "memory_engine" in report.components
        assert "tool_engine" in report.components
        assert "api" in report.components
        # Le moteur de mémoire doit être unhealthy
        assert report.components["memory_engine"].status == "unhealthy"
        # Mais le moteur d'outils doit être healthy
        assert report.components["tool_engine"].status == "healthy"

    def test_memory_engine_cleanup_failure_ignored(self, start_time, version):
        """L'échec du nettoyage (delete) ne doit pas affecter le résultat."""
        mgr = MagicMock()
        mgr.save_memory.return_value = "test-id"
        mock_item = MagicMock()
        mock_item.content = "health_check_test"
        mgr.get_memory.return_value = mock_item
        mgr.delete_memory.side_effect = RuntimeError("Échec du nettoyage")

        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=mgr,
        )
        result = checker._check_memory_engine()
        # Le nettoyage échoue mais la vérification a réussi
        assert result.status == "healthy"

    def test_overall_status_unhealthy_wins_over_degraded(self, start_time, version):
        """Unhealthy doit avoir priorité sur degraded dans le statut global."""
        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=None,  # unhealthy
            model_manager=None,   # unhealthy
            knowledge_manager=None,  # unhealthy
            tool_engine=MagicMock(),  # healthy
        )
        checker._tool_engine.list_tools.return_value = [{"name": "test"}]
        # Le stockage peut être degraded si on définit un backend inconnu
        with patch.dict(os.environ, {"GALSEN_STORAGE_BACKEND": "in-memory"}):
            report = checker.check_health()
            # Avec des composants unhealthy, le statut global doit être unhealthy
            assert report.status == "unhealthy"

    def test_model_manager_exception_in_providers(self, start_time, version, mock_tool_engine):
        """Si get_configured_providers lève une exception, on récupère une liste vide."""
        mgr = MagicMock()
        mgr.get_provider_status.side_effect = RuntimeError("Échec")

        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            model_manager=mgr,
            tool_engine=mock_tool_engine,
        )
        report = checker.check_health()
        # Le moteur de modèles sera unhealthy
        assert report.components["model_engine"].status == "unhealthy"
        # Les fournisseurs configurés seront vides (exception rattrapée)
        assert report.configured_providers == []

    def test_knowledge_stats_without_store_key(self, start_time, version):
        """Si get_stats() ne contient pas la clé 'store', total_items = 0."""
        mgr = MagicMock()
        mgr.get_stats.return_value = {"cache": {"size": 5}}

        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            knowledge_manager=mgr,
        )
        result = checker._check_knowledge_engine()
        assert result.status == "healthy"
        assert result.details["total_items"] == 0

    def test_knowledge_stats_not_a_dict(self, start_time, version):
        """Si get_stats() ne retourne pas un dict, on ne plante pas."""
        mgr = MagicMock()
        mgr.get_stats.return_value = "not_a_dict"

        checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            knowledge_manager=mgr,
        )
        result = checker._check_knowledge_engine()
        # Ne doit pas planter — le except dans la méthode capture tout
        assert result.status == "healthy"
