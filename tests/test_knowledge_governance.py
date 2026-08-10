"""
Tests de la gouvernance des connaissances (VOLET 05, chapitre 06).

Le chapitre exige un propriétaire par domaine. La plateforme ne tient pas
d'annuaire : elle rapporte ce qui a été déclaré et ce qui manque, sans jamais
inventer un propriétaire.
"""

import pytest

from src.knowledge_engine.knowledge_governance import (
    OWNERS_ENV, configured_owners, owner_of, unowned_domains,
)
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.types import KnowledgeDomain, KnowledgeItem, KnowledgeStatus


@pytest.fixture
def manager():
    """Gestionnaire de connaissances isolé pour un test."""
    km = KnowledgeManagerImpl()
    yield km
    km.cleanup()


def test_proprietaires_lus_dans_l_environnement(monkeypatch):
    """La déclaration est lue telle quelle, domaine par domaine."""
    monkeypatch.setenv(OWNERS_ENV, "legal:aissatou, technical:moussa")
    assert configured_owners() == {
        KnowledgeDomain.LEGAL: "aissatou",
        KnowledgeDomain.TECHNICAL: "moussa",
    }
    assert owner_of(KnowledgeDomain.LEGAL) == "aissatou"
    assert owner_of(KnowledgeDomain.BUSINESS) is None


def test_declaration_illisible_n_invente_pas_de_proprietaire(monkeypatch):
    """Entrée mal formée, domaine inconnu ou sujet vide : ignorés, pas devinés."""
    monkeypatch.setenv(OWNERS_ENV, "legal, agriculture:fatou, technical:, ai:awa")
    assert configured_owners() == {KnowledgeDomain.AI: "awa"}


def test_environnement_absent(monkeypatch):
    """Sans déclaration, aucun domaine n'a de propriétaire."""
    monkeypatch.delenv(OWNERS_ENV, raising=False)
    assert configured_owners() == {}


def test_seuls_les_domaines_utilises_sont_reclames(monkeypatch):
    """Un domaine vide n'a pas besoin de propriétaire."""
    monkeypatch.setenv(OWNERS_ENV, "legal:aissatou")
    manquants = unowned_domains([KnowledgeDomain.LEGAL, KnowledgeDomain.BUSINESS])
    assert manquants == [KnowledgeDomain.BUSINESS]
    assert unowned_domains([]) == []


def test_rapport_de_gouvernance(monkeypatch, manager):
    """Le rapport dit qui possède quoi, et ce que personne ne possède."""
    monkeypatch.setenv(OWNERS_ENV, "legal:aissatou")
    manager.add_knowledge(KnowledgeItem(content="Le code des marchés publics.",
                                        domain=KnowledgeDomain.LEGAL,
                                        status=KnowledgeStatus.APPROVED))
    manager.add_knowledge(KnowledgeItem(content="Le schéma de la base de connaissances.",
                                        domain=KnowledgeDomain.TECHNICAL))
    manager.add_knowledge(KnowledgeItem(content="Note dont personne n'a fixé le domaine."))

    rapport = manager.governance_report()

    assert rapport["domains"]["legal"]["items"] == 1
    assert rapport["domains"]["legal"]["owner"] == "aissatou"
    assert rapport["domains"]["legal"]["by_status"] == {"approved": 1}
    assert rapport["domains"]["technical"]["owner"] is None
    # « unspecified » est un domaine utilisé comme un autre : il apparaît sans
    # propriétaire, et le compteur dédié dit combien de connaissances sont à classer.
    assert set(rapport["unowned_domains"]) == {"technical", "unspecified"}
    assert rapport["unclassified_items"] == 1
    assert rapport["declared_owners"] == {"legal": "aissatou"}


def test_rapport_sur_une_base_vide(manager):
    """Une base vide ne produit aucun reproche."""
    rapport = manager.governance_report()
    assert rapport["domains"] == {}
    assert rapport["unowned_domains"] == []
    assert rapport["unclassified_items"] == 0
