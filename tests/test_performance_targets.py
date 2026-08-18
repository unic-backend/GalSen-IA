"""
Tests de performance (VOLET 03, chapitres 04 et 08).

C'était le cinquième niveau de test, absent — pour une raison légitime : aucune
cible n'existait, et une assertion de durée sans seuil déclaré est un chiffre
choisi pour passer. Les cibles sont désormais écrites dans
`docs/standards/performance.md`, mesures à l'appui, et ces tests les vérifient.

Ce qui est mesuré est le **traitement côté serveur**, jamais le réseau : rien
n'est déployé, et une latence de bout en bout serait inventée.

Les seuils sont volontairement 20 à 60 fois au-dessus des mesures : un test qui
échoue parce que la machine est chargée est un test qu'on désactive.
"""

import os
import statistics
import sys
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.knowledge_engine.knowledge_indexer import InMemoryKnowledgeIndexer  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.knowledge_engine.knowledge_store import InMemoryKnowledgeStore  # noqa: E402
from src.knowledge_engine.types import KnowledgeItem  # noqa: E402

# Cibles de `docs/standards/performance.md`, en millisecondes, au 95e centile.
CIBLE_SUPERVISION_MS = 50
CIBLE_LECTURE_MS = 200

# Assez d'appels pour un 95e centile qui veut dire quelque chose, assez peu pour
# que la suite reste rapide.
APPELS = 40


@pytest.fixture
def client(monkeypatch):
    """Client d'API authentifié, limiteur de taux désactivé.

    Le limiteur coupe à 60 requêtes par minute : sans cela il tronquerait
    l'échantillon et la mesure porterait sur des refus.
    """
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-perf:admin")
    monkeypatch.setenv("GALSEN_RATE_LIMIT_ENABLED", "false")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    with TestClient(app) as c:
        yield c
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def _p95(appel) -> float:
    """Retourne le 95e centile de la durée d'un appel, en millisecondes."""
    appel()  # échauffement : le premier appel construit des objets partagés
    durees = []
    for _ in range(APPELS):
        debut = time.perf_counter()
        reponse = appel()
        durees.append((time.perf_counter() - debut) * 1000)
        assert reponse.status_code == 200, f"réponse {reponse.status_code}, mesure sans objet"
    durees.sort()
    return durees[int(0.95 * len(durees)) - 1]


def test_supervision_repond_sous_la_cible(client):
    """`/health` doit répondre même quand la plateforme est dégradée."""
    assert _p95(lambda: client.get("/health")) < CIBLE_SUPERVISION_MS


def test_metriques_repondent_sous_la_cible(client):
    """`/metrics` est lu par la supervision : il ne doit pas coûter cher."""
    entetes = {"X-API-Key": "cle-perf"}
    assert _p95(lambda: client.get("/metrics", headers=entetes)) < CIBLE_SUPERVISION_MS


def test_recherche_de_connaissance_sous_la_cible(client):
    """La recherche est le chemin que quelqu'un attend en tapant."""
    entetes = {"X-API-Key": "cle-perf"}
    appel = lambda: client.post("/knowledge/search",  # noqa: E731
                                json={"query": "production agricole", "limit": 5},
                                headers=entetes)
    assert _p95(appel) < CIBLE_LECTURE_MS


def test_recherche_unifiee_sous_la_cible(client):
    """La recherche unifiée traverse le service, ses fournisseurs et le filtrage."""
    entetes = {"X-API-Key": "cle-perf"}
    appel = lambda: client.post("/search", json={"query": "production agricole"},  # noqa: E731
                                headers=entetes)
    assert _p95(appel) < CIBLE_LECTURE_MS


def test_la_recherche_ne_degrade_pas_avec_la_taille_de_la_base():
    """Un index inversé doit rester plat : sinon la cible tombe avec le contenu.

    Comparé sur 100 puis 1 000 documents. Le rapport toléré est large — c'est
    l'effondrement qu'on cherche à voir, pas une variation de quelques pour cent.
    """
    def mesurer(nombre: int) -> float:
        magasin = InMemoryKnowledgeStore()
        for i in range(nombre):
            magasin.save(KnowledgeItem(content=f"Note {i} sur la production agricole au Sénégal."))
        moteur = KnowledgeManagerImpl(store=magasin, indexer=InMemoryKnowledgeIndexer(magasin))
        try:
            moteur.search_knowledge_with_scores("production agricole", limit=5)
            durees = []
            for _ in range(20):
                debut = time.perf_counter()
                moteur.search_knowledge_with_scores("production agricole", limit=5)
                durees.append((time.perf_counter() - debut) * 1000)
            return statistics.median(durees)
        finally:
            moteur.cleanup()

    petite, grande = mesurer(100), mesurer(1000)
    # Dix fois plus de documents ne doit pas coûter dix fois plus cher.
    assert grande < max(petite * 5, 5.0), f"{petite:.3f} ms → {grande:.3f} ms pour 10× le contenu"
