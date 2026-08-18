"""
Tests du fournisseur de recherche sur la connaissance (VOLET 14, ch. 04).

C'est le premier fournisseur réel du service unifié. Deux exigences pèsent sur
lui : rendre ce que le moteur trouve, et ne jamais rendre plus que ce que
l'appelant a le droit de lire (VOLET 05 ch. 07).
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.knowledge_engine.types import (  # noqa: E402
    KnowledgeDomain, KnowledgeItem, KnowledgeSensitivity, KnowledgeStatus,
)
from src.services.search.manager import SearchManagerImpl  # noqa: E402
from src.services.search.providers import KnowledgeSearchProvider  # noqa: E402
from src.services.search.types import SearchQuery, SearchSource  # noqa: E402


@pytest.fixture
def moteur():
    """Moteur de connaissances isolé, peuplé de deux éléments."""
    km = KnowledgeManagerImpl()
    km.add_knowledge(KnowledgeItem(
        content="Le barème public des redevances portuaires de Dakar.",
        domain=KnowledgeDomain.BUSINESS,
        status=KnowledgeStatus.APPROVED,
        sensitivity=KnowledgeSensitivity.PUBLIC,
    ))
    km.add_knowledge(KnowledgeItem(
        content="Le détail confidentiel des redevances portuaires négociées.",
        sensitivity=KnowledgeSensitivity.CONFIDENTIAL,
    ))
    yield km
    km.cleanup()


@pytest.fixture
def service(moteur):
    """Service de recherche unifiée avec la source connaissance branchée."""
    gestionnaire = SearchManagerImpl()
    gestionnaire.register_provider(KnowledgeSearchProvider(moteur))
    return gestionnaire


@pytest.fixture
def cles(monkeypatch):
    """Clés opérateur et lecture seule, avec restauration de l'état RBAC."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-op:operator,cle-lecture:readonly")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield {"operator": "cle-op", "readonly": "cle-lecture"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def test_la_source_connaissance_est_branchee_au_demarrage():
    """Le module d'API enregistre le fournisseur : `/search` a une source."""
    assert SearchSource.KNOWLEDGE in server_module.search_manager.registered_sources()


def test_le_fournisseur_rend_ce_que_le_moteur_trouve(service):
    """Un résultat porte le contenu, le score et sa classification."""
    reponse = service.search(SearchQuery(query="redevances portuaires", limit=10,
                                         role="operator"))
    assert reponse.total == 2
    assert reponse.sources_used == ["knowledge"]
    premier = reponse.results[0]
    assert premier.source is SearchSource.KNOWLEDGE
    assert premier.score > 0
    assert premier.metadata["status"] in {"draft", "approved"}
    assert premier.metadata["sensitivity"] in {"public", "confidential"}


def test_le_role_limite_ce_que_la_recherche_rend(service):
    """Chercher n'autorise pas à lire : le confidentiel n'apparaît pas."""
    lecture = service.search(SearchQuery(query="redevances portuaires", limit=10,
                                         role="readonly"))
    assert lecture.total == 1
    assert all(r.metadata["sensitivity"] == "public" for r in lecture.results)

    # Sans rôle, la lecture est publique — jamais élargie par défaut.
    anonyme = service.search(SearchQuery(query="redevances portuaires", limit=10))
    assert anonyme.total == 1


def test_une_panne_du_moteur_ne_casse_pas_la_recherche():
    """Un moteur qui lève laisse la recherche répondre, sans cette source."""

    class _MoteurEnPanne:
        def search_knowledge_with_scores(self, *args, **kwargs):
            raise RuntimeError("magasin injoignable")

    gestionnaire = SearchManagerImpl()
    gestionnaire.register_provider(KnowledgeSearchProvider(_MoteurEnPanne()))
    reponse = gestionnaire.search(SearchQuery(query="peu importe"))
    assert reponse.total == 0
    assert reponse.results == []


def test_la_route_transmet_le_role_de_l_appelant(cles, moteur, monkeypatch):
    """De bout en bout : `/search` ne rend pas ce que le rôle ne peut pas lire."""
    gestionnaire = SearchManagerImpl()
    gestionnaire.register_provider(KnowledgeSearchProvider(moteur))
    monkeypatch.setattr(server_module, "search_manager", gestionnaire)

    with TestClient(app) as client:
        op = client.post("/search", json={"query": "redevances portuaires"},
                         headers={"X-API-Key": cles["operator"]})
        lecture = client.post("/search", json={"query": "redevances portuaires"},
                              headers={"X-API-Key": cles["readonly"]})

    assert op.status_code == 200 and op.json()["total"] == 2
    assert lecture.status_code == 200 and lecture.json()["total"] == 1
