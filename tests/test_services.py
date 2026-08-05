"""
Tests unitaires pour les services backend (Notification, Search, File).

Couvre :
- NotificationService : envoi, lecture, filtrage, marquage, suppression, statistiques
- SearchService : enregistrement de providers, recherche multi-source, tri, fusion
- FileService : upload, validation, lecture, filtrage, métadonnées, statistiques
"""

import os
import sys
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# S'assurer que le projet est dans le chemin
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# =========================================================================
# Tests — Notification Service
# =========================================================================


class TestNotificationTypes:
    """Vérifie les modèles de données des notifications."""

    def test_generate_notification_id_prefix(self):
        """L'identifiant de notification doit commencer par 'notif_'."""
        from src.services.notification import generate_notification_id
        nid = generate_notification_id()
        assert nid.startswith("notif_")
        assert len(nid) > 10

    def test_notification_default_priority(self):
        """La priorité par défaut doit être NORMAL."""
        from src.services.notification import Notification, NotificationType
        n = Notification(notification_type=NotificationType.INFO, title="Test", message="Message")
        assert n.priority.value == "normal"

    def test_notification_default_unread(self):
        """Une nouvelle notification doit être non lue."""
        from src.services.notification import Notification, NotificationType
        n = Notification(notification_type=NotificationType.INFO, title="Test", message="Message")
        assert not n.read

    def test_notification_mark_read(self):
        """mark_read() doit marquer la notification comme lue et horodater."""
        from src.services.notification import Notification, NotificationType
        n = Notification(notification_type=NotificationType.INFO, title="Test", message="Message")
        n.mark_read()
        assert n.read
        assert n.read_at is not None
        assert n.read_at > 0

    def test_notification_to_dict(self):
        """to_dict() doit inclure tous les champs obligatoires et optionnels."""
        from src.services.notification import Notification, NotificationType
        n = Notification(
            notification_type=NotificationType.WARNING,
            title="Alerte",
            message="Message important",
            recipient="user123",
            metadata={"source": "system"},
        )
        d = n.to_dict()
        assert d["id"] == n.id
        assert d["type"] == "warning"
        assert d["title"] == "Alerte"
        assert d["message"] == "Message important"
        assert d["recipient"] == "user123"
        assert d["read"] is False
        assert "created_at" in d
        assert "metadata" in d

    def test_notification_from_mapping(self):
        """from_mapping() doit reconstruire une notification depuis un dictionnaire."""
        from src.services.notification import Notification, NotificationType
        original = Notification(notification_type=NotificationType.ERROR, title="Erreur", message="Détail")
        d = original.to_dict()
        restored = Notification.from_mapping(d)
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.message == original.message
        assert restored.notification_type == NotificationType.ERROR

    def test_notification_from_mapping_string_type(self):
        """from_mapping() doit accepter un type sous forme de chaîne."""
        from src.services.notification import Notification, NotificationType
        restored = Notification.from_mapping({
            "type": "error",
            "title": "Test",
            "message": "Message",
        })
        assert restored.notification_type == NotificationType.ERROR

    def test_notification_from_mapping_invalid_type_defaults_info(self):
        """Un type invalide doit être remplacé par INFO."""
        from src.services.notification import Notification, NotificationType
        restored = Notification.from_mapping({
            "type": "unknown_type",
            "title": "Test",
            "message": "Message",
        })
        assert restored.notification_type == NotificationType.INFO


