"""
Tests du cache de requêtes (VOLET 05, chapitre 05 — PERFORMANCE).

« Cache frequent queries » : une requête répétée ne doit pas re-parcourir
l'index. La contrainte qui compte est l'inverse du gain : un résultat mis en
cache ne doit jamais survivre à une écriture, sinon une connaissance ajoutée
reste invisible.
"""

import pytest

from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.types import KnowledgeItem, KnowledgeStatus


@pytest.fixture
def manager():
    """Gestionnaire de connaissances isolé pour un test."""
    km = KnowledgeManagerImpl()
    yield km
    km.cleanup()


def test_requete_repetee_est_servie_par_le_cache(manager):
    """La seconde recherche identique ne redescend pas dans l'index."""
    manager.add_knowledge(KnowledgeItem(content="La culture du mil dans le bassin arachidier."))
    avant = manager.get_stats()["cache"]["hits"]

    premier = manager.search_knowledge_with_scores("culture mil", limit=5)
    apres_miss = manager.get_stats()["cache"]["hits"]
    second = manager.search_knowledge_with_scores("culture mil", limit=5)
    apres_hit = manager.get_stats()["cache"]["hits"]

    assert [k.id for k, _ in premier] == [k.id for k, _ in second]
    assert apres_hit > apres_miss >= avant


def test_deux_limites_ne_partagent_pas_un_resultat_tronque(manager):
    """La limite fait partie de la clé : limit=1 ne sert pas une demande de 5."""
    for i in range(4):
        manager.add_knowledge(KnowledgeItem(content=f"Note {i} sur la pluviométrie à Kaolack."))

    assert len(manager.search_knowledge("pluviométrie Kaolack", limit=1)) == 1
    assert len(manager.search_knowledge("pluviométrie Kaolack", limit=4)) == 4


def test_un_ajout_invalide_le_cache(manager):
    """Une connaissance ajoutée après une recherche apparaît immédiatement."""
    manager.add_knowledge(KnowledgeItem(content="Premier rapport sur les engrais organiques."))
    assert len(manager.search_knowledge("engrais organiques", limit=10)) == 1

    manager.add_knowledge(KnowledgeItem(content="Second rapport sur les engrais organiques."))
    assert len(manager.search_knowledge("engrais organiques", limit=10)) == 2


def test_une_suppression_invalide_le_cache(manager):
    """Une connaissance supprimée disparaît des résultats mis en cache."""
    identifiant = manager.add_knowledge(KnowledgeItem(content="Note à supprimer sur le maraîchage."))
    assert len(manager.search_knowledge("maraîchage", limit=10)) == 1

    manager.delete_knowledge(identifiant)
    assert manager.search_knowledge("maraîchage", limit=10) == []


def test_une_transition_de_statut_invalide_le_cache(manager):
    """Déprécier une connaissance la retire du RAG sans attendre l'expiration."""
    identifiant = manager.add_knowledge(KnowledgeItem(content="Chiffre provisoire sur le coton."))
    assert len(manager.retrieve_for_prompt("coton", max_items=5)) == 1

    manager.set_status(identifiant, KnowledgeStatus.UNDER_REVIEW, actor="aissatou")
    manager.set_status(identifiant, KnowledgeStatus.DRAFT, actor="moussa", reason="chiffre douteux")
    manager.set_status(identifiant, KnowledgeStatus.DEPRECATED, actor="moussa",
                       reason="chiffre démenti par la source officielle")

    assert manager.retrieve_for_prompt("coton", max_items=5) == []


def test_le_cache_ne_melange_pas_recherche_et_rag(manager):
    """Les deux chemins ont leurs propres clés : le filtrage du RAG ne fuit pas
    dans la recherche exhaustive."""
    manager.add_knowledge(KnowledgeItem(content="Note archivée sur le budget municipal.",
                                        status=KnowledgeStatus.ARCHIVED))
    assert manager.retrieve_for_prompt("budget municipal", max_items=5) == []
    assert len(manager.search_knowledge("budget municipal", limit=5)) == 1
