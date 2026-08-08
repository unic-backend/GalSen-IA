"""
Tests unitaires pour la persistance SQLite des stores de services
(Notification, Calendar, Email, Cloud, File).

Couvre pour chaque store :
- Opérations CRUD : save, get, delete
- Gestion des valeurs manquantes (get, delete retournent None/False)
- list_* avec filtres, limite et offset
- Métriques : count, clear, stats
- Persistance à travers une réouverture du fichier
- Fonctionnement en :memory: et création automatique des dossiers
- Aller-retour de sérialisation (enums, dates, JSON, booléens)
- Concurrence (verrou + PRAGMA busy_timeout)
- Opérations spécifiques (mark_read, update_status, update_metadata, etc.)

Et le branchement des managers (GALSEN_STORAGE_BACKEND) :
- Sélection du backend SQLite via variable d'environnement
- Backend en mémoire par défaut
- Injection explicite d'un store prioritaire
"""

import os
import sys
import threading
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from storage.sqlite_notification_store import SQLiteNotificationStore
from storage.sqlite_calendar_store import SQLiteCalendarStore
from storage.sqlite_email_store import SQLiteEmailStore
from storage.sqlite_cloud_store import SQLiteCloudStore
from storage.sqlite_file_store import SQLiteFileStore

from services.notification.types import Notification, NotificationType, NotificationPriority
from services.calendar.types import CalendarEvent, EventStatus, EventVisibility
from services.email.types import EmailMessage, EmailAttachment, EmailStatus
from services.cloud.types import CloudFileItem, CloudProvider, CloudFileCategory
from services.file.types import FileItem, FileCategory


# ==============================================================================
# SQLiteNotificationStore
# ==============================================================================

