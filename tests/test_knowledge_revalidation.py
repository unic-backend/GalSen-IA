"""
Tests de la revalidation périodique (VOLET 05, chapitre 04, étape 5 du processus de revue).

Une connaissance approuvée une fois ne doit pas rester approuvée indéfiniment.
Ces tests vérifient la détection, son seuil configurable, et le fait qu'aucune
date n'est inventée quand l'historique n'en fournit pas.
"""

import datetime

import pytest

from src.knowledge_engine.knowledge_lifecycle import (
    DEFAULT_REVALIDATION_DAYS, REVALIDATION_DAYS_ENV, approved_at,
    is_due_for_revalidation, revalidation_days,
)
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.types import KnowledgeItem, KnowledgeStatus


def _approuvee(jours_depuis: int) -> KnowledgeItem:
    """Connaissance approuvée il y a `jours_depuis` jours, historique compris."""
    date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=jours_depuis)
    return KnowledgeItem(
        content="Le taux de bancarisation au Sénégal.",
        status=KnowledgeStatus.APPROVED,
        metadata={"status_history": [
            {"from": "reviewed", "to": "approved", "actor": "aissatou",
             "reason": None, "at": date.isoformat()},
        ]},
    )


def test_seuil_par_defaut_et_configurable(monkeypatch):
    """Le seuil vient de l'environnement, avec repli sur le défaut."""
    monkeypatch.delenv(REVALIDATION_DAYS_ENV, raising=False)
    assert revalidation_days() == DEFAULT_REVALIDATION_DAYS

    monkeypatch.setenv(REVALIDATION_DAYS_ENV, "30")
    assert revalidation_days() == 30

    # Une valeur illisible ou nulle ne doit pas désactiver la revalidation.
    monkeypatch.setenv(REVALIDATION_DAYS_ENV, "bientôt")
    assert revalidation_days() == DEFAULT_REVALIDATION_DAYS
    monkeypatch.setenv(REVALIDATION_DAYS_ENV, "0")
    assert revalidation_days() == DEFAULT_REVALIDATION_DAYS


def test_approbation_ancienne_est_a_revoir():
    """Au-delà du seuil, l'approbation a périmé."""
    assert is_due_for_revalidation(_approuvee(400), max_age_days=180)
    assert not is_due_for_revalidation(_approuvee(10), max_age_days=180)


def test_seule_une_approbation_perime():
    """Un brouillon n'a pas d'approbation à revalider."""
    brouillon = KnowledgeItem(content="Chiffres à confirmer auprès de l'ANSD.")
    assert approved_at(brouillon) is None
    assert not is_due_for_revalidation(brouillon, max_age_days=1)


def test_approbation_sans_historique_retombe_sur_updated_at():
    """Sans historique, la seule date réelle est utilisée — aucune n'est inventée."""
    item = KnowledgeItem(content="Approuvée sans historique.", status=KnowledgeStatus.APPROVED)
    assert approved_at(item) == item.updated_at
    assert not is_due_for_revalidation(item, max_age_days=180)


def test_derniere_approbation_prise_en_compte():
    """Une réapprobation récente remet le compteur à zéro."""
    ancienne = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=400)).isoformat()
    recente = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)).isoformat()
    item = KnowledgeItem(
        content="Réapprouvée après revalidation.",
        status=KnowledgeStatus.APPROVED,
        metadata={"status_history": [
            {"from": "reviewed", "to": "approved", "actor": "aissatou", "at": ancienne},
            {"from": "approved", "to": "under_review", "actor": "moussa", "at": recente},
            {"from": "reviewed", "to": "approved", "actor": "moussa", "at": recente},
        ]},
    )
    assert not is_due_for_revalidation(item, max_age_days=180)


def test_le_gestionnaire_liste_les_connaissances_a_revoir():
    """Le gestionnaire ne retourne que les approbations périmées, la plus ancienne d'abord."""
    km = KnowledgeManagerImpl()
    try:
        id_perimee = km.add_knowledge(_approuvee(400))
        km.add_knowledge(_approuvee(3))
        km.add_knowledge(KnowledgeItem(content="Encore en brouillon, jamais approuvée."))

        a_revoir = km.list_due_for_revalidation(max_age_days=180)
        assert [k.id for k in a_revoir] == [id_perimee]

        # Un seuil plus large ne réclame plus rien.
        assert km.list_due_for_revalidation(max_age_days=1000) == []
    finally:
        km.cleanup()