class TestInMemoryNotificationStore:
    """Vérifie le stockage en mémoire des notifications."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.notification import InMemoryNotificationStore, Notification, NotificationType
        self.store = InMemoryNotificationStore()
        self.notif_a = Notification(notification_type=NotificationType.INFO, title="A", message="Msg A",
                                     recipient="user1")
        self.notif_b = Notification(notification_type=NotificationType.WARNING, title="B", message="Msg B",
                                     recipient="user2")
        self.notif_c = Notification(notification_type=NotificationType.ERROR, title="C", message="Msg C",
                                     recipient="user1")

    def test_save_and_get(self):
        """save() puis get() doivent retourner la même notification."""
        nid = self.store.save(self.notif_a)
        retrieved = self.store.get(nid)
        assert retrieved is not None
        assert retrieved.id == self.notif_a.id
        assert retrieved.title == "A"

    def test_save_duplicate_raises(self):
        """save() d'un identifiant existant doit lever ValueError."""
        self.store.save(self.notif_a)
        with pytest.raises(ValueError, match="existe déjà"):
            self.store.save(self.notif_a)

    def test_get_missing_returns_none(self):
        """get() d'un identifiant inconnu doit retourner None."""
        assert self.store.get("nonexistent") is None

    def test_list_notifications_ordered_by_recency(self):
        """list_notifications() doit retourner les notifications de la plus récente à la plus ancienne."""
        self.store.save(self.notif_a)
        time.sleep(0.01)
        self.store.save(self.notif_b)
        time.sleep(0.01)
        self.store.save(self.notif_c)
        all_notifs = self.store.list_notifications(limit=10)
        assert len(all_notifs) == 3
        # La plus récente en premier (c, b, a)
        assert all_notifs[0].id == self.notif_c.id
        assert all_notifs[2].id == self.notif_a.id

    def test_list_notifications_filter_unread(self):
        """list_notifications(unread_only=True) doit exclure les lues."""
        self.store.save(self.notif_a)
        self.store.save(self.notif_b)
        self.store.mark_read(self.notif_a.id)
        unread = self.store.list_notifications(limit=10, unread_only=True)
        assert len(unread) == 1
        assert unread[0].id == self.notif_b.id

    def test_list_notifications_filter_type(self):
        """list_notifications() doit filtrer par type."""
        self.store.save(self.notif_a)  # INFO
        self.store.save(self.notif_b)  # WARNING
        self.store.save(self.notif_c)  # ERROR
        warnings = self.store.list_notifications(limit=10, notification_type="warning")
        assert len(warnings) == 1
        assert warnings[0].id == self.notif_b.id

    def test_list_notifications_filter_recipient(self):
        """list_notifications() doit filtrer par destinataire."""
        self.store.save(self.notif_a)  # user1
        self.store.save(self.notif_b)  # user2
        self.store.save(self.notif_c)  # user1
        user1_notifs = self.store.list_notifications(limit=10, recipient="user1")
        assert len(user1_notifs) == 2

    def test_mark_read(self):
        """mark_read() doit marquer la notification comme lue."""
        self.store.save(self.notif_a)
        assert self.store.mark_read(self.notif_a.id)
        retrieved = self.store.get(self.notif_a.id)
        assert retrieved is not None
        assert retrieved.read

    def test_mark_read_missing(self):
        """mark_read() d'une notification inconnue doit retourner False."""
        assert not self.store.mark_read("nonexistent")

    def test_mark_read_already_read_is_idempotent(self):
        """mark_read() deux fois sur la même notification doit être idempotent."""
        self.store.save(self.notif_a)
        assert self.store.mark_read(self.notif_a.id)
        assert self.store.mark_read(self.notif_a.id)  # ne doit pas lever

    def test_mark_all_read(self):
        """mark_all_read() doit marquer toutes les notifications comme lues."""
        self.store.save(self.notif_a)
        self.store.save(self.notif_b)
        count = self.store.mark_all_read()
        assert count == 2
        assert self.store.get(self.notif_a.id).read
        assert self.store.get(self.notif_b.id).read

    def test_mark_all_read_filter_recipient(self):
        """mark_all_read(recipient=...) doit uniquement marquer celles du destinataire."""
        self.store.save(self.notif_a)  # user1
        self.store.save(self.notif_b)  # user2
        count = self.store.mark_all_read(recipient="user1")
        assert count == 1
        assert self.store.get(self.notif_a.id).read
        assert not self.store.get(self.notif_b.id).read

    def test_delete(self):
        """delete() doit supprimer une notification."""
        self.store.save(self.notif_a)
        assert self.store.delete(self.notif_a.id)
        assert self.store.get(self.notif_a.id) is None

    def test_delete_missing(self):
        """delete() d'une notification inconnue doit retourner False."""
        assert not self.store.delete("nonexistent")

    def test_stats(self):
        """stats() doit retourner des statistiques correctes."""
        self.store.save(self.notif_a)  # INFO, user1
        self.store.save(self.notif_b)  # WARNING, user2
        stats = self.store.stats()
        assert stats["total"] == 2
        assert stats["unread"] == 2
        assert stats["by_type"]["info"] == 1
        assert stats["by_type"]["warning"] == 1

    def test_stats_filter_recipient(self):
        """stats(recipient=...) doit filtrer par destinataire."""
        self.store.save(self.notif_a)  # user1
        self.store.save(self.notif_b)  # user2
        stats = self.store.stats(recipient="user1")
        assert stats["total"] == 1

    def test_clear(self):
        """clear() doit supprimer toutes les notifications."""
        self.store.save(self.notif_a)
        self.store.save(self.notif_b)
        assert self.store.clear() == 2
        assert self.store.count() == 0

    def test_list_with_limit(self):
        """list_notifications() doit respecter la limite."""
        self.store.save(self.notif_a)
        self.store.save(self.notif_b)
        self.store.save(self.notif_c)
        assert len(self.store.list_notifications(limit=2)) == 2

    def test_list_with_offset(self):
        """list_notifications() doit respecter l'offset."""
        self.store.save(self.notif_a)
        self.store.save(self.notif_b)
        self.store.save(self.notif_c)
        # Offset 2: seulement le plus ancien (a)
        results = self.store.list_notifications(limit=10, offset=2)
        assert len(results) == 1
        assert results[0].id == self.notif_a.id


