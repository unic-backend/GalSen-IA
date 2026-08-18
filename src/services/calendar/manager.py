"""
Gestionnaire du service de Calendrier.

Fournit `CalendarManagerImpl`, une façade best-effort conforme à
`CalendarManager` : chaque appel est protégé et ne lève jamais ; en cas
d'échec, un avertissement est journalisé et une valeur vide est retournée.
"""

import logging
from typing import Any, Dict, List, Optional

from .interfaces import CalendarManager, CalendarStore
from .store import InMemoryCalendarStore
from .types import CalendarEvent, CalendarEventResult, EventStatus
from src.storage.paths import sqlite_enabled

logger = logging.getLogger(__name__)


class CalendarManagerImpl(CalendarManager):
    """Façade du service de calendrier, toujours disponible en mémoire."""

    def __init__(self, store: Optional[CalendarStore] = None) -> None:
        if store is not None:
            self._store = store
        elif sqlite_enabled():
            from src.storage.sqlite_calendar_store import SQLiteCalendarStore
            self._store = SQLiteCalendarStore()
        else:
            self._store = InMemoryCalendarStore()
        self._logger = logging.getLogger(f"{__name__}.CalendarManagerImpl")

    def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        organizer: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        status: EventStatus = EventStatus.CONFIRMED,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CalendarEventResult:
        """Crée un nouvel événement."""
        if not title or not title.strip():
            return CalendarEventResult(False, "Le titre de l'événement est requis.")
        if not start_time or not end_time:
            return CalendarEventResult(False, "Les dates de début et fin sont requises.")
        if start_time >= end_time:
            return CalendarEventResult(False, "La date de début doit précéder la date de fin.")

        try:
            event = CalendarEvent(
                title=title.strip(),
                start_time=start_time,
                end_time=end_time,
                description=description,
                location=location,
                organizer=organizer,
                attendees=attendees or [],
                status=status,
                metadata=metadata or {},
            )
            event_id = self._store.save(event)
            return CalendarEventResult(
                True,
                f"Événement '{title}' créé avec succès.",
                event_id=event_id,
                event=event,
            )
        except Exception as error:
            self._logger.warning("Échec de la création de l'événement : %s", error)
            return CalendarEventResult(False, f"Échec de la création : {error}")

    def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        """Retourne un événement par identifiant."""
        try:
            return self._store.get(event_id)
        except Exception as error:
            self._logger.warning("Échec de la lecture de l'événement %s : %s", event_id, error)
            return None

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        organizer: Optional[str] = None,
        start_after: Optional[str] = None,
        start_before: Optional[str] = None,
    ) -> List[CalendarEvent]:
        """Retourne les événements filtrés."""
        try:
            return self._store.list_events(
                limit=limit,
                offset=offset,
                status=status,
                organizer=organizer,
                start_after=start_after,
                start_before=start_before,
            )
        except Exception as error:
            self._logger.warning("Échec du filtrage des événements : %s", error)
            return []

    def update_event(self, event_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un événement."""
        try:
            return self._store.update(event_id, updates)
        except Exception as error:
            self._logger.warning("Échec de la mise à jour de l'événement %s : %s", event_id, error)
            return False

    def cancel_event(self, event_id: str) -> bool:
        """Annule un événement."""
        try:
            return self._store.update(event_id, {"status": EventStatus.CANCELLED})
        except Exception as error:
            self._logger.warning("Échec de l'annulation de l'événement %s : %s", event_id, error)
            return False

    def delete_event(self, event_id: str) -> bool:
        """Supprime un événement."""
        try:
            return self._store.delete(event_id)
        except Exception as error:
            self._logger.warning("Échec de la suppression de l'événement %s : %s", event_id, error)
            return False

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        try:
            return self._store.stats()
        except Exception as error:
            self._logger.warning("Échec du calcul des statistiques calendrier : %s", error)
            return {}

    def clear(self) -> int:
        """Supprime tous les événements et retourne le nombre supprimé."""
        try:
            return self._store.clear()
        except Exception as error:
            self._logger.warning("Échec de la suppression des événements : %s", error)
            return 0