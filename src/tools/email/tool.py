"""
Outil de messagerie électronique pour GalSen IA.

Fournit une interface pour envoyer des e-mails via SMTP.
"""

import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

logger = __import__('logging').getLogger(__name__)


class EmailTool(BaseTool):
    """
    Outil d'envoi d'e-mails via SMTP.

    Opérations disponibles : `send` (envoyer un e-mail).

    Exemple:
        tool.execute("send",
                    to=["destinataire@example.com"],
                    subject="Bonjour",
                    message="Ceci est un test.")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil de messagerie électronique.

        Args:
            config: Configuration avec les clés optionnelles :
                - `smtp_host`: serveur SMTP (requis pour envoyer)
                - `smtp_port`: port du serveur SMTP (défaut: 587 pour TLS, 465 pour SSL, 25 pour sans TLS)
                - `smtp_user`: nom d'utilisateur pour l'authentification SMTP (optionnel)
                - `smtp_password`: mot de passe pour l'authentification SMTP (optionnel)
                - `use_tls`: utiliser STARTTLS (défaut: True)
                - `use_ssl`: utiliser SSL/TLS (défaut: False)
        """
        super().__init__(config)
        self.smtp_host = self.config.get("smtp_host")
        self.smtp_port = self.config.get("smtp_port")
        self.smtp_user = self.config.get("smtp_user")
        self.smtp_password = self.config.get("smtp_password")
        self.use_tls = self.config.get("use_tls", True)
        self.use_ssl = self.config.get("use_ssl", False)

        # Validation de la configuration
        if not self.smtp_host:
            # Nous ne levons pas d'erreur ici pour permettre l'instantiation sans configuration,
            # mais l'envoi échouera si l'hôte n'est pas fourni.
            pass

    def _op_send(
        self,
        to: List[str],
        subject: str,
        body: str,
        **kwargs,
    ) -> dict:
        """
        Envoie un e-mail via SMTP.

        Args:
            to: Liste des adresses e-mail des destinataires (requise).
            subject: Sujet de l'e-mail (requis).
            body: Corps de l'e-mail (requis).
            **kwargs: Options supplémentaires :
                - `from_`: adresse e-mail de l'expéditeur (optionnel, par défaut utilise smtp_user)
                - `cc`: liste des adresses e-mail en copie (optionnel)
                - `bcc`: liste des adresses e-mail en copie cachée (optionnel)
                - `html`: booléen indiquant si le corps est en HTML (défaut: False)

        Returns:
            Dictionnaire contenant le statut de l'envoi et un message.

        Raises:
            ValueError: Si les paramètres sont invalides.
            RuntimeError: Si l'envoi de l'e-mail échoue.
        """
        if not isinstance(to, list) or not all(isinstance(addr, str) for addr in to):
            raise ValueError("Le paramètre 'to' doit être une liste de chaînes de caractères")
        if not to:
            raise ValueError("La liste des destinataires 'to' ne peut pas être vide")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("Le sujet doit être une chaîne non vide")
        if not isinstance(body, str):
            raise ValueError("Le corps doit être une chaîne de caractères")

        from_addr = kwargs.get("from_", self.smtp_user)
        cc = kwargs.get("cc", [])
        bcc = kwargs.get("bcc", [])
        is_html = kwargs.get("html", False)

        # Validation des adresses e-mail optionnelles
        for addr_list, name in [(cc, "cc"), (bcc, "bcc")]:
            if not isinstance(addr_list, list) or not all(isinstance(addr, str) for addr in addr_list):
                raise ValueError(f"Le paramètre '{name}' doit être une liste de chaînes de caractères")

        # Création du message
        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            # Note: Bcc n'est généralement pas ajouté aux en-têtes pour la confidentialité
            pass
        msg["Subject"] = subject

        if is_html:
            msg.add_alternative(body, subtype="html")
        else:
            msg.set_content(body)

        # Liste de tous les destinataires (To, Cc, Bcc) pour l'envoi SMTP
        all_recipients = to[:]
        if cc:
            all_recipients.extend(cc)
        if bcc:
            all_recipients.extend(bcc)

        try:
            if self.use_ssl:
                # SSL: le chiffrement est établi dès la connexion, pas de STARTTLS
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port or 465) as server:
                    # Authentification si nécessaire
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    # Envoi du message
                    server.send_message(from_addr=from_addr, to_addrs=all_recipients, msg=msg)
            else:
                # TLS ou pas de chiffrement
                with smtplib.SMTP(self.smtp_host, self.smtp_port or 25) as server:
                    if self.use_tls:
                        server.starttls()
                    # Authentification si nécessaire
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    # Envoi du message
                    server.send_message(from_addr=from_addr, to_addrs=all_recipients, msg=msg)
        except Exception as e:
            raise RuntimeError(f"Échec de l'envoi de l'e-mail : {e}") from e

        return {
            "status": "success",
            "message": f"Email sent to {len(to)} recipient(s)",
            "details": {
                "to": to,
                "cc": cc,
                "bcc": bcc,
                "subject": subject,
            },
        }

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur l'outil de messagerie électronique.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération.

        Raises:
            ValueError: Opération inconnue.
        """
        if not args:
            raise ValueError("Une opération est requise (send)")

        operation = str(args[0]).lower()
        operation_args = args[1:]

        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. "
                f"Opérations disponibles: {', '.join(self.available_operations())}"
            )

        return handler(*operation_args, **kwargs)

    def available_operations(self) -> list[str]:
        """Retourne la liste des opérations prises en charge."""
        return ["send"]