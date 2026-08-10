"""
Tests du flux d'intégration des connaissances (VOLET 05, chapitre 08).

Le chapitre décrit un flux en cinq étapes : requête reçue, permissions
vérifiées, connaissance récupérée, résultats enrichis de métadonnées, réponse
délivrée. Ces tests couvrent les deux étapes qui traversent les frontières de
modules : la propagation du rôle, et l'enrichissement des résultats.
"""

import pytest

from src.agent.context import AgentContext
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.types import (
    KnowledgeDomain, KnowledgeItem, KnowledgeSensitivity, KnowledgeStatus,
)
from src.tools.rag.tool import RAGTool


class _StubRegistry:
    """Registre factice : ne fournit que les moteurs demandés par le test."""

    def __init__(self, engines=None):
        self._engines = engines or {}

    def try_get(self, name):
        return self._engines.get(name)


@pytest.fixture
def manager():
    """Gestionnaire de connaissances isolé pour un test."""
    km = KnowledgeManagerImpl()
    yield km
    km.cleanup()


@pytest.fixture
def rag(manager):
    """Outil RAG branché sur le gestionnaire du test."""
    outil = RAGTool()
    outil._knowledge_manager = manager
    return outil


def _peupler(manager) -> None:
    """Deux connaissances : une publique approuvée, une confidentielle."""
    manager.add_knowledge(KnowledgeItem(
        content="Le barème public des redevances portuaires de Dakar.",
        domain=KnowledgeDomain.BUSINESS,
        sensitivity=KnowledgeSensitivity.PUBLIC,
        status=KnowledgeStatus.APPROVED,
    ))
    manager.add_knowledge(KnowledgeItem(
        content="Le détail confidentiel des redevances portuaires négociées.",
        domain=KnowledgeDomain.BUSINESS,
        sensitivity=KnowledgeSensitivity.CONFIDENTIAL,
    ))


def test_le_rag_transmet_le_role(rag, manager):
    """L'outil RAG ne contourne pas le contrôle de lecture."""
    _peupler(manager)
    assert len(rag._op_search("redevances portuaires", limit=10, role="readonly")) == 1
    assert len(rag._op_search("redevances portuaires", limit=10, role="operator")) == 2
    # Sans rôle : lecture publique seulement.
    assert len(rag._op_search("redevances portuaires", limit=10)) == 1


def test_le_rag_transmet_le_role_pour_un_prompt(rag, manager):
    """Le contexte d'un prompt subit le même contrôle."""
    _peupler(manager)
    assert len(rag._op_retrieve_for_prompt("redevances portuaires", max_items=5,
                                           role="operator")) == 2
    assert len(rag._op_retrieve_for_prompt("redevances portuaires", max_items=5)) == 1


def test_les_resultats_portent_la_classification(rag, manager):
    """Étape 4 du flux : les résultats sont enrichis de leurs métadonnées."""
    _peupler(manager)
    resultat = rag._op_search("barème public redevances", limit=1, role="admin")[0]
    assert resultat["domain"] == "business"
    assert resultat["sensitivity"] == "public"
    assert resultat["status"] == "approved"


def test_le_contexte_d_agent_transmet_le_role_et_enrichit(manager):
    """Un agent lit selon son rôle et reçoit domaine et statut."""
    contexte = AgentContext(request="peu importe", agent_id="researcher",
                            registry=_StubRegistry({"knowledge": manager}))
    _peupler(manager)

    public = contexte.search_knowledge("redevances portuaires", limit=10)
    assert len(public) == 1
    assert public[0]["domain"] == "business"
    assert public[0]["status"] == "approved"

    complet = contexte.search_knowledge("redevances portuaires", limit=10, role="operator")
    assert len(complet) == 2


def test_aller_retour_par_l_outil_conserve_la_classification(rag, manager):
    """Relire, modifier et renvoyer une connaissance ne la fait pas disparaître.

    Les sorties sérialisent domaine, sensibilité et statut en chaînes ; sans la
    conversion inverse, la connaissance repart avec des chaînes là où le moteur
    attend des énumérations et sort silencieusement des résultats filtrés.
    """
    identifiant = rag._op_add({
        "content": "Le calendrier cultural du bassin arachidier.",
        "domain": "operational",
        "sensitivity": "internal",
    })["id"]

    relu = rag._op_get(identifiant)
    relu["content"] = "Le calendrier cultural révisé du bassin arachidier."
    assert rag._op_update(relu)["updated"] is True

    apres = rag._op_get(identifiant)
    assert apres["domain"] == "operational"
    assert apres["sensitivity"] == "internal"
    # Un contenu réécrit repart en brouillon, mais reste récupérable.
    assert apres["status"] == "draft"
    assert len(rag._op_retrieve_for_prompt("calendrier cultural", max_items=5,
                                           role="user")) == 1


def test_classification_invalide_est_refusee(rag):
    """Une valeur hors énumération est refusée à l'entrée, pas convertie au hasard."""
    with pytest.raises(ValueError, match="Domaine"):
        rag._op_add({"content": "Contenu de test suffisamment long.", "domain": "agriculture"})


def test_moteur_absent_ne_fait_pas_echouer_l_agent():
    """Sans moteur de connaissances, l'agent obtient une liste vide, pas une exception."""
    contexte = AgentContext(request="peu importe", agent_id="researcher",
                            registry=_StubRegistry())
    assert contexte.search_knowledge("n'importe quoi") == []
