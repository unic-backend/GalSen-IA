"""
Stockage en mémoire des notifications.

Fournit `InMemoryNotificationStore`, une implémentation thread-safe du contrat
`NotificationStore`. Les notifications sont conservées en mémoire ; la
persistance (SQLite) peut être ajoutée ultérieurement sans changer ce module.
"""

import logging
import threading
from typing import Any, Dict, List, Optional

from .interfaces import NotificationStore
from .types import Notification, NotificationPriority

logger = logging.getLogger(__name__)


class InMemoryNotificationStore(NotificationStore):
    """Stockage de notifications en mémoire, thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._notifications: Dict[str, Notification] = {}
        self._order: List[str] = []

    def save(self, notification: Notification) -> str:
        """Enregistre une notification et retourne son identifiant."""
        with self._lock:
            if notification.id in self._notifications:
                raise ValueError(f"La notification {notification.id} existe déjà.")
            self._notifications[notification.id] = notification
            self._order.append(notification.id)
            return notification.id

    def get(self, notification_id: str) -> Optional[Notification]:
        """Retourne une notification par identifiant, ou None si absente."""
        with self._lock:
            return self._notifications.get(notification_id)

    def _priority_value(self, priority: Optional[str]) -> int:
        """Convertit une priorité en valeur numérique pour le filtrage."""
        if priority is None:
            return 0
        ranking = {
            NotificationPriority.LOW.value: 1,
            NotificationPriority.NORMAL.value: 2,
            NotificationPriority.HIGH.value: 3,
            NotificationPriority.URGENT.value: 4,
        }
        return ranking.get(priority, 0)

    def _matches(
        self,
        notification: Notification,
        unread_only: bool,
        notification_type: Optional[str],
        recipient: Optional[str],
        role: Optional[str],
        min_priority: Optional[str],
    ) -> bool:
        """Vérifie si une notification correspond aux filtres fournis."""
        if unread_only and notification.read:
            return False
        if notification_type is not None and notification.notification_type.value != notification_type:
            return False
        if recipient is not None and notification.recipient != recipient:
            return False
        if role is not None and notification.role != role:
            return False
        if min_priority is not None:
            if self._priority_value(notification.priority.value) < self._priority_value(min_priority):
                return False
        return True

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
        with self._lock:
            matched: List[Notification] = []
            for notification_id in reversed(self._order):
                notification = self._notifications[notification_id]
                if self._matches(notification, unread_only, notification_type, recipient, role, min_priority):
                    matched.append(notification)
            return matched[offset:offset + limit]

    def mark_read(self, notification_id: str) -> bool:
        """Marque une notification comme lue ; retourne False si absente."""
        with self._lock:
            notification = self._notifications.get(notification_id)
            if notification is None:
                return False
            if not notification.read:
                notification.mark_read()
            return True

    def mark_all_read(self, recipient: Optional[str] = None) -> int:
        """Marque toutes les notifications comme lues pour un destinataire."""
        with self._lock:
            count = 0
            for notification in self._notifications.values():
                if notification.read:
                    continue
                if recipient is not None and notification.recipient != recipient:
                    continue
                notification.mark_read()
                count += 1
            return count

    def delete(self, notification_id: str) -> bool:
        """Supprime une notification ; retourne False si absente."""
        with self._lock:
            if notification_id not in self._notifications:
                return False
            del self._notifications[notification_id]
            self._order = [nid for nid in self._order if nid != notification_id]
            return True

    def stats(self, recipient: Optional[str] = None) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        with self._lock:
            total = 0
            unread = 0
            by_type: Dict[str, int] = {}
            by_priority: Dict[str, int] = {}

            for notification in self._notifications.values():
                if recipient is not None and notification.recipient != recipient:
                    continue
                total += 1
                if not notification.read:
                    unread += 1
                t = notification.notification_type.value
                by_type[t] = by_type.get(t, 0) + 1
                p = notification.priority.value
                by_priority[p] = by_priority.get(p, 0) + 1

            return {
                "total": total,
                "unread": unread,
                "by_type": by_type,
                "by_priority": by_priority,
            }

    def clear(self) -> int:
        """Supprime toutes les notifications et retourne le nombre supprimé."""
        with self._lock:
            count = len(self._order)
            self._notifications.clear()
            self._order.clear()
            return count

    def count(self) -> int:
        """Retourne le nombre total de notifications."""
        with self._lock:
            return len(self._order)