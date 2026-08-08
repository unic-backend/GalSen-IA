"""
Modèles de données du service de Calendrier.

Définit les types partagés : événements, statuts, répétitions et
générateur d'identifiants.

Ce module n'a aucune dépendance externe.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def generate_event_id() -> str:
    """Génère un identifiant unique d'événement (préfixe ``evt_``)."""
    return f"evt_{uuid.uuid4().hex[:12]}"


class EventStatus(Enum):
    """Statut d'un événement de calendrier."""

    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class EventVisibility(Enum):
    """Visibilité d'un événement."""

    PUBLIC = "public"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"


@dataclass
class CalendarEvent:
    """
    Événement de calendrier dans la plateforme GalSen IA.

    Représente un rendez-vous, une réunion ou une tâche planifiée.
    """

    title: str
    start_time: str  # ISO 8601
    end_time: str    # ISO 8601
    description: Optional[str] = None
    location: Optional[str] = None
    organizer: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    status: EventStatus = EventStatus.CONFIRMED
    visibility: EventVisibility = EventVisibility.PUBLIC
    recurrence: Optional[str] = None  # Règle RRULE (ex: "FREQ=WEEKLY")
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=generate_event_id)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'événement en dictionnaire."""
        created_iso = datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat()
        updated_iso = datetime.fromtimestamp(self.updated_at, tz=timezone.utc).isoformat()
        result: Dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status.value,
            "visibility": self.visibility.value,
            "created_at": created_iso,
            "updated_at": updated_iso,
        }
        optional_fields = {
            "description": self.description,
            "location": self.location,
            "organizer": self.organizer,
            "recurrence": self.recurrence,
        }
        for key, value in optional_fields.items():
            if value is not None:
                result[key] = value
        if self.attendees:
            result["attendees"] = self.attendees
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "CalendarEvent":
        """Construit un événement à partir d'un dictionnaire."""
        raw_status = data.get("status", "confirmed")
        if isinstance(raw_status, EventStatus):
            status = raw_status
        else:
            try:
                status = EventStatus(raw_status)
            except ValueError:
                status = EventStatus.CONFIRMED

        raw_visibility = data.get("visibility", "public")
        if isinstance(raw_visibility, EventVisibility):
            visibility = raw_visibility
        else:
            try:
                visibility = EventVisibility(raw_visibility)
            except ValueError:
                visibility = EventVisibility.PUBLIC

        return cls(
            title=data.get("title", ""),
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time", ""),
            description=data.get("description"),
            location=data.get("location"),
            organizer=data.get("organizer"),
            attendees=data.get("attendees", []),
            status=status,
            visibility=visibility,
            recurrence=data.get("recurrence"),
            metadata=data.get("metadata") or {},
            id=data.get("id", generate_event_id()),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


@dataclass
class CalendarEventResult:
    """Résultat d'une opération sur un événement."""

    success: bool
    message: str
    event_id: Optional[str] = None
    event: Optional[CalendarEvent] = None


@dataclass
class CalendarStats:
    """Statistiques agrégées du calendrier."""

    total: int
    upcoming: int
    by_status: Dict[str, int]