class TestNotificationManager:
    """Vérifie le gestionnaire de notifications (best-effort)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.notification import NotificationManagerImpl, NotificationType
        self.manager = NotificationManagerImpl()
        self.notif_type = NotificationType

    def test_send_notification(self):
        """send_notification() doit retourner un identifiant valide."""
        nid = self.manager.send_notification(self.notif_type.INFO, "Test", "Message")
        assert nid is not None
        assert nid.startswith("notif_")

    def test_send_and_get(self):
        """send_notification() puis get() doivent retourner la même notification."""
        nid = self.manager.send_notification(self.notif_type.WARNING, "Alerte", "Attention")
        notif = self.manager.get(nid)
        assert notif is not None
        assert notif.title == "Alerte"
        assert notif.notification_type == self.notif_type.WARNING

    def test_send_notification_with_all_fields(self):
        """send_notification() doit accepter tous les champs optionnels."""
        from src.services.notification import NotificationPriority
        nid = self.manager.send_notification(
            notification_type=self.notif_type.ERROR,
            title="Erreur critique",
            message="Détail de l'erreur",
            priority=NotificationPriority.HIGH,
            recipient="admin",
            role="operator",
            source="test",
            related_id="req_123",
            metadata={"code": 500},
        )
        assert nid is not None
        notif = self.manager.get(nid)
        assert notif.recipient == "admin"
        assert notif.role == "operator"

    def test_list(self):
        """list_notifications() doit retourner les notifications envoyées."""
        self.manager.send_notification(self.notif_type.INFO, "A", "Msg A", recipient="user1")
        self.manager.send_notification(self.notif_type.WARNING, "B", "Msg B", recipient="user2")
        results = self.manager.list_notifications()
        assert len(results) == 2

    def test_list_filter_recipient(self):
        """list_notifications(recipient=...) doit filtrer."""
        self.manager.send_notification(self.notif_type.INFO, "A", "Msg A", recipient="user1")
        self.manager.send_notification(self.notif_type.WARNING, "B", "Msg B", recipient="user2")
        results = self.manager.list_notifications(recipient="user1")
        assert len(results) == 1
        assert results[0].title == "A"

    def test_mark_read(self):
        """mark_read() doit marquer comme lue."""
        nid = self.manager.send_notification(self.notif_type.INFO, "Test", "Message")
        assert self.manager.mark_read(nid)
        notif = self.manager.get(nid)
        assert notif.read

    def test_mark_read_missing(self):
        """mark_read() d'une notification inconnue doit retourner False sans erreur."""
        assert not self.manager.mark_read("nonexistent")

    def test_mark_all_read(self):
        """mark_all_read() doit marquer toutes les notifications comme lues."""
        self.manager.send_notification(self.notif_type.INFO, "A", "Msg A")
        self.manager.send_notification(self.notif_type.INFO, "B", "Msg B")
        assert self.manager.mark_all_read() == 2

    def test_delete(self):
        """delete() doit supprimer la notification."""
        nid = self.manager.send_notification(self.notif_type.INFO, "Test", "Message")
        assert self.manager.delete(nid)
        assert self.manager.get(nid) is None

    def test_delete_missing(self):
        """delete() d'une notification inconnue doit retourner False sans erreur."""
        assert not self.manager.delete("nonexistent")

    def test_stats(self):
        """stats() doit retourner des statistiques cohérentes."""
        self.manager.send_notification(self.notif_type.INFO, "A", "Msg A")
        self.manager.send_notification(self.notif_type.WARNING, "B", "Msg B")
        stats = self.manager.stats()
        assert stats["total"] == 2
        assert stats["unread"] == 2

    def test_clear(self):
        """clear() doit tout supprimer."""
        self.manager.send_notification(self.notif_type.INFO, "A", "Msg A")
        assert self.manager.clear() == 1
        assert len(self.manager.list_notifications()) == 0

    def test_store_failure_graceful(self):
        """Une panne du store ne doit pas crasher le manager."""
        from src.services.notification import NotificationStore
        broken_store = MagicMock(spec=NotificationStore)
        broken_store.save.side_effect = RuntimeError("Stockage indisponible")
        broken_store.get.side_effect = RuntimeError("Stockage indisponible")
        broken_store.list_notifications.side_effect = RuntimeError("Stockage indisponible")
        broken_store.mark_read.side_effect = RuntimeError("Stockage indisponible")
        broken_store.delete.side_effect = RuntimeError("Stockage indisponible")
        broken_store.stats.side_effect = RuntimeError("Stockage indisponible")
        broken_store.mark_all_read.side_effect = RuntimeError("Stockage indisponible")
        broken_store.clear.side_effect = RuntimeError("Stockage indisponible")
        manager = type(self.manager)(store=broken_store)
        assert manager.send_notification(self.notif_type.INFO, "T", "M") is None
        assert manager.get("any") is None
        assert manager.list_notifications() == []
        assert manager.mark_read("any") is False
        assert manager.delete("any") is False
        assert manager.stats() == {}
        assert manager.mark_all_read() == 0
        assert manager.clear() == 0


