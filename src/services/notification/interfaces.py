"""
Contrats du service de notification.

Définit les interfaces abstraites `NotificationStore` et `NotificationManager`.
Tout backend de stockage (mémoire, SQLite, file externe) peut être branché
à l'avenir sans modifier le code appelant.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import Notification, NotificationType, NotificationPriority


class NotificationStore(ABC):
    """Contrat de stockage des notifications."""

    @abstractmethod
    def save(self, notification: Notification) -> str:
        """Enregistre une notification et retourne son identifiant."""

    @abstractmethod
    def get(self, notification_id: str) -> Optional[Notification]:
        """Retourne une notification par identifiant, ou None si absente."""

    @abstractmethod
    def list_notifications(
        self,
        limit: int = 100,
        offset: int = 0,
        unread_only: bool = False,
        notification_type: Optional[str] = None,
        recipient: Optional[str] = None,
        role: Optional[str] = None,
        min_priority: Optional[str] = None,
    ) -> List[Notification]:
        """Retourne les notifications filtrées, de la plus récente à la plus ancienne."""

    @abstractmethod
    def mark_read(self, notification_id: str) -> bool:
        """Marque une notification comme lue ; retourne False si absente."""

    @abstractmethod
    def mark_all_read(self, recipient: Optional[str] = None) -> int:
        """Marque toutes les notifications comme lues pour un destinataire."""

    @abstractmethod
    def delete(self, notification_id: str) -> bool:
        """Supprime une notification ; retourne False si absente."""

    @abstractmethod
    def stats(self, recipient: Optional[str] = None) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime toutes les notifications et retourne le nombre supprimé."""

    @abstractmethod
    def count(self) -> int:
        """Retourne le nombre total de notifications."""


class NotificationManager(ABC):
    """Contrat du gestionnaire de notifications, façade du service."""

    @abstractmethod
    def send_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        recipient: Optional[str] = None,
        role: Optional[str] = None,
        source: Optional[str] = None,
        related_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Envoie une notification et retourne son identifiant, ou None en cas d'échec."""

    @abstractmethod
    def get(self, notification_id: str) -> Optional[Notification]:
        """Retourne une notification par identifiant, ou None si absente."""

    @abstractmethod
    def list_notifications(
        self,
        limit: int = 100,
        offset: int = 0,
        unread_only: bool = False,
        notification_type: Optional[str] = None,
        recipient: Optional[str] = None,
        role: Optional[str] = None,
    ) -> List[Notification]:
        """Retourne les notifications filtrées."""

    @abstractmethod
    def mark_read(self, notification_id: str) -> bool:
        """Marque une notification comme lue ; retourne False si absente."""

    @abstractmethod
    def mark_all_read(self, recipient: Optional[str] = None) -> int:
        """Marque toutes les notifications comme lues."""

    @abstractmethod
    def delete(self, notification_id: str) -> bool:
        """Supprime une notification ; retourne False si absente."""

    @abstractmethod
    def stats(self, recipient: Optional[str] = None) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime toutes les notifications et retourne le nombre supprimé."""