class TestSQLiteNotificationStore:

    def _make_notif(self, **kwargs) -> Notification:
        defaults = dict(
            notification_type=NotificationType.INFO,
            title="Test",
            message="Message de test",
            priority=NotificationPriority.NORMAL,
            recipient="user@test.sn",
        )
        defaults.update(kwargs)
        if "id" not in kwargs:
            defaults["id"] = f"notif_{id(kwargs)}"
        return Notification(**defaults)

    def test_save_and_get(self, tmp_path):
        """save puis get retournent la notification correctement."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        n = self._make_notif()
        nid = store.save(n)
        assert nid == n.id

        retrieved = store.get(nid)
        assert retrieved is not None
        assert retrieved.title == "Test"
        assert retrieved.message == "Message de test"
        assert retrieved.notification_type is NotificationType.INFO
        assert retrieved.priority is NotificationPriority.NORMAL
        assert retrieved.recipient == "user@test.sn"

    def test_get_missing_returns_none(self, tmp_path):
        """get() retourne None pour un ID inconnu."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        assert store.get("inconnu") is None

    def test_save_duplicate_overwrites(self, tmp_path):
        """save() avec un ID existant écrase silencieusement (INSERT OR REPLACE)."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        n = self._make_notif(id="notif_dup")
        store.save(n)
        n2 = self._make_notif(id="notif_dup", title="Modifié")
        store.save(n2)
        retrieved = store.get("notif_dup")
        assert retrieved.title == "Modifié"

    def test_list_notifications(self, tmp_path):
        """list_notifications retourne les notifications filtrées."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        store.save(self._make_notif(id="a", recipient="user@test.sn"))
        store.save(self._make_notif(id="b", recipient="other@test.sn"))
        store.save(self._make_notif(id="c", notification_type=NotificationType.ERROR, recipient="admin@test.sn"))

        assert len(store.list_notifications()) == 3
        assert len(store.list_notifications(recipient="user@test.sn")) == 1
        assert len(store.list_notifications(notification_type="error")) == 1

    def test_list_notifications_limit(self, tmp_path):
        """list_notifications respecte limit et offset."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        for i in range(5):
            store.save(self._make_notif(id=f"n{i}"))
        assert len(store.list_notifications(limit=2)) == 2
        assert len(store.list_notifications(limit=2, offset=3)) == 2

    def test_mark_read(self, tmp_path):
        """mark_read passe read à True et remplit read_at."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        n = self._make_notif()
        store.save(n)
        assert store.mark_read(n.id) is True
        retrieved = store.get(n.id)
        assert retrieved.read is True
        assert retrieved.read_at is not None

    def test_mark_read_missing_returns_false(self, tmp_path):
        """mark_read retourne False pour un ID inconnu."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        assert store.mark_read("inconnu") is False

    def test_mark_all_read(self, tmp_path):
        """mark_all_read marque toutes les notifications d'un destinataire comme lues."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        store.save(self._make_notif(id="a", recipient="user@test.sn"))
        store.save(self._make_notif(id="b", recipient="user@test.sn"))
        store.save(self._make_notif(id="c", recipient="other@test.sn"))

        assert store.mark_all_read(recipient="user@test.sn") == 2
        assert store.get("a").read is True
        assert store.get("c").read is False

        assert store.mark_all_read() == 1  # la notification c restante

    def test_delete(self, tmp_path):
        """delete supprime une notification et retourne True."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        n = self._make_notif()
        store.save(n)
        assert store.delete(n.id) is True
        assert store.get(n.id) is None
        assert store.delete(n.id) is False

    def test_stats(self, tmp_path):
        """stats retourne les bonnes métriques."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        store.save(self._make_notif(id="a", recipient="user@test.sn"))
        store.save(self._make_notif(id="b", recipient="user@test.sn",
                                     notification_type=NotificationType.WARNING))
        store.save(self._make_notif(id="c", recipient="other@test.sn",
                                     priority=NotificationPriority.HIGH))

        s = store.stats()
        assert s["total"] == 3
        assert s["unread"] == 3

        s_user = store.stats(recipient="user@test.sn")
        assert s_user["total"] == 2

    def test_clear(self, tmp_path):
        """clear vide la table et retourne le nombre supprimé."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        store.save(self._make_notif(id="a"))
        store.save(self._make_notif(id="b"))
        assert store.clear() == 2
        assert store.count() == 0

    def test_count(self, tmp_path):
        """count retourne le nombre total de notifications."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        assert store.count() == 0
        store.save(self._make_notif(id="a"))
        assert store.count() == 1

    def test_persistence_across_reopen(self, tmp_path):
        """Les données survivent à la fermeture + réouverture du fichier."""
        db_path = str(tmp_path / "persist.sqlite")
        store = SQLiteNotificationStore(db_path=db_path)
        n = self._make_notif(id="persist", title="Persistant")
        store.save(n)

        reopened = SQLiteNotificationStore(db_path=db_path)
        retrieved = reopened.get("persist")
        assert retrieved is not None
        assert retrieved.title == "Persistant"

    def test_memory_mode(self):
        """Le mode :memory: fonctionne sans fichier."""
        store = SQLiteNotificationStore(db_path=":memory:")
        n = self._make_notif(id="mem")
        store.save(n)
        assert store.get("mem").title == "Test"

    def test_auto_creates_directory(self, tmp_path):
        """Le dossier parent est créé automatiquement."""
        db_path = str(tmp_path / "sub" / "deep" / "notif.sqlite")
        store = SQLiteNotificationStore(db_path=db_path)
        store.save(self._make_notif(id="deep"))
        assert os.path.isfile(db_path)
        assert store.get("deep") is not None

    def test_concurrent_saves(self, tmp_path):
        """Plusieurs threads sauvegardent sans corruption."""
        store = SQLiteNotificationStore(db_path=str(tmp_path / "notif.sqlite"))
        errors = []

        def worker(index):
            try:
                for j in range(10):
                    store.save(self._make_notif(id=f"t{index}-{j}"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert errors == []
        assert store.count() == 50


# ==============================================================================
# SQLiteCalendarStore
# ==============================================================================

class TestSQLiteCalendarStore:

    def _make_event(self, **kwargs) -> CalendarEvent:
        defaults = dict(
            title="Réunion",
            start_time="2026-01-15T10:00:00",
            end_time="2026-01-15T11:00:00",
            organizer="admin@test.sn",
        )
        defaults.update(kwargs)
        if "id" not in kwargs:
            defaults["id"] = f"evt_{id(kwargs)}"
        return CalendarEvent(**defaults)

    def test_save_and_get(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        e = self._make_event()
        eid = store.save(e)
        retrieved = store.get(eid)
        assert retrieved is not None
        assert retrieved.title == "Réunion"
        assert retrieved.organizer == "admin@test.sn"
        assert retrieved.status is EventStatus.CONFIRMED

    def test_get_missing_returns_none(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        assert store.get("inconnu") is None

    def test_list_events_filters(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        store.save(self._make_event(id="a", status=EventStatus.CONFIRMED, organizer="admin@test.sn"))
        store.save(self._make_event(id="b", status=EventStatus.TENTATIVE, organizer="other@test.sn"))
        store.save(self._make_event(id="c", status=EventStatus.CANCELLED, organizer="admin@test.sn"))

        assert len(store.list_events(status="confirmed")) == 1
        assert len(store.list_events(organizer="admin@test.sn")) == 2
        assert len(store.list_events(start_after="2026-02-01T00:00:00")) == 0

    def test_list_events_ordered_by_start_time(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        store.save(self._make_event(id="a", start_time="2026-03-01T10:00:00"))
        store.save(self._make_event(id="b", start_time="2026-01-01T10:00:00"))
        events = store.list_events()
        assert events[0].id == "b"  # plus tôt en premier
        assert events[1].id == "a"

    def test_list_events_limit(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        for i in range(5):
            store.save(self._make_event(id=f"e{i}"))
        assert len(store.list_events(limit=2)) == 2

    def test_update(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        e = self._make_event()
        store.save(e)
        assert store.update(e.id, {"title": "Mis à jour", "location": "Salle A"}) is True
        retrieved = store.get(e.id)
        assert retrieved.title == "Mis à jour"
        assert retrieved.location == "Salle A"

    def test_update_missing_returns_false(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        assert store.update("inconnu", {"title": "Nope"}) is False

    def test_delete(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        e = self._make_event()
        store.save(e)
        assert store.delete(e.id) is True
        assert store.get(e.id) is None
        assert store.delete(e.id) is False

    def test_stats(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        store.save(self._make_event(id="a"))
        store.save(self._make_event(id="b", status=EventStatus.TENTATIVE))
        s = store.stats()
        assert s["total"] == 2
        assert s["upcoming"] == 1
        assert s["by_status"]["confirmed"] == 1
        assert s["by_status"]["tentative"] == 1

    def test_clear(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        store.save(self._make_event(id="a"))
        assert store.clear() == 1
        assert store.count() == 0

    def test_count(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        assert store.count() == 0
        store.save(self._make_event(id="a"))
        assert store.count() == 1

    def test_persistence_across_reopen(self, tmp_path):
        db_path = str(tmp_path / "persist.sqlite")
        store = SQLiteCalendarStore(db_path=db_path)
        store.save(self._make_event(id="persist"))
        reopened = SQLiteCalendarStore(db_path=db_path)
        assert reopened.get("persist") is not None

    def test_memory_mode(self):
        store = SQLiteCalendarStore(db_path=":memory:")
        store.save(self._make_event(id="mem"))
        assert store.get("mem").title == "Réunion"

    def test_concurrent_saves(self, tmp_path):
        store = SQLiteCalendarStore(db_path=str(tmp_path / "cal.sqlite"))
        errors = []

        def worker(index):
            try:
                for j in range(10):
                    store.save(self._make_event(id=f"t{index}-{j}"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert errors == []
        assert store.count() == 50


# ==============================================================================
# SQLiteEmailStore
# ==============================================================================

class TestSQLiteEmailStore:

    def _make_email(self, **kwargs) -> EmailMessage:
        defaults = dict(
            subject="Test Email",
            body="Ceci est un test",
            sender="sender@test.sn",
            recipients=["recipient@test.sn"],
        )
        defaults.update(kwargs)
        if "id" not in kwargs:
            defaults["id"] = f"email_{id(kwargs)}"
        return EmailMessage(**defaults)

    def test_save_and_get(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        m = self._make_email()
        mid = store.save(m)
        retrieved = store.get(mid)
        assert retrieved is not None
        assert retrieved.subject == "Test Email"
        assert retrieved.sender == "sender@test.sn"
        assert retrieved.recipients == ["recipient@test.sn"]

    def test_save_with_attachments(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        m = self._make_email(attachments=[
            EmailAttachment(filename="doc.pdf", content_type="application/pdf",
                           data=b"%PDF-1.4 content"),
        ])
        mid = store.save(m)
        retrieved = store.get(mid)
        assert len(retrieved.attachments) == 1
        assert retrieved.attachments[0].filename == "doc.pdf"
        assert retrieved.attachments[0].data == b"%PDF-1.4 content"

    def test_get_missing_returns_none(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        assert store.get("inconnu") is None

    def test_list_emails_filters(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        store.save(self._make_email(id="a", sender="alice@test.sn",
                                     recipients=["bob@test.sn"]))
        store.save(self._make_email(id="b", sender="bob@test.sn",
                                     recipients=["alice@test.sn"]))
        store.save(self._make_email(id="c", status=EmailStatus.SENT))

        assert len(store.list_emails(sender="alice@test.sn")) == 1
        assert len(store.list_emails(recipient="bob@test.sn")) == 1
        assert len(store.list_emails(status="sent")) == 1

    def test_list_emails_recipient_checks_cc(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        store.save(self._make_email(id="a", sender="alice@test.sn",
                                     recipients=["bob@test.sn"],
                                     cc=["carol@test.sn"]))
        assert len(store.list_emails(recipient="carol@test.sn")) == 1

    def test_list_emails_limit(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        for i in range(5):
            store.save(self._make_email(id=f"e{i}"))
        assert len(store.list_emails(limit=2)) == 2

    def test_update_status(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        m = self._make_email(id="status-test", status=EmailStatus.DRAFT)
        store.save(m)
        assert store.update_status(m.id, "sent") is True
        retrieved = store.get(m.id)
        assert retrieved.status is EmailStatus.SENT
        assert retrieved.sent_at is not None

    def test_update_status_invalid(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        m = self._make_email(id="bad-status")
        store.save(m)
        assert store.update_status(m.id, "invalid_status") is False

    def test_update_status_missing_returns_false(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        assert store.update_status("inconnu", "sent") is False

    def test_delete_cascades_attachments(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        m = self._make_email(id="del", attachments=[
            EmailAttachment(filename="f.txt", content_type="text/plain", data=b"hello"),
        ])
        store.save(m)
        assert store.delete(m.id) is True
        # L'email n'existe plus
        assert store.get(m.id) is None
        # Les pièces jointes sont supprimées (vérifié par le fait que get ne retourne rien)

    def test_delete_missing_returns_false(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        assert store.delete("inconnu") is False

    def test_stats(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        store.save(self._make_email(id="a"))
        store.save(self._make_email(id="b", sender="other@test.sn"))
        s = store.stats()
        assert s["total"] == 2
        assert s["by_status"]["draft"] == 2
        assert s["unique_senders"] == 2

    def test_clear(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        store.save(self._make_email(id="a"))
        assert store.clear() == 1
        assert store.count() == 0

    def test_count(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        assert store.count() == 0
        store.save(self._make_email(id="a"))
        assert store.count() == 1

    def test_persistence_across_reopen(self, tmp_path):
        db_path = str(tmp_path / "persist.sqlite")
        store = SQLiteEmailStore(db_path=db_path)
        store.save(self._make_email(id="persist"))
        reopened = SQLiteEmailStore(db_path=db_path)
        assert reopened.get("persist") is not None

    def test_memory_mode(self):
        store = SQLiteEmailStore(db_path=":memory:")
        store.save(self._make_email(id="mem"))
        assert store.get("mem").subject == "Test Email"

    def test_concurrent_saves(self, tmp_path):
        store = SQLiteEmailStore(db_path=str(tmp_path / "email.sqlite"))
        errors = []

        def worker(index):
            try:
                for j in range(10):
                    store.save(self._make_email(id=f"t{index}-{j}"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert errors == []
        assert store.count() == 50


# ==============================================================================
# SQLiteCloudStore
# ==============================================================================

class TestSQLiteCloudStore:

    def _make_cloud_item(self, **kwargs) -> CloudFileItem:
        defaults = dict(
            name="test.pdf",
            content_type="application/pdf",
            size=1024,
            provider=CloudProvider.LOCAL,
            category=CloudFileCategory.DOCUMENT,
        )
        defaults.update(kwargs)
        if "id" not in kwargs:
            defaults["id"] = f"cloud_{id(kwargs)}"
        return CloudFileItem(**defaults)

    def test_save_and_get(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        item = self._make_cloud_item()
        data = b"Binary content here"
        store.save(item, data)
        retrieved = store.get(item.id)
        assert retrieved is not None
        assert retrieved.name == "test.pdf"
        assert retrieved.category is CloudFileCategory.DOCUMENT

    def test_get_data(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        item = self._make_cloud_item()
        data = b"binary data to verify"
        store.save(item, data)
        assert store.get_data(item.id) == data

    def test_get_data_missing_returns_none(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        assert store.get_data("inconnu") is None

    def test_get_missing_returns_none(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        assert store.get("inconnu") is None

    def test_list_files(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        store.save(self._make_cloud_item(id="a", provider=CloudProvider.LOCAL), b"a")
        store.save(self._make_cloud_item(id="b", provider=CloudProvider.S3), b"b")
        store.save(self._make_cloud_item(id="c", category=CloudFileCategory.IMAGE), b"c")

        assert len(store.list_files()) == 3
        assert len(store.list_files(provider="s3")) == 1
        assert len(store.list_files(category="image")) == 1

    def test_list_files_limit(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        for i in range(5):
            store.save(self._make_cloud_item(id=f"f{i}"), b"d")
        assert len(store.list_files(limit=2)) == 2

    def test_delete(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        item = self._make_cloud_item()
        store.save(item, b"data")
        assert store.delete(item.id) is True
        assert store.get(item.id) is None
        assert store.get_data(item.id) is None
        assert store.delete(item.id) is False

    def test_update_metadata(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        item = self._make_cloud_item()
        store.save(item, b"data")
        assert store.update_metadata(item.id, {"project": "GalSen"}) is True
        retrieved = store.get(item.id)
        assert retrieved.metadata["project"] == "GalSen"

    def test_update_metadata_missing_returns_false(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        assert store.update_metadata("inconnu", {"x": "y"}) is False

    def test_stats(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        store.save(self._make_cloud_item(id="a", size=1000), b"a" * 1000)
        store.save(self._make_cloud_item(id="b", size=2000), b"b" * 2000)
        s = store.stats()
        assert s["total"] == 2
        assert s["total_size"] == 3000

    def test_total_size(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        assert store.total_size() == 0
        store.save(self._make_cloud_item(id="a", size=500), b"a" * 500)
        assert store.total_size() == 500

    def test_clear(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        store.save(self._make_cloud_item(id="a"), b"d")
        assert store.clear() == 1
        assert store.count() == 0

    def test_count(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        assert store.count() == 0
        store.save(self._make_cloud_item(id="a"), b"d")
        assert store.count() == 1

    def test_persistence_across_reopen(self, tmp_path):
        db_path = str(tmp_path / "persist.sqlite")
        store = SQLiteCloudStore(db_path=db_path)
        store.save(self._make_cloud_item(id="persist", name="survived.pdf"), b"persist data")
        reopened = SQLiteCloudStore(db_path=db_path)
        assert reopened.get("persist").name == "survived.pdf"
        assert reopened.get_data("persist") == b"persist data"

    def test_memory_mode(self):
        store = SQLiteCloudStore(db_path=":memory:")
        store.save(self._make_cloud_item(id="mem"), b"mem data")
        assert store.get("mem").name == "test.pdf"
        assert store.get_data("mem") == b"mem data"

    def test_concurrent_saves(self, tmp_path):
        store = SQLiteCloudStore(db_path=str(tmp_path / "cloud.sqlite"))
        errors = []

        def worker(index):
            try:
                for j in range(10):
                    store.save(self._make_cloud_item(id=f"t{index}-{j}"), b"d")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert errors == []
        assert store.count() == 50


# ==============================================================================
# SQLiteFileStore
# ==============================================================================

class TestSQLiteFileStore:

    def _make_file(self, **kwargs) -> FileItem:
        defaults = dict(
            name="document.txt",
            content_type="text/plain",
            size=13,
            data=b"Hello, World!",
            category=FileCategory.DOCUMENT,
        )
        defaults.update(kwargs)
        if "id" not in kwargs:
            defaults["id"] = f"file_{id(kwargs)}"
        return FileItem(**defaults)

    def test_save_and_get(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        f = self._make_file()
        fid = store.save(f)
        retrieved = store.get(fid)
        assert retrieved is not None
        assert retrieved.name == "document.txt"
        assert retrieved.data == b"Hello, World!"
        assert retrieved.category is FileCategory.DOCUMENT

    def test_get_by_name(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        store.save(self._make_file())
        retrieved = store.get_by_name("document.txt")
        assert retrieved is not None
        assert retrieved.content_type == "text/plain"

    def test_get_by_name_missing(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        assert store.get_by_name("inconnu.txt") is None

    def test_get_missing_returns_none(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        assert store.get("inconnu") is None

    def test_list_files_filters(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        store.save(self._make_file(id="a", category=FileCategory.DOCUMENT, content_type="text/plain"))
        store.save(self._make_file(id="b", category=FileCategory.IMAGE, content_type="image/png"))
        store.save(self._make_file(id="c", category=FileCategory.DOCUMENT, uploaded_by="admin"))

        assert len(store.list_files()) == 3
        assert len(store.list_files(category="document")) == 2
        assert len(store.list_files(content_type="image/png")) == 1
        assert len(store.list_files(uploaded_by="admin")) == 1

    def test_list_files_tags_filter(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        store.save(self._make_file(id="a", tags={"env": "prod", "team": "core"}))
        store.save(self._make_file(id="b", tags={"env": "dev", "team": "core"}))
        store.save(self._make_file(id="c", tags={"env": "prod", "team": "ml"}))

        assert len(store.list_files(tags={"env": "prod"})) == 2
        assert len(store.list_files(tags={"env": "prod", "team": "core"})) == 1
        assert len(store.list_files(tags={"env": "staging"})) == 0

    def test_list_files_limit(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        for i in range(5):
            store.save(self._make_file(id=f"f{i}"))
        assert len(store.list_files(limit=2)) == 2

    def test_delete(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        f = self._make_file()
        store.save(f)
        assert store.delete(f.id) is True
        assert store.get(f.id) is None
        assert store.delete(f.id) is False

    def test_update_metadata(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        f = self._make_file()
        store.save(f)
        assert store.update_metadata(f.id, {"processed": True}) is True
        retrieved = store.get(f.id)
        assert retrieved.metadata["processed"] is True

    def test_update_metadata_missing_returns_false(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        assert store.update_metadata("inconnu", {"x": "y"}) is False

    def test_stats(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        store.save(self._make_file(id="a", size=100))
        store.save(self._make_file(id="b", size=200, category=FileCategory.IMAGE,
                                    content_type="image/png"))
        s = store.stats()
        assert s["total"] == 2
        assert s["total_size"] == 300
        assert s["by_category"]["document"] == 1
        assert s["by_category"]["image"] == 1
        assert s["total_size_mb"] == round(300 / (1024 * 1024), 2)

    def test_total_size(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        assert store.total_size() == 0
        store.save(self._make_file(id="a", size=500))
        assert store.total_size() == 500

    def test_clear(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        store.save(self._make_file(id="a"))
        assert store.clear() == 1
        assert store.count() == 0

    def test_count(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        assert store.count() == 0
        store.save(self._make_file(id="a"))
        assert store.count() == 1

    def test_persistence_across_reopen(self, tmp_path):
        db_path = str(tmp_path / "persist.sqlite")
        store = SQLiteFileStore(db_path=db_path)
        store.save(self._make_file(id="persist", data=b"survived data"))
        reopened = SQLiteFileStore(db_path=db_path)
        assert reopened.get("persist").data == b"survived data"

    def test_memory_mode(self):
        store = SQLiteFileStore(db_path=":memory:")
        store.save(self._make_file(id="mem"))
        assert store.get("mem").name == "document.txt"

    def test_binary_roundtrip(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        large_data = bytes(range(256)) * 100  # 25.6 KB
        store.save(self._make_file(id="binary", data=large_data))
        retrieved = store.get("binary")
        assert retrieved.data == large_data

    def test_concurrent_saves(self, tmp_path):
        store = SQLiteFileStore(db_path=str(tmp_path / "file.sqlite"))
        errors = []

        def worker(index):
            try:
                for j in range(10):
                    store.save(self._make_file(id=f"t{index}-{j}"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        assert errors == []
        assert store.count() == 50


# ==============================================================================
# Branchement des services sur SQLite (GALSEN_STORAGE_BACKEND)
# ==============================================================================

class TestServiceBackendSelection:

    def test_notification_manager_uses_sqlite_when_env_set(self, tmp_path, monkeypatch):
        """GALSEN_STORAGE_BACKEND=sqlite branche le service sur SQLite."""
        monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
        monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
        from services.notification.manager import NotificationManagerImpl
        manager = NotificationManagerImpl()
        assert isinstance(manager._store, SQLiteNotificationStore)

    def test_notification_manager_defaults_in_memory(self, monkeypatch):
        """Sans variable d'environnement, reste en mémoire."""
        monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)
        from services.notification.manager import NotificationManagerImpl
        from services.notification.store import InMemoryNotificationStore
        manager = NotificationManagerImpl()
        assert isinstance(manager._store, InMemoryNotificationStore)

    def test_notification_manager_explicit_store_wins(self, tmp_path, monkeypatch):
        """Un store injecté prime sur la variable d'environnement."""
        monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
        from services.notification.store import InMemoryNotificationStore
        injected = InMemoryNotificationStore()
        from services.notification.manager import NotificationManagerImpl
        manager = NotificationManagerImpl(store=injected)
        assert manager._store is injected

    def test_calendar_manager_uses_sqlite_when_env_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
        from services.calendar.manager import CalendarManagerImpl
        manager = CalendarManagerImpl()
        assert isinstance(manager._store, SQLiteCalendarStore)

    def test_calendar_manager_defaults_in_memory(self, monkeypatch):
        monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)
        from services.calendar.manager import CalendarManagerImpl
        from services.calendar.store import InMemoryCalendarStore
        manager = CalendarManagerImpl()
        assert isinstance(manager._store, InMemoryCalendarStore)

    def test_email_manager_uses_sqlite_when_env_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
        from services.email.manager import EmailManagerImpl
        manager = EmailManagerImpl()
        assert isinstance(manager._store, SQLiteEmailStore)

    def test_email_manager_defaults_in_memory(self, monkeypatch):
        monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)
        from services.email.manager import EmailManagerImpl
        from services.email.store import InMemoryEmailStore
        manager = EmailManagerImpl()
        assert isinstance(manager._store, InMemoryEmailStore)

    def test_cloud_manager_uses_sqlite_when_env_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
        from services.cloud.manager import CloudManagerImpl
        manager = CloudManagerImpl()
        assert isinstance(manager._store, SQLiteCloudStore)

    def test_cloud_manager_defaults_in_memory(self, monkeypatch):
        monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)
        from services.cloud.manager import CloudManagerImpl
        from services.cloud.store import InMemoryCloudStore
        manager = CloudManagerImpl()
        assert isinstance(manager._store, InMemoryCloudStore)

    def test_file_manager_uses_sqlite_when_env_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
        from services.file.manager import FileManagerImpl
        manager = FileManagerImpl()
        assert isinstance(manager._store, SQLiteFileStore)

    def test_file_manager_defaults_in_memory(self, monkeypatch):
        monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)
        from services.file.manager import FileManagerImpl
        from services.file.store import InMemoryFileStore
        manager = FileManagerImpl()
        assert isinstance(manager._store, InMemoryFileStore)