# =========================================================================
# Tests — Search Service
# =========================================================================


class TestSearchTypes:
    """Vérifie les modèles de données de la recherche."""

    def test_generate_search_id_prefix(self):
        """L'identifiant de recherche doit commencer par 'search_'."""
        from src.services.search import generate_search_id
        sid = generate_search_id()
        assert sid.startswith("search_")

    def test_search_query_default_sources(self):
        """SearchQuery doit avoir toutes les sources par défaut."""
        from src.services.search import SearchQuery, SearchSource
        q = SearchQuery(query="test")
        assert len(q.sources) == len(list(SearchSource))

    def test_search_query_default_limit(self):
        """SearchQuery doit avoir une limite par défaut de 10."""
        from src.services.search import SearchQuery
        q = SearchQuery(query="test")
        assert q.limit == 10

    def test_search_result_item_to_dict(self):
        """SearchResultItem.to_dict() doit sérialiser correctement."""
        from src.services.search import SearchResultItem, SearchSource
        item = SearchResultItem(
            id="item_1",
            source=SearchSource.KNOWLEDGE,
            content="Contenu test",
            score=0.95,
            title="Résultat test",
        )
        d = item.to_dict()
        assert d["id"] == "item_1"
        assert d["source"] == "knowledge"
        assert d["score"] == 0.95
        assert d["title"] == "Résultat test"

    def test_search_response_to_dict(self):
        """SearchResponse.to_dict() doit inclure résultats, total, métadonnées."""
        from src.services.search import SearchResponse, SearchResultItem, SearchSource
        item = SearchResultItem(id="1", source=SearchSource.MEMORY, content="test", score=0.8)
        resp = SearchResponse(results=[item], total=1, query="test")
        d = resp.to_dict()
        assert d["total"] == 1
        assert len(d["results"]) == 1
        assert d["query"] == "test"
        assert "search_id" in d
        assert "execution_time_ms" in d


