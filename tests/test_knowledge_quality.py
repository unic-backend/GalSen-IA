"""
Tests des métriques de qualité (VOLET 05, chapitre 09).

Quatre métriques sur six se calculent. Ces tests vérifient les chiffres sur un
contenu connu, et surtout que les deux autres sont déclarées indisponibles avec
leur raison au lieu de recevoir une valeur plausible.
"""

import datetime

import pytest

from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.knowledge_quality import UNAVAILABLE_METRICS
from src.knowledge_engine.types import (
    KnowledgeDomain, KnowledgeItem, KnowledgeSource, KnowledgeStatus,
)


@pytest.fixture
def manager():
    """Gestionnaire de connaissances isolé pour un test."""
    km = KnowledgeManagerImpl()
    yield km
    km.cleanup()


def test_base_vide_ne_vaut_pas_qualite_parfaite(manager):
    """Sur une base vide, les taux valent 0.0 — « rien » n'est pas « bon »."""
    rapport = manager.quality_report()
    assert rapport["items"] == 0
    assert rapport["completeness"]["classified_domain"] == 0.0
    assert rapport["validation_coverage"]["reviewed_or_approved"] == 0.0
    assert rapport["duplicates"]["rate"] == 0.0
    assert rapport["freshness"]["median_age_days"] == 0.0


def test_les_metriques_non_calculables_sont_nommees(manager):
    """L'exactitude et le retour utilisateur sont déclarés absents, avec la raison."""
    indisponibles = manager.quality_report()["unavailable"]
    assert set(indisponibles) == {"accuracy_rate", "user_feedback"}
    assert set(indisponibles) == set(UNAVAILABLE_METRICS)
    for raison in indisponibles.values():
        assert raison.strip()
    # Aucune valeur numérique ne doit exister pour ces deux métriques.
    rapport = manager.quality_report()
    assert "accuracy_rate" not in rapport
    assert "user_feedback" not in rapport


def test_completude(manager):
    """La complétude compte les métadonnées réellement renseignées."""
    manager.add_knowledge(KnowledgeItem(
        content="Connaissance complète sur la filière halieutique.",
        summary="Filière halieutique.",
        domain=KnowledgeDomain.BUSINESS,
        source=KnowledgeSource(id="src1", type="file", location="docs/peche.md"),
    ))
    manager.add_knowledge(KnowledgeItem(content="Connaissance sans domaine ni source."))

    completude = manager.quality_report()["completeness"]
    assert completude["classified_domain"] == 0.5
    assert completude["traceable_source"] == 0.5
    assert completude["with_summary"] == 0.5


def test_taux_de_doublons(manager):
    """Deux contenus identiques comptent pour un élément redondant."""
    contenu = "Le port de Dakar traite l'essentiel du fret national."
    manager.add_knowledge(KnowledgeItem(content=contenu, id="kn_premier"))
    manager.add_knowledge(KnowledgeItem(content=contenu, id="kn_second"))
    manager.add_knowledge(KnowledgeItem(content="Un contenu différent des deux autres."))

    doublons = manager.quality_report()["duplicates"]
    assert doublons["groups"] == 1
    assert doublons["redundant_items"] == 1
    assert doublons["rate"] == round(1 / 3, 4)


def test_couverture_de_validation(manager):
    """La couverture compte ce qui est passé par la revue, pas ce qui existe."""
    manager.add_knowledge(KnowledgeItem(content="Fiche approuvée sur le mil.",
                                        status=KnowledgeStatus.APPROVED))
    manager.add_knowledge(KnowledgeItem(content="Fiche revue sur le sorgho.",
                                        status=KnowledgeStatus.REVIEWED))
    manager.add_knowledge(KnowledgeItem(content="Fiche en brouillon sur le fonio."))
    manager.add_knowledge(KnowledgeItem(content="Fiche en cours de revue sur le niébé.",
                                        status=KnowledgeStatus.UNDER_REVIEW))

    couverture = manager.quality_report()["validation_coverage"]
    assert couverture["reviewed_or_approved"] == 0.5
    assert couverture["by_status"] == {
        "approved": 1, "reviewed": 1, "draft": 1, "under_review": 1,
    }


def test_fraicheur_et_approbations_perimees(manager):
    """La fraîcheur mesure l'âge réel et compte les approbations à revalider."""
    vieille = (datetime.datetime.now(datetime.timezone.utc)
               - datetime.timedelta(days=400)).isoformat()
    manager.add_knowledge(KnowledgeItem(
        content="Donnée approuvée il y a longtemps sur les quotas.",
        status=KnowledgeStatus.APPROVED,
        metadata={"status_history": [
            {"from": "reviewed", "to": "approved", "actor": "aissatou", "at": vieille},
        ]},
    ))
    manager.add_knowledge(KnowledgeItem(content="Donnée fraîche sur les quotas."))

    fraicheur = manager.quality_report()["freshness"]
    assert fraicheur["stale_approvals"] == 1
    # Les deux éléments viennent d'être écrits : leur âge de mise à jour est nul.
    assert fraicheur["median_age_days"] < 1
