"""
Connecteur e-mail SMTP.

Propriétaire, côté plateforme, du service d'envoi d'e-mails. Il répond à trois
questions sans jamais envoyer de message : la messagerie est-elle configurée sur
ce déploiement, le serveur répond-il, et qui accepte nos identifiants.

La vérification ouvre une connexion SMTP, tente `STARTTLS` puis
l'authentification si des identifiants sont fournis, et se déconnecte proprement.
Aucun e-mail n'est émis : vérifier ne doit rien coûter au destinataire.

Référence : ADR-007, ADR-004 (identifiants), VOLET 02 chapitre 09.
"""

import logging
import smtplib
import socket
import ssl
import time
from typing import Optional

from .interfaces import Connector
from ..tool.capabilities import DataScope, Effect
from .contract import DataContract
from .types import ConnectorCheck, ConnectorDescription, ConnectorKind, ConnectorStatus

logger = logging.getLogger(__name__)


class SMTPEmailConnector(Connector):
    """
    Connecteur vers un serveur SMTP.

    Les identifiants sont lus dans l'environnement à chaque appel (ADR-004) :
    ils ne sont jamais conservés en attribut, jamais journalisés, jamais exposés
    par `describe()`.

    Exemple:
        connecteur = SMTPEmailConnector()
        if connecteur.is_configured():
            resultat = connecteur.check()
    """

    CONNECTOR_ID = "email_smtp"

    # Variables lues dans l'environnement. Seul l'hôte est indispensable : un
    # relais interne peut très bien n'exiger aucune authentification.
    HOST_VARIABLE = "GALSEN_SMTP_HOST"
    PORT_VARIABLE = "GALSEN_SMTP_PORT"
    USER_VARIABLE = "GALSEN_SMTP_USER"
    PASSWORD_VARIABLE = "GALSEN_SMTP_PASSWORD"
    SENDER_VARIABLE = "GALSEN_SMTP_SENDER"
    SECURITY_VARIABLE = "GALSEN_SMTP_SECURITY"

    REQUIRED_VARIABLES = [HOST_VARIABLE]

    # Ports par défaut selon le mode de sécurité demandé
    DEFAULT_PORTS = {"starttls": 587, "ssl": 465, "none": 25}

    DEFAULT_TIMEOUT_SECONDS = 10

    def __init__(self, timeout: Optional[int] = None) -> None:
        """
        Initialise le connecteur.

        Args:
            timeout: Délai maximum d'une vérification, en secondes. Un serveur
                injoignable doit être signalé vite, pas bloquer l'appelant.
        """
        self._timeout = int(timeout or self.DEFAULT_TIMEOUT_SECONDS)

    @property
    def connector_id(self) -> str:
        """Identifiant stable du connecteur."""
        return self.CONNECTOR_ID

    @property
    def kind(self) -> ConnectorKind:
        """Catégorie : messagerie."""
        return ConnectorKind.EMAIL

    @property
    def data_contract(self) -> DataContract:
        """
        Ce connecteur relaie le courrier **de la plateforme**, pas celui d'une
        personne : notifications et alertes, avec les identifiants SMTP du
        déploiement. Il n'ouvre aucune boîte, donc il n'est lié à personne.
        Le connecteur Gmail de la vague II sera l'inverse exact, et c'est
        pourquoi les deux ne peuvent pas partager une seule déclaration.
        """
        return DataContract(
            data_scope=DataScope.SYSTEM,
            per_subject=False,
            effects=frozenset({Effect.EXTERNAL}),
            retention="Rien. Le message est remis au relais et n'est pas conservé.",
            rationale="Sortie de la plateforme, sous ses propres identifiants.",
        )

    def describe(self) -> ConnectorDescription:
        """Décrit le connecteur et les variables qu'il consulte, jamais leurs valeurs."""
        return ConnectorDescription(
            connector_id=self.CONNECTOR_ID,
            kind=ConnectorKind.EMAIL,
            summary=(
                "Envoi d'e-mails via un serveur SMTP. La vérification ouvre une "
                "connexion et s'authentifie sans émettre de message."
            ),
            environment_variables=[
                self.HOST_VARIABLE,
                self.PORT_VARIABLE,
                self.USER_VARIABLE,
                self.PASSWORD_VARIABLE,
                self.SENDER_VARIABLE,
                self.SECURITY_VARIABLE,
            ],
            operations=["check", "send"],
            owner="plateforme",
        )

    def is_configured(self) -> bool:
        """Indique si l'hôte SMTP est renseigné, sans aucun appel réseau."""
        return not self._missing_variables(self.REQUIRED_VARIABLES)

    def security_mode(self) -> str:
        """
        Retourne le mode de sécurité demandé : `starttls`, `ssl` ou `none`.

        `starttls` est le défaut : c'est le mode attendu par la majorité des
        serveurs, et le seul des trois qui chiffre sans exiger un port dédié.
        Une valeur inconnue retombe sur `starttls` plutôt que de désactiver le
        chiffrement — se tromper de nom ne doit jamais exposer le trafic.
        """
        demande = (self._read_environment(self.SECURITY_VARIABLE) or "starttls").strip().lower()
        return demande if demande in self.DEFAULT_PORTS else "starttls"

    def port(self) -> int:
        """Retourne le port à utiliser : celui configuré, sinon celui du mode de sécurité."""
        brut = self._read_environment(self.PORT_VARIABLE)
        if brut:
            try:
                return int(brut)
            except ValueError:
                logger.warning(
                    "%s='%s' n'est pas un entier : port par défaut utilisé.",
                    self.PORT_VARIABLE, brut,
                )
        return self.DEFAULT_PORTS[self.security_mode()]

    def sender(self) -> Optional[str]:
        """Retourne l'expéditeur configuré, ou à défaut l'utilisateur SMTP."""
        return self._read_environment(self.SENDER_VARIABLE) or self._read_environment(
            self.USER_VARIABLE
        )

    def check(self) -> ConnectorCheck:
        """
        Vérifie que le serveur SMTP répond et accepte les identifiants.

        Aucun e-mail n'est envoyé. La méthode ne lève jamais : chaque échec
        devient un statut lisible par l'appelant.
        """
        manquantes = self._missing_variables(self.REQUIRED_VARIABLES)
        if manquantes:
            return self._not_configured(manquantes)

        hote = self._read_environment(self.HOST_VARIABLE)
        port = self.port()
        mode = self.security_mode()
        debut = time.time()

        try:
            with self._open_connection(hote, port, mode) as serveur:
                if mode == "starttls":
                    serveur.starttls(context=ssl.create_default_context())
                    # Après STARTTLS, le protocole exige de resaluer le serveur
                    serveur.ehlo()

                identifiant = self._read_environment(self.USER_VARIABLE)
                secret = self._read_environment(self.PASSWORD_VARIABLE)
                if identifiant and secret:
                    serveur.login(identifiant, secret)
                    detail = f"Serveur {hote}:{port} joignable, authentification acceptée ({mode})."
                else:
                    detail = f"Serveur {hote}:{port} joignable, sans authentification ({mode})."

            return self._resultat(ConnectorStatus.READY, detail, debut)

        except smtplib.SMTPAuthenticationError as erreur:
            # Le serveur répond : le problème vient des identifiants, pas du réseau
            return self._resultat(
                ConnectorStatus.UNAUTHORIZED,
                f"Identifiants SMTP refusés par {hote}:{port} (code {erreur.smtp_code}).",
                debut,
            )
        except (socket.timeout, TimeoutError):
            return self._resultat(
                ConnectorStatus.UNREACHABLE,
                f"Aucune réponse de {hote}:{port} après {self._timeout}s.",
                debut,
            )
        except (OSError, smtplib.SMTPException) as erreur:
            # OSError couvre le DNS, le refus de connexion et les erreurs TLS
            return self._resultat(
                ConnectorStatus.UNREACHABLE,
                f"Connexion à {hote}:{port} impossible : {type(erreur).__name__}: {erreur}",
                debut,
            )

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _open_connection(self, hote: str, port: int, mode: str):
        """Ouvre la connexion SMTP correspondant au mode de sécurité demandé."""
        if mode == "ssl":
            return smtplib.SMTP_SSL(
                hote, port, timeout=self._timeout, context=ssl.create_default_context()
            )
        return smtplib.SMTP(hote, port, timeout=self._timeout)

    def _resultat(self, statut: ConnectorStatus, detail: str, debut: float) -> ConnectorCheck:
        """Construit le résultat d'une vérification en mesurant sa durée."""
        return ConnectorCheck(
            connector_id=self.CONNECTOR_ID,
            kind=ConnectorKind.EMAIL,
            status=statut,
            detail=detail,
            latency_ms=(time.time() - debut) * 1000,
        )