class TestSearchManager:
    """Vérifie le gestionnaire de recherche unifiée."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.search import (
            SearchManagerImpl, SearchProvider, SearchQuery, SearchResultItem, SearchSource,
        )
        self.SearchQuery = SearchQuery
        self.SearchSource = SearchSource
        self.manager = SearchManagerImpl()

        # Provider simulé pour la connaissance
        self.knowledge_provider = MagicMock(spec=SearchProvider)
        self.knowledge_provider.source = SearchSource.KNOWLEDGE
        self.knowledge_provider.search.return_value = [
            SearchResultItem(id="k1", source=SearchSource.KNOWLEDGE, content="Savoir 1", score=0.9),
            SearchResultItem(id="k2", source=SearchSource.KNOWLEDGE, content="Savoir 2", score=0.7),
        ]
        self.manager.register_provider(self.knowledge_provider)

        # Provider simulé pour la mémoire
        self.memory_provider = MagicMock(spec=SearchProvider)
        self.memory_provider.source = SearchSource.MEMORY
        self.memory_provider.search.return_value = [
            SearchResultItem(id="m1", source=SearchSource.MEMORY, content="Souvenir 1", score=0.85),
        ]
        self.manager.register_provider(self.memory_provider)

    def test_register_provider(self):
        """register_provider() doit ajouter un fournisseur."""
        from src.services.search import SearchManagerImpl, SearchProvider, SearchSource
        mgr = SearchManagerImpl()
        p = MagicMock(spec=SearchProvider)
        p.source = SearchSource.VISION
        mgr.register_provider(p)
        mgr._providers[SearchSource.VISION] = p  # ne doit pas planter

    def test_search_calls_all_providers(self):
        """search() doit appeler tous les fournisseurs enregistrés."""
        query = self.SearchQuery(query="test", sources=[self.SearchSource.KNOWLEDGE, self.SearchSource.MEMORY])
        response = self.manager.search(query)
        self.knowledge_provider.search.assert_called_once()
        self.memory_provider.search.assert_called_once()

    def test_search_merges_results(self):
        """search() doit fusionner les résultats triés par score."""
        query = self.SearchQuery(query="test", sources=[self.SearchSource.KNOWLEDGE, self.SearchSource.MEMORY])
        response = self.manager.search(query)
        # k1=0.9, m1=0.85 (pondéré), k2=0.7
        assert len(response.results) == 3
        # Le premier résultat doit être le plus pertinent
        assert response.results[0].score >= response.results[-1].score

    def test_search_total_count(self):
        """search() doit retourner le nombre total correct."""
        query = self.SearchQuery(query="test", sources=[self.SearchSource.KNOWLEDGE, self.SearchSource.MEMORY])
        response = self.manager.search(query)
        assert response.total == 3

    def test_search_single_source(self):
        """search_single_source() doit interroger une seule source."""
        from src.services.search import SearchSource, SearchQuery
        query = SearchQuery(query="test")
        results = self.manager.search_single_source(SearchSource.KNOWLEDGE, query)
        assert len(results) == 2

    def test_search_single_source_unregistered(self):
        """search_single_source() sur une source non enregistrée doit retourner []."""
        from src.services.search import SearchSource, SearchQuery
        query = SearchQuery(query="test")
        results = self.manager.search_single_source(SearchSource.VISION, query)
        assert results == []

    def test_search_respects_limit(self):
        """search() doit respecter la limite de résultats."""
        query = self.SearchQuery(query="test", sources=[self.SearchSource.KNOWLEDGE], limit=1)
        response = self.manager.search(query)
        assert len(response.results) <= 1

    def test_search_min_score(self):
        """search() doit filtrer par score minimum."""
        from src.services.search import SearchQuery, SearchSource
        query = SearchQuery(query="test", sources=[SearchSource.KNOWLEDGE], min_score=0.8)
        response = self.manager.search(query)
        assert all(r.score >= 0.8 for r in response.results)

    def test_search_sources_used(self):
        """search() doit lister les sources utilisées."""
        query = self.SearchQuery(query="test", sources=[self.SearchSource.KNOWLEDGE, self.SearchSource.MEMORY])
        response = self.manager.search(query)
        assert "knowledge" in response.sources_used
        assert "memory" in response.sources_used

    def test_search_date_sort(self):
        """search() doit supporter le tri par date."""
        from src.services.search import SearchQuery, SearchSource, SearchSort, SearchResultItem
        from unittest.mock import MagicMock

        # Provider avec dates différentes
        time_provider = MagicMock()
        time_provider.source = SearchSource.MEMORY
        time_provider.search.return_value = [
            SearchResultItem(id="old", source=SearchSource.MEMORY, content="Ancien", score=0.5, created_at=100),
            SearchResultItem(id="new", source=SearchSource.MEMORY, content="Récent", score=0.5, created_at=200),
        ]
        mgr = type(self.manager)()
        mgr.register_provider(time_provider)

        q = SearchQuery(query="test", sources=[SearchSource.MEMORY], sort=SearchSort.DATE_DESC)
        resp = mgr.search(q)
        assert resp.results[0].id == "new"
        assert resp.results[1].id == "old"

    def test_provider_failure_graceful(self):
        """Un provider qui échoue ne doit pas bloquer la recherche."""
        broken = MagicMock()
        broken.source = self.knowledge_provider.source
        broken.search.side_effect = RuntimeError("Provider indisponible")

        from src.services.search import SearchSource, SearchQuery
        mgr = type(self.manager)()
        mgr.register_provider(broken)
        mgr.register_provider(self.memory_provider)

        query = SearchQuery(query="test", sources=[SearchSource.KNOWLEDGE, SearchSource.MEMORY])
        response = mgr.search(query)
        # La mémoire doit encore répondre
        assert len(response.results) == 1
        assert response.results[0].id == "m1"


# =========================================================================
# Tests — File Service
# =========================================================================


class TestFileTypes:
    """Vérifie les modèles de données des fichiers."""

    def test_generate_file_id_prefix(self):
        """L'identifiant de fichier doit commencer par 'file_'."""
        from src.services.file import generate_file_id
        fid = generate_file_id()
        assert fid.startswith("file_")

    def test_file_item_default_category(self):
        """Un fichier sans type MIME reconnu doit avoir la catégorie OTHER."""
        from src.services.file import FileItem
        f = FileItem(name="test.xyz", content_type="application/octet-stream", size=10, data=b"data")
        assert f.category.value == "other"

    def test_file_item_to_dict_without_data(self):
        """to_dict(include_data=False) ne doit pas inclure le contenu binaire."""
        from src.services.file import FileItem
        f = FileItem(name="test.txt", content_type="text/plain", size=5, data=b"hello")
        d = f.to_dict(include_data=False)
        assert d["name"] == "test.txt"
        assert "data" not in d

    def test_file_item_to_dict_with_data(self):
        """to_dict(include_data=True) doit inclure le contenu en base64."""
        from src.services.file import FileItem
        import base64
        f = FileItem(name="test.txt", content_type="text/plain", size=5, data=b"hello")
        d = f.to_dict(include_data=True)
        assert d["data"] == base64.b64encode(b"hello").decode("utf-8")

    def test_file_item_from_mapping(self):
        """from_mapping() doit reconstruire un fichier depuis un dictionnaire."""
        from src.services.file import FileItem
        import base64
        original = FileItem(name="doc.pdf", content_type="application/pdf", size=100, data=b"pdf content")
        d = original.to_dict(include_data=True)
        restored = FileItem.from_mapping(d)
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.content_type == original.content_type
        assert restored.data == original.data

    def test_get_category_for_content_type(self):
        """get_category_for_content_type() doit mapper les types MIME courants."""
        from src.services.file import get_category_for_content_type, FileCategory
        assert get_category_for_content_type("application/pdf") == FileCategory.DOCUMENT
        assert get_category_for_content_type("image/jpeg") == FileCategory.IMAGE
        assert get_category_for_content_type("application/json") == FileCategory.DATA
        assert get_category_for_content_type("text/csv") == FileCategory.DATA

    def test_is_content_type_allowed(self):
        """is_content_type_allowed() doit fonctionner avec un ensemble d'autorisation."""
        from src.services.file import is_content_type_allowed
        allowed = {"text/plain", "application/pdf"}
        assert is_content_type_allowed("text/plain", allowed)
        assert is_content_type_allowed("text/csv", allowed) is False
        assert is_content_type_allowed("text/plain")  # pas de filtre


