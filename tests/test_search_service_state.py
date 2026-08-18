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


def test_la_route_rapporte_l_indisponibilite_au_lieu_de_zero_resultat(cle, monkeypatch):
    """Sans fournisseur, 503 avec une raison — jamais un `total: 0` trompeur.

    C'est l'état dans lequel se trouvait le dépôt avant la phase 4.1 : le service
    était instancié et aucun fournisseur n'était enregistré. La source
    connaissance est branchée depuis, mais un déploiement qui la perdrait doit
    encore le dire au lieu de rendre une réponse vide crédible.
    """
    monkeypatch.setattr(server_module, "search_manager", SearchManagerImpl())
    with TestClient(app) as client:
        reponse = client.post("/search", json={"query": "agriculture"},
                              headers={"X-API-Key": cle})
    assert reponse.status_code == 503
    assert "branchée" in reponse.json()["detail"]


def test_les_sources_declarees_depassent_les_sources_branchees():
    """La vision est déclarée et n'a toujours aucun fournisseur.

    Le test a suivi la mesure, le 2026-08-13 : il affirmait que **document et**
    vision étaient vides. C'était faux pour les documents — le moteur indexait
    déjà ce qu'il chargeait, seul le fournisseur manquait, et il existe
    désormais.

    Ce qu'il garde est ce qui doit rester vrai : **une source déclarée sans
    fournisseur ne doit jamais se lire comme une source interrogée sans
    résultat**. Pour la vision ce n'est pas du code qui manque, c'est du texte
    à indexer.
    """
    branchees = set(server_module.search_manager.registered_sources())

    assert {SearchSource.KNOWLEDGE, SearchSource.MEMORY, SearchSource.DOCUMENT} <= branchees
    assert SearchSource.VISION not in branchees
    # L'absence est rapportée, pas déduite du silence.
    reponse = server_module.search_manager.search(SearchQuery(query="mil"))
    assert SearchSource.VISION.value in reponse.sources_unavailable


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
