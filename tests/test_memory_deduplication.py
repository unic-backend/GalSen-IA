"""
Déduplication des mémoires (VOLET 20, chapitre 03).

Le chapitre range « supprimer les connaissances en double » parmi ses pratiques
de gestion et la détection parmi ses contrôles qualité. Seule la détection
existait : le rapport annonçait « 2 éléments redondants » et rien ne pouvait
agir dessus. Mesuré avant correction, trois enregistrements du même contenu
produisaient trois mémoires **et la recherche rendait les trois**.
"""

import time

import pytest

from src.memory_engine.memory_manager import MemoryManager
from src.memory_engine.types import MemoryItem, MemoryStatus, MemoryType


@pytest.fixture
def memoire():
    """Moteur de mémoire isolé."""
    return MemoryManager()


def _enregistrer(moteur, contenu="Le mil se sème en juin au Sénégal.", proprietaire="awa"):
    """Enregistre une mémoire et retourne son identifiant."""
    return moteur.save_memory(MemoryItem(
        content=contenu, memory_type=MemoryType.KNOWLEDGE, user_id=proprietaire,
    ))


def test_trois_fois_le_meme_contenu_laisse_une_seule_active(memoire):
    """Le cas mesuré : trois enregistrements, trois mémoires, trois résultats."""
    identifiants = [_enregistrer(memoire) for _ in range(3)]

    rapport = memoire.deduplicate()

    assert rapport["groups"] == 1
    assert rapport["archived"] == 2
    actifs = [i for i in identifiants if memoire.get_memory(i).status is MemoryStatus.ACTIVE]
    assert len(actifs) == 1


def test_la_plus_ancienne_est_conservee(memoire):
    """Elle porte la date à laquelle la connaissance est apparue."""
    premier = _enregistrer(memoire)
    time.sleep(0.01)
    _enregistrer(memoire)

    memoire.deduplicate()

    assert memoire.get_memory(premier).status is MemoryStatus.ACTIVE


def test_les_doublons_sont_archives_et_non_supprimes(memoire):
    """
    Rien n'autorise à effacer ce qu'un utilisateur a enregistré au motif qu'il
    l'a enregistré deux fois. Même distinction que `forget_memory()`.
    """
    _enregistrer(memoire)
    second = _enregistrer(memoire)

    memoire.deduplicate()

    archive = memoire.get_memory(second)
    assert archive is not None
    assert archive.status is MemoryStatus.ARCHIVED


def test_deux_proprietaires_ne_se_dedupliquent_pas_entre_eux(memoire):
    """La mémoire d'awa n'est pas un doublon de celle de moussa."""
    _enregistrer(memoire, proprietaire="awa")
    _enregistrer(memoire, proprietaire="moussa")

    assert memoire.deduplicate()["archived"] == 0


def test_deux_contenus_differents_restent_deux_memoires(memoire):
    """La déduplication ne doit pas avaler une information nouvelle."""
    _enregistrer(memoire, contenu="Le mil se sème en juin.")
    _enregistrer(memoire, contenu="L'arachide se récolte en octobre.")

    assert memoire.deduplicate()["archived"] == 0


def test_l_essai_a_blanc_ne_modifie_rien(memoire):
    """Un opérateur doit pouvoir regarder avant d'agir."""
    _enregistrer(memoire)
    second = _enregistrer(memoire)

    rapport = memoire.deduplicate(dry_run=True)

    assert rapport["archived"] == 2 - 1
    assert rapport["dry_run"] is True
    assert memoire.get_memory(second).status is MemoryStatus.ACTIVE


def test_la_deduplication_se_limite_a_un_proprietaire(memoire):
    """Dédupliquer une boîte ne doit pas toucher celle des autres."""
    _enregistrer(memoire, proprietaire="awa")
    _enregistrer(memoire, proprietaire="awa")
    _enregistrer(memoire, proprietaire="moussa")
    _enregistrer(memoire, proprietaire="moussa")

    memoire.deduplicate(user_id="awa")

    restants = [i for i in memoire.get_store().list_items(limit=100)
                if i.status is MemoryStatus.ACTIVE and i.user_id == "moussa"]
    assert len(restants) == 2


def test_le_rapport_qualite_suit_l_action(memoire):
    """
    Sans cela, un opérateur dédupliquerait puis lirait « il reste 2 doublons »
    et conclurait que l'opération n'a rien fait.

    Le rapport comptait toutes les mémoires, statut compris ; il ne compte plus
    que les actives, c'est-à-dire l'ensemble sur lequel `deduplicate()` agit.
    """
    for _ in range(3):
        _enregistrer(memoire)
    assert memoire.quality_report()["duplicates"]["redundant_items"] == 2

    memoire.deduplicate()

    doublons = memoire.quality_report()["duplicates"]
    assert doublons["redundant_items"] == 0
    assert doublons["rate"] == 0.0
    assert doublons["scope"] == "active_only"


def test_dedupliquer_deux_fois_n_archive_rien_de_plus(memoire):
    """L'opération doit être idempotente pour être exécutable périodiquement."""
    for _ in range(3):
        _enregistrer(memoire)

    memoire.deduplicate()
    assert memoire.deduplicate()["archived"] == 0


def test_un_magasin_vide_ne_rapporte_aucun_groupe(memoire):
    """Un rapport inventé sur rien serait pire que vide."""
    rapport = memoire.deduplicate()

    assert rapport == {"groups": 0, "archived": 0, "archived_ids": [], "dry_run": False}
