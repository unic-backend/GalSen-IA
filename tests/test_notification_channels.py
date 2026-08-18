"""
Les canaux de livraison (phase 50.2).

Une notification allait dans le magasin de la plateforme et s'arrêtait là. C'est
un vrai canal — c'est celui que les six routes existantes lisent — mais c'est le
seul, et il demande que quelqu'un vienne regarder. Or les événements de la vague
III sont exactement ceux devant lesquels personne n'est assis.

Ce que ces tests gardent :

1. **Un canal sans identifiants ne prétend jamais avoir envoyé.** Il rapporte
   `NOT_CONFIGURED` et nomme ce qui manque. Croire que quelqu'un a été prévenu
   alors que rien n'est parti serait le pire résultat possible.
2. **Une destination partagée ne porte pas la notification de quelqu'un.** La
   même frontière que partout ailleurs (VOLET 40), appliquée là où le contenu
   quitte la machine.
3. **Aucune valeur de secret ne sort.** Les noms des variables attendues, jamais
   leur contenu.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.services.notification.channels import (  # noqa: E402
    ChannelRegistry,
    ChannelState,
    DeliveryChannel,
    load_channels,
)


@pytest.fixture
def registre():
    """Les canaux réellement déclarés dans le dépôt."""
    return ChannelRegistry()


@pytest.fixture
def cles(monkeypatch):
    """Une clé nommée."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield {"awa": "cle-awa"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def client():
    """Client HTTP sur l'application réelle."""
    with TestClient(app) as essai:
        yield essai


# ----------------------------------------------------------------------
# 1. Un canal non configuré le dit
# ----------------------------------------------------------------------

def test_les_canaux_externes_sont_non_configures_ici(registre):
    """
    Mesuré, pas supposé : cette installation n'a aucun identifiant de
    livraison externe.
    """
    rapport = registre.channels_report()

    assert rapport["available"] == ["in_app"]
    assert set(rapport["not_configured"]) == {"email", "webhook"}


def test_un_canal_non_configure_nomme_ce_qui_manque(registre):
    """Sinon « non configuré » ne dit pas quoi faire."""
    courriel = registre.get("email")

    assert courriel.state is ChannelState.NOT_CONFIGURED
    assert "GALSEN_SMTP_HOST" in courriel.missing


def test_un_canal_configure_devient_disponible(monkeypatch):
    """L'état est mesuré à l'instant où on le demande, pas figé au chargement."""
    canal = DeliveryChannel("email", "Courriel", requires=["GALSEN_SMTP_HOST"])
    assert canal.state is ChannelState.NOT_CONFIGURED

    monkeypatch.setenv("GALSEN_SMTP_HOST", "smtp.example.org")

    assert canal.state is ChannelState.AVAILABLE


def test_une_variable_vide_ne_compte_pas_comme_posee(monkeypatch):
    """Une chaîne d'espaces n'est pas une configuration."""
    monkeypatch.setenv("GALSEN_SMTP_HOST", "   ")
    canal = DeliveryChannel("email", "Courriel", requires=["GALSEN_SMTP_HOST"])

    assert canal.state is ChannelState.NOT_CONFIGURED


def test_aucune_valeur_de_secret_ne_figure_dans_le_rapport(monkeypatch, registre):
    """Les noms des variables attendues, jamais leur contenu."""
    monkeypatch.setenv("GALSEN_NOTIFICATION_WEBHOOK_URL", "https://exemple/secret-tres-prive")

    rapport = str(ChannelRegistry().channels_report())

    assert "GALSEN_NOTIFICATION_WEBHOOK_URL" in rapport
    assert "secret-tres-prive" not in rapport


def test_le_rapport_dit_qu_il_n_envoie_rien(registre):
    """Un envoi simulé ferait croire que quelqu'un a été prévenu."""
    ne_fait_pas = " ".join(registre.channels_report()["does_not"])

    assert "Envoyer réellement" in ne_fait_pas
    assert "ferait croire" in ne_fait_pas


# ----------------------------------------------------------------------
# 2. Une destination partagée ne porte pas le privé
# ----------------------------------------------------------------------

def test_un_canal_partage_refuse_la_notification_de_quelqu_un(monkeypatch):
    """
    Un salon d'équipe est lu par plus de monde que le destinataire. La même
    frontière que partout, appliquée là où le contenu quitte la machine.
    """
    monkeypatch.setenv("GALSEN_NOTIFICATION_WEBHOOK_URL", "https://exemple/hook")
    canal = ChannelRegistry().get("webhook")

    accepte, motif = canal.accepts(recipient="awa")

    assert canal.state is ChannelState.AVAILABLE
    assert accepte is False
    assert "partagé" in motif


def test_un_canal_partage_accepte_ce_qui_appartient_a_la_plateforme(monkeypatch):
    """Un incident sans propriétaire regarde l'exploitation."""
    monkeypatch.setenv("GALSEN_NOTIFICATION_WEBHOOK_URL", "https://exemple/hook")

    accepte, _ = ChannelRegistry().get("webhook").accepts(recipient=None)

    assert accepte is True


def test_le_refus_du_partage_prime_sur_la_configuration(registre):
    """
    Un canal partagé **et** non configuré refuse d'abord parce qu'il est
    partagé : le configurer ne le rendrait pas apte à porter du privé.
    """
    accepte, motif = registre.get("webhook").accepts(recipient="awa")

    assert accepte is False
    assert "partagé" in motif


def test_le_plan_de_livraison_distingue_les_deux_cas(registre):
    """Ce qui partirait pour une personne, et ce qui partirait pour la plateforme."""
    personnel = registre.delivery_plan("awa")
    plateforme = registre.delivery_plan(None)

    assert personnel["recipient_kind"] == "user"
    assert plateforme["recipient_kind"] == "platform"
    assert personnel["delivering"] == ["in_app"]


# ----------------------------------------------------------------------
# 3. La déclaration, et les routes
# ----------------------------------------------------------------------

def test_les_canaux_viennent_d_un_fichier_de_declaration():
    """Ajouter un canal ne doit pas demander de toucher au code."""
    canaux = {canal.channel_id for canal in load_channels()}

    assert {"in_app", "email", "webhook"} <= canaux


def test_un_fichier_absent_laisse_la_plateforme_sans_canal(tmp_path):
    """Sûr par défaut : rien ne sort plutôt qu'un canal supposé."""
    assert load_channels(tmp_path / "nexistepas.yaml") == []


def test_la_route_publie_l_etat_des_canaux(client, cles):
    """Un opérateur doit voir ce qui est branché sans lire le code."""
    rapport = client.get(
        "/notification/channels", headers={"X-API-Key": cles["awa"]}
    ).json()

    assert rapport["available"] == ["in_app"]
    assert "email" in rapport["not_configured"]


def test_la_route_de_plan_repond_pour_l_appelant(client, cles):
    """Le sujet vient de la clé, jamais du corps."""
    plan = client.get(
        "/notification/channels/plan", headers={"X-API-Key": cles["awa"]}
    ).json()

    assert plan["personal"]["recipient_kind"] == "user"
    assert plan["platform"]["recipient_kind"] == "platform"


def test_les_routes_de_canaux_exigent_une_cle(client):
    """Aucune n'est publique."""
    assert client.get("/notification/channels").status_code in (401, 403)
    assert client.get("/notification/channels/plan").status_code in (401, 403)
