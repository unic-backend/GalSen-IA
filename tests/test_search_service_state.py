"""
Tests de l'état réel du service de recherche unifiée (VOLET 14, ch. 01 et 02).

Le service fusionne les résultats de fournisseurs enregistrés. Aucun n'est
enregistré dans le dépôt : la route doit le dire au lieu de rendre « aucun
résultat », qui se lit comme une base vide.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.services.search.manager import SearchManagerImpl  # noqa: E402
from src.services.search.types import (  # noqa: E402
    SearchQuery, SearchResultItem, SearchSource,
)


@pytest.fixture
def cle(monkeypatch):
    """Clé utilisateur, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-user:user")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield "cle-user"
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


class _FournisseurFactice:
    """Fournisseur minimal : retourne un résultat fixe pour toute requête."""

    source = SearchSource.KNOWLEDGE

    def search(self, query: SearchQuery):
        return [SearchResultItem(
            id="kn_test", source=SearchSource.KNOWLEDGE,
            title="Résultat de test", content="Contenu de test", score=1.0,
        )]


def test_aucun_fournisseur_n_est_enregistre_dans_le_depot():
    """Constat mesuré : rien dans `src/` n'implémente `SearchProvider`."""
    assert server_module.search_manager.registered_sources() == []


def test_la_route_rapporte_l_indisponibilite_au_lieu_de_zero_resultat(cle):
    """Sans fournisseur, 503 avec une raison — jamais un `total: 0` trompeur."""
    with TestClient(app) as client:
        reponse = client.post("/search", json={"query": "agriculture"},
                              headers={"X-API-Key": cle})
    assert reponse.status_code == 503
    assert "branchée" in reponse.json()["detail"]


def test_la_route_repond_des_qu_une_source_est_branchee(cle, monkeypatch):
    """La route n'est pas cassée : elle répond dès qu'un fournisseur existe."""
    gestionnaire = SearchManagerImpl()
    gestionnaire.register_provider(_FournisseurFactice())
    monkeypatch.setattr(server_module, "search_manager", gestionnaire)

    with TestClient(app) as client:
        reponse = client.post("/search", json={"query": "agriculture"},
                              headers={"X-API-Key": cle})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["total"] == 1
    assert corps["sources_used"] == ["knowledge"]


def test_sources_enregistrees_reflete_les_enregistrements():
    """`registered_sources()` dit ce qui est branché, pas ce qui est déclaré."""
    gestionnaire = SearchManagerImpl()
    assert gestionnaire.registered_sources() == []
    gestionnaire.register_provider(_FournisseurFactice())
    assert gestionnaire.registered_sources() == [SearchSource.KNOWLEDGE]
    # `SearchSource` déclare plus de sources que ce qui est branché.
    assert len(list(SearchSource)) > len(gestionnaire.registered_sources())
