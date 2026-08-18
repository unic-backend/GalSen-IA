"""
Les connecteurs Google branchés au démarrage (phase 45.2).

Une capacité qui fonctionne et que personne ne peut atteindre est le défaut que
ce dépôt a déjà trouvé plusieurs fois — les magasins cloud du VOLET 24,
l'orchestrateur du VOLET 26. Les trois connecteurs existaient et passaient leurs
tests ; aucune route ne les voyait.

Le point d'intégration qui compte est **le partage du magasin de jetons**. Un
consentement donné par `/oauth/google/authorize` et des connecteurs qui gardent
leurs jetons ailleurs, ce sont deux moitiés qui fonctionnent chacune et un
ensemble qui ne fonctionne pas : la personne a consenti, l'interface le dit, et
la lecture répond « jamais accordé ». Ce fichier vérifie la jonction, pas les
deux moitiés.
"""

import os
import sys

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.connectors import (  # noqa: E402
    get_shared_connector_registry,
    reset_shared_connector_registry,
)
from src.connectors.contract import conformance  # noqa: E402
from src.connectors.lifecycle import AuthorizationState  # noqa: E402
from src.connectors.oauth import get_provider  # noqa: E402
from src.storage import encryption  # noqa: E402

CONNECTEURS_GOOGLE = ("google_gmail", "google_drive", "google_calendar")
ACCES = "ya29.a0AfB-JETON-SECRET"


@pytest.fixture(autouse=True)
def registre_neuf():
    """Le registre de connecteurs est partagé par le processus."""
    reset_shared_connector_registry()
    yield
    reset_shared_connector_registry()


@pytest.fixture
def cle(monkeypatch):
    """Une clé nommée, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin:fatou")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield "cle-admin"
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def sans_identifiants(monkeypatch):
    """L'état réel de cet environnement."""
    fournisseur = get_provider("google")
    for variable in (
        fournisseur.client_id_variable, fournisseur.client_secret_variable,
        fournisseur.redirect_uri_variable,
    ):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(server_module, "_oauth_sessions", {})


@pytest.fixture
def avec_identifiants(monkeypatch):
    """Chiffrement et identifiants **factices**, et des sessions neuves."""
    monkeypatch.setenv(encryption.KEY_VARIABLE, Fernet.generate_key().decode("ascii"))
    fournisseur = get_provider("google")
    monkeypatch.setenv(fournisseur.client_id_variable, "id-de-test")
    monkeypatch.setenv(fournisseur.client_secret_variable, "secret-de-test")
    monkeypatch.setenv(fournisseur.redirect_uri_variable, "https://exemple.test/retour")
    monkeypatch.setattr(server_module, "_oauth_sessions", {})
    return fournisseur


# ----------------------------------------------------------------------
# 1. Ils sont visibles, configurés ou non
# ----------------------------------------------------------------------

def test_les_trois_connecteurs_sont_inscrits_au_demarrage(sans_identifiants):
    """
    Une capacité que personne ne peut atteindre est le défaut que ce dépôt a
    déjà trouvé plusieurs fois.
    """
    with TestClient(app):
        inscrits = {c.connector_id for c in get_shared_connector_registry().list_connectors()}

    for identifiant in CONNECTEURS_GOOGLE:
        assert identifiant in inscrits


def test_ils_restent_visibles_sans_identifiants(cle, sans_identifiants):
    """
    Sans cela, un opérateur ne peut pas savoir ce que l'installation saurait
    joindre une fois branchée.
    """
    with TestClient(app) as client:
        reponse = client.get("/connectors", headers={"X-API-Key": cle})

    corps = reponse.json()
    identifiants = {c["connector_id"] for c in corps["connectors"]}
    assert set(CONNECTEURS_GOOGLE) <= identifiants


def test_leur_etat_publie_est_non_configure(cle, sans_identifiants):
    """`IMPLEMENTED` + `NOT_CONFIGURED`, nommant les variables manquantes."""
    with TestClient(app) as client:
        reponse = client.get(
            "/connectors/google_gmail/contract", headers={"X-API-Key": cle}
        )

    corps = reponse.json()
    assert corps["conformant"] is True
    assert corps["contract"]["per_subject"] is True
    assert corps["lifecycle"]["state"] == "not_configured"


def test_ils_sont_conformes_une_fois_inscrits(sans_identifiants):
    """Le registre les a acceptés, donc contrat et privilèges sont vérifiés."""
    with TestClient(app):
        registre = get_shared_connector_registry()
        for identifiant in CONNECTEURS_GOOGLE:
            assert conformance(registre.get(identifiant))["conformant"] is True


def test_un_double_demarrage_ne_double_pas_les_connecteurs(sans_identifiants):
    """Le cycle de vie est rejoué en test comme au rechargement."""
    with TestClient(app):
        pass
    with TestClient(app):
        registre = get_shared_connector_registry()

    identifiants = [c.connector_id for c in registre.list_connectors()]
    assert len(identifiants) == len(set(identifiants))


