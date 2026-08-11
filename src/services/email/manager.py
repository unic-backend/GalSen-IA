"""
Gestionnaire du service Email.

Fournit `EmailManagerImpl`, une façade best-effort conforme à
`EmailManager` : chaque appel est protégé et ne lève jamais ; en cas
d'échec, un avertissement est journalisé et une valeur vide est retournée.

Supporte l'injection d'un transport SMTP optionnel. Si aucun transport
n'est fourni, utilise `NoopTransport` (stockage mémoire uniquement).
"""

import logging
import os
from typing import Any, Dict, List, Optional

from .interfaces import EmailManager, EmailStore
from .store import InMemoryEmailStore
from .transport import EmailTransport, NoopTransport
from .types import EmailMessage, EmailSendResult, EmailStatus
from src.storage.paths import sqlite_enabled

logger = logging.getLogger(__name__)


class EmailManagerImpl(EmailManager):
    """Façade du service email, avec transport réel optionnel."""

    def __init__(
        self,
        store: Optional[EmailStore] = None,
        transport: Optional[EmailTransport] = None,
    ) -> None:
        if store is not None:
            self._store = store
        elif sqlite_enabled():
            from src.storage.sqlite_email_store import SQLiteEmailStore
            self._store = SQLiteEmailStore()
        else:
            self._store = InMemoryEmailStore()
        self._transport = transport or NoopTransport()
        self._logger = logging.getLogger(f"{__name__}.EmailManagerImpl")

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
        if not subject or not subject.strip():
            return EmailSendResult(False, "Le sujet de l'email est requis.")
        if not body:
            return EmailSendResult(False, "Le corps de l'email est vide.")
        if not sender or "@" not in sender:
            return EmailSendResult(False, "L'adresse expéditeur est invalide.")
        if not recipients or not all("@" in r for r in recipients):
            return EmailSendResult(False, "Au moins un destinataire valide est requis.")

        try:
            # Envoyer via le transport réel si configuré
            transport_ok, transport_msg = self._transport.send(
                sender=sender,
                recipients=recipients,
                subject=subject.strip(),
                body=body,
                is_html=is_html,
                cc=cc,
                bcc=bcc,
                attachments=None,
            )
            # Le message est enregistré dans tous les cas : ce qu'un utilisateur a
            # rédigé ne doit pas disparaître parce que l'infrastructure manque. Le
            # statut dit ce qui s'est réellement passé — `sent` seulement quand un
            # transport a accepté le message (VOLET 12, ch. 02, étape 5).
            message = EmailMessage(
                subject=subject.strip(),
                body=body,
                sender=sender,
                recipients=recipients,
                cc=cc or [],
                bcc=bcc or [],
                is_html=is_html,
                status=EmailStatus.SENT if transport_ok else EmailStatus.FAILED,
                metadata=metadata or {},
            )
            if transport_ok:
                message.mark_sent()
            email_id = self._store.save(message)

            if not transport_ok:
                return EmailSendResult(
                    False,
                    transport_msg,
                    email_id=email_id,
                    details={"subject": subject, "recipients": recipients, "cc": cc or [],
                             "stored": True, "delivered": False},
                )
            return EmailSendResult(
                True,
                f"Email envoyé à {len(recipients)} destinataire(s).",
                email_id=email_id,
                details={"subject": subject, "recipients": recipients, "cc": cc or []},
            )
        except Exception as error:
            self._logger.warning("Échec de l'envoi de l'email : %s", error)
            return EmailSendResult(False, f"Échec de l'envoi : {error}")

    def get_email(self, email_id: str) -> Optional[EmailMessage]:
        """Retourne un email par identifiant."""
        try:
            return self._store.get(email_id)
        except Exception as error:
            self._logger.warning("Échec de la lecture de l'email %s : %s", email_id, error)
            return None

    def list_emails(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> List[EmailMessage]:
        """Retourne les emails filtrés."""
        try:
            return self._store.list_emails(
                limit=limit,
                offset=offset,
                status=status,
                sender=sender,
                recipient=recipient,
            )
        except Exception as error:
            self._logger.warning("Échec du filtrage des emails : %s", error)
            return []

    def delete_email(self, email_id: str) -> bool:
        """Supprime un email."""
        try:
            return self._store.delete(email_id)
        except Exception as error:
            self._logger.warning("Échec de la suppression de l'email %s : %s", email_id, error)
            return False

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        try:
            return self._store.stats()
        except Exception as error:
            self._logger.warning("Échec du calcul des statistiques email : %s", error)
            return {}

    def clear(self) -> int:
        """Supprime tous les emails et retourne le nombre supprimé."""
        try:
            return self._store.clear()
        except Exception as error:
            self._logger.warning("Échec de la suppression des emails : %s", error)
            return 0