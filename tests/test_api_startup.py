"""
Tests d'intégration du démarrage réel de l'API GalSen IA.

Ces tests utilisent `with TestClient(app)` — la seule forme qui déclenche le
cycle de vie de FastAPI. Sans cela, `lifespan()` n'est jamais exécuté et
une erreur de câblage au démarrage reste invisible pour toute la suite.

Couvre :
- L'import de `src.api.server` depuis la racine du dépôt (commande du Dockerfile)
- L'exécution de `lifespan()` : construction du moteur d'outils
- La publication tardive du moteur d'outils au vérificateur de santé
- Le comportement de `/tool/execute` quand le moteur n'a pas pu être construit
"""

import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# La racine du dépôt doit être importable : c'est la convention de `src.api.server`
# et la commande lancée par le Dockerfile (`uvicorn src.api.server:app`).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402


@pytest.fixture
def api_key(monkeypatch):
    """
    Configure une clé API admin, puis rend son état d'origine à l'application.

    `rbac_manager` et le limiteur de taux sont des singletons partagés par toute
    la suite : recharger l'un sans le restaurer invalide les clés des autres
    fichiers de tests, qui se mettent alors à recevoir des 401.
    """
    from src.api.rate_limiter import set_valid_api_keys

    ancien_mapping = dict(server_module.rbac_manager._key_role_map)

    monkeypatch.setenv("GALSEN_API_KEYS", "cle-test:admin")
    server_module.rbac_manager.reload()
    set_valid_api_keys(server_module.rbac_manager.get_valid_keys())

    yield "cle-test"

    server_module.rbac_manager._key_role_map = ancien_mapping
    set_valid_api_keys(server_module.rbac_manager.get_valid_keys())


class TestApplicationStartup:
    """Vérifie que l'application démarre réellement."""

    def test_lifespan_builds_the_tool_engine(self):
        """Le cycle de vie doit construire le moteur d'outils."""
        with TestClient(app):
            assert server_module.tool_engine is not None
            assert len(server_module.tool_engine.list_enabled_tools()) > 0

    def test_health_reports_the_tool_engine_after_startup(self):
        """Après démarrage, /health ne doit plus signaler le moteur d'outils absent."""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            payload = response.json()
            tool_check = payload["components"]["tool_engine"]
            assert tool_check["status"] == "healthy", tool_check

    def test_startup_survives_a_broken_tool_engine(self):
        """Un moteur d'outils non constructible ne doit pas empêcher l'API de démarrer."""
        with patch.object(
            server_module, "ToolEngine", side_effect=RuntimeError("registre illisible")
        ):
            with TestClient(app) as client:
                assert server_module.tool_engine is None
                # L'API répond toujours, en signalant le composant défaillant
                assert client.get("/health").status_code == 200

    def test_tool_execute_returns_503_without_engine(self, api_key):
        """Sans moteur d'outils, /tool/execute doit répondre 503 et non planter."""
        with patch.object(
            server_module, "ToolEngine", side_effect=RuntimeError("registre illisible")
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/tool/execute",
                    json={"tool_id": "filesystem", "input": {}},
                    headers={"X-API-Key": api_key},
                )
                assert response.status_code == 503


class TestApplicationEndpointsAfterStartup:
    """Vérifie quelques endpoints sur une application réellement démarrée."""

    def test_memory_store_and_notification_send(self, api_key):
        """Les endpoints mémoire et notification doivent répondre après démarrage."""
        with TestClient(app) as client:
            headers = {"X-API-Key": api_key}
            stored = client.post(
                "/memory/store",
                json={"content": "Dakar est la capitale du Sénégal", "memory_type": "long_term"},
                headers=headers,
            )
            assert stored.status_code == 200
            assert stored.json()["id"]

            sent = client.post(
                "/notification/send",
                json={"notification_type": "info", "title": "Test", "message": "Message"},
                headers=headers,
            )
            assert sent.status_code == 200
            assert sent.json()["notification_id"].startswith("notif_")

    def test_tool_execute_runs_a_real_tool(self, api_key):
        """L'endpoint outil doit exécuter un vrai outil, options comprises."""
        with TestClient(app) as client:
            response = client.post(
                "/tool/execute",
                json={
                    "tool_id": "filesystem",
                    "input": "exists",
                    "config": {"path": "README.md"},
                },
                headers={"X-API-Key": api_key},
            )
            assert response.status_code == 200, response.text
            assert response.json() == {
                "output": True,
                "status": "success",
                "tool_id": "filesystem",
            }

    def test_endpoints_require_an_api_key(self):
        """Sans clé API, les endpoints protégés doivent répondre 401."""
        with TestClient(app) as client:
            response = client.post("/search", json={"query": "dakar"})
            assert response.status_code == 401
