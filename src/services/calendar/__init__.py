"""
Service de calendrier.

Permet de créer, lister, modifier et supprimer des événements de
calendrier dans la plateforme GalSen IA.

Référence : VOLET 02, Chapitre 09 (Integration).
"""

from .interfaces import CalendarManager, CalendarStore
from .manager import CalendarManagerImpl
from .store import InMemoryCalendarStore
from .types import (
    CalendarEvent,
    CalendarEventResult,
    CalendarStats,
    EventStatus,
    EventVisibility,
    generate_event_id,
)

__all__ = [
    "CalendarEvent",
    "CalendarEventResult",
    "CalendarManager",
    "CalendarManagerImpl",
    "CalendarStats",
    "CalendarStore",
    "EventStatus",
    "EventVisibility",
    "InMemoryCalendarStore",
    "generate_event_id",
]