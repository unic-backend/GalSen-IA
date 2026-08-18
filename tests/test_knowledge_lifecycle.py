"""
Tests du cycle de vie des connaissances (VOLET 05, chapitre 03).

Le chapitre exige une évolution contrôlée et traçable : ces tests vérifient que
les transitions interdites sont refusées, que chaque passage laisse une trace
nominative, et qu'une transition compte comme une révision.
"""

import pytest

from src.knowledge_engine.knowledge_lifecycle import (
    InvalidStatusTransition, allowed_targets, check_transition, is_allowed,
)
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.types import KnowledgeItem, KnowledgeStatus


@pytest.fixture
def manager():
    """Gestionnaire de connaissances isolé pour un test."""
    km = KnowledgeManagerImpl()
    yield km
    km.cleanup()


def _ajouter(manager, contenu="Le fleuve Sénégal traverse quatre pays.") -> str:
    """Ajoute une connaissance et retourne son identifiant."""
    return manager.add_knowledge(KnowledgeItem(content=contenu))


def test_le_retrait_est_terminal():
    """Rien ne sort de DEPRECATED : le cycle s'arrête là."""
    assert allowed_targets(KnowledgeStatus.DEPRECATED) == frozenset()
    assert not is_allowed(KnowledgeStatus.DEPRECATED, KnowledgeStatus.APPROVED)


def test_la_revue_ne_peut_pas_etre_sautee():
    """Un brouillon ne devient pas approuvé sans passer par la revue."""
    assert not is_allowed(KnowledgeStatus.DRAFT, KnowledgeStatus.APPROVED)
    assert is_allowed(KnowledgeStatus.DRAFT, KnowledgeStatus.UNDER_REVIEW)
    with pytest.raises(InvalidStatusTransition) as erreur:
        check_transition(KnowledgeStatus.DRAFT, KnowledgeStatus.APPROVED)
    # Le message dit ce qui était possible, sinon l'appelant doit deviner.
    assert "under_review" in str(erreur.value)


def test_parcours_complet_jusqu_a_l_archivage(manager):
    """Brouillon → revue → revu → approuvé → archivé, une étape à la fois."""
    identifiant = _ajouter(manager)
    assert manager.get_knowledge(identifiant).status is KnowledgeStatus.DRAFT

    for cible, motif in [
        (KnowledgeStatus.UNDER_REVIEW, None),
        (KnowledgeStatus.REVIEWED, None),
        (KnowledgeStatus.APPROVED, None),
        (KnowledgeStatus.ARCHIVED, "remplacée par le recensement 2026"),
    ]:
        item = manager.set_status(identifiant, cible, actor="aissatou", reason=motif)
        assert item.status is cible

    assert manager.get_knowledge(identifiant).status is KnowledgeStatus.ARCHIVED


def test_transition_refusee_ne_modifie_rien(manager):
    """Une transition interdite laisse la connaissance dans son état."""
    identifiant = _ajouter(manager)
    with pytest.raises(InvalidStatusTransition):
        manager.set_status(identifiant, KnowledgeStatus.APPROVED, actor="aissatou")
    assert manager.get_knowledge(identifiant).status is KnowledgeStatus.DRAFT
    assert manager.get_knowledge(identifiant).version == 1


def test_chaque_transition_est_tracee_et_compte_comme_revision(manager):
    """L'historique nomme l'acteur, les deux statuts et le moment."""
    identifiant = _ajouter(manager)
    manager.set_status(identifiant, KnowledgeStatus.UNDER_REVIEW, actor="aissatou")
    item = manager.set_status(identifiant, KnowledgeStatus.DRAFT, actor="moussa",
                              reason="chiffres à revoir")

    historique = item.metadata["status_history"]
    assert len(historique) == 2
    assert historique[0]["from"] == "draft" and historique[0]["to"] == "under_review"
    assert historique[0]["actor"] == "aissatou"
    assert historique[1]["actor"] == "moussa"
    assert historique[1]["reason"] == "chiffres à revoir"
    assert historique[1]["at"]
    # Deux transitions = deux révisions.
    assert item.version == 3


def test_acteur_obligatoire(manager):
    """Une transition anonyme est refusée : la gouvernance exige un responsable."""
    identifiant = _ajouter(manager)
    with pytest.raises(ValueError, match="acteur"):
        manager.set_status(identifiant, KnowledgeStatus.UNDER_REVIEW, actor="   ")


def test_motif_obligatoire_pour_retirer(manager):
    """Archiver ou déprécier sans motif est refusé."""
    identifiant = _ajouter(manager)
    with pytest.raises(ValueError, match="motif"):
        manager.set_status(identifiant, KnowledgeStatus.DEPRECATED, actor="aissatou")

    item = manager.set_status(identifiant, KnowledgeStatus.DEPRECATED, actor="aissatou",
                              reason="information démentie par la source officielle")
    assert item.status is KnowledgeStatus.DEPRECATED


def test_connaissance_absente(manager):
    """Une transition sur une connaissance inexistante répond None, sans lever."""
    assert manager.set_status("kn000000000000", KnowledgeStatus.UNDER_REVIEW, actor="aissatou") is None
