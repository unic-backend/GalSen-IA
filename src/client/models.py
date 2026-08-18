"""
Modèles Pydantic pour le SDK client GalSen IA.

Tous les modèles retournés par le client sont définis ici.
"""

from pydantic import BaseModel
from typing import Any, Dict, List, Optional


# =============================================================================
# Génériques
# =============================================================================

class ApiResponse(BaseModel):
    """Réponse générique d'un endpoint."""
    success: bool = True
    error: Optional[str] = None
    data: Optional[Any] = None


class PaginatedResponse(BaseModel):
    """Réponse paginée."""
    items: List[Any] = []
    total: int = 0


# =============================================================================
# Santé
# =============================================================================

class ComponentStatus(BaseModel):
    """État d'un composant de la plateforme."""
    name: str = ""
    status: str = "unknown"
    details: Optional[str] = None


class HealthReport(BaseModel):
    """Rapport de santé complet."""
    status: str = "unknown"
    version: str = ""
    uptime: str = ""
    components: List[ComponentStatus] = []


# =============================================================================
# Mémoire
# =============================================================================

class MemoryItem(BaseModel):
    """Élément de mémoire."""
    id: str = ""
    content: Any = None
    memory_type: str = ""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    tags: List[str] = []
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    metadata: Dict[str, Any] = {}


class MemorySearchResult(BaseModel):
    """Résultat de recherche mémoire."""
    items: List[MemoryItem] = []
    total: int = 0


# =============================================================================
# Modèles
# =============================================================================

class ModelInfo(BaseModel):
    """Information sur un modèle."""
    name: str = ""
    provider: str = ""
    status: str = ""
    model_type: Optional[str] = None


class ModelGenerateResult(BaseModel):
    """Résultat d'une génération."""
    text: str = ""
    status: str = ""
    model_used: str = ""
    tokens_used: int = 0
    latency_seconds: float = 0.0


# =============================================================================
# Notifications
# =============================================================================

class NotificationItem(BaseModel):
    """Notification."""
    id: str = ""
    type: str = ""
    title: str = ""
    message: str = ""
    priority: str = "normal"
    read: bool = False
    created_at: Optional[float] = None


class NotificationStats(BaseModel):
    """Statistiques des notifications."""
    total: int = 0
    unread: int = 0


# =============================================================================
# Fichiers
# =============================================================================

class FileItem(BaseModel):
    """Fichier stocké."""
    id: str = ""
    name: str = ""
    content_type: str = ""
    size: int = 0
    category: str = ""
    uploaded_by: Optional[str] = None
    created_at: Optional[float] = None


# =============================================================================
# Cloud
# =============================================================================

class CloudFileItem(BaseModel):
    """Fichier cloud."""
    id: str = ""
    name: str = ""
    content_type: str = ""
    size: int = 0
    provider: str = ""
    category: str = ""
    uploaded_by: Optional[str] = None


class CloudStats(BaseModel):
    """Statistiques cloud."""
    total: int = 0
    total_size: int = 0


# =============================================================================
# Calendrier
# =============================================================================

class CalendarEvent(BaseModel):
    """Événement calendrier."""
    id: str = ""
    title: str = ""
    start_time: str = ""
    end_time: str = ""
    description: Optional[str] = None
    location: Optional[str] = None
    organizer: Optional[str] = None
    status: str = ""
    attendees: List[str] = []


# =============================================================================
# Email
# =============================================================================

class EmailMessage(BaseModel):
    """Message email."""
    id: str = ""
    subject: str = ""
    sender: str = ""
    recipients: List[str] = []
    status: str = ""
    created_at: Optional[float] = None