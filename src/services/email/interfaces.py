"""
Contrats du service Email.

Définit les interfaces abstraites `EmailStore` et `EmailManager`.
Tout backend (SMTP direct, SendGrid, Mailgun) peut être branché
à l'avenir sans modifier le code appelant.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import EmailMessage, EmailSendResult


class EmailStore(ABC):
    """Contrat de stockage des messages électroniques."""

    @abstractmethod
    def save(self, message: EmailMessage) -> str:
        """Enregistre un message et retourne son identifiant."""

    @abstractmethod
    def get(self, email_id: str) -> Optional[EmailMessage]:
        """Retourne un message par identifiant, ou None si absent."""

    @abstractmethod
    def list_emails(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> List[EmailMessage]:
        """Retourne les messages filtrés, du plus récent au plus ancien."""

    @abstractmethod
    def update_status(self, email_id: str, status: str) -> bool:
        """Met à jour le statut d'un message ; retourne False si absent."""

    @abstractmethod
    def delete(self, email_id: str) -> bool:
        """Supprime un message ; retourne False si absent."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime tous les messages et retourne le nombre supprimé."""

    @abstractmethod
    def count(self) -> int:
        """Retourne le nombre total de messages."""


class EmailManager(ABC):
    """Contrat du gestionnaire email, façade du service."""

    @abstractmethod
    def send_email(
        self,
        subject: str,
        body: str,
        sender: str,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        is_html: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EmailSendResult:
        """Envoie un email et retourne le résultat."""

    @abstractmethod
    def get_email(self, email_id: str) -> Optional[EmailMessage]:
        """Retourne un email par identifiant."""

    @abstractmethod
    def list_emails(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> List[EmailMessage]:
        """Retourne les emails filtrés."""

    @abstractmethod
    def delete_email(self, email_id: str) -> bool:
        """Supprime un email."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime tous les emails et retourne le nombre supprimé."""