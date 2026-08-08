"""
SDK Client GalSen IA.

Wrapper Python typé pour l'API REST de la plateforme.
Toutes les méthodes retournent des objets Pydantic et suivent le
pattern best-effort : pas de levée d'exception, retour de résultats
partiels avec `success` et `error` en cas d'échec.
"""

from .client import GalSenClient
from .models import (
    # Santé
    HealthReport, ComponentStatus,
    # Mémoire
    MemoryItem, MemorySearchResult,
    # Modèles
    ModelInfo, ModelGenerateResult,
    # Notifications
    NotificationItem, NotificationStats,
    # Fichiers
    FileItem,
    # Cloud
    CloudFileItem, CloudStats,
    # Calendrier
    CalendarEvent,
    # Email
    EmailMessage,
    # Génériques
    ApiResponse, PaginatedResponse,
)

__all__ = [
    "GalSenClient",
    "HealthReport", "ComponentStatus",
    "MemoryItem", "MemorySearchResult",
    "ModelInfo", "ModelGenerateResult",
    "NotificationItem", "NotificationStats",
    "FileItem",
    "CloudFileItem", "CloudStats",
    "CalendarEvent",
    "EmailMessage",
    "ApiResponse", "PaginatedResponse",
]