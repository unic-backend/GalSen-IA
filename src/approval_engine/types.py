"""
Modèles de données du moteur d'approbation.

Définit les types partagés par l'ensemble du portillon d'approbation
humaine : demandes, statuts et générateur d'identifiants.

Ce module n'a aucune dépendance externe : il est réutilisable tel quel
par tous les composants de la plateforme.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


def generate_approval_request_id() -> str:
    """Génère un identifiant unique de demande d'approbation (préfixe ``appr_``)."""
    return f"appr_{uuid.uuid4().hex[:12]}"


class ApprovalStatus(Enum):
    """Statut d'une demande d'approbation."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """
    Demande d'approbation humaine pour une action d'agent.

    Une demande est créée dans l'état ``pending`` et bascule vers
    ``approved`` ou ``rejected`` lorsqu'un humain se prononce. La décision,
    sa raison et son auteur sont conservés pour la traçabilité.
    """

    agent_id: str
    request_id: Optional[str]
    action: str
    description: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = ApprovalStatus.PENDING.value
    id: str = field(default_factory=generate_approval_request_id)
    created_at: float = field(default_factory=time.time)
    decided_at: Optional[float] = None
    reason: Optional[str] = None
    decided_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la demande en dictionnaire (champs vides omis)."""
        created_iso = datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat()
        result: Dict[str, Any] = {
            "id": self.id,
            "status": self.status,
            "agent_id": self.agent_id,
            "action": self.action,
            "created_at": created_iso,
            "created_at_unix": self.created_at,
        }
        optional_fields = {
            "request_id": self.request_id,
            "description": self.description,
            "confidence": self.confidence,
            "reason": self.reason,
            "decided_by": self.decided_by,
        }
        for key, value in optional_fields.items():
            if value is not None:
                result[key] = value
        if self.decided_at is not None:
            decided_iso = datetime.fromtimestamp(self.decided_at, tz=timezone.utc).isoformat()
            result["decided_at"] = decided_iso
            result["decided_at_unix"] = self.decided_at
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        """Construit une demande à partir d'un dictionnaire (champs absents tolérés)."""
        return cls(
            agent_id=data.get("agent_id", "unknown"),
            request_id=data.get("request_id"),
            action=data.get("action", "unknown"),
            description=data.get("description"),
            confidence=data.get("confidence"),
            metadata=data.get("metadata") or {},
            status=data.get("status", ApprovalStatus.PENDING.value),
            id=data.get("id", generate_approval_request_id()),
            created_at=data.get("created_at", time.time()),
            decided_at=data.get("decided_at"),
            reason=data.get("reason"),
            decided_by=data.get("decided_by"),
        )
