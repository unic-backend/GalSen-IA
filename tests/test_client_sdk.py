"""
Tests unitaires pour le SDK client GalSen IA.

Couvre :
- Initialisation du client
- Appels vers chaque endpoint (avec mocking HTTP)
- Gestion des erreurs et timeouts

Utilise ``monkeypatch`` (built-in pytest) pour les mocks.
"""


import pytest

from src.client import GalSenClient
from src.client.models import (
    ApiResponse,
    HealthReport,
    MemoryItem,
    ModelGenerateResult,
)


@pytest.fixture
def client():
    """Client SDK de base."""
    return GalSenClient(base_url="http://test:8000", api_key="sk-test")


# =============================================================================
#  Initialisation
# =============================================================================

class TestInit:
    def test_default_base_url(self):
        c = GalSenClient()
        assert c.base_url == "http://localhost:8000"

    def test_custom_base_url(self):
        c = GalSenClient(base_url="http://example.com/api")
        assert c.base_url == "http://example.com/api"

    def test_trailing_slash_stripped(self):
        c = GalSenClient(base_url="http://x.com/")
        assert c.base_url == "http://x.com"

    def test_api_key_stored(self):
        c = GalSenClient(api_key="sk-abc")
        assert c._api_key == "sk-abc"

    def test_url_construction(self, client):
        assert client._url("/health") == "http://test:8000/health"
        assert client._url("health") == "http://test:8000/health"


# =============================================================================
#  Santé
# =============================================================================

class TestHealth:
    def test_health_ok(self, client, monkeypatch):
        def mock_get_json(path, params=None):
            return {
                "status": "healthy",
                "version": "0.1.0",
                "uptime": "2m",
                "components": [
                    {"name": "api", "status": "healthy", "details": "OK"}
                ],
            }
        monkeypatch.setattr(client, "_get_json", mock_get_json)
        report = client.health()
        assert report.status == "healthy"
        assert len(report.components) == 1
        assert report.components[0].name == "api"

    def test_health_error(self, client, monkeypatch):
        monkeypatch.setattr(client, "_get_json", lambda *a, **kw: None)
        report = client.health()
        assert report.status == "error"

    def test_ready_true(self, client, monkeypatch):
        monkeypatch.setattr(client, "_get_json", lambda *a, **kw: {"status": "ready"})
        assert client.ready() is True

    def test_ready_false(self, client, monkeypatch):
        monkeypatch.setattr(client, "_get_json", lambda *a, **kw: None)
        assert client.ready() is False


# =============================================================================
#  Mémoire
# =============================================================================

class TestMemory:
    def test_store_memory(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=True, data={"id": "mem-1"}),
        )
        result = client.store_memory("hello", user_id="u1")
        assert result.success
        assert result.data["id"] == "mem-1"

    def test_store_memory_fails(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=False, error="Non autorisé"),
        )
        result = client.store_memory("test")
        assert not result.success

    def test_retrieve_memory(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_get_json",
            lambda *a, **kw: {"id": "mem-1", "content": "hello", "tags": []},
        )
        item = client.retrieve_memory("mem-1")
        assert item is not None
        assert item.id == "mem-1"

    def test_retrieve_missing(self, client, monkeypatch):
        monkeypatch.setattr(client, "_get_json", lambda *a, **kw: None)
        assert client.retrieve_memory("nonexistent") is None

    def test_search_memory(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_get_json",
            lambda *a, **kw: [
                {"id": "m1", "content": "senegal", "memory_type": "short_term", "tags": []}
            ],
        )
        result = client.search_memory("senegal")
        assert len(result.items) == 1
        assert result.items[0].content == "senegal"

    def test_search_memory_empty(self, client, monkeypatch):
        monkeypatch.setattr(client, "_get_json", lambda *a, **kw: None)
        result = client.search_memory("xxx")
        assert len(result.items) == 0


# =============================================================================
#  Modèles
# =============================================================================

class TestModels:
    def test_generate(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(
                success=True,
                data={
                    "text": "Bonjour!",
                    "status": "completed",
                    "model_used": "gpt-4",
                    "tokens_used": 10,
                    "latency_seconds": 1.5,
                },
            ),
        )
        result = client.generate("Dis bonjour")
        assert result.text == "Bonjour!"
        assert result.model_used == "gpt-4"

    def test_generate_error(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=False, error="Modèle indisponible"),
        )
        result = client.generate("test")
        assert result.status == "error"

    def test_list_models(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_get_json",
            lambda *a, **kw: {"models": [{"name": "gpt-4", "provider": "openai", "status": "active"}]},
        )
        models = client.list_models()
        assert len(models) == 1
        assert models[0].name == "gpt-4"

    def test_list_models_none(self, client, monkeypatch):
        monkeypatch.setattr(client, "_get_json", lambda *a, **kw: None)
        assert client.list_models() == []


# =============================================================================
#  Notifications
# =============================================================================

