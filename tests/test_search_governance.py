"""
Tests de la gouvernance et de la qualité de la recherche (VOLET 14, ch. 08 et 09).

Le rapport dit sur quoi la plateforme cherche, qui en répond, si l'index est
intègre — et ce qu'il ne sait pas mesurer, plutôt que de produire un chiffre de
pertinence qu'aucun jugement de référence ne soutient.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.services.search.governance import (  # noqa: E402
    OWNERS_ENV, UNAVAILABLE_METRICS, configured_owners, governance_report,
)
from src.services.search.manager import SearchManagerImpl  # noqa: E402
from src.services.search.providers import KnowledgeSearchProvider  # noqa: E402
from src.services.search.types import SearchSource  # noqa: E402


@pytest.fixture
def service():
    """Service de recherche avec la seule source réellement branchée."""
    moteur = KnowledgeManagerImpl()
    gestionnaire = SearchManagerImpl()
    gestionnaire.register_provider(KnowledgeSearchProvider(moteur))
    yield gestionnaire
    moteur.cleanup()


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


def test_responsables_lus_dans_l_environnement(monkeypatch):
    """La déclaration est lue source par source ; l'illisible est ignoré, pas deviné."""
    monkeypatch.setenv(OWNERS_ENV, "knowledge:aissatou, inconnue:fatou, memory:, vision:awa")
    assert configured_owners() == {
        SearchSource.KNOWLEDGE: "aissatou",
        SearchSource.VISION: "awa",
    }


def test_le_rapport_distingue_declare_et_branche(monkeypatch, service):
    """Une source déclarée sans fournisseur ne doit pas passer pour disponible."""
    monkeypatch.delenv(OWNERS_ENV, raising=False)
    rapport = governance_report(service)

    assert rapport["sources"]["knowledge"]["wired"] is True
    assert rapport["sources"]["memory"]["wired"] is False
    assert rapport["wired_count"] == 1
    assert rapport["declared_count"] == 4


def test_seules_les_sources_branchees_reclament_un_responsable(monkeypatch, service):
    """Réclamer un responsable pour une source inexistante serait du bruit."""
    monkeypatch.delenv(OWNERS_ENV, raising=False)
    assert governance_report(service)["unowned_wired_sources"] == ["knowledge"]

    monkeypatch.setenv(OWNERS_ENV, "knowledge:aissatou")
    rapport = governance_report(service)
    assert rapport["unowned_wired_sources"] == []
    assert rapport["sources"]["knowledge"]["owner"] == "aissatou"
    # Une source non branchée peut avoir un responsable déclaré sans être réclamée.
    assert rapport["sources"]["memory"]["owner"] is None


def test_la_pertinence_est_declaree_non_mesurable(service):
    """Précision, rappel et satisfaction ne portent aucun chiffre inventé."""
    rapport = governance_report(service)
    assert set(rapport["unavailable_metrics"]) == set(UNAVAILABLE_METRICS)
    assert set(rapport["unavailable_metrics"]) == {"precision", "recall", "user_satisfaction"}
    for raison in rapport["unavailable_metrics"].values():
        assert raison.strip()
    # Aucune de ces clés ne doit exister ailleurs avec une valeur.
    assert "precision" not in rapport and "recall" not in rapport


def test_le_rapport_porte_l_integrite_et_les_compteurs(service):
    """Index et métriques sont inclus quand ils sont fournis, absents sinon."""
    moteur = KnowledgeManagerImpl()
    try:
        rapport = governance_report(service, indexer=moteur._indexer,
                                    metrics={"search": {"queries": 3, "empty": 1}})
        assert rapport["index"]["consistent"] is True
        assert rapport["queries"]["queries"] == 3
    finally:
        moteur.cleanup()

    sans = governance_report(service)
    assert "index" not in sans and "queries" not in sans


def test_la_route_est_reservee_a_la_supervision(cles):
    """`/search/status` décrit l'exploitation : un rôle en lecture seule n'y accède pas."""
    with TestClient(app) as client:
        admin = client.get("/search/status", headers={"X-API-Key": cles["admin"]})
        lecture = client.get("/search/status", headers={"X-API-Key": cles["readonly"]})
        sans_cle = client.get("/search/status")

    assert admin.status_code == 200
    assert "sources" in admin.json() and "unavailable_metrics" in admin.json()
    assert lecture.status_code == 403
    assert sans_cle.status_code == 401
