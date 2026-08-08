"""
Gestionnaire du service de notification.

Fournit `NotificationManagerImpl`, une façade best-effort conforme à
`NotificationManager` : chaque appel est protégé et ne lève jamais ; en cas
d'échec, un avertissement est journalisé et une valeur vide est retournée.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from .interfaces import NotificationManager, NotificationStore
from .store import InMemoryNotificationStore
from .types import Notification, NotificationPriority, NotificationType

logger = logging.getLogger(__name__)


class NotificationManagerImpl(NotificationManager):
    """Façade du service de notification, toujours disponible en mémoire."""

    def __init__(self, store: Optional[NotificationStore] = None) -> None:
        if store is not None:
            self._store = store
        elif os.getenv("GALSEN_STORAGE_BACKEND", "in-memory").lower() == "sqlite":
            from src.storage.sqlite_notification_store import SQLiteNotificationStore
            self._store = SQLiteNotificationStore()
        else:
            self._store = InMemoryNotificationStore()
        self._logger = logging.getLogger(f"{__name__}.NotificationManagerImpl")

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
        try:
            notification = Notification(
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority,
                recipient=recipient,
                role=role,
                source=source,
                related_id=related_id,
                metadata=metadata or {},
            )
            return self._store.save(notification)
        except Exception as error:
            self._logger.warning("Échec de l'envoi d'une notification : %s", error)
            return None

    def get(self, notification_id: str) -> Optional[Notification]:
        """Retourne une notification par identifiant, ou None si absente."""
        try:
            return self._store.get(notification_id)
        except Exception as error:
            self._logger.warning("Échec de la lecture de la notification %s : %s", notification_id, error)
            return None

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
        try:
            return self._store.list_notifications(
                limit=limit,
                offset=offset,
                unread_only=unread_only,
                notification_type=notification_type,
                recipient=recipient,
                role=role,
            )
        except Exception as error:
            self._logger.warning("Échec du filtrage des notifications : %s", error)
            return []

    def mark_read(self, notification_id: str) -> bool:
        """Marque une notification comme lue ; retourne False si absente."""
        try:
            return self._store.mark_read(notification_id)
        except Exception as error:
            self._logger.warning("Échec du marquage de la notification %s : %s", notification_id, error)
            return False

    def mark_all_read(self, recipient: Optional[str] = None) -> int:
        """Marque toutes les notifications comme lues."""
        try:
            return self._store.mark_all_read(recipient=recipient)
        except Exception as error:
            self._logger.warning("Échec du marquage de toutes les notifications : %s", error)
            return 0

    def delete(self, notification_id: str) -> bool:
        """Supprime une notification ; retourne False si absente."""
        try:
            return self._store.delete(notification_id)
        except Exception as error:
            self._logger.warning("Échec de la suppression de la notification %s : %s", notification_id, error)
            return False

    def stats(self, recipient: Optional[str] = None) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        try:
            return self._store.stats(recipient=recipient)
        except Exception as error:
            self._logger.warning("Échec du calcul des statistiques de notifications : %s", error)
            return {}

    def clear(self) -> int:
        """Supprime toutes les notifications et retourne le nombre supprimé."""
        try:
            return self._store.clear()
        except Exception as error:
            self._logger.warning("Échec de la suppression des notifications : %s", error)
            return 0