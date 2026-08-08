"""
Stockage en mémoire des messages électroniques.

Fournit `InMemoryEmailStore`, une implémentation thread-safe du contrat
`EmailStore`. Les messages sont conservés en mémoire ; la persistance
(SQLite) peut être ajoutée ultérieurement sans changer ce module.
"""

import logging
import threading
from typing import Any, Dict, List, Optional

from .interfaces import EmailStore
from .types import EmailMessage

logger = logging.getLogger(__name__)


class InMemoryEmailStore(EmailStore):
    """Stockage d'emails en mémoire, thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._emails: Dict[str, EmailMessage] = {}
        self._order: List[str] = []

    def save(self, message: EmailMessage) -> str:
        """Enregistre un message et retourne son identifiant."""
        with self._lock:
            if message.id in self._emails:
                raise ValueError(f"Le message {message.id} existe déjà.")
            self._emails[message.id] = message
            self._order.append(message.id)
            return message.id

    def get(self, email_id: str) -> Optional[EmailMessage]:
        """Retourne un message par identifiant, ou None si absent."""
        with self._lock:
            return self._emails.get(email_id)

    def _matches(
        self,
        message: EmailMessage,
        status: Optional[str],
        sender: Optional[str],
        recipient: Optional[str],
    ) -> bool:
        """Vérifie si un message correspond aux filtres fournis."""
        if status is not None and message.status.value != status:
            return False
        if sender is not None and message.sender != sender:
            return False
        if recipient is not None:
            if recipient not in message.recipients and recipient not in message.cc:
                return False
        return True

    def list_emails(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> List[EmailMessage]:
        """Retourne les messages filtrés, du plus récent au plus ancien."""
        with self._lock:
            matched: List[EmailMessage] = []
            for email_id in reversed(self._order):
                message = self._emails[email_id]
                if self._matches(message, status, sender, recipient):
                    matched.append(message)
            return matched[offset:offset + limit]

    def update_status(self, email_id: str, status: str) -> bool:
        """Met à jour le statut d'un message ; retourne False si absent."""
        from .types import EmailStatus
        with self._lock:
            message = self._emails.get(email_id)
            if message is None:
                return False
            try:
                message.status = EmailStatus(status)
            except ValueError:
                return False
            if message.status == EmailStatus.SENT and message.sent_at is None:
                message.sent_at = __import__("time").time()
            return True

    def delete(self, email_id: str) -> bool:
        """Supprime un message ; retourne False si absent."""
        with self._lock:
            if email_id not in self._emails:
                return False
            del self._emails[email_id]
            self._order = [eid for eid in self._order if eid != email_id]
            return True

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        with self._lock:
            total = len(self._order)
            by_status: Dict[str, int] = {}
            sender_set: set = set()

            for message in self._emails.values():
                s = message.status.value
                by_status[s] = by_status.get(s, 0) + 1
                sender_set.add(message.sender)

            return {
                "total": total,
                "by_status": by_status,
                "unique_senders": len(sender_set),
            }

    def clear(self) -> int:
        """Supprime tous les messages et retourne le nombre supprimé."""
        with self._lock:
            count = len(self._order)
            self._emails.clear()
            self._order.clear()
            return count

    def count(self) -> int:
        """Retourne le nombre total de messages."""
        with self._lock:
            return len(self._order)