class TestNotifications:
    def test_send(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=True),
        )
        result = client.send_notification("Titre", "Message")
        assert result.success

    def test_list(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(
                success=True,
                data={"notifications": [
                    {"id": "n1", "title": "Test", "message": "msg", "type": "info",
                     "priority": "normal", "read": False}
                ]},
            ),
        )
        notifs = client.list_notifications()
        assert len(notifs) == 1
        assert notifs[0].title == "Test"

    def test_list_fail(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=False, error="err"),
        )
        assert client.list_notifications() == []

    def test_mark_read(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=True),
        )
        assert client.mark_read("n1") is True

    def test_stats(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_get_json",
            lambda *a, **kw: {"total": 5, "unread": 2},
        )
        stats = client.notification_stats()
        assert stats.total == 5
        assert stats.unread == 2


# =============================================================================
#  Fichiers
# =============================================================================

class TestFiles:
    def test_upload(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=True),
        )
        result = client.upload_file("doc.pdf", "application/pdf", b"data")
        assert result.success

    def test_list(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(
                success=True,
                data={"files": [{"id": "f1", "name": "doc.pdf", "size": 100}]},
            ),
        )
        files = client.list_files()
        assert len(files) == 1
        assert files[0].name == "doc.pdf"

    def test_get_file_missing(self, client, monkeypatch):
        monkeypatch.setattr(client, "_get_json", lambda *a, **kw: None)
        assert client.get_file("missing") is None


# =============================================================================
#  Cloud
# =============================================================================

class TestCloud:
    def test_upload(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=True),
        )
        result = client.cloud_upload("f.pdf", "application/pdf", b"data")
        assert result.success

    def test_list(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(
                success=True,
                data={"files": [{"id": "c1", "name": "photo.jpg", "size": 500}]},
            ),
        )
        files = client.cloud_list()
        assert len(files) == 1

    def test_download(self, client, monkeypatch):
        monkeypatch.setattr(client, "_get_bytes", lambda *a, **kw: b"filedata")
        data = client.cloud_download("c1")
        assert data == b"filedata"

    def test_download_missing(self, client, monkeypatch):
        monkeypatch.setattr(client, "_get_bytes", lambda *a, **kw: None)
        assert client.cloud_download("missing") is None

    def test_delete(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=True),
        )
        assert client.cloud_delete("c1") is True

    def test_stats(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_get_json",
            lambda *a, **kw: {"total": 3, "total_size": 1000},
        )
        stats = client.cloud_stats()
        assert stats.total == 3


# =============================================================================
#  Calendrier
# =============================================================================

class TestCalendar:
    def test_create(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=True),
        )
        result = client.calendar_create(
            "Réunion", "2026-08-06T10:00", "2026-08-06T11:00"
        )
        assert result.success

    def test_list(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(
                success=True,
                data={"events": [{"id": "e1", "title": "Event1"}]},
            ),
        )
        events = client.calendar_list()
        assert len(events) == 1
        assert events[0].title == "Event1"

    def test_get(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_get_json",
            lambda *a, **kw: {"id": "e1", "title": "Event1"},
        )
        ev = client.calendar_get("e1")
        assert ev is not None
        assert ev.title == "Event1"

    def test_cancel(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=True),
        )
        assert client.calendar_cancel("e1") is True


# =============================================================================
#  Email
# =============================================================================

class TestEmail:
    def test_send(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(success=True),
        )
        result = client.send_email(
            "Sujet", "Corps", "moi@exemple.sn", ["toi@exemple.sn"]
        )
        assert result.success

    def test_list(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_request",
            lambda *a, **kw: ApiResponse(
                success=True,
                data={"emails": [{"id": "em1", "subject": "Bonjour", "sender": "a@b.c"}]},
            ),
        )
        emails = client.list_emails()
        assert len(emails) == 1

    def test_get(self, client, monkeypatch):
        monkeypatch.setattr(
            client, "_get_json",
            lambda *a, **kw: {"id": "em1", "subject": "Hello", "sender": "a@b"},
        )
        email = client.get_email("em1")
        assert email is not None
        assert email.subject == "Hello"

    def test_get_missing(self, client, monkeypatch):
        monkeypatch.setattr(client, "_get_json", lambda *a, **kw: None)
        assert client.get_email("missing") is None


# =============================================================================
#  Appels réseau réels simulés
# =============================================================================

class TestRealNetwork:
    def test_connection_refused(self):
        """Le client ne doit pas crasher sur une connexion refusée."""
        c = GalSenClient(base_url="http://localhost:1", timeout=1)
        report = c.health()
        assert report.status == "error"

    def test_client_import(self):
        """Vérifie que le module s'importe sans erreur."""
        from src.client import GalSenClient as C
        assert C is not None
        from src.client.models import HealthReport
        r = HealthReport(status="ok")
        assert r.status == "ok"

    def test_client_url(self, client):
        """Vérifie la construction d'URL."""
        assert "test:8000/health" in client._url("/health")


# =============================================================================
#  Modèles Pydantic
# =============================================================================

class TestSdkModels:
    def test_health_report_defaults(self):
        r = HealthReport()
        assert r.status == "unknown"
        assert r.components == []

    def test_api_response_defaults(self):
        r = ApiResponse()
        assert r.success is True

    def test_memory_item_defaults(self):
        m = MemoryItem()
        assert m.tags == []

    def test_model_generate_defaults(self):
        m = ModelGenerateResult()
        assert m.text == ""
        assert m.tokens_used == 0