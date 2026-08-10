"""
Tests des métriques de recherche (VOLET 14, ch. 02 étape 6, ch. 06 et ch. 09).

Le manuel réclame deux fois un module d'analytique et rien n'enregistrait la
moindre requête. Deux exigences pèsent sur ce qui a été ajouté : mesurer le
comportement de la recherche, et **ne jamais enregistrer ce qui est cherché**.
"""

import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.metrics import (  # noqa: E402
    RECHERCHE_TOTAL, RECHERCHE_VIDE, metrics_snapshot, record_search, reset_metrics,
)
from src.api.server import app  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.knowledge_engine.types import KnowledgeItem  # noqa: E402
from src.services.search.manager import SearchManagerImpl  # noqa: E402
from src.services.search.providers import KnowledgeSearchProvider  # noqa: E402


@pytest.fixture(autouse=True)
def compteurs_neufs():
    """Chaque test part de compteurs vides : ils sont partagés par le processus."""
    reset_metrics()
    yield
    reset_metrics()


@pytest.fixture
def cle(monkeypatch):
    """Clé opérateur, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-op:operator")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield "cle-op"
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def service_peuple(monkeypatch):
    """Service de recherche branché sur un moteur contenant un document."""
    moteur = KnowledgeManagerImpl()
    moteur.add_knowledge(KnowledgeItem(content="Le calendrier cultural du bassin arachidier."))
    gestionnaire = SearchManagerImpl()
    gestionnaire.register_provider(KnowledgeSearchProvider(moteur))
    monkeypatch.setattr(server_module, "search_manager", gestionnaire)
    yield gestionnaire
    moteur.cleanup()


def test_une_recherche_est_comptee():
    """Volume et latence sont enregistrés pour chaque source interrogée."""
    record_search(["knowledge"], results_count=3, duration_ms=12.5)
    instantane = metrics_snapshot()
    assert instantane["search"]["queries"] == 1
    assert instantane["search"]["empty"] == 0
    assert instantane["search"]["empty_rate"] == 0.0
    assert "search.latency.knowledge" in instantane["latency_ms"]


def test_le_taux_de_recherches_vides_est_calcule():
    """La seule métrique de qualité mesurable sans jury : n'avoir rien trouvé."""
    record_search(["knowledge"], results_count=0, duration_ms=1.0)
    record_search(["knowledge"], results_count=0, duration_ms=1.0)
    record_search(["knowledge"], results_count=5, duration_ms=1.0)
    recherche = metrics_snapshot()["search"]
    assert recherche["queries"] == 3
    assert recherche["empty"] == 2
    assert recherche["empty_rate"] == round(2 / 3, 4)


def test_aucune_recherche_ne_donne_pas_de_taux():
    """Sans recherche, le taux est None — pas 0.0, qui se lirait comme « tout va bien »."""
    assert metrics_snapshot()["search"]["empty_rate"] is None


def test_le_contenu_de_la_requete_n_est_jamais_enregistre(cle, service_peuple):
    """Une requête est ce que quelqu'un cherche : elle ne doit apparaître nulle part."""
    secret = "zzsecretrecherchezz"
    with TestClient(app) as client:
        client.post("/search", json={"query": secret}, headers={"X-API-Key": cle})
        reponse = client.get("/metrics", headers={"X-API-Key": cle})

    assert reponse.status_code == 200
    assert secret not in json.dumps(reponse.json())
    assert metrics_snapshot()["counters"][RECHERCHE_TOTAL] == 1
    # La requête n'a rien trouvé : elle compte comme vide, sans dire quoi.
    assert metrics_snapshot()["counters"][RECHERCHE_VIDE] == 1


def test_la_route_alimente_les_compteurs(cle, service_peuple):
    """Une recherche fructueuse par l'API est comptée et n'est pas vide."""
    with TestClient(app) as client:
        reponse = client.post("/search", json={"query": "calendrier cultural"},
                              headers={"X-API-Key": cle})
    assert reponse.status_code == 200 and reponse.json()["total"] == 1
    recherche = metrics_snapshot()["search"]
    assert recherche["queries"] == 1 and recherche["empty"] == 0
