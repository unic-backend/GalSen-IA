"""
Tests du cycle de vie de la mémoire (VOLET 07, chapitres 03 et 05).

Le chapitre distingue huit étapes, dont l'archivage (7) et la suppression (8).
Quatre défauts sont couverts ici, tous du même genre : une règle déclarée que
rien n'appliquait, donc une mémoire qui survivait à ce qui aurait dû l'effacer.
"""

import time

import pytest

from src.memory_engine.memory_manager import MemoryManager
from src.memory_engine.types import MemoryItem, MemoryStatus


@pytest.fixture
def memoire():
    """Moteur de mémoire isolé pour un test."""
    return MemoryManager()


def _ids(resultats):
    """Extrait les identifiants d'une liste (élément, score)."""
    return [element.id for element, _ in resultats]


def test_oublier_archive_au_lieu_de_supprimer(memoire):
    """« Oublier » ne détruit pas : le chapitre distingue archiver et supprimer."""
    identifiant = memoire.save_memory(MemoryItem(content="Le client préfère le matin.",
                                                 user_id="awa"))
    assert memoire.forget_memory(identifiant) is True

    archive = memoire.get_memory(identifiant)
    assert archive is not None, "une mémoire archivée reste lisible par son identifiant"
    assert archive.status is MemoryStatus.ARCHIVED


def test_une_memoire_archivee_ne_remonte_plus_dans_la_recherche(memoire):
    """Sans cela, l'archivage serait une étiquette sans effet."""
    actif = memoire.save_memory(MemoryItem(content="Le client préfère le matin.", user_id="awa"))
    ancien = memoire.save_memory(MemoryItem(content="Le client préférait le soir.", user_id="awa"))
    memoire.forget_memory(ancien)

    trouves = _ids(memoire.search_memory(query="client", user_id="awa"))
    assert actif in trouves
    assert ancien not in trouves


def test_oublier_une_memoire_absente_repond_faux(memoire):
    """Rien à archiver n'est pas une réussite."""
    assert memoire.forget_memory("mem_inexistante") is False


def test_la_suppression_reste_definitive(memoire):
    """L'étape 8 existe toujours et efface pour de bon."""
    identifiant = memoire.save_memory(MemoryItem(content="À supprimer.", user_id="awa"))
    assert memoire.delete_memory(identifiant) is True
    assert memoire.get_memory(identifiant) is None


def test_une_memoire_expiree_n_est_pas_servie(memoire):
    """L'expiration est respectée à la lecture, sans attendre le nettoyage.

    Elle ne l'était pas : une date de rétention ne s'appliquait que si quelqu'un
    appelait `cleanup_expired()`.
    """
    identifiant = memoire.save_memory(MemoryItem(content="Périmée.", user_id="awa",
                                                 expires_at=time.time() - 10))
    assert memoire.get_memory(identifiant) is None
    assert _ids(memoire.search_memory(query="Périmée", user_id="awa")) == []


def test_le_nettoyage_purge_aussi_le_cache(memoire):
    """`cleanup_expired()` comptait des suppressions que le cache annulait."""
    identifiant = memoire.save_memory(MemoryItem(content="Périmée mais lue.", user_id="awa",
                                                 expires_at=time.time() + 60))
    assert memoire.get_memory(identifiant) is not None  # met l'élément en cache

    # La mémoire expire pendant qu'elle est en cache.
    item = memoire.get_store().get(identifiant)
    item.expires_at = time.time() - 1
    memoire.get_store().update(item)

    assert memoire.cleanup_expired() == 1
    assert memoire.get_memory(identifiant) is None, "servie depuis le cache après nettoyage"


def test_une_memoire_valide_survit_au_nettoyage(memoire):
    """Le nettoyage ne doit emporter que ce qui a expiré."""
    valide = memoire.save_memory(MemoryItem(content="Toujours valable.", user_id="awa"))
    memoire.save_memory(MemoryItem(content="Périmée.", user_id="awa", expires_at=time.time() - 5))

    assert memoire.cleanup_expired() == 1
    assert memoire.get_memory(valide) is not None


def test_la_consolidation_dit_qu_elle_n_existe_pas(memoire):
    """Elle retournait 0, indiscernable de « rien à consolider »."""
    with pytest.raises(NotImplementedError, match="consolidation"):
        memoire.consolidate_memory(user_id="awa")
