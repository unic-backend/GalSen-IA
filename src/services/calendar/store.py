"""
Stockage en mémoire des événements de calendrier.

Fournit `InMemoryCalendarStore`, une implémentation thread-safe du contrat
`CalendarStore`. Les événements sont conservés en mémoire ; la persistance
(SQLite, CalDAV) peut être ajoutée ultérieurement sans changer ce module.
"""

import logging
import threading
from typing import Any, Dict, List, Optional

from .interfaces import CalendarStore
from .types import CalendarEvent, EventStatus

logger = logging.getLogger(__name__)


class InMemoryCalendarStore(CalendarStore):
    """Stockage d'événements de calendrier en mémoire, thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: Dict[str, CalendarEvent] = {}
        self._order: List[str] = []

    def save(self, event: CalendarEvent) -> str:
        """Enregistre un événement et retourne son identifiant."""
        with self._lock:
            if event.id in self._events:
                raise ValueError(f"L'événement {event.id} existe déjà.")
            self._events[event.id] = event
            self._order.append(event.id)
            return event.id

    def get(self, event_id: str) -> Optional[CalendarEvent]:
        """Retourne un événement par identifiant, ou None si absent."""
        with self._lock:
            return self._events.get(event_id)

    def _matches(
        self,
        event: CalendarEvent,
        status: Optional[str],
        organizer: Optional[str],
        start_after: Optional[str],
        start_before: Optional[str],
    ) -> bool:
        """Vérifie si un événement correspond aux filtres fournis."""
        if status is not None and event.status.value != status:
            return False
        if organizer is not None and event.organizer != organizer:
            return False
        if start_after is not None and event.start_time < start_after:
            return False
        if start_before is not None and event.start_time > start_before:
            return False
        return True

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        organizer: Optional[str] = None,
        start_after: Optional[str] = None,
        start_before: Optional[str] = None,
    ) -> List[CalendarEvent]:
        """Retourne les événements filtrés, triés par date de début."""
        with self._lock:
            matched: List[CalendarEvent] = []
            for event_id in self._order:
                event = self._events[event_id]
                if self._matches(event, status, organizer, start_after, start_before):
                    matched.append(event)
            # Tri par start_time
            matched.sort(key=lambda e: e.start_time)
            return matched[offset:offset + limit]

    def update(self, event_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un événement ; retourne False si absent."""
        with self._lock:
            event = self._events.get(event_id)
            if event is None:
                return False
            for key, value in updates.items():
                if hasattr(event, key) and key not in ("id", "created_at"):
                    setattr(event, key, value)
            event.updated_at = __import__("time").time()
            return True

    def delete(self, event_id: str) -> bool:
        """Supprime un événement ; retourne False si absent."""
        with self._lock:
            if event_id not in self._events:
                return False
            del self._events[event_id]
            self._order = [eid for eid in self._order if eid != event_id]
            return True

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        with self._lock:
            total = len(self._order)
            upcoming = 0
            by_status: Dict[str, int] = {}

            for event in self._events.values():
                s = event.status.value
                by_status[s] = by_status.get(s, 0) + 1
                if event.status == EventStatus.CONFIRMED:
                    upcoming += 1

            return {
                "total": total,
                "upcoming": upcoming,
                "by_status": by_status,
            }

    def clear(self) -> int:
        """Supprime tous les événements et retourne le nombre supprimé."""
        with self._lock:
            count = len(self._order)
            self._events.clear()
            self._order.clear()
            return count

    def count(self) -> int:
        """Retourne le nombre total d'événements."""
        with self._lock:
            return len(self._order)