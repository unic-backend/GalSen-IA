"""
Tests de la sécurité de la recherche (VOLET 14, chapitre 07).

Le chapitre demande un accès contrôlé au contenu indexé. Le piège propre à un
index est qu'il est bâti **avant** tout contrôle d'accès : tout y est, y compris
ce que l'appelant n'a pas le droit de lire. Ce qui compte est donc que le
filtrage tienne sur chaque chemin de sortie — résultats, compte total, scores et
messages.
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
    KnowledgeItem, KnowledgeSensitivity,
)
from src.services.search.manager import SearchManagerImpl  # noqa: E402
from src.services.search.providers import KnowledgeSearchProvider  # noqa: E402
from src.services.search.types import SearchQuery  # noqa: E402

SECRET = "négociation confidentielle du contrat portuaire"


@pytest.fixture
def service():
    """Un service de recherche sur une base contenant un secret et un public."""
    moteur = KnowledgeManagerImpl()
    moteur.add_knowledge(KnowledgeItem(
        content="Le barème public du contrat portuaire est publié chaque année.",
        sensitivity=KnowledgeSensitivity.PUBLIC,
    ))
    moteur.add_knowledge(KnowledgeItem(
        content=f"La {SECRET} prévoit une remise exceptionnelle.",
        sensitivity=KnowledgeSensitivity.RESTRICTED,
    ))
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


def test_l_index_contient_ce_que_le_role_ne_lit_pas(service):
    """Constat, non défaut : l'index est bâti avant tout contrôle d'accès."""
    admin = service.search(SearchQuery(query="contrat portuaire", limit=10, role="admin"))
    assert admin.total == 2  # le document restreint est bien indexé et trouvable


def test_le_total_ne_revele_pas_les_documents_filtres(service):
    """Le compte rendu est celui des résultats permis, pas celui de l'index.

    Un total de 2 accompagné d'un seul résultat dirait « il existe un document
    que vous ne pouvez pas voir » — assez pour en déduire l'existence.
    """
    lecture = service.search(SearchQuery(query="contrat portuaire", limit=10, role="readonly"))
    assert lecture.total == 1
    assert len(lecture.results) == 1


@pytest.mark.parametrize("terme", ["négociation", "remise exceptionnelle", "confidentielle"])
def test_aucun_terme_du_document_restreint_ne_le_fait_apparaitre(service, terme):
    """Chercher les mots exacts du secret ne le révèle pas davantage."""
    lecture = service.search(SearchQuery(query=terme, limit=10, role="readonly"))
    assert lecture.total == 0
    assert lecture.results == []


def test_la_reponse_ne_contient_aucun_fragment_du_secret(cles, service, monkeypatch):
    """De bout en bout : rien du contenu restreint n'atteint un rôle sans droit."""
    monkeypatch.setattr(server_module, "search_manager", service)
    with TestClient(app) as client:
        reponse = client.post("/search", json={"query": "contrat portuaire négociation"},
                              headers={"X-API-Key": cles["readonly"]})

    assert reponse.status_code == 200
    corps = reponse.text
    assert "remise exceptionnelle" not in corps
    assert "restricted" not in corps


def test_une_recherche_sans_role_ne_lit_que_le_public(service):
    """Un appel interne qui oublie le rôle perd l'accès, il n'en gagne pas."""
    anonyme = service.search(SearchQuery(query="contrat portuaire", limit=10))
    assert anonyme.total == 1
    assert all(r.metadata["sensitivity"] == "public" for r in anonyme.results)
