"""
Modèles de données du service de notification.

Définit les types partagés : notifications, statuts de lecture,
types de notification et générateur d'identifiants.

Ce module n'a aucune dépendance externe.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def generate_notification_id() -> str:
    """Génère un identifiant unique de notification (préfixe ``notif_``)."""
    return f"notif_{uuid.uuid4().hex[:12]}"


class NotificationType(Enum):
    """Type de notification dans la plateforme GalSen IA."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_DECIDED = "approval_decided"
    SYSTEM = "system"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"


class NotificationPriority(Enum):
    """Priorité d'une notification."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """
    Notification dans la plateforme GalSen IA.

    Une notification peut être créée par un agent, le système ou un service
    externe. Elle est destinée à un utilisateur ou à un rôle spécifique.
    """

    notification_type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    recipient: Optional[str] = None
    role: Optional[str] = None
    source: Optional[str] = None
    related_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=generate_notification_id)
    read: bool = False
    read_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)

    def mark_read(self) -> None:
        """Marque la notification comme lue."""
        self.read = True
        self.read_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la notification en dictionnaire."""
        created_iso = datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat()
        result: Dict[str, Any] = {
            "id": self.id,
            "type": self.notification_type.value,
            "title": self.title,
            "message": self.message,
            "priority": self.priority.value,
            "read": self.read,
            "created_at": created_iso,
            "created_at_unix": self.created_at,
        }
        optional_fields = {
            "recipient": self.recipient,
            "role": self.role,
            "source": self.source,
            "related_id": self.related_id,
        }
        for key, value in optional_fields.items():
            if value is not None:
                result[key] = value
        if self.read_at is not None:
            read_iso = datetime.fromtimestamp(self.read_at, tz=timezone.utc).isoformat()
            result["read_at"] = read_iso
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "Notification":
        """Construit une notification à partir d'un dictionnaire."""
        # Résoudre le type de notification
        raw_type = data.get("type", "info")
        if isinstance(raw_type, NotificationType):
            notification_type = raw_type
        else:
            try:
                notification_type = NotificationType(raw_type)
            except ValueError:
                notification_type = NotificationType.INFO

        # Résoudre la priorité
        raw_priority = data.get("priority", "normal")
        if isinstance(raw_priority, NotificationPriority):
            priority = raw_priority
        else:
            try:
                priority = NotificationPriority(raw_priority)
            except ValueError:
                priority = NotificationPriority.NORMAL

        return cls(
            notification_type=notification_type,
            title=data.get("title", ""),
            message=data.get("message", ""),
            priority=priority,
            recipient=data.get("recipient"),
            role=data.get("role"),
            source=data.get("source"),
            related_id=data.get("related_id"),
            metadata=data.get("metadata") or {},
            id=data.get("id", generate_notification_id()),
            read=data.get("read", False),
            read_at=data.get("read_at"),
            created_at=data.get("created_at", time.time()),
        )


@dataclass
class NotificationStats:
    """Statistiques agrégées des notifications."""

    total: int
    unread: int
    by_type: Dict[str, int]
    by_priority: Dict[str, int]