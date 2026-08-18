"""
Tests unitaires du connecteur e-mail SMTP (phase 3.2, ADR-007).

Aucune connexion réelle n'est ouverte : `smtplib` est simulé. Le point vérifié en
priorité est qu'une vérification **n'envoie jamais d'e-mail** et ne lève jamais —
un serveur injoignable ou des identifiants refusés doivent devenir des statuts
distincts, car ils appellent des corrections différentes.
"""

import smtplib
import socket
from unittest.mock import MagicMock, patch

import pytest

from src.connectors import ConnectorKind, ConnectorStatus
from src.connectors.email_connector import SMTPEmailConnector


@pytest.fixture(autouse=True)
def environnement_propre(monkeypatch):
    """Retire toute configuration SMTP héritée de l'environnement réel."""
    for variable in (
        SMTPEmailConnector.HOST_VARIABLE,
        SMTPEmailConnector.PORT_VARIABLE,
        SMTPEmailConnector.USER_VARIABLE,
        SMTPEmailConnector.PASSWORD_VARIABLE,
        SMTPEmailConnector.SENDER_VARIABLE,
        SMTPEmailConnector.SECURITY_VARIABLE,
    ):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def connecteur():
    """Connecteur avec un délai court, pour ne pas ralentir la suite."""
    return SMTPEmailConnector(timeout=2)


@pytest.fixture
def configure(monkeypatch):
    """Configure un serveur SMTP minimal dans l'environnement."""
    monkeypatch.setenv(SMTPEmailConnector.HOST_VARIABLE, "smtp.exemple.sn")
    return monkeypatch


def _serveur_simule():
    """Construit un serveur SMTP simulé utilisable en gestionnaire de contexte."""
    serveur = MagicMock()
    serveur.__enter__ = MagicMock(return_value=serveur)
    serveur.__exit__ = MagicMock(return_value=False)
    return serveur


class TestConfiguration:
    """Vérifie ce que le connecteur sait dire sans toucher au réseau."""

    def test_non_configure_sans_hote(self, connecteur):
        """Sans hôte SMTP, le connecteur se déclare non configuré."""
        assert connecteur.is_configured() is False

    def test_configure_avec_l_hote_seul(self, connecteur, configure):
        """L'hôte suffit : un relais interne peut n'exiger aucune authentification."""
        assert connecteur.is_configured() is True

    def test_check_sans_configuration_n_ouvre_aucune_connexion(self, connecteur):
        """Non configuré, la vérification doit répondre sans toucher au réseau."""
        with patch("smtplib.SMTP") as smtp:
            resultat = connecteur.check()
        smtp.assert_not_called()
        assert resultat.status is ConnectorStatus.NOT_CONFIGURED
        assert SMTPEmailConnector.HOST_VARIABLE in resultat.detail

    def test_identite(self, connecteur):
        """Le connecteur doit s'annoncer comme un connecteur de messagerie."""
        assert connecteur.connector_id == "email_smtp"
        assert connecteur.kind is ConnectorKind.EMAIL


class TestPortEtSecurite:
    """Vérifie le choix du port et du mode de chiffrement."""

    def test_starttls_par_defaut(self, connecteur):
        """Sans précision, le mode doit être STARTTLS sur le port 587."""
        assert connecteur.security_mode() == "starttls"
        assert connecteur.port() == 587

    def test_ssl(self, connecteur, monkeypatch):
        """Le mode SSL doit basculer sur le port 465."""
        monkeypatch.setenv(SMTPEmailConnector.SECURITY_VARIABLE, "ssl")
        assert connecteur.port() == 465

    def test_sans_chiffrement(self, connecteur, monkeypatch):
        """Le mode `none` doit basculer sur le port 25."""
        monkeypatch.setenv(SMTPEmailConnector.SECURITY_VARIABLE, "none")
        assert connecteur.port() == 25

    def test_mode_inconnu_retombe_sur_starttls(self, connecteur, monkeypatch):
        """Une valeur inconnue ne doit jamais désactiver le chiffrement."""
        monkeypatch.setenv(SMTPEmailConnector.SECURITY_VARIABLE, "aucun-chiffrement-stp")
        assert connecteur.security_mode() == "starttls"

    def test_port_explicite_prime(self, connecteur, monkeypatch):
        """Un port configuré doit primer sur celui du mode de sécurité."""
        monkeypatch.setenv(SMTPEmailConnector.PORT_VARIABLE, "2525")
        assert connecteur.port() == 2525

    def test_port_invalide_retombe_sur_le_defaut(self, connecteur, monkeypatch):
        """Un port illisible ne doit pas faire échouer le connecteur."""
        monkeypatch.setenv(SMTPEmailConnector.PORT_VARIABLE, "pas-un-nombre")
        assert connecteur.port() == 587

    def test_expediteur_retombe_sur_l_utilisateur(self, connecteur, monkeypatch):
        """Sans expéditeur déclaré, l'utilisateur SMTP fait office d'adresse."""
        monkeypatch.setenv(SMTPEmailConnector.USER_VARIABLE, "contact@galsen.sn")
        assert connecteur.sender() == "contact@galsen.sn"

    def test_expediteur_explicite_prime(self, connecteur, monkeypatch):
        """L'expéditeur déclaré doit primer sur l'utilisateur SMTP."""
        monkeypatch.setenv(SMTPEmailConnector.USER_VARIABLE, "technique@galsen.sn")
        monkeypatch.setenv(SMTPEmailConnector.SENDER_VARIABLE, "bonjour@galsen.sn")
        assert connecteur.sender() == "bonjour@galsen.sn"


