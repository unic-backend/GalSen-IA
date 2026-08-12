"""
Tests de la rotation et de la révocation des clés API (VOLET 02 ch. 08, phase 8.4).

Avant cette phase, une clé compromise restait valide jusqu'au redémarrage du
serveur. Deux propriétés sont vérifiées ici :

- la révocation **prend effet immédiatement**, sur la requête suivante ;
- elle **ne prétend pas être durable** : la source des clés reste
  l'environnement du déploiement (ADR-004), et la réponse le dit à l'opérateur
  pour qu'il ne croie pas l'incident clos.

Aucune clé en clair ne doit apparaître dans une réponse : on ne révoque que par
empreinte.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.api.rate_limiter import set_valid_api_key_digests  # noqa: E402
from src.api.rbac import hash_api_key, key_fingerprint  # noqa: E402


@pytest.fixture
def api(monkeypatch):
    """Configure deux clés et rend son état d'origine à l'application."""
    ancien_mapping = dict(server_module.rbac_manager._key_role_map)
    anciennes_revocations = set(server_module.rbac_manager._revoked_digests)

    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin,cle-usager:user")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.active_key_digests())

    yield server_module.rbac_manager

    server_module.rbac_manager._key_role_map = ancien_mapping
    server_module.rbac_manager._revoked_digests = anciennes_revocations
    set_valid_api_key_digests(server_module.rbac_manager.active_key_digests())


def _empreinte(cle: str) -> str:
    """Retourne l'empreinte publique d'une clé."""
    return key_fingerprint(hash_api_key(cle))


class TestInventaire:
    """Vérifie `/auth/keys`."""

    def test_inventaire_sans_aucune_cle_en_clair(self, api):
        """L'inventaire montre les empreintes et les rôles, jamais les clés."""
        with TestClient(app) as client:
            reponse = client.get("/auth/keys", headers={"X-API-Key": "cle-admin"})
        assert reponse.status_code == 200
        assert "cle-admin" not in reponse.text
        assert "cle-usager" not in reponse.text
        assert reponse.json()["total"] == 2

    def test_roles_visibles(self, api):
        """Un opérateur doit voir avec quels droits chaque clé entre."""
        with TestClient(app) as client:
            corps = client.get("/auth/keys", headers={"X-API-Key": "cle-admin"}).json()
        roles = {entree["fingerprint"]: entree["role"] for entree in corps["keys"]}
        assert roles[_empreinte("cle-admin")] == "admin"
        assert roles[_empreinte("cle-usager")] == "user"

    def test_reserve_aux_administrateurs(self, api):
        """Un usager ordinaire ne doit pas énumérer les clés."""
        with TestClient(app) as client:
            reponse = client.get("/auth/keys", headers={"X-API-Key": "cle-usager"})
        assert reponse.status_code == 403


class TestRevocation:
    """Vérifie que couper une clé prend effet tout de suite."""

    def test_effet_immediat(self, api):
        """La clé révoquée doit être refusée dès la requête suivante."""
        with TestClient(app) as client:
            entetes = {"X-API-Key": "cle-admin"}
            assert client.get("/auth/keys", headers=entetes).status_code == 200

            client.post(
                f"/auth/keys/{_empreinte('cle-usager')}/revoke", headers=entetes
            )
            assert client.get("/health", headers={"X-API-Key": "cle-usager"}).status_code == 200
            reponse = client.get("/connectors", headers={"X-API-Key": "cle-usager"})
        assert reponse.status_code == 401

    def test_les_autres_cles_restent_valides(self, api):
        """Révoquer une clé ne doit pas couper les autres."""
        with TestClient(app) as client:
            entetes = {"X-API-Key": "cle-admin"}
            client.post(f"/auth/keys/{_empreinte('cle-usager')}/revoke", headers=entetes)
            assert client.get("/auth/keys", headers=entetes).status_code == 200

    def test_la_reponse_avertit_de_la_non_persistance(self, api):
        """L'opérateur doit savoir que l'incident n'est pas clos."""
        with TestClient(app) as client:
            corps = client.post(
                f"/auth/keys/{_empreinte('cle-usager')}/revoke",
                headers={"X-API-Key": "cle-admin"},
            ).json()
        assert corps["persistent"] is False
        assert "GALSEN_API_KEYS" in corps["detail"]

    def test_empreinte_inconnue(self, api):
        """Une empreinte qui ne correspond à rien doit répondre 404."""
        with TestClient(app) as client:
            reponse = client.post(
                "/auth/keys/000000000000/revoke", headers={"X-API-Key": "cle-admin"}
            )
        assert reponse.status_code == 404

    def test_le_refus_ne_distingue_pas_revoquee_d_inconnue(self, api):
        """Confirmer qu'une clé a existé renseignerait un attaquant."""
        with TestClient(app) as client:
            client.post(
                f"/auth/keys/{_empreinte('cle-usager')}/revoke",
                headers={"X-API-Key": "cle-admin"},
            )
            revoquee = client.get("/connectors", headers={"X-API-Key": "cle-usager"})
            inventee = client.get("/connectors", headers={"X-API-Key": "jamais-existe"})
        assert revoquee.status_code == inventee.status_code == 401
        assert revoquee.json()["detail"] == inventee.json()["detail"]

    def test_revocation_visible_dans_l_inventaire(self, api):
        """L'inventaire doit refléter l'état de révocation."""
        with TestClient(app) as client:
            entetes = {"X-API-Key": "cle-admin"}
            client.post(f"/auth/keys/{_empreinte('cle-usager')}/revoke", headers=entetes)
            corps = client.get("/auth/keys", headers=entetes).json()
        assert corps["revoked"] == 1
        revoquees = [e["fingerprint"] for e in corps["keys"] if e["revoked"]]
        assert revoquees == [_empreinte("cle-usager")]