class TestInMemoryFileStore:
    """Vérifie le stockage en mémoire des fichiers."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.file import InMemoryFileStore, FileItem, FileCategory
        self.store = InMemoryFileStore()
        self.file_a = FileItem(name="doc1.pdf", content_type="application/pdf", size=100, data=b"pdf data",
                               category=FileCategory.DOCUMENT)
        self.file_b = FileItem(name="img1.png", content_type="image/png", size=200, data=b"png data",
                               uploaded_by="user1", category=FileCategory.IMAGE)
        self.file_c = FileItem(name="doc2.txt", content_type="text/plain", size=50, data=b"text data",
                               uploaded_by="user1", category=FileCategory.DOCUMENT)

    def test_save_and_get(self):
        """save() puis get() doivent retourner le même fichier."""
        fid = self.store.save(self.file_a)
        retrieved = self.store.get(fid)
        assert retrieved is not None
        assert retrieved.id == self.file_a.id

    def test_save_duplicate_raises(self):
        """save() d'un identifiant existant doit lever ValueError."""
        self.store.save(self.file_a)
        with pytest.raises(ValueError, match="existe déjà"):
            self.store.save(self.file_a)

    def test_get_missing_returns_none(self):
        """get() d'un identifiant inconnu doit retourner None."""
        assert self.store.get("nonexistent") is None

    def test_get_by_name(self):
        """get_by_name() doit trouver un fichier par nom."""
        self.store.save(self.file_a)
        found = self.store.get_by_name("doc1.pdf")
        assert found is not None
        assert found.id == self.file_a.id

    def test_get_by_name_missing(self):
        """get_by_name() d'un nom inconnu doit retourner None."""
        assert self.store.get_by_name("missing.txt") is None

    def test_list_files_all(self):
        """list_files() doit retourner tous les fichiers du plus récent au plus ancien."""
        self.store.save(self.file_a)
        self.store.save(self.file_b)
        self.store.save(self.file_c)
        results = self.store.list_files()
        assert len(results) == 3

    def test_list_files_filter_category(self):
        """list_files() doit filtrer par catégorie."""
        self.store.save(self.file_a)  # document
        self.store.save(self.file_b)  # image
        self.store.save(self.file_c)  # document
        docs = self.store.list_files(category="document")
        assert len(docs) == 2

    def test_list_files_filter_uploaded_by(self):
        """list_files() doit filtrer par utilisateur."""
        self.store.save(self.file_a)  # pas d'uploader
        self.store.save(self.file_b)  # user1
        self.store.save(self.file_c)  # user1
        user1_files = self.store.list_files(uploaded_by="user1")
        assert len(user1_files) == 2

    def test_delete(self):
        """delete() doit supprimer un fichier."""
        fid = self.store.save(self.file_a)
        assert self.store.delete(fid)
        assert self.store.get(fid) is None

    def test_delete_missing(self):
        """delete() d'un fichier inconnu doit retourner False."""
        assert not self.store.delete("nonexistent")

    def test_update_metadata(self):
        """update_metadata() doit ajouter des métadonnées."""
        fid = self.store.save(self.file_a)
        assert self.store.update_metadata(fid, {"source": "test"})
        retrieved = self.store.get(fid)
        assert retrieved.metadata.get("source") == "test"

    def test_update_metadata_missing(self):
        """update_metadata() d'un fichier inconnu doit retourner False."""
        assert not self.store.update_metadata("nonexistent", {"key": "val"})

    def test_stats(self):
        """stats() doit retourner des statistiques correctes."""
        self.store.save(self.file_a)  # pdf, 100 bytes
        self.store.save(self.file_b)  # png, 200 bytes
        stats = self.store.stats()
        assert stats["total"] == 2
        assert stats["total_size"] == 300
        assert stats["by_category"]["document"] == 1
        assert stats["by_category"]["image"] == 1

    def test_clear(self):
        """clear() doit supprimer tous les fichiers."""
        self.store.save(self.file_a)
        self.store.save(self.file_b)
        assert self.store.clear() == 2
        assert self.store.count() == 0

    def test_total_size(self):
        """total_size() doit retourner la somme des tailles."""
        self.store.save(self.file_a)  # 100
        self.store.save(self.file_b)  # 200
        assert self.store.total_size() == 300

    def test_list_with_limit(self):
        """list_files() doit respecter la limite."""
        self.store.save(self.file_a)
        self.store.save(self.file_b)
        self.store.save(self.file_c)
        assert len(self.store.list_files(limit=2)) == 2


