"""
Tests de la qualité et de la rétention de la mémoire (VOLET 07, ch. 08 et 09).

Quatre métriques sur six se calculent. Les deux autres sont déclarées absentes
avec leur raison, plutôt que de recevoir une valeur plausible.
"""

import time

import pytest

from src.memory_engine.memory_manager import MemoryManager
from src.memory_engine.memory_quality import (
    DEFAULT_INACTIVITY_DAYS, UNAVAILABLE_METRICS, inactive_memories,
)
from src.memory_engine.types import MemoryItem, MemoryStatus, MemoryType


@pytest.fixture
def memoire():
    """Moteur de mémoire isolé pour un test."""
    return MemoryManager()


def test_base_vide_ne_vaut_pas_qualite_parfaite(memoire):
    """Sur une mémoire vide, les taux valent 0.0 — « rien » n'est pas « bon »."""
    rapport = memoire.quality_report()
    assert rapport["items"] == 0
    assert rapport["duplicates"]["rate"] == 0.0
    assert rapport["metadata_completeness"]["with_owner"] == 0.0
    assert rapport["freshness"]["median_age_days"] == 0.0


def test_les_metriques_non_calculables_sont_nommees(memoire):
    """Précision de récupération et satisfaction : absentes, avec leur raison."""
    rapport = memoire.quality_report()
    assert set(rapport["unavailable"]) == set(UNAVAILABLE_METRICS)
    assert set(rapport["unavailable"]) == {"retrieval_accuracy", "user_satisfaction"}
    assert "retrieval_accuracy" not in rapport
    for raison in rapport["unavailable"].values():
        assert raison.strip()


def test_taux_de_doublons_par_sujet(memoire):
    """Deux mêmes contenus pour un même utilisateur comptent une redondance.

    Le même contenu chez deux utilisateurs différents n'en est pas une : ce sont
    deux souvenirs distincts qui se ressemblent.
    """
    memoire.save_memory(MemoryItem(content="Le client préfère le matin.", user_id="awa"))
    memoire.save_memory(MemoryItem(content="Le client préfère le matin.", user_id="awa"))
    memoire.save_memory(MemoryItem(content="Le client préfère le matin.", user_id="moussa"))

    doublons = memoire.quality_report()["duplicates"]
    assert doublons["redundant_items"] == 1
    assert doublons["rate"] == round(1 / 3, 4)


def test_completude_des_metadonnees(memoire):
    """
    La complétude compte ce qui est réellement renseigné.

    **Ce que la phase 60.2 a changé, et pourquoi ce test le suit** : une
    mémoire reçoit désormais l'expiration que sa couche impose. « A-t-elle une
    expiration ? » ne mesure donc plus le soin de celui qui l'a écrite — cela
    mesure sa **couche**. La distinction utile est devenue celle-ci : une
    mémoire à court terme périme, une connaissance non, et c'est écrit dans les
    deux cas.
    """
    memoire.save_memory(MemoryItem(content="Complète.", user_id="awa", tags=["contrat"],
                                   expires_at=time.time() + 3600))
    memoire.save_memory(MemoryItem(content="Sans tags.", user_id="awa"))
    memoire.save_memory(MemoryItem(content="Connaissance commune.", user_id="awa",
                                   memory_type=MemoryType.KNOWLEDGE))

    completude = memoire.quality_report()["metadata_completeness"]
    assert completude["with_owner"] == 1.0
    assert completude["with_tags"] == round(1 / 3, 4)
    # Les deux mémoires à court terme périment ; la connaissance ne périme pas.
    assert completude["with_expiry"] == round(2 / 3, 4)


def test_repartition_par_statut_et_par_type(memoire):
    """Le rapport dit ce que contient la mémoire, pas ce qu'elle devrait contenir."""
    actif = memoire.save_memory(MemoryItem(content="Active.", user_id="awa"))
    archive = memoire.save_memory(MemoryItem(content="À archiver.", user_id="awa"))
    memoire.save_memory(MemoryItem(content="Longue durée.", user_id="awa",
                                   memory_type=MemoryType.LONG_TERM))
    memoire.forget_memory(archive)

    rapport = memoire.quality_report()
    assert rapport["by_status"]["active"] == 2
    assert rapport["by_status"]["archived"] == 1
    assert rapport["by_type"]["long_term"] == 1
    assert memoire.get_memory(actif) is not None


def test_les_memoires_inactives_sont_designees_sans_etre_archivees(memoire):
    """Le chapitre 08 demande de les revoir : le rapport les nomme, il n'agit pas."""
    ancienne = memoire.save_memory(MemoryItem(content="Souvenir ancien.", user_id="awa"))
    memoire.save_memory(MemoryItem(content="Souvenir récent.", user_id="awa"))

    item = memoire.get_store().get(ancienne)
    item.updated_at = time.time() - 200 * 86400
    memoire.get_store().update(item)

    inactives = memoire.list_inactive(max_age_days=90)
    assert [i.id for i in inactives] == [ancienne]
    # Rien n'a été archivé au passage.
    assert memoire.get_memory(ancienne).status is MemoryStatus.ACTIVE
    assert memoire.quality_report(max_age_days=90)["freshness"]["inactive_over_threshold"] == 1


def test_seules_les_memoires_actives_sont_dites_inactives():
    """Une mémoire déjà archivée n'a pas à être revue une seconde fois."""
    ancienne = MemoryItem(content="Archivée et ancienne.", user_id="awa",
                          status=MemoryStatus.ARCHIVED)
    ancienne.updated_at = time.time() - 400 * 86400
    assert inactive_memories([ancienne], max_age_days=DEFAULT_INACTIVITY_DAYS) == []
