"""
Service de messagerie électronique.

Permet d'envoyer, lister et gérer des emails dans la plateforme
GalSen IA. Supporte l'envoi SMTP réel via `SmtpTransport`.

Référence : VOLET 02, Chapitre 09 (Integration).
"""

from .interfaces import EmailManager, EmailStore
from .manager import EmailManagerImpl
from .store import InMemoryEmailStore
from .transport import (
    ConsoleTransport,
    EmailTransport,
    NoopTransport,
    SmtpTransport,
)
from .types import (
    EmailAttachment,
    EmailMessage,
    EmailSendResult,
    EmailStats,
    EmailStatus,
    generate_email_id,
)

__all__ = [
    "ConsoleTransport",
    "EmailAttachment",
    "EmailManager",
    "EmailManagerImpl",
    "EmailMessage",
    "EmailSendResult",
    "EmailStats",
    "EmailStatus",
    "EmailStore",
    "EmailTransport",
    "InMemoryEmailStore",
    "NoopTransport",
    "SmtpTransport",
    "generate_email_id",
]