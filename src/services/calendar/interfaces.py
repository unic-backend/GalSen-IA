"""
Contrats du service de Calendrier.

Définit les interfaces abstraites `CalendarStore` et `CalendarManager`.
Tout backend de stockage (mémoire, SQLite, CalDAV) peut être branché
à l'avenir sans modifier le code appelant.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import CalendarEvent, CalendarEventResult, EventStatus


class CalendarStore(ABC):
    """Contrat de stockage des événements de calendrier."""

    @abstractmethod
    def save(self, event: CalendarEvent) -> str:
        """Enregistre un événement et retourne son identifiant."""

    @abstractmethod
    def get(self, event_id: str) -> Optional[CalendarEvent]:
        """Retourne un événement par identifiant, ou None si absent."""

    @abstractmethod
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

    @abstractmethod
    def update(self, event_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un événement ; retourne False si absent."""

    @abstractmethod
    def delete(self, event_id: str) -> bool:
        """Supprime un événement ; retourne False si absent."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime tous les événements et retourne le nombre supprimé."""

    @abstractmethod
    def count(self) -> int:
        """Retourne le nombre total d'événements."""


class CalendarManager(ABC):
    """Contrat du gestionnaire de calendrier, façade du service."""

    @abstractmethod
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

    @abstractmethod
    def get_event(self, event_id: str) -> Optional[CalendarEvent]:
        """Retourne un événement par identifiant."""

    @abstractmethod
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

    @abstractmethod
    def update_event(self, event_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un événement."""

    @abstractmethod
    def cancel_event(self, event_id: str) -> bool:
        """Annule un événement."""

    @abstractmethod
    def delete_event(self, event_id: str) -> bool:
        """Supprime un événement."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime tous les événements et retourne le nombre supprimé."""