class TestFileManager:
    """Vérifie le gestionnaire de fichiers (best-effort)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.file import FileManagerImpl
        self.manager = FileManagerImpl()

    def test_upload_file(self):
        """upload_file() doit retourner un résultat positif."""
        result = self.manager.upload_file("test.txt", "text/plain", b"Hello")
        assert result.success
        assert result.file_id is not None

    def test_upload_empty_name(self):
        """upload_file() avec un nom vide doit échouer."""
        result = self.manager.upload_file("", "text/plain", b"Hello")
        assert not result.success
        assert "nom" in result.error.lower()

    def test_upload_empty_data(self):
        """upload_file() avec des données vides doit échouer."""
        result = self.manager.upload_file("empty.txt", "text/plain", b"")
        assert not result.success
        assert "vide" in result.error.lower()

    def test_upload_exceeds_max_size(self):
        """upload_file() avec des données trop volumineuses doit échouer."""
        result = self.manager.upload_file("big.txt", "text/plain", b"x" * 100, max_size=50)
        assert not result.success
        assert "taille" in result.error.lower()

    def test_upload_and_get(self):
        """upload_file() puis get_file() doivent retourner le même fichier."""
        result = self.manager.upload_file("hello.txt", "text/plain", b"Hello World")
        file = self.manager.get_file(result.file_id)
        assert file is not None
        assert file.name == "hello.txt"
        assert file.data == b"Hello World"

    def test_get_file_missing(self):
        """get_file() d'un fichier inconnu doit retourner None."""
        assert self.manager.get_file("nonexistent") is None

    def test_list_files(self):
        """list_files() doit retourner les fichiers uploadés."""
        self.manager.upload_file("a.txt", "text/plain", b"a")
        self.manager.upload_file("b.txt", "text/plain", b"b")
        files = self.manager.list_files()
        assert len(files) == 2

    def test_list_files_filter_uploaded_by(self):
        """list_files() doit filtrer par uploader."""
        self.manager.upload_file("a.txt", "text/plain", b"a", uploaded_by="user1")
        self.manager.upload_file("b.txt", "text/plain", b"b", uploaded_by="user2")
        files = self.manager.list_files(uploaded_by="user1")
        assert len(files) == 1

    def test_delete_file(self):
        """delete_file() doit supprimer le fichier."""
        result = self.manager.upload_file("del.txt", "text/plain", b"delete me")
        assert self.manager.delete_file(result.file_id)
        assert self.manager.get_file(result.file_id) is None

    def test_delete_file_missing(self):
        """delete_file() d'un fichier inconnu doit retourner False sans erreur."""
        assert not self.manager.delete_file("nonexistent")

    def test_update_metadata(self):
        """update_metadata() doit fonctionner."""
        result = self.manager.upload_file("meta.txt", "text/plain", b"metadata")
        assert self.manager.update_metadata(result.file_id, {"key": "value"})
        file = self.manager.get_file(result.file_id)
        assert file.metadata.get("key") == "value"

    def test_update_metadata_missing(self):
        """update_metadata() d'un fichier inconnu doit retourner False sans erreur."""
        assert not self.manager.update_metadata("nonexistent", {"k": "v"})

    def test_stats(self):
        """stats() doit retourner des statistiques cohérentes."""
        self.manager.upload_file("a.txt", "text/plain", b"hello")
        self.manager.upload_file("b.png", "image/png", b"pngdata" * 10)
        stats = self.manager.stats()
        assert stats["total"] == 2
        assert stats["total_size"] > 0
        assert "document" in stats["by_category"]
        assert "image" in stats["by_category"]

    def test_clear(self):
        """clear() doit tout supprimer."""
        self.manager.upload_file("a.txt", "text/plain", b"a")
        assert self.manager.clear() == 1
        assert len(self.manager.list_files()) == 0


# =========================================================================
# Exécution directe
# =========================================================================

if __name__ == "__main__":
    """
    Exécute tous les tests sans pytest.
    Utile pour vérifier rapidement que les services fonctionnent.
    """
    import traceback

    tests = [
        # Notification types
        TestNotificationTypes(),
        # Notification store
        TestInMemoryNotificationStore(),
        # Notification manager
        TestNotificationManager(),
        # Search types
        TestSearchTypes(),
        # Search manager
        TestSearchManager(),
        # File types
        TestFileTypes(),
        # File store
        TestInMemoryFileStore(),
        # File manager
        TestFileManager(),
    ]

    passed = 0
    failed = 0
    for test_instance in tests:
        class_name = type(test_instance).__name__
        for attr in dir(test_instance):
            if attr.startswith("test_") and callable(getattr(test_instance, attr)):
                test_method = getattr(test_instance, attr)
                try:
                    # Exécuter le setup si présent
                    if hasattr(test_instance, "_setup"):
                        pass  # Les fixtures pytest ne sont pas appelées ici
                    test_method()
                    print(f"PASS: {class_name}.{attr}")
                    passed += 1
                except Exception as e:
                    print(f"FAIL: {class_name}.{attr} - {e}")
                    traceback.print_exc()
                    failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} tests passed.")
    if failed > 0:
        print(f"{failed} tests FAILED.")
        sys.exit(1)
    else:
        print("All tests passed!")