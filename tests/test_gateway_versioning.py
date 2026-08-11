"""
Versionnement et fin de vie des routes (VOLET 15, chapitres 04 et 08 — ADR-011).

Les deux chapitres demandent un contrôle de version et le retrait sûr des API
obsolètes. Il n'existait ni préfixe de version, ni moyen d'annoncer qu'une route
allait disparaître : le seul retrait possible était la suppression, que
l'appelant découvrait en 404, en production.
"""

import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GALSEN_API_KEYS", "test-key-0123456789abcdef")

from src.api import server, versioning  # noqa: E402
from src.api.rate_limiter import set_valid_api_key_digests  # noqa: E402
from src.version import __version__  # noqa: E402

CLE = "test-key-0123456789abcdef"


@pytest.fixture
def client(monkeypatch):
    """Client administrateur sur l'application réelle."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin")
    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    with TestClient(server.app) as instance:
        yield instance


@pytest.fixture
def route_depreciee():
    """Déprécie `/live` le temps d'un test, puis restaure le registre."""
    annonce = versioning.Deprecation(
        path="/live",
        since="0.1.0",
        reason="test",
        sunset=time.time() + 30 * 86400,
        replacement="/health",
    )
    versioning.DEPRECATIONS[annonce.path] = annonce
    yield annonce
    versioning.DEPRECATIONS.pop(annonce.path, None)


def test_le_registre_est_vide(client):
    """
    Aucune route n'est dépréciée aujourd'hui.

    Y inscrire un exemple pour montrer que le mécanisme marche fabriquerait un
    fait — `.claude/rules/verification.md`. Le mécanisme est prouvé par les
    tests qui suivent, pas par une fausse entrée.
    """
    assert versioning.DEPRECATIONS == {}
    assert client.get("/api/versions", headers={"X-API-Key": CLE}).json()["deprecated_count"] == 0


def test_la_route_dit_qu_il_n_y_a_pas_de_versionnage_d_url(client):
    """
    Un appelant qui suppose un `/v1` implicite suppose une stabilité que rien ne
    garantit. La réponse le dit au lieu de le laisser deviner.
    """
    corps = client.get("/api/versions", headers={"X-API-Key": CLE}).json()

    assert corps["version"] == __version__
    assert corps["url_versioning"] is None
    assert "Aucun préfixe" in corps["url_versioning_note"]


def test_une_route_saine_ne_porte_aucun_en_tete_de_fin_de_vie(client):
    """Annoncer une fin de vie qui n'existe pas ferait fuir des appelants."""
    entetes = {nom.lower() for nom in client.get("/live").headers}

    assert "deprecation" not in entetes
    assert "sunset" not in entetes


def test_une_route_depreciee_annonce_sa_fin_de_vie(client, route_depreciee):
    """Les trois en-têtes de la RFC 8594, sur une réponse normale."""
    reponse = client.get("/live")

    assert reponse.headers["Deprecation"] == "true"
    assert reponse.headers["Sunset"].endswith("GMT")
    assert reponse.headers["Link"] == '</health>; rel="successor-version"'


def test_depreciee_ne_veut_pas_dire_supprimee(client, route_depreciee):
    """
    Le préavis est un en-tête, pas une panne.

    Une dépréciation qui casserait la route serait une suppression déguisée, et
    l'appelant l'apprendrait exactement comme avant : en production.
    """
    reponse = client.get("/live")

    assert reponse.status_code == 200
    assert reponse.json()["status"] == "alive"


def test_l_annonce_couvre_aussi_les_reponses_d_erreur(client, route_depreciee):
    """
    C'est la raison d'être de l'intergiciel.

    Un appelant qui n'appelle une route qu'en erreur — parce que ses paramètres
    sont mauvais depuis des mois — est justement celui qu'il faut prévenir.
    """
    versioning.DEPRECATIONS["/metrics"] = versioning.Deprecation(
        path="/metrics", since="0.1.0", reason="test",
    )
    try:
        reponse = client.get("/metrics")  # sans clé : 401
        assert reponse.status_code == 401
        assert reponse.headers["Deprecation"] == "true"
    finally:
        versioning.DEPRECATIONS.pop("/metrics", None)


def test_sans_date_de_retrait_aucun_sunset_n_est_invente(client):
    """Une date inventée serait pire qu'absente : on la croirait."""
    versioning.DEPRECATIONS["/live"] = versioning.Deprecation(
        path="/live", since="0.1.0", reason="pas encore de date",
    )
    try:
        reponse = client.get("/live")
        assert reponse.headers["Deprecation"] == "true"
        assert "Sunset" not in reponse.headers
        assert "Link" not in reponse.headers
    finally:
        versioning.DEPRECATIONS.pop("/live", None)


def test_le_rapport_liste_l_annonce_complete(client, route_depreciee):
    """Ce que `/api/versions` sert doit suffire à planifier une migration."""
    corps = client.get("/api/versions", headers={"X-API-Key": CLE}).json()

    assert corps["deprecated_count"] == 1
    annonce = corps["deprecations"][0]
    assert annonce["path"] == "/live"
    assert annonce["replacement"] == "/health"
    assert annonce["sunset"].endswith("GMT")
