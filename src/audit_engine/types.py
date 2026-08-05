"""
Modèles de données du moteur d'audit.

Définit les types partagés par l'ensemble du système d'audit :
événements, statuts, référence de source de connaissance et générateur
d'identifiants de requête.

Ce module n'a aucune dépendance externe : il est réutilisable tel quel
par tous les composants de la plateforme.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def generate_request_id() -> str:
    """Génère un identifiant unique de requête (préfixe ``req_``)."""
    return f"req_{uuid.uuid4().hex[:12]}"


class AuditEventType(Enum):
    """Catégorie d'un événement d'audit."""

    REQUEST = "request"
    AGENT = "agent"
    TOOL = "tool"
    GENERATION = "generation"
    KNOWLEDGE = "knowledge"


class AuditStatus(Enum):
    """Statut d'exécution d'un événement d'audit."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"
    RUNNING = "running"
    REQUIRES_APPROVAL = "requires_approval"


@dataclass
class KnowledgeSourceRef:
    """
    Référence légère vers une source de connaissance consignée dans l'audit.

    Permet de tracer l'origine d'une réponse sans dupliquer le contenu
    complet de la source.
    """

    id: Optional[str] = None
    title: Optional[str] = None
    source_category: Optional[str] = None
    priority: Optional[str] = None
    confidence: Optional[float] = None
    citation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la référence en dictionnaire (les champs vides sont omis)."""
        result: Dict[str, Any] = {}
        for key in ("id", "title", "source_category", "priority", "confidence", "citation"):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "KnowledgeSourceRef":
        """Construit une référence à partir d'un dictionnaire (champs absents tolérés)."""
        return cls(
            id=data.get("id"),
            title=data.get("title"),
            source_category=data.get("source_category"),
            priority=data.get("priority"),
            confidence=data.get("confidence"),
            citation=data.get("citation"),
        )


@dataclass
class AuditEvent:
    """
    Événement d'audit : trace structurée d'une action importante.

    Couvre les neuf champs requis : timestamp, request_id, agent_id,
    requête utilisateur, modèle utilisé, niveau de confiance, sources de
    connaissance, statut d'exécution et temps d'exécution.
    """

    event_type: AuditEventType
    action: str
    agent_id: Optional[str] = None
    request_id: Optional[str] = None
    user_request: Optional[str] = None
    model_id: Optional[str] = None
    confidence: Optional[float] = None
    knowledge_sources: List[Dict[str, Any]] = field(default_factory=list)
    status: AuditStatus = AuditStatus.SUCCESS
    execution_time_seconds: Optional[float] = None
    detail: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'événement en dictionnaire (champs vides omis)."""
        timestamp_iso = datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat()
        result: Dict[str, Any] = {
            "id": self.id,
            "timestamp": timestamp_iso,
            "timestamp_unix": self.timestamp,
            "event_type": self.event_type.value,
            "action": self.action,
            "status": self.status.value,
        }
        optional_fields = {
            "agent_id": self.agent_id,
            "request_id": self.request_id,
            "user_request": self.user_request,
            "model_id": self.model_id,
            "confidence": self.confidence,
            "execution_time_seconds": self.execution_time_seconds,
            "detail": self.detail,
        }
        for key, value in optional_fields.items():
            if value is not None:
                result[key] = value
        if self.knowledge_sources:
            result["knowledge_sources"] = self.knowledge_sources
        if self.metadata:
            result["metadata"] = self.metadata
        return result
