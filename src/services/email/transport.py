"""
Transport SMTP pour le service Email.

Fournit `SmtpTransport`, une implémentation concrète du transport email
qui envoie les messages via un serveur SMTP réel.

Configuration par variables d'environnement :
- EMAIL_SMTP_HOST : serveur SMTP (défaut : localhost)
- EMAIL_SMTP_PORT : port SMTP (défaut : 587)
- EMAIL_SMTP_USER : utilisateur SMTP (optionnel)
- EMAIL_SMTP_PASSWORD : mot de passe SMTP (optionnel)
- EMAIL_SMTP_USE_TLS : utiliser STARTTLS (défaut : true)
- EMAIL_SMTP_USE_SSL : utiliser SSL direct (défaut : false)

Référence : VOLET 02, Chapitre 09 (Integration).
"""

import logging
import os
import smtplib
import ssl
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from typing import Dict, List, Optional, Tuple

from .types import EmailMessage, EmailSendResult

logger = logging.getLogger(__name__)


class EmailTransport(ABC):
    """Interface de transport pour l'envoi réel d'emails."""

    @abstractmethod
    def send(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        body: str,
        is_html: bool = False,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> Tuple[bool, str]:
        """
        Envoie un email via le transport.

        Returns:
            Tuple (succès, message d'erreur éventuel).
        """


class SmtpTransport(EmailTransport):
    """
    Transport email via SMTP.

    Envoie les messages via un serveur SMTP configuré par variables
    d'environnement. Supporte STARTTLS et SSL direct.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: Optional[bool] = None,
        use_ssl: Optional[bool] = None,
        timeout: int = 30,
    ) -> None:
        """
        Initialise le transport SMTP.

        Les valeurs non fournies sont lues depuis les variables
        d'environnement, avec des valeurs par défaut raisonnables.
        """
        self._host = host or os.environ.get("EMAIL_SMTP_HOST", "localhost")
        self._port = port or int(os.environ.get("EMAIL_SMTP_PORT", "587"))
        self._username = username or os.environ.get("EMAIL_SMTP_USER", "")
        self._password = password or os.environ.get("EMAIL_SMTP_PASSWORD", "")
        self._use_tls = use_tls if use_tls is not None else os.environ.get("EMAIL_SMTP_USE_TLS", "true").lower() == "true"
        self._use_ssl = use_ssl if use_ssl is not None else os.environ.get("EMAIL_SMTP_USE_SSL", "false").lower() == "true"
        self._timeout = timeout
        self._logger = logging.getLogger(f"{__name__}.SmtpTransport")

    def _build_message(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        body: str,
        is_html: bool,
        cc: Optional[List[str]],
        bcc: Optional[List[str]],
        attachments: Optional[List[Dict]],
    ) -> MIMEMultipart:
        """Construit un message MIME complet."""
        msg = MIMEMultipart("alternative")
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)

        if cc:
            msg["Cc"] = ", ".join(cc)

        # Corps du message : toujours texte + HTML si is_html
        if is_html:
            msg.attach(MIMEText(_html_to_plain(body), "plain", "utf-8"))
            msg.attach(MIMEText(body, "html", "utf-8"))
        else:
            msg.attach(MIMEText(body, "plain", "utf-8"))

        # Pièces jointes
        if attachments:
            msg_related = MIMEMultipart("mixed")
            msg_related.attach(msg)
            for att in attachments:
                part = MIMEBase(
                    att.get("content_type", "application/octet-stream").split("/")[0],
                    att.get("content_type", "application/octet-stream").split("/")[1] if "/" in att.get("content_type", "") else "octet-stream",
                )
                part.set_payload(att.get("data", b""))
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=att.get("filename", "attachment"),
                )
                msg_related.attach(part)
            return msg_related

        return msg

    def send(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        body: str,
        is_html: bool = False,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> Tuple[bool, str]:
        """Envoie un email via SMTP."""
        try:
            # Construire le message
            msg = self._build_message(
                sender=sender,
                recipients=recipients,
                subject=subject,
                body=body,
                is_html=is_html,
                cc=cc,
                bcc=bcc,
                attachments=attachments,
            )

            # Tous les destinataires (To + Cc + Bcc)
            all_recipients = list(recipients)
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)

            # Se connecter et envoyer
            if self._use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self._host, self._port, timeout=self._timeout, context=context) as server:
                    if self._username:
                        server.login(self._username, self._password)
                    server.sendmail(sender, all_recipients, msg.as_string())
            else:
                with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as server:
                    if self._use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                    if self._username:
                        server.login(self._username, self._password)
                    server.sendmail(sender, all_recipients, msg.as_string())

            self._logger.info(
                "Email envoyé via SMTP : sujet='%s', destinataires=%d",
                subject, len(all_recipients),
            )
            return True, ""

        except smtplib.SMTPAuthenticationError:
            return False, "Échec d'authentification SMTP : vérifiez les identifiants."
        except smtplib.SMTPRecipientsRefused as e:
            return False, f"Destinataires refusés : {e}"
        except smtplib.SMTPServerDisconnected:
            return False, "Connexion SMTP interrompue."
        except smtplib.SMTPException as e:
            return False, f"Erreur SMTP : {e}"
        except OSError as e:
            return False, f"Erreur réseau SMTP : {e}"
        except Exception as e:
            self._logger.warning("Échec inattendu de l'envoi SMTP : %s", e)
            return False, f"Échec inattendu : {e}"

    def is_configured(self) -> bool:
        """Vérifie si le transport SMTP est configuré."""
        return self._host != "localhost" or self._username != ""


class ConsoleTransport(EmailTransport):
    """
    Transport email qui affiche les messages dans la console.

    Utilisé en développement pour éviter de configurer un vrai serveur
    SMTP. Affiche l'email dans les logs plutôt que de l'envoyer.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.ConsoleTransport")

    def send(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        body: str,
        is_html: bool = False,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> Tuple[bool, str]:
        """Affiche l'email dans les logs."""
        self._logger.info(
            "--- EMAIL (console) ---\nDe: %s\nÀ: %s\nCc: %s\nSujet: %s\n%s\n---",
            sender, ", ".join(recipients), ", ".join(cc or []),
            subject,
            body[:500] + ("..." if len(body) > 500 else ""),
        )
        return True, ""


class NoopTransport(EmailTransport):
    """
    Transport email qui ne fait rien.

    Utilisé par défaut : l'email est stocké mais pas envoyé réellement.
    Comportement historiquement équivalent à l'ancien EmailManagerImpl.
    """

    def send(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        body: str,
        is_html: bool = False,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict]] = None,
    ) -> Tuple[bool, str]:
        """Ne fait rien (comportement historique)."""
        logger.debug("NoopTransport : email '%s' ignoré (aucun transport configuré)", subject)
        return True, ""


def _html_to_plain(html: str) -> str:
    """Convertit approximativement du HTML en texte brut."""
    import re
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"<p[^>]*>", "\n", text)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()