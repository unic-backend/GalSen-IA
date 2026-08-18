"""
Tests des routes de publication des métriques de connaissance (VOLET 05, ch. 10).

Le chapitre demande de publier les métriques de gouvernance et de qualité. Deux
choses sont vérifiées ici : que les routes répondent avec le contenu réel de la
base, et qu'un rôle sans permission de supervision ne les atteint pas.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.knowledge_engine.knowledge_governance import OWNERS_ENV  # noqa: E402
from src.knowledge_engine.types import (  # noqa: E402
    KnowledgeDomain, KnowledgeItem, KnowledgeStatus,
)


@pytest.fixture
def cles(monkeypatch):
    """Clés admin et lecture seule, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin,cle-lecture:readonly")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield {"admin": "cle-admin", "readonly": "cle-lecture"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def connaissance(monkeypatch):
    """Une connaissance légale approuvée, avec son propriétaire déclaré."""
    monkeypatch.setenv(OWNERS_ENV, "legal:aissatou")
    identifiant = server_module.knowledge_manager.add_knowledge(KnowledgeItem(
        content="Le code des marchés publics du Sénégal, édition en vigueur.",
        domain=KnowledgeDomain.LEGAL,
        status=KnowledgeStatus.APPROVED,
    ))
    yield identifiant
    server_module.knowledge_manager.delete_knowledge(identifiant)


def test_gouvernance_publie_les_proprietaires(cles, connaissance):
    """La route dit qui possède le domaine, depuis le contenu réel de la base."""
    with TestClient(app) as client:
        reponse = client.get("/knowledge/governance", headers={"X-API-Key": cles["admin"]})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["domains"]["legal"]["owner"] == "aissatou"
    assert corps["domains"]["legal"]["by_status"]["approved"] >= 1


def test_qualite_publie_les_metriques_et_les_absences(cles, connaissance):
    """La route publie les quatre métriques calculables et nomme les deux autres."""
    with TestClient(app) as client:
        reponse = client.get("/knowledge/quality", headers={"X-API-Key": cles["admin"]})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["items"] >= 1
    assert set(corps["unavailable"]) == {"accuracy_rate", "user_feedback"}
    assert "accuracy_rate" not in corps
    for cle in ("completeness", "freshness", "duplicates", "validation_coverage"):
        assert cle in corps


def test_les_langues_publient_ce_qui_n_est_pas_acquis(cles):
    """
    La route des langues dit ce que la plateforme **ne** sait **pas** faire
    (VOLET 36, ch. B).

    Elle est ouverte à la lecture seule, à l'inverse des deux autres : une
    limite connue doit pouvoir être lue par qui utilise la plateforme, pas
    seulement par qui l'administre.
    """
    with TestClient(app) as client:
        reponse = client.get("/knowledge/languages", headers={"X-API-Key": cles["readonly"]})

    assert reponse.status_code == 200
    corps = reponse.json()
    wolof = corps["support"]["wo"]["capabilities"]
    assert wolof["generation"]["support"] == "unknown"
    assert "C1" in wolof["generation"]["blocked_on"]
    assert "comprend le wolof" in corps["caveat"]


def test_le_jeu_de_reference_factuel_publie_son_vide(cles):
    """
    La route dit qu'aucune entrée n'est vérifiée (VOLET 36, ch. C).

    Publier un 0 est le contraire d'un aveu de faiblesse : c'est ce qui
    distingue une mesure absente d'une mesure réussie.
    """
    with TestClient(app) as client:
        reponse = client.get(
            "/knowledge/factual-benchmark", headers={"X-API-Key": cles["readonly"]}
        )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["verified"] == 0
    assert corps["scorable"] == 0
    assert corps["to_source"] > 0
    assert corps["source_types"], "Aucune entrée ne nomme l'institution qui trancherait"


@pytest.mark.parametrize("route", ["/knowledge/governance", "/knowledge/quality"])
def test_routes_reservees_a_la_supervision(cles, route):
    """Un rôle en lecture seule n'accède pas aux métriques de gouvernance."""
    with TestClient(app) as client:
        reponse = client.get(route, headers={"X-API-Key": cles["readonly"]})
    assert reponse.status_code == 403


@pytest.mark.parametrize("route", ["/knowledge/governance", "/knowledge/quality"])
def test_routes_exigent_une_cle(cles, route):
    """Sans clé, la route refuse au lieu de publier."""
    with TestClient(app) as client:
        assert client.get(route).status_code == 401
