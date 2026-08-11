"""
La mémoire comme deuxième source de recherche (P1 du backlog).

Trois sources sur quatre n'avaient aucun fournisseur : `/search` ne pouvait
interroger que la connaissance. Brancher la mémoire pose une question que la
connaissance ne posait pas — la mémoire est **possédée**, pas seulement
classifiée (ADR-010, critère de sortie C2), et un rôle ne suffit pas à décider
qui peut la lire.
"""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GALSEN_API_KEYS", "test-key-0123456789abcdef")

from src.api import server  # noqa: E402
from src.api.rate_limiter import set_valid_api_key_digests  # noqa: E402
from src.memory_engine.memory_manager import MemoryManager  # noqa: E402
from src.memory_engine.types import MemoryItem, MemoryType  # noqa: E402
from src.services.search.providers import MemorySearchProvider  # noqa: E402
from src.services.search.types import SearchQuery, SearchSource  # noqa: E402

CLE_AWA = "cle-awa-0123456789abcdef"
CLE_MOUSSA = "cle-moussa-0123456789abcd"


@pytest.fixture
def memoire():
    """Mémoire contenant un souvenir par sujet, sur le même thème."""
    manager = MemoryManager()
    manager.save_memory(MemoryItem(content="La pluviométrie du Sénégal varie.",
                                   memory_type=MemoryType.KNOWLEDGE, user_id="awa"))
    manager.save_memory(MemoryItem(content="Le carnet de moussa sur la pluviométrie.",
                                   memory_type=MemoryType.KNOWLEDGE, user_id="moussa"))
    return manager


@pytest.fixture
def fournisseur(memoire):
    """Fournisseur de recherche branché sur cette mémoire."""
    return MemorySearchProvider(memoire)


def _requete(**kwargs):
    """Construit une requête de recherche sur la mémoire."""
    parametres = {"query": "pluviometrie", "sources": [SearchSource.MEMORY]}
    parametres.update(kwargs)
    return SearchQuery(**parametres)


def test_un_sujet_ne_voit_que_ses_propres_souvenirs(fournisseur):
    """Le critère C2 est déjà atteint ; une nouvelle source ne doit pas le défaire."""
    resultats = fournisseur.search(_requete(subject="awa"))

    assert len(resultats) == 1
    assert "Sénégal" in resultats[0].content
    assert "moussa" not in resultats[0].content


def test_l_autre_sujet_voit_les_siens(fournisseur):
    """Le contre-test : isoler ne doit pas rendre la source muette."""
    resultats = fournisseur.search(_requete(subject="moussa"))

    assert len(resultats) == 1
    assert "moussa" in resultats[0].content


def test_sans_sujet_la_source_ne_cherche_pas(fournisseur):
    """
    Rendre tous les souvenirs serait une fuite ; en rendre au hasard, une
    invention. Une requête sans sujet ne désigne aucune mémoire.
    """
    assert fournisseur.search(_requete(subject=None)) == []


def test_un_role_eleve_ne_donne_pas_les_souvenirs_des_autres(fournisseur):
    """
    Un administrateur a le droit de lire beaucoup de choses ; il n'a pas pour
    autant la mémoire d'autrui. Le rôle classifie, le sujet possède.
    """
    resultats = fournisseur.search(_requete(subject="awa", role="admin"))

    assert [r.content for r in resultats] == ["La pluviométrie du Sénégal varie."]


def test_le_proprietaire_n_est_pas_recopie_dans_le_resultat(fournisseur):
    """L'appelant est le sujet : le lui répéter n'apprend rien et crée une donnée à protéger."""
    resultat = fournisseur.search(_requete(subject="awa"))[0]

    assert "user_id" not in resultat.metadata
    assert "owner" not in resultat.metadata
    assert resultat.metadata["memory_type"] == "knowledge"


def test_une_requete_sans_rapport_ne_rend_rien(fournisseur):
    """La source hérite du filtrage réel de la recherche de mémoire."""
    assert fournisseur.search(_requete(query="automobile", subject="awa")) == []


# ----------------------------------------------------------------------
# De bout en bout, par l'API
# ----------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    """Deux sujets administrateurs, chacun avec sa clé."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE_AWA}:admin:awa,{CLE_MOUSSA}:admin:moussa")
    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    server.memory_manager.save_memory(MemoryItem(
        content="La pluviométrie du Sénégal varie.",
        memory_type=MemoryType.KNOWLEDGE, user_id="awa"))
    server.memory_manager.save_memory(MemoryItem(
        content="Le carnet de moussa sur la pluviométrie.",
        memory_type=MemoryType.KNOWLEDGE, user_id="moussa"))
    with TestClient(server.app) as instance:
        yield instance


def test_la_memoire_est_une_source_reellement_branchee(client):
    """Trois sources sur quatre n'en avaient aucune ; il en reste deux."""
    corps = client.post("/search", json={"query": "pluviometrie"},
                        headers={"X-API-Key": CLE_AWA}).json()

    assert "memory" in corps["sources_used"]


def test_la_recherche_unifiee_respecte_la_propriete(client):
    """Le chemin complet, celui qu'un utilisateur emprunte réellement."""
    pour_awa = client.post("/search", json={"query": "pluviometrie"},
                           headers={"X-API-Key": CLE_AWA}).json()
    pour_moussa = client.post("/search", json={"query": "pluviometrie"},
                              headers={"X-API-Key": CLE_MOUSSA}).json()

    contenus_awa = [r["content"] for r in pour_awa["results"]]
    contenus_moussa = [r["content"] for r in pour_moussa["results"]]

    assert any("Sénégal" in c for c in contenus_awa)
    assert not any("moussa" in c for c in contenus_awa)
    assert any("moussa" in c for c in contenus_moussa)


def test_la_reponse_dit_que_le_classement_inter_sources_n_est_pas_fonde(client):
    """
    Les poids valaient 1.0 / 0.9 / 0.85 / 0.8 sans venir d'aucune mesure, et
    ils étaient inertes tant qu'une seule source était branchée. Deux sources
    les auraient rendus vivants : ils auraient réordonné des résultats sans que
    personne puisse dire pourquoi.
    """
    corps = client.post("/search", json={"query": "pluviometrie"},
                        headers={"X-API-Key": CLE_AWA}).json()

    assert corps["ranking"]["cross_source_comparable"] is False
    assert "pas comparables" in corps["ranking"]["detail"]


def test_aucune_source_n_est_privilegiee_par_un_poids_arbitraire():
    """Tant qu'aucune mesure ne justifie une préférence, aucune n'est appliquée."""
    poids = {source: server.search_manager._get_score_weight(source)
             for source in SearchSource}

    assert set(poids.values()) == {1.0}
