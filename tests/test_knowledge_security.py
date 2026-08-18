"""
Tests du contrôle de lecture par sensibilité (VOLET 05, chapitre 07).

« Least privilege access » et « restrict sensitive knowledge » : un rôle ne lit
que ce que sa place autorise, et un appelant sans rôle ne lit que le public.
"""

import pytest

from src.api.rbac import Role
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.knowledge_security import (
    PUBLIC_ONLY, READABLE_BY_ROLE, can_read, filter_readable, readable_sensitivities,
)
from src.knowledge_engine.types import KnowledgeItem, KnowledgeSensitivity


@pytest.fixture
def manager():
    """Gestionnaire de connaissances isolé pour un test."""
    km = KnowledgeManagerImpl()
    yield km
    km.cleanup()


def test_les_roles_de_la_plateforme_sont_tous_couverts():
    """La table de lecture et les rôles RBAC ne doivent pas diverger."""
    assert {r.value for r in Role} == set(READABLE_BY_ROLE)


def test_hierarchie_de_lecture():
    """Chaque rôle lit ce que lit le précédent, et rien de plus par accident."""
    lecture = {role: readable_sensitivities(role) for role in READABLE_BY_ROLE}
    assert lecture["readonly"] < lecture["user"] < lecture["operator"] < lecture["admin"]
    assert lecture["admin"] == frozenset(KnowledgeSensitivity)
    assert KnowledgeSensitivity.RESTRICTED not in lecture["operator"]


@pytest.mark.parametrize("role", [None, "", "  ", "inconnu", "root"])
def test_role_absent_ou_inconnu_ne_lit_que_le_public(role):
    """Le défaut d'un contrôle d'accès est le refus."""
    assert readable_sensitivities(role) == PUBLIC_ONLY
    assert can_read(role, KnowledgeItem(content="Note publique.",
                                        sensitivity=KnowledgeSensitivity.PUBLIC))
    assert not can_read(role, KnowledgeItem(content="Note interne.",
                                            sensitivity=KnowledgeSensitivity.INTERNAL))


def test_role_insensible_a_la_casse_et_aux_espaces():
    """« Admin » et « admin » désignent le même rôle."""
    assert readable_sensitivities(" Admin ") == readable_sensitivities("admin")


def test_filtre_de_liste():
    """Le filtrage retire les éléments interdits sans rien signaler."""
    items = [
        KnowledgeItem(content="Barème public des redevances.", sensitivity=KnowledgeSensitivity.PUBLIC),
        KnowledgeItem(content="Procédure interne de validation.", sensitivity=KnowledgeSensitivity.INTERNAL),
        KnowledgeItem(content="Grille salariale détaillée.", sensitivity=KnowledgeSensitivity.CONFIDENTIAL),
    ]
    lisibles = filter_readable("user", items)
    assert [k.sensitivity for k in lisibles] == [KnowledgeSensitivity.PUBLIC,
                                                 KnowledgeSensitivity.INTERNAL]


def test_la_recherche_respecte_le_role(manager):
    """Une connaissance confidentielle n'apparaît pas à un rôle qui n'y a pas droit."""
    manager.add_knowledge(KnowledgeItem(content="Le barème public des redevances portuaires.",
                                        sensitivity=KnowledgeSensitivity.PUBLIC))
    manager.add_knowledge(KnowledgeItem(content="Le détail confidentiel des redevances portuaires.",
                                        sensitivity=KnowledgeSensitivity.CONFIDENTIAL))

    assert len(manager.search_knowledge("redevances portuaires", limit=10, role="readonly")) == 1
    assert len(manager.search_knowledge("redevances portuaires", limit=10, role="operator")) == 2
    # Sans rôle, la lecture est publique — y compris pour un appel interne.
    assert len(manager.search_knowledge("redevances portuaires", limit=10)) == 1


def test_le_rag_respecte_le_role(manager):
    """Le contexte d'un agent ne contient pas ce que son rôle ne peut pas lire."""
    manager.add_knowledge(KnowledgeItem(content="Note restreinte sur la stratégie tarifaire.",
                                        sensitivity=KnowledgeSensitivity.RESTRICTED))
    assert manager.retrieve_for_prompt("stratégie tarifaire", max_items=5, role="operator") == []
    assert len(manager.retrieve_for_prompt("stratégie tarifaire", max_items=5, role="admin")) == 1


def test_retrieve_reliable_respecte_le_role(manager):
    """La récupération fiable applique le même contrôle."""
    manager.add_knowledge(KnowledgeItem(content="Chiffre confidentiel sur les marges.",
                                        sensitivity=KnowledgeSensitivity.CONFIDENTIAL,
                                        confidence=0.9))
    assert manager.retrieve_reliable("marges", max_items=5, role="user")["items"] == []
    assert len(manager.retrieve_reliable("marges", max_items=5, role="admin")["items"]) == 1