def test_leur_securite_est_publiee_avec_le_contrat(cle, sans_identifiants):
    """Ce qu'une personne doit lire avant de consentir voyage avec eux."""
    with TestClient(app) as client:
        reponse = client.get(
            "/connectors/google_drive/contract", headers={"X-API-Key": cle}
        )

    securite = reponse.json()["safety"]
    assert securite["destructive"] == []
    assert [d["privilege"] for d in securite["requested"]] == ["read"]


# ----------------------------------------------------------------------
# 2. La jonction : un consentement, trois connecteurs
# ----------------------------------------------------------------------

def test_un_consentement_par_l_api_est_vu_par_les_connecteurs(cle, avec_identifiants):
    """
    Le test qui justifie cette phase. Deux moitiés qui fonctionnent chacune et
    un ensemble qui ne fonctionne pas, c'est ce qui arrive si le magasin de
    jetons n'est pas partagé.
    """
    with TestClient(app) as client:
        depart = client.post("/oauth/google/authorize", headers={"X-API-Key": cle})
        assert depart.status_code == 200

        session = server_module._oauth_sessions["google"]
        session.complete(depart.json()["state"], "code-recu", {
            "access_token": ACCES, "refresh_token": "1//R", "expires_in": 3599,
            "scope": " ".join(session.provider.allowed_scopes),
        })

        registre = get_shared_connector_registry()
        for identifiant in CONNECTEURS_GOOGLE:
            connecteur = registre.get(identifiant)
            assert connecteur.authorization_state("fatou") is AuthorizationState.AUTHORIZED, identifiant


def test_le_retrait_par_l_api_ferme_les_trois(cle, avec_identifiants):
    """La symétrie : reprendre son accès le reprend partout."""
    with TestClient(app) as client:
        depart = client.post("/oauth/google/authorize", headers={"X-API-Key": cle})
        session = server_module._oauth_sessions["google"]
        session.complete(depart.json()["state"], "code", {
            "access_token": ACCES, "expires_in": 3599,
            "scope": " ".join(session.provider.allowed_scopes),
        })

        retrait = client.delete(
            "/oauth/google/authorization", headers={"X-API-Key": cle}
        )
        assert retrait.json()["forgotten_locally"] is True

        registre = get_shared_connector_registry()
        for identifiant in CONNECTEURS_GOOGLE:
            connecteur = registre.get(identifiant)
            assert connecteur.authorization_state("fatou") is AuthorizationState.NOT_AUTHORIZED


def test_l_etat_d_une_personne_n_est_pas_celui_d_une_autre(cle, avec_identifiants):
    """L'isolation par sujet tient jusque dans le branchement."""
    with TestClient(app) as client:
        depart = client.post("/oauth/google/authorize", headers={"X-API-Key": cle})
        session = server_module._oauth_sessions["google"]
        session.complete(depart.json()["state"], "code", {
            "access_token": ACCES, "expires_in": 3599,
            "scope": " ".join(session.provider.allowed_scopes),
        })

        connecteur = get_shared_connector_registry().get("google_gmail")
        assert connecteur.authorization_state("fatou").usable is True
        assert connecteur.authorization_state("moussa") is AuthorizationState.NOT_AUTHORIZED


def test_le_contrat_publie_l_etat_de_l_appelant(cle, avec_identifiants):
    """L'identité vient de la clé, pas d'un paramètre."""
    with TestClient(app) as client:
        depart = client.post("/oauth/google/authorize", headers={"X-API-Key": cle})
        session = server_module._oauth_sessions["google"]
        session.complete(depart.json()["state"], "code", {
            "access_token": ACCES, "expires_in": 3599,
            "scope": " ".join(session.provider.allowed_scopes),
        })

        reponse = client.get(
            "/connectors/google_calendar/contract", headers={"X-API-Key": cle}
        )

    corps = reponse.json()
    assert corps["lifecycle"]["subject"] == "fatou"
    assert corps["lifecycle"]["state"] == "authorized"


def test_aucune_reponse_ne_porte_de_jeton(cle, avec_identifiants):
    """Vérifié sur le texte brut, après un consentement réel."""
    with TestClient(app) as client:
        depart = client.post("/oauth/google/authorize", headers={"X-API-Key": cle})
        session = server_module._oauth_sessions["google"]
        session.complete(depart.json()["state"], "code", {
            "access_token": ACCES, "refresh_token": "1//R", "expires_in": 3599,
            "scope": " ".join(session.provider.allowed_scopes),
        })

        for route in (
            "/connectors",
            "/connectors/google_gmail/contract",
            "/oauth/providers",
        ):
            reponse = client.get(route, headers={"X-API-Key": cle})
            assert ACCES not in reponse.text, route
            assert "secret-de-test" not in reponse.text, route