class TestRestauration:
    """Vérifie qu'une révocation posée par erreur se lève."""

    def test_restauration(self, api):
        """La clé restaurée doit redevenir utilisable."""
        with TestClient(app) as client:
            entetes = {"X-API-Key": "cle-admin"}
            empreinte = _empreinte("cle-usager")
            client.post(f"/auth/keys/{empreinte}/revoke", headers=entetes)
            reponse = client.post(f"/auth/keys/{empreinte}/restore", headers=entetes)
            assert reponse.json()["revoked"] is False
            assert client.get("/connectors", headers={"X-API-Key": "cle-usager"}).status_code == 200

    def test_restaurer_une_cle_non_revoquee(self, api):
        """Sans révocation en cours, la restauration doit répondre 404."""
        with TestClient(app) as client:
            reponse = client.post(
                f"/auth/keys/{_empreinte('cle-usager')}/restore",
                headers={"X-API-Key": "cle-admin"},
            )
        assert reponse.status_code == 404


class TestRotation:
    """Vérifie le rechargement, qui permet une rotation sans interruption."""

    def test_resume_du_rechargement(self, api, monkeypatch):
        """Le rechargement doit rapporter ce qui a changé, en empreintes."""
        with TestClient(app) as client:
            monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin,cle-neuve:user")
            corps = client.post(
                "/auth/keys/reload", headers={"X-API-Key": "cle-admin"}
            ).json()
        assert corps["before"] == 2
        assert corps["after"] == 2
        assert corps["added"] == [_empreinte("cle-neuve")]
        assert corps["removed"] == [_empreinte("cle-usager")]
        assert "cle-neuve" not in str(corps)

    def test_la_nouvelle_cle_fonctionne_et_l_ancienne_non(self, api, monkeypatch):
        """Une rotation doit ouvrir la nouvelle clé et fermer l'ancienne."""
        with TestClient(app) as client:
            monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin,cle-neuve:user")
            client.post("/auth/keys/reload", headers={"X-API-Key": "cle-admin"})

            assert client.get(
                "/connectors", headers={"X-API-Key": "cle-neuve"}
            ).status_code == 200
            assert client.get("/connectors", headers={"X-API-Key": "cle-usager"}).status_code == 401

    def test_une_revocation_devenue_sans_objet_est_oubliee(self, api, monkeypatch):
        """Une clé disparue de l'environnement ne doit pas rester en liste."""
        gestionnaire = api
        gestionnaire.revoke(_empreinte("cle-usager"))
        assert len(gestionnaire._revoked_digests) == 1

        monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin")
        gestionnaire.reload()
        assert gestionnaire._revoked_digests == set()


class TestLimiteurDeTaux:
    """Vérifie que le limiteur suit les révocations."""

    def test_une_cle_revoquee_perd_son_quota_authentifie(self, api):
        """Une clé coupée ne doit plus être traitée comme un client authentifié."""
        from src.api import rate_limiter

        gestionnaire = api
        gestionnaire.revoke(_empreinte("cle-usager"))
        set_valid_api_key_digests(gestionnaire.active_key_digests())

        assert hash_api_key("cle-usager") not in rate_limiter._valid_key_digests
        assert hash_api_key("cle-admin") in rate_limiter._valid_key_digests
