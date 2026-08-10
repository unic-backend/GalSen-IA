"""
Tests de l'étape 5 du pipeline de récupération (VOLET 05, chapitre 05).

« Filter by permissions and policies » : ce qui a été retiré de l'usage —
archivé ou déprécié — ne doit pas nourrir un raisonnement, même s'il reste le
résultat le plus pertinent pour la requête.
"""

import pytest

from src.knowledge_engine.knowledge_lifecycle import WITHDRAWN_STATUSES, is_retrievable
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.types import KnowledgeItem, KnowledgeStatus


@pytest.fixture
def manager():
    """Gestionnaire de connaissances isolé pour un test."""
    km = KnowledgeManagerImpl()
    yield km
    km.cleanup()


def _ajouter(manager, contenu: str, statut: KnowledgeStatus) -> str:
    """Ajoute une connaissance dans un statut donné."""
    return manager.add_knowledge(KnowledgeItem(content=contenu, status=statut))


def test_statuts_retires():
    """Seuls l'archivage et le retrait écartent une connaissance de l'usage."""
    assert WITHDRAWN_STATUSES == frozenset({KnowledgeStatus.ARCHIVED, KnowledgeStatus.DEPRECATED})
    for statut in (KnowledgeStatus.DRAFT, KnowledgeStatus.UNDER_REVIEW,
                   KnowledgeStatus.REVIEWED, KnowledgeStatus.APPROVED):
        assert is_retrievable(KnowledgeItem(content="Contenu quelconque.", status=statut))
    for statut in WITHDRAWN_STATUSES:
        assert not is_retrievable(KnowledgeItem(content="Contenu quelconque.", status=statut))


def test_le_rag_ecarte_les_connaissances_retirees(manager):
    """Une connaissance dépréciée n'entre pas dans le contexte, même pertinente."""
    id_actif = _ajouter(manager, "Le tarif du transport urbain à Dakar est révisé.",
                        KnowledgeStatus.APPROVED)
    _ajouter(manager, "Le tarif du transport urbain à Dakar était fixé en 2019.",
             KnowledgeStatus.DEPRECATED)
    _ajouter(manager, "Le tarif du transport urbain à Dakar avant réforme.",
             KnowledgeStatus.ARCHIVED)

    resultats = manager.retrieve_for_prompt("tarif transport urbain Dakar", max_items=5)
    assert [k.id for k in resultats] == [id_actif]


def test_le_filtrage_ne_reduit_pas_le_nombre_de_resultats(manager):
    """Un résultat retiré ne consomme pas une place dans la réponse."""
    for i in range(3):
        _ajouter(manager, f"Connaissance retirée numéro {i} sur le mil.", KnowledgeStatus.DEPRECATED)
    attendus = {_ajouter(manager, f"Connaissance utile numéro {i} sur le mil.", KnowledgeStatus.DRAFT)
                for i in range(2)}

    resultats = manager.retrieve_for_prompt("mil", max_items=2)
    assert {k.id for k in resultats} == attendus


def test_statuts_explicites(manager):
    """L'appelant peut exiger un statut précis, par exemple l'approbation."""
    id_approuve = _ajouter(manager, "Donnée approuvée sur la pluviométrie.", KnowledgeStatus.APPROVED)
    _ajouter(manager, "Donnée en brouillon sur la pluviométrie.", KnowledgeStatus.DRAFT)

    approuvees = manager.retrieve_for_prompt("pluviométrie", max_items=5,
                                             statuses=[KnowledgeStatus.APPROVED])
    assert [k.id for k in approuvees] == [id_approuve]

    # Un statut explicite peut aussi réclamer ce qui est retiré, pour un audit.
    _ajouter(manager, "Donnée dépréciée sur la pluviométrie.", KnowledgeStatus.DEPRECATED)
    retirees = manager.retrieve_for_prompt("pluviométrie", max_items=5,
                                           statuses=[KnowledgeStatus.DEPRECATED])
    assert len(retirees) == 1
    assert retirees[0].status is KnowledgeStatus.DEPRECATED


def test_retrieve_reliable_applique_la_meme_politique(manager):
    """La récupération fiable écarte aussi ce qui est retiré de l'usage."""
    manager.add_knowledge(KnowledgeItem(
        content="Chiffre déprécié sur la production arachidière.",
        status=KnowledgeStatus.DEPRECATED,
        confidence=0.95,
    ))
    resultat = manager.retrieve_reliable("production arachidière", max_items=5)
    assert resultat["items"] == []
    assert resultat["reliable"] is False


def test_la_recherche_explicite_reste_exhaustive(manager):
    """`search_knowledge` sert l'exploration : elle montre tout, y compris le retiré."""
    _ajouter(manager, "Note archivée sur le budget municipal.", KnowledgeStatus.ARCHIVED)
    assert len(manager.search_knowledge("budget municipal")) == 1
