"""
Tests de la délivrance des communications (VOLET 12, chapitres 02 et 05).

L'étape 5 du flux du chapitre 02 est « delivered securely ». La plateforme
répondait « Email envoyé à 1 destinataire(s) », enregistrait le message avec le
statut `sent` et **ne contactait aucun serveur** : le transport par défaut
retournait un succès sans rien faire.

Deux choses sont vérifiées ici : que la non-délivrance est dite, et que le
message rédigé n'est pas perdu pour autant.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.services.email.manager import EmailManagerImpl  # noqa: E402
from src.services.email.transport import ConsoleTransport, NoopTransport  # noqa: E402


@pytest.fixture
def cle(monkeypatch):
    """Clé administrateur, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield "cle-admin"
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def test_sans_transport_l_envoi_est_refuse():
    """« Envoyé » ne doit jamais désigner un message que personne n'a reçu."""
    gestionnaire = EmailManagerImpl(transport=NoopTransport())
    resultat = gestionnaire.send_email(subject="Sujet", body="Corps",
                                       sender="a@b.sn", recipients=["c@d.sn"])

    assert resultat.success is False
    assert "aucun transport" in resultat.message.lower()
    assert resultat.details["delivered"] is False


def test_le_message_redige_est_conserve():
    """L'infrastructure manque ; ce que l'utilisateur a écrit ne doit pas disparaître."""
    gestionnaire = EmailManagerImpl(transport=NoopTransport())
    resultat = gestionnaire.send_email(subject="À conserver", body="Corps",
                                       sender="a@b.sn", recipients=["c@d.sn"])

    stocke = gestionnaire.get_email(resultat.email_id)
    assert stocke is not None
    assert stocke.subject == "À conserver"
    assert stocke.status.value == "failed", "le statut doit dire ce qui s'est passé"


def test_le_message_d_erreur_dit_quoi_faire():
    """Un refus sans remède oblige l'opérateur à lire le code."""
    _, message = NoopTransport().send("a@b.sn", ["c@d.sn"], "Sujet", "Corps")
    assert "GALSEN_SMTP_HOST" in message


def test_un_transport_qui_delivre_rend_bien_un_succes():
    """Le correctif ne doit pas rendre tout envoi impossible."""
    gestionnaire = EmailManagerImpl(transport=ConsoleTransport())
    resultat = gestionnaire.send_email(subject="Sujet", body="Corps",
                                       sender="a@b.sn", recipients=["c@d.sn"])

    assert resultat.success is True
    assert gestionnaire.get_email(resultat.email_id).status.value == "sent"


def test_les_statistiques_distinguent_envoye_et_non_delivre():
    """Un compteur d'envois qui inclut les non-délivrés ne mesure rien."""
    gestionnaire = EmailManagerImpl(transport=NoopTransport())
    gestionnaire.send_email(subject="A", body="a", sender="a@b.sn", recipients=["r@b.sn"])
    gestionnaire.send_email(subject="B", body="b", sender="a@b.sn", recipients=["r@b.sn"])

    statistiques = gestionnaire.stats()
    assert statistiques["total"] == 2
    assert statistiques["by_status"].get("sent", 0) == 0
    assert statistiques["by_status"]["failed"] == 2


def test_la_route_repond_503_quand_le_deploiement_n_est_pas_configure(cle):
    """503 et non 400 : l'appelant n'a commis aucune erreur."""
    with TestClient(app) as client:
        reponse = client.post("/email/send", headers={"X-API-Key": cle}, json={
            "subject": "Sujet", "body": "Corps",
            "sender": "a@b.sn", "recipients": ["c@d.sn"],
        })

    assert reponse.status_code == 503
    assert "transport" in reponse.json()["detail"].lower()


def test_la_route_repond_400_quand_la_requete_est_fautive(cle):
    """La distinction doit tenir dans les deux sens."""
    with TestClient(app) as client:
        reponse = client.post("/email/send", headers={"X-API-Key": cle}, json={
            "subject": "", "body": "Corps",
            "sender": "a@b.sn", "recipients": ["c@d.sn"],
        })

    assert reponse.status_code == 400
