"""
Modèles de données du service Email.

Définit les types partagés : messages électroniques, pièces jointes,
statuts d'envoi et générateur d'identifiants.

Ce module n'a aucune dépendance externe.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def generate_email_id() -> str:
    """Génère un identifiant unique d'email (préfixe ``email_``)."""
    return f"email_{uuid.uuid4().hex[:12]}"


class EmailStatus(Enum):
    """Statut d'un message électronique."""

    DRAFT = "draft"
    SENT = "sent"
    FAILED = "failed"
    RECEIVED = "received"


@dataclass
class EmailAttachment:
    """Pièce jointe d'un email."""

    filename: str
    content_type: str
    data: bytes
    size: int = 0

    def __post_init__(self) -> None:
        if self.size == 0 and self.data:
            self.size = len(self.data)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la pièce jointe en dictionnaire (sans les données)."""
        return {
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
        }


@dataclass
class EmailMessage:
    """
    Message électronique dans la plateforme GalSen IA.

    Représente un email envoyé ou reçu, avec ses métadonnées.
    """

    subject: str
    body: str
    sender: str
    recipients: List[str]
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)
    reply_to: Optional[str] = None
    attachments: List[EmailAttachment] = field(default_factory=list)
    is_html: bool = False
    status: EmailStatus = EmailStatus.DRAFT
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=generate_email_id)
    created_at: float = field(default_factory=time.time)
    sent_at: Optional[float] = None

    def mark_sent(self) -> None:
        """Marque l'email comme envoyé."""
        self.status = EmailStatus.SENT
        self.sent_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le message en dictionnaire (sans les pièces jointes binaires)."""
        created_iso = datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat()
        result: Dict[str, Any] = {
            "id": self.id,
            "subject": self.subject,
            "body": self.body[:500] + ("..." if len(self.body) > 500 else ""),
            "sender": self.sender,
            "recipients": self.recipients,
            "status": self.status.value,
            "created_at": created_iso,
        }
        if self.cc:
            result["cc"] = self.cc
        if self.reply_to is not None:
            result["reply_to"] = self.reply_to
        if self.attachments:
            result["attachments"] = [a.to_dict() for a in self.attachments]
            result["attachment_count"] = len(self.attachments)
        if self.sent_at is not None:
            sent_iso = datetime.fromtimestamp(self.sent_at, tz=timezone.utc).isoformat()
            result["sent_at"] = sent_iso
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "EmailMessage":
        """Construit un message à partir d'un dictionnaire."""
        raw_status = data.get("status", "draft")
        if isinstance(raw_status, EmailStatus):
            status = raw_status
        else:
            try:
                status = EmailStatus(raw_status)
            except ValueError:
                status = EmailStatus.DRAFT

        attachments_data = data.get("attachments", [])
        attachments = []
        for att_data in attachments_data:
            if isinstance(att_data, EmailAttachment):
                attachments.append(att_data)
            elif isinstance(att_data, dict):
                attachments.append(EmailAttachment(
                    filename=att_data.get("filename", "unknown"),
                    content_type=att_data.get("content_type", "application/octet-stream"),
                    data=att_data.get("data", b""),
                ))

        return cls(
            subject=data.get("subject", ""),
            body=data.get("body", ""),
            sender=data.get("sender", ""),
            recipients=data.get("recipients", []),
            cc=data.get("cc", []),
            bcc=data.get("bcc", []),
            reply_to=data.get("reply_to"),
            attachments=attachments,
            is_html=data.get("is_html", False),
            status=status,
            metadata=data.get("metadata") or {},
            id=data.get("id", generate_email_id()),
            created_at=data.get("created_at", time.time()),
            sent_at=data.get("sent_at"),
        )


@dataclass
class EmailSendResult:
    """Résultat d'une opération d'envoi d'email."""

    success: bool
    message: str
    email_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class EmailStats:
    """Statistiques agrégées des emails."""

    total: int
    sent: int
    failed: int
    draft: int