class TestVerification:
    """Vérifie le comportement de `check()` face au serveur."""

    def test_serveur_joignable_sans_authentification(self, connecteur, configure):
        """Un serveur qui répond sans identifiants doit être déclaré prêt."""
        serveur = _serveur_simule()
        with patch("smtplib.SMTP", return_value=serveur):
            resultat = connecteur.check()
        assert resultat.status is ConnectorStatus.READY
        assert "sans authentification" in resultat.detail
        serveur.login.assert_not_called()

    def test_starttls_puis_ehlo(self, connecteur, configure):
        """En mode STARTTLS, le protocole exige de resaluer le serveur après le chiffrement."""
        serveur = _serveur_simule()
        with patch("smtplib.SMTP", return_value=serveur):
            connecteur.check()
        serveur.starttls.assert_called_once()
        serveur.ehlo.assert_called_once()

    def test_authentification_reussie(self, connecteur, configure):
        """Avec des identifiants, le connecteur doit s'authentifier."""
        configure.setenv(SMTPEmailConnector.USER_VARIABLE, "contact@galsen.sn")
        configure.setenv(SMTPEmailConnector.PASSWORD_VARIABLE, "secret-tres-confidentiel")
        serveur = _serveur_simule()
        with patch("smtplib.SMTP", return_value=serveur):
            resultat = connecteur.check()
        serveur.login.assert_called_once_with("contact@galsen.sn", "secret-tres-confidentiel")
        assert resultat.status is ConnectorStatus.READY
        assert "authentification acceptée" in resultat.detail

    def test_aucun_email_n_est_envoye(self, connecteur, configure):
        """Vérifier ne doit rien coûter au destinataire : aucun message émis."""
        serveur = _serveur_simule()
        with patch("smtplib.SMTP", return_value=serveur):
            connecteur.check()
        serveur.send_message.assert_not_called()
        serveur.sendmail.assert_not_called()

    def test_mode_ssl_utilise_smtp_ssl(self, connecteur, configure):
        """Le mode SSL doit ouvrir une connexion chiffrée d'emblée, sans STARTTLS."""
        configure.setenv(SMTPEmailConnector.SECURITY_VARIABLE, "ssl")
        serveur = _serveur_simule()
        with patch("smtplib.SMTP_SSL", return_value=serveur) as smtp_ssl:
            connecteur.check()
        smtp_ssl.assert_called_once()
        serveur.starttls.assert_not_called()

    def test_le_secret_n_apparait_pas_dans_le_resultat(self, connecteur, configure):
        """Aucun identifiant ne doit fuir dans le détail retourné."""
        configure.setenv(SMTPEmailConnector.USER_VARIABLE, "contact@galsen.sn")
        configure.setenv(SMTPEmailConnector.PASSWORD_VARIABLE, "secret-tres-confidentiel")
        serveur = _serveur_simule()
        with patch("smtplib.SMTP", return_value=serveur):
            resultat = connecteur.check()
        assert "secret-tres-confidentiel" not in str(resultat.to_dict())

    def test_latence_mesuree(self, connecteur, configure):
        """La vérification doit rapporter sa durée."""
        with patch("smtplib.SMTP", return_value=_serveur_simule()):
            assert connecteur.check().latency_ms >= 0


