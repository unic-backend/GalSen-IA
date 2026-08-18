"""
Tests de l'intégrité de l'index (VOLET 14, chapitre 05).

Un index qui diverge de son magasin ne se voit pas : la recherche rend
simplement moins, ou désigne des documents disparus. Ces tests provoquent les
trois divergences possibles et vérifient que chacune est nommée.
"""

import pytest

from src.knowledge_engine.knowledge_indexer import InMemoryKnowledgeIndexer
from src.knowledge_engine.knowledge_store import InMemoryKnowledgeStore
from src.knowledge_engine.types import KnowledgeItem


@pytest.fixture
def magasin_et_index():
    """Un magasin peuplé et son index, cohérents au départ."""
    magasin = InMemoryKnowledgeStore()
    for i in range(3):
        magasin.save(KnowledgeItem(content=f"Note numéro {i} sur la filière rizicole."))
    return magasin, InMemoryKnowledgeIndexer(magasin)


def test_index_construit_est_coherent(magasin_et_index):
    """Un index bâti sur son magasin est cohérent, sans divergence d'aucune sorte."""
    _, index = magasin_et_index
    rapport = index.check_integrity()
    assert rapport["consistent"] is True
    assert rapport["indexed_documents"] == rapport["stored_documents"] == 3
    assert rapport["missing_count"] == rapport["orphaned_count"] == rapport["stale_count"] == 0


def test_document_ajoute_hors_index_est_signale(magasin_et_index):
    """Une écriture directe dans le magasin laisse l'index en retard : c'est dit."""
    magasin, index = magasin_et_index
    identifiant = magasin.save(KnowledgeItem(content="Note écrite sans passer par l'index."))

    rapport = index.check_integrity()
    assert rapport["consistent"] is False
    assert rapport["missing"] == [identifiant]
    assert rapport["orphaned_count"] == 0


def test_document_supprime_du_magasin_laisse_un_orphelin(magasin_et_index):
    """Un document effacé du magasin mais resté indexé est signalé orphelin."""
    magasin, index = magasin_et_index
    identifiant = magasin.list_items()[0].id
    magasin.delete(identifiant)

    rapport = index.check_integrity()
    assert rapport["consistent"] is False
    assert rapport["orphaned"] == [identifiant]


def test_contenu_modifie_sans_reindexation_est_perime(magasin_et_index):
    """Un contenu réécrit dont l'index garde les anciens termes est « périmé »."""
    magasin, index = magasin_et_index
    item = magasin.list_items()[0]
    nouvelle_version = item.update_content("Contenu entièrement réécrit sur l'arachide.")
    magasin.update(nouvelle_version)

    rapport = index.check_integrity()
    assert rapport["consistent"] is False
    assert rapport["stale"] == [item.id]
    # Ni manquant ni orphelin : le document est bien là des deux côtés.
    assert rapport["missing_count"] == rapport["orphaned_count"] == 0


def test_reconstruction_retablit_la_coherence(magasin_et_index):
    """Après reconstruction, plus aucune divergence n'est rapportée."""
    magasin, index = magasin_et_index
    magasin.save(KnowledgeItem(content="Note écrite sans passer par l'index."))
    assert index.check_integrity()["consistent"] is False

    index._rebuild_index()
    assert index.check_integrity()["consistent"] is True


def test_index_vide_sur_magasin_vide():
    """Un magasin vide donne un index cohérent, pas une erreur."""
    index = InMemoryKnowledgeIndexer(InMemoryKnowledgeStore())
    rapport = index.check_integrity()
    assert rapport["consistent"] is True
    assert rapport["stored_documents"] == 0
