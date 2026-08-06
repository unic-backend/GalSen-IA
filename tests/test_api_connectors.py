"""
Tests des endpoints de connecteurs externes (phase 3.5, ADR-007).

Deux distinctions comptent ici et sont vérifiées comme telles :

- **décrire n'est pas vérifier** : `/connectors` répond depuis la configuration
  seule, sans le moindre appel sortant, pour qu'un déploiement s'audite hors
  ligne ; `/connectors/status` contacte les services distants et demande donc
  une permission séparée ;
- un connecteur **non configuré reste visible** : le masquer priverait un
  opérateur de la liste de ce que l'installation saurait joindre une fois branchée.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.connectors import reset_shared_connector_registry  # noqa: E402


@pytest.fixture(autouse=True)
def registre_neuf():
    """Repart d'un registre vide : le registre est partagé par tout le processus."""
    reset_shared_connector_registry()
    yield
    reset_shared_connector_registry()


@pytest.fixture
def cle_admin(monkeypatch):
    """Clé administrateur, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin,cle-lecture:readonly")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield "cle-admin"
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


class TestInventaire:
    """Vérifie `/connectors`, qui ne doit contacter personne."""

    def test_connecteurs_livres_enregistres_au_demarrage(self, cle_admin):
        """Le démarrage doit inscrire les connecteurs livrés avec la plateforme."""
        with TestClient(app) as client:
            reponse = client.get("/connectors", headers={"X-API-Key": cle_admin})
        assert reponse.status_code == 200
        identifiants = {c["connector_id"] for c in reponse.json()["connectors"]}
        assert {"email_smtp", "storage_local_disk"} <= identifiants

    def test_categories_annoncees(self, cle_admin):
        """L'inventaire doit dire quelles catégories sont couvertes."""
        with TestClient(app) as client:
            corps = client.get("/connectors", headers={"X-API-Key": cle_admin}).json()
        assert set(corps["kinds"]) >= {"email", "storage"}
        assert corps["total"] >= 2

    def test_connecteur_non_configure_reste_visible(self, cle_admin, monkeypatch):
        """Sans configuration, le connecteur doit figurer à l'inventaire."""
        monkeypatch.delenv("GALSEN_SMTP_HOST", raising=False)
        with TestClient(app) as client:
            corps = client.get("/connectors", headers={"X-API-Key": cle_admin}).json()
        assert any(c["connector_id"] == "email_smtp" for c in corps["connectors"])

    def test_aucune_valeur_de_secret_exposee(self, cle_admin, monkeypatch):
        """L'inventaire nomme les variables, jamais leur contenu (ADR-004)."""
        monkeypatch.setenv("GALSEN_SMTP_PASSWORD", "secret-tres-confidentiel")
        with TestClient(app) as client:
            reponse = client.get("/connectors", headers={"X-API-Key": cle_admin})
        assert "GALSEN_SMTP_PASSWORD" in reponse.text
        assert "secret-tres-confidentiel" not in reponse.text


class TestDescriptionUnitaire:
    """Vérifie `/connectors/{id}`."""

    def test_description_avec_etat_de_configuration(self, cle_admin, monkeypatch):
        """La description doit dire si le connecteur est configuré."""
        monkeypatch.delenv("GALSEN_SMTP_HOST", raising=False)
        with TestClient(app) as client:
            corps = client.get("/connectors/email_smtp", headers={"X-API-Key": cle_admin}).json()
        assert corps["connector_id"] == "email_smtp"
        assert corps["configured"] is False

    def test_configure_apres_renseignement(self, cle_admin, monkeypatch):
        """Une fois l'hôte renseigné, la description doit le refléter."""
        monkeypatch.setenv("GALSEN_SMTP_HOST", "smtp.exemple.sn")
        with TestClient(app) as client:
            corps = client.get("/connectors/email_smtp", headers={"X-API-Key": cle_admin}).json()
        assert corps["configured"] is True

    def test_connecteur_inconnu(self, cle_admin):
        """Un identifiant inconnu doit répondre 404, pas une description vide."""
        with TestClient(app) as client:
            reponse = client.get("/connectors/inexistant", headers={"X-API-Key": cle_admin})
        assert reponse.status_code == 404


class TestVerification:
    """Vérifie `/connectors/status` et `/connectors/{id}/check`."""

    def test_rapport_agrege(self, cle_admin, monkeypatch):
        """Le rapport doit compter les connecteurs et leurs statuts."""
        monkeypatch.delenv("GALSEN_SMTP_HOST", raising=False)
        monkeypatch.delenv("GALSEN_FILE_STORAGE_DIR", raising=False)
        with TestClient(app) as client:
            corps = client.get("/connectors/status", headers={"X-API-Key": cle_admin}).json()
        assert corps["total"] >= 2
        assert corps["by_status"]["not_configured"] >= 2

    def test_verification_unitaire(self, cle_admin, tmp_path, monkeypatch):
        """Un connecteur configuré doit être vérifiable individuellement."""
        monkeypatch.setenv("GALSEN_FILE_STORAGE_DIR", str(tmp_path / "objets"))
        with TestClient(app) as client:
            corps = client.get(
                "/connectors/storage_local_disk/check", headers={"X-API-Key": cle_admin}
            ).json()
        assert corps["status"] == "ready"
        assert corps["connector_id"] == "storage_local_disk"

    def test_verification_d_un_inconnu(self, cle_admin):
        """Vérifier un connecteur inconnu doit répondre 404."""
        with TestClient(app) as client:
            reponse = client.get(
                "/connectors/inexistant/check", headers={"X-API-Key": cle_admin}
            )
        assert reponse.status_code == 404


class TestPermissions:
    """Vérifie que décrire et vérifier ne demandent pas le même droit."""

    def test_lecture_seule_peut_decrire(self, cle_admin):
        """Un rôle en lecture seule doit pouvoir consulter l'inventaire."""
        with TestClient(app) as client:
            reponse = client.get("/connectors", headers={"X-API-Key": "cle-lecture"})
        assert reponse.status_code == 200

    def test_lecture_seule_ne_peut_pas_verifier(self, cle_admin):
        """Déclencher des appels sortants demande une permission distincte."""
        with TestClient(app) as client:
            reponse = client.get("/connectors/status", headers={"X-API-Key": "cle-lecture"})
        assert reponse.status_code == 403
        assert "connector:check" in reponse.json()["detail"]

    def test_sans_cle_refuse(self, cle_admin):
        """Sans clé API, l'inventaire doit être refusé."""
        with TestClient(app) as client:
            assert client.get("/connectors").status_code == 401
