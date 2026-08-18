"""
Service de notification.

Permet d'envoyer, lister et gérer des notifications dans la plateforme
GalSen IA. Les notifications peuvent être créées par les agents, le système
ou les services externes.

Référence : VOLET 02, Chapitres 03 (Backend), 09 (Integration).
"""

from .channels import (
    ChannelRegistry,
    ChannelState,
    DeliveryChannel,
    load_channels,
)
from .events import ROLE_EXPLOITATION, PlatformNotifier
from .interfaces import NotificationManager, NotificationStore
from .manager import NotificationManagerImpl
from .store import InMemoryNotificationStore
from .types import (
    Notification,
    NotificationPriority,
    NotificationStats,
    NotificationType,
    generate_notification_id,
)

__all__ = [
    "ChannelRegistry",
    "ChannelState",
    "DeliveryChannel",
    "InMemoryNotificationStore",
    "Notification",
    "NotificationManager",
    "NotificationManagerImpl",
    "NotificationPriority",
    "NotificationStats",
    "NotificationStore",
    "NotificationType",
    "PlatformNotifier",
    "ROLE_EXPLOITATION",
    "load_channels",
    "generate_notification_id",
]