class TestEchecs:
    """Vérifie que chaque échec devient un statut distinct, jamais une exception."""

    def test_identifiants_refuses(self, connecteur, configure):
        """Des identifiants refusés doivent donner UNAUTHORIZED, pas UNREACHABLE."""
        configure.setenv(SMTPEmailConnector.USER_VARIABLE, "contact@galsen.sn")
        configure.setenv(SMTPEmailConnector.PASSWORD_VARIABLE, "mauvais")
        serveur = _serveur_simule()
        serveur.login.side_effect = smtplib.SMTPAuthenticationError(535, b"refuse")
        with patch("smtplib.SMTP", return_value=serveur):
            resultat = connecteur.check()
        assert resultat.status is ConnectorStatus.UNAUTHORIZED
        assert "535" in resultat.detail

    def test_serveur_injoignable(self, connecteur, configure):
        """Une connexion refusée doit donner UNREACHABLE."""
        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("connexion refusée")):
            resultat = connecteur.check()
        assert resultat.status is ConnectorStatus.UNREACHABLE
        assert "smtp.exemple.sn:587" in resultat.detail

    def test_delai_depasse(self, connecteur, configure):
        """Un serveur muet doit donner UNREACHABLE en citant le délai."""
        with patch("smtplib.SMTP", side_effect=socket.timeout()):
            resultat = connecteur.check()
        assert resultat.status is ConnectorStatus.UNREACHABLE
        assert "2s" in resultat.detail

    def test_nom_de_domaine_introuvable(self, connecteur, configure):
        """Un DNS qui ne résout pas doit être signalé, pas propagé."""
        with patch("smtplib.SMTP", side_effect=socket.gaierror("nom inconnu")):
            resultat = connecteur.check()
        assert resultat.status is ConnectorStatus.UNREACHABLE

    def test_erreur_smtp_generique(self, connecteur, configure):
        """Toute erreur du protocole doit devenir un statut lisible."""
        with patch("smtplib.SMTP", side_effect=smtplib.SMTPServerDisconnected("coupé")):
            resultat = connecteur.check()
        assert resultat.status is ConnectorStatus.UNREACHABLE

    def test_check_ne_leve_jamais(self, connecteur, configure):
        """Quelle que soit la panne, la vérification retourne un résultat."""
        for panne in (
            ConnectionRefusedError(),
            socket.timeout(),
            smtplib.SMTPException("inattendu"),
            OSError("erreur TLS"),
        ):
            with patch("smtplib.SMTP", side_effect=panne):
                assert connecteur.check().is_ready is False


class TestDescription:
    """Vérifie la documentation portée par le connecteur."""

    def test_variables_nommees_sans_valeur(self, connecteur, configure):
        """La description nomme les variables, jamais leur contenu (ADR-004)."""
        configure.setenv(SMTPEmailConnector.PASSWORD_VARIABLE, "secret-tres-confidentiel")
        description = connecteur.describe().to_dict()
        assert SMTPEmailConnector.HOST_VARIABLE in description["environment_variables"]
        assert SMTPEmailConnector.PASSWORD_VARIABLE in description["environment_variables"]
        assert "secret-tres-confidentiel" not in str(description)

    def test_le_secret_n_est_pas_conserve_en_attribut(self, connecteur, configure):
        """Le connecteur relit l'environnement : rien ne subsiste dans son état."""
        configure.setenv(SMTPEmailConnector.PASSWORD_VARIABLE, "secret-tres-confidentiel")

        # L'expression `connecteur.check.__self__` occupait cette ligne sans
        # rien vérifier : elle était évaluée puis jetée. L'assertion vérifiée
        # est celle qui suit.
        assert "secret-tres-confidentiel" not in str(vars(connecteur))

    def test_operations_annoncees(self, connecteur):
        """La description doit annoncer ce que le connecteur sait faire."""
        assert set(connecteur.describe().operations) == {"check", "send"}


class TestIntegrationAuRegistre:
    """Vérifie que le connecteur se comporte comme n'importe quel autre."""

    def test_enregistrable_et_verifiable(self, configure):
        """Le registre doit pouvoir l'inventorier et le vérifier."""
        from src.connectors import ConnectorRegistry

        registre = ConnectorRegistry()
        registre.register(SMTPEmailConnector(timeout=2))
        with patch("smtplib.SMTP", return_value=_serveur_simule()):
            rapport = registre.check_all()
        assert rapport["total"] == 1
        assert rapport["ready"] == 1
        assert rapport["connectors"][0]["connector_id"] == "email_smtp"

    def test_non_configure_dans_le_rapport(self):
        """Sans configuration, le rapport doit le signaler sans appel réseau."""
        from src.connectors import ConnectorRegistry

        registre = ConnectorRegistry()
        registre.register(SMTPEmailConnector(timeout=2))
        with patch("smtplib.SMTP") as smtp:
            rapport = registre.check_all()
        smtp.assert_not_called()
        assert rapport["by_status"] == {"not_configured": 1}
