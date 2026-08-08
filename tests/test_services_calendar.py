"""
Tests unitaires pour le service Calendrier.

Couvre :
- CalendarEvent, CalendarEventResult, CalendarStats
- InMemoryCalendarStore : CRUD, filtrage, mise à jour, annulation
- CalendarManagerImpl : création, validation, dégradation gracieuse du store
"""

import os
import sys
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestCalendarTypes:
    """Vérifie les modèles de données du calendrier."""

    def test_generate_event_id_prefix(self):
        """L'identifiant d'événement doit commencer par 'evt_'."""
        from src.services.calendar import generate_event_id
        eid = generate_event_id()
        assert eid.startswith("evt_")
        assert len(eid) > 10

    def test_event_default_status(self):
        """Un nouvel événement doit avoir le statut CONFIRMED."""
        from src.services.calendar import CalendarEvent
        evt = CalendarEvent(title="Réunion", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00")
        assert evt.status.value == "confirmed"

    def test_event_default_visibility(self):
        """Un nouvel événement doit avoir la visibilité PUBLIC."""
        from src.services.calendar import CalendarEvent
        evt = CalendarEvent(title="Réunion", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00")
        assert evt.visibility.value == "public"

    def test_event_to_dict(self):
        """to_dict() doit inclure tous les champs obligatoires et optionnels."""
        from src.services.calendar import CalendarEvent, EventStatus, EventVisibility
        evt = CalendarEvent(
            title="Sprint Review",
            start_time="2026-01-01T10:00",
            end_time="2026-01-01T11:00",
            description="Revue de sprint",
            location="Salle A",
            organizer="chef@exemple.com",
            attendees=["dev1@exemple.com", "dev2@exemple.com"],
            status=EventStatus.TENTATIVE,
            visibility=EventVisibility.PRIVATE,
            recurrence="FREQ=WEEKLY",
            metadata={"project": "GalSen"},
        )
        d = evt.to_dict()
        assert d["id"] == evt.id
        assert d["title"] == "Sprint Review"
        assert d["start_time"] == "2026-01-01T10:00"
        assert d["end_time"] == "2026-01-01T11:00"
        assert d["status"] == "tentative"
        assert d["visibility"] == "private"
        assert d["description"] == "Revue de sprint"
        assert d["location"] == "Salle A"
        assert d["organizer"] == "chef@exemple.com"
        assert d["attendees"] == ["dev1@exemple.com", "dev2@exemple.com"]
        assert d["recurrence"] == "FREQ=WEEKLY"
        assert "created_at" in d
        assert "updated_at" in d
        assert d["metadata"]["project"] == "GalSen"

    def test_event_from_mapping(self):
        """from_mapping() doit reconstruire un CalendarEvent depuis un dictionnaire."""
        from src.services.calendar import CalendarEvent, EventStatus
        original = CalendarEvent(
            title="Test", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00",
            status=EventStatus.TENTATIVE,
        )
        d = original.to_dict()
        restored = CalendarEvent.from_mapping(d)
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.status == EventStatus.TENTATIVE

    def test_event_from_mapping_string_status(self):
        """from_mapping() doit accepter un statut sous forme de chaîne."""
        from src.services.calendar import CalendarEvent, EventStatus
        restored = CalendarEvent.from_mapping({
            "title": "T", "start_time": "2026-01-01T10:00", "end_time": "2026-01-01T11:00",
            "status": "cancelled",
        })
        assert restored.status == EventStatus.CANCELLED

    def test_event_from_mapping_invalid_status_defaults_confirmed(self):
        """Un statut invalide dans from_mapping() doit être remplacé par CONFIRMED."""
        from src.services.calendar import CalendarEvent, EventStatus
        restored = CalendarEvent.from_mapping({
            "title": "T", "start_time": "2026-01-01T10:00", "end_time": "2026-01-01T11:00",
            "status": "unknown",
        })
        assert restored.status == EventStatus.CONFIRMED

    def test_event_from_mapping_string_visibility(self):
        """from_mapping() doit accepter une visibilité sous forme de chaîne."""
        from src.services.calendar import CalendarEvent, EventVisibility
        restored = CalendarEvent.from_mapping({
            "title": "T", "start_time": "2026-01-01T10:00", "end_time": "2026-01-01T11:00",
            "visibility": "confidential",
        })
        assert restored.visibility == EventVisibility.CONFIDENTIAL

    def test_event_from_mapping_invalid_visibility_defaults_public(self):
        """Une visibilité invalide dans from_mapping() doit être remplacée par PUBLIC."""
        from src.services.calendar import CalendarEvent, EventVisibility
        restored = CalendarEvent.from_mapping({
            "title": "T", "start_time": "2026-01-01T10:00", "end_time": "2026-01-01T11:00",
            "visibility": "unknown",
        })
        assert restored.visibility == EventVisibility.PUBLIC

    def test_event_result_defaults(self):
        """CalendarEventResult doit accepter les champs minimaux."""
        from src.services.calendar import CalendarEventResult
        r = CalendarEventResult(True, "Créé")
        assert r.success is True
        assert r.message == "Créé"
        assert r.event_id is None

    def test_calendar_stats_creation(self):
        """CalendarStats doit stocker les compteurs."""
        from src.services.calendar import CalendarStats
        stats = CalendarStats(total=5, upcoming=3, by_status={"confirmed": 3, "cancelled": 2})
        assert stats.total == 5
        assert stats.upcoming == 3


class TestInMemoryCalendarStore:
    """Vérifie le stockage en mémoire des événements."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.calendar import InMemoryCalendarStore, CalendarEvent, EventStatus
        self.store = InMemoryCalendarStore()
        self.evt_a = CalendarEvent(
            title="Réunion A", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00",
        )
        self.evt_b = CalendarEvent(
            title="Réunion B", start_time="2026-01-02T10:00", end_time="2026-01-02T11:00",
            organizer="b@b.com",
        )
        self.evt_c = CalendarEvent(
            title="Réunion C", start_time="2026-01-03T10:00", end_time="2026-01-03T11:00",
            status=EventStatus.TENTATIVE,
        )

    def test_save_and_get(self):
        """save() puis get() doivent retourner le même événement."""
        eid = self.store.save(self.evt_a)
        retrieved = self.store.get(eid)
        assert retrieved is not None
        assert retrieved.id == self.evt_a.id
        assert retrieved.title == "Réunion A"

    def test_save_duplicate_raises(self):
        """save() d'un identifiant existant doit lever ValueError."""
        self.store.save(self.evt_a)
        with pytest.raises(ValueError, match="existe déjà"):
            self.store.save(self.evt_a)

    def test_get_missing_returns_none(self):
        """get() d'un identifiant inconnu doit retourner None."""
        assert self.store.get("nonexistent") is None

    def test_list_events_sorted_by_start_time(self):
        """list_events() doit trier par date de début croissante."""
        self.store.save(self.evt_c)  # 2026-01-03
        self.store.save(self.evt_a)  # 2026-01-01
        self.store.save(self.evt_b)  # 2026-01-02
        all_events = self.store.list_events(limit=10)
        assert len(all_events) == 3
        assert all_events[0].title == "Réunion A"
        assert all_events[1].title == "Réunion B"
        assert all_events[2].title == "Réunion C"

    def test_list_events_filter_status(self):
        """list_events() doit filtrer par statut."""
        self.store.save(self.evt_a)  # CONFIRMED
        self.store.save(self.evt_c)  # TENTATIVE
        confirmed = self.store.list_events(limit=10, status="confirmed")
        assert len(confirmed) == 1
        assert confirmed[0].title == "Réunion A"

    def test_list_events_filter_organizer(self):
        """list_events() doit filtrer par organisateur."""
        self.store.save(self.evt_a)  # pas d'organizer
        self.store.save(self.evt_b)  # b@b.com
        by_b = self.store.list_events(limit=10, organizer="b@b.com")
        assert len(by_b) == 1
        assert by_b[0].title == "Réunion B"

    def test_list_events_filter_start_after(self):
        """list_events() doit filtrer par date de début minimale."""
        self.store.save(self.evt_a)  # 2026-01-01
        self.store.save(self.evt_b)  # 2026-01-02
        after = self.store.list_events(limit=10, start_after="2026-01-02")
        assert len(after) == 1
        assert after[0].title == "Réunion B"

    def test_list_events_filter_start_before(self):
        """list_events() doit filtrer par date de début maximale."""
        self.store.save(self.evt_a)  # 2026-01-01
        self.store.save(self.evt_b)  # 2026-01-02
        before = self.store.list_events(limit=10, start_before="2026-01-02")
        assert len(before) == 1
        assert before[0].title == "Réunion A"

    def test_update(self):
        """update() doit modifier les champs d'un événement."""
        eid = self.store.save(self.evt_a)
        assert self.store.update(eid, {"title": "Modifié", "location": "Salle B"})
        retrieved = self.store.get(eid)
        assert retrieved.title == "Modifié"
        assert retrieved.location == "Salle B"

    def test_update_protects_id_and_created_at(self):
        """update() ne doit pas modifier l'id ni created_at."""
        eid = self.store.save(self.evt_a)
        original_created = self.evt_a.created_at
        self.store.update(eid, {"id": "new_id", "created_at": 0})
        retrieved = self.store.get(eid)
        assert retrieved.id == eid  # inchangé
        assert retrieved.created_at == original_created  # inchangé

    def test_update_missing(self):
        """update() d'un événement inconnu doit retourner False."""
        assert not self.store.update("nonexistent", {"title": "Nouveau"})

    def test_delete(self):
        """delete() doit supprimer un événement."""
        eid = self.store.save(self.evt_a)
        assert self.store.delete(eid)
        assert self.store.get(eid) is None

    def test_delete_missing(self):
        """delete() d'un événement inconnu doit retourner False."""
        assert not self.store.delete("nonexistent")

    def test_stats(self):
        """stats() doit retourner des statistiques correctes."""
        self.store.save(self.evt_a)  # CONFIRMED
        self.store.save(self.evt_b)  # CONFIRMED
        self.store.save(self.evt_c)  # TENTATIVE
        stats = self.store.stats()
        assert stats["total"] == 3
        assert stats["upcoming"] == 2  # seulement les CONFIRMED
        assert stats["by_status"]["confirmed"] == 2
        assert stats["by_status"]["tentative"] == 1

    def test_clear(self):
        """clear() doit supprimer tous les événements."""
        self.store.save(self.evt_a)
        self.store.save(self.evt_b)
        assert self.store.clear() == 2
        assert self.store.count() == 0

    def test_list_with_limit(self):
        """list_events() doit respecter la limite."""
        self.store.save(self.evt_a)
        self.store.save(self.evt_b)
        self.store.save(self.evt_c)
        assert len(self.store.list_events(limit=2)) == 2

    def test_list_with_offset(self):
        """list_events() doit respecter l'offset."""
        self.store.save(self.evt_a)
        self.store.save(self.evt_b)
        self.store.save(self.evt_c)
        results = self.store.list_events(limit=10, offset=2)
        assert len(results) == 1


class TestCalendarManager:
    """Vérifie le gestionnaire de calendrier (best-effort)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.calendar import CalendarManagerImpl
        self.manager = CalendarManagerImpl()

    def test_create_event(self):
        """create_event() doit retourner un résultat positif."""
        result = self.manager.create_event(
            title="Réunion", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00",
        )
        assert result.success
        assert result.event_id is not None
        assert result.event_id.startswith("evt_")
        assert result.event is not None

    def test_create_and_get(self):
        """create_event() puis get_event() doivent retourner le même événement."""
        result = self.manager.create_event(
            title="Sprint", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00",
        )
        event = self.manager.get_event(result.event_id)
        assert event is not None
        assert event.title == "Sprint"
        assert event.status.value == "confirmed"

    def test_create_event_empty_title(self):
        """create_event() avec un titre vide doit échouer."""
        result = self.manager.create_event(
            title="", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00",
        )
        assert not result.success
        assert "titre" in result.message.lower()

    def test_create_event_missing_start_time(self):
        """create_event() sans start_time doit échouer."""
        result = self.manager.create_event(
            title="Test", start_time="", end_time="2026-01-01T11:00",
        )
        assert not result.success
        assert "dates" in result.message.lower()

    def test_create_event_end_before_start(self):
        """create_event() avec end_time < start_time doit échouer."""
        result = self.manager.create_event(
            title="Test", start_time="2026-01-01T11:00", end_time="2026-01-01T10:00",
        )
        assert not result.success
        assert "précéder" in result.message.lower()

    def test_create_event_with_all_fields(self):
        """create_event() doit accepter tous les champs optionnels."""
        from src.services.calendar import EventStatus
        result = self.manager.create_event(
            title="Complet", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00",
            description="Description complète",
            location="Salle C",
            organizer="org@exemple.com",
            attendees=["a@e.com", "b@e.com"],
            status=EventStatus.TENTATIVE,
            metadata={"projet": "GalSen"},
        )
        assert result.success
        event = result.event
        assert event.description == "Description complète"
        assert event.location == "Salle C"
        assert event.organizer == "org@exemple.com"
        assert len(event.attendees) == 2
        assert event.status.value == "tentative"

    def test_list_events(self):
        """list_events() doit retourner les événements créés."""
        self.manager.create_event(title="A", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00")
        self.manager.create_event(title="B", start_time="2026-01-02T10:00", end_time="2026-01-02T11:00")
        events = self.manager.list_events()
        assert len(events) == 2

    def test_list_events_filter_organizer(self):
        """list_events(organizer=...) doit filtrer."""
        self.manager.create_event(
            title="A", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00",
            organizer="org@e.com",
        )
        self.manager.create_event(
            title="B", start_time="2026-01-02T10:00", end_time="2026-01-02T11:00",
            organizer="autre@e.com",
        )
        events = self.manager.list_events(organizer="org@e.com")
        assert len(events) == 1
        assert events[0].title == "A"

    def test_update_event(self):
        """update_event() doit modifier un événement."""
        result = self.manager.create_event(
            title="Original", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00",
        )
        assert self.manager.update_event(result.event_id, {"title": "Modifié", "location": "Nouveau lieu"})
        event = self.manager.get_event(result.event_id)
        assert event.title == "Modifié"
        assert event.location == "Nouveau lieu"

    def test_update_event_missing(self):
        """update_event() d'un événement inconnu doit retourner False sans erreur."""
        assert not self.manager.update_event("nonexistent", {"title": "Nouveau"})

    def test_cancel_event(self):
        """cancel_event() doit passer le statut à CANCELLED."""
        result = self.manager.create_event(
            title="À annuler", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00",
        )
        assert self.manager.cancel_event(result.event_id)
        event = self.manager.get_event(result.event_id)
        assert event.status.value == "cancelled"

    def test_cancel_event_missing(self):
        """cancel_event() d'un événement inconnu doit retourner False sans erreur."""
        assert not self.manager.cancel_event("nonexistent")

    def test_delete_event(self):
        """delete_event() doit supprimer l'événement."""
        result = self.manager.create_event(
            title="Supprimé", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00",
        )
        assert self.manager.delete_event(result.event_id)
        assert self.manager.get_event(result.event_id) is None

    def test_delete_event_missing(self):
        """delete_event() d'un événement inconnu doit retourner False sans erreur."""
        assert not self.manager.delete_event("nonexistent")

    def test_stats(self):
        """stats() doit retourner des statistiques cohérentes."""
        self.manager.create_event(title="A", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00")
        self.manager.create_event(title="B", start_time="2026-01-02T10:00", end_time="2026-01-02T11:00")
        stats = self.manager.stats()
        assert stats["total"] == 2
        assert stats["upcoming"] == 2
        assert stats["by_status"]["confirmed"] == 2

    def test_clear(self):
        """clear() doit tout supprimer."""
        self.manager.create_event(title="A", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00")
        assert self.manager.clear() == 1
        assert len(self.manager.list_events()) == 0

    def test_store_failure_graceful(self):
        """Une panne du store ne doit pas crasher le manager."""
        from src.services.calendar import CalendarStore
        broken_store = MagicMock(spec=CalendarStore)
        broken_store.save.side_effect = RuntimeError("Stockage indisponible")
        broken_store.get.side_effect = RuntimeError("Stockage indisponible")
        broken_store.list_events.side_effect = RuntimeError("Stockage indisponible")
        broken_store.update.side_effect = RuntimeError("Stockage indisponible")
        broken_store.delete.side_effect = RuntimeError("Stockage indisponible")
        broken_store.stats.side_effect = RuntimeError("Stockage indisponible")
        broken_store.clear.side_effect = RuntimeError("Stockage indisponible")
        manager = type(self.manager)(store=broken_store)

        result = manager.create_event(title="T", start_time="2026-01-01T10:00", end_time="2026-01-01T11:00")
        assert not result.success

        assert manager.get_event("any") is None
        assert manager.list_events() == []
        assert manager.update_event("any", {}) is False
        assert manager.cancel_event("any") is False
        assert manager.delete_event("any") is False
        assert manager.stats() == {}
        assert manager.clear() == 0