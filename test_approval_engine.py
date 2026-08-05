"""
Tests du moteur d'approbation humaine (Phase 3, ADR-006).

Couverture :
- types : génération d'identifiants, sérialisation `to_dict`, reconstruction `from_mapping`
- `InMemoryApprovalStore` : soumission, décisions, filtres, statistiques, purge
- `ApprovalManagerImpl` : comportement best-effort (ne lève jamais)
- `EngineRegistry` : moteur `approval` disponible et partagé
- `AgentContext` : raccourcis `submit_approval` / `approve_approval` / `reject_approval`
- `BaseAgent` : portillon (statut `requires_approval`, portillon indisponible, défaut compatible)
- `RetryManager` : statuts terminaux (dont `requires_approval`)
- `ResultAggregator` : agrégation des actions en attente d'approbation
"""

import os
import sys

import pytest

# La racine du projet est ajoutée pour importer le paquet `src` : les imports
# relatifs internes (ex. `..approval_engine`) exigent ce niveau de paquetage.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.approval_engine.approval_manager import ApprovalManagerImpl
from src.approval_engine.approval_store import InMemoryApprovalStore
from src.approval_engine.types import (
    ApprovalRequest,
    ApprovalStatus,
    generate_approval_request_id,
)
from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.integration.engine_registry import EngineRegistry, get_shared_registry
from src.router.result_aggregator import ResultAggregator
from src.router.retry_manager import RetryManager


class _StubRegistry:
    """Registre minimal pour isoler les tests du contexte et des agents."""

    def __init__(self, engines=None):
        self._engines = dict(engines or {})

    def try_get(self, name):
        return self._engines.get(name)


# ----------------------------------------------------------------------
# Types
# ----------------------------------------------------------------------

def test_generate_approval_request_id_unique():
    """Chaque identifiant est unique et préfixé par ``appr_``."""
    first = generate_approval_request_id()
    second = generate_approval_request_id()
    assert first.startswith("appr_")
    assert first != second


def test_approval_request_to_dict_omits_empty_fields():
    """Les champs vides (None, métadonnées vides) ne sont pas sérialisés."""
    request = ApprovalRequest(agent_id="agent_a", request_id=None, action="act")
    payload = request.to_dict()
    assert payload["status"] == "pending"
    assert payload["agent_id"] == "agent_a"
    assert payload["action"] == "act"
    assert payload["id"] == request.id
    assert "created_at" in payload
    assert "created_at_unix" in payload
    assert "request_id" not in payload
    assert "description" not in payload
    assert "reason" not in payload
    assert "decided_by" not in payload
    assert "metadata" not in payload


def test_approval_request_to_dict_decided():
    """Une demande décidée expose sa décision, son motif et son auteur."""
    request = ApprovalRequest(
        agent_id="agent_a",
        request_id="req_1",
        action="act",
        description="Description",
        confidence=0.7,
        metadata={"cle": "valeur"},
    )
    request.status = ApprovalStatus.APPROVED.value
    request.decided_at = 1000.0
    request.reason = "Autorisé"
    request.decided_by = "operator"
    payload = request.to_dict()
    assert payload["request_id"] == "req_1"
    assert payload["description"] == "Description"
    assert payload["confidence"] == 0.7
    assert payload["metadata"] == {"cle": "valeur"}
    assert payload["status"] == "approved"
    assert payload["decided_at"] is not None
    assert payload["decided_at_unix"] == 1000.0
    assert payload["reason"] == "Autorisé"
    assert payload["decided_by"] == "operator"


def test_approval_request_from_mapping():
    """La reconstruction tolère les champs absents et reprend ceux fournis."""
    request = ApprovalRequest.from_mapping({
        "agent_id": "agent_a",
        "request_id": "req_1",
        "action": "act",
        "status": "approved",
        "id": "appr_fixe",
    })
    assert request.agent_id == "agent_a"
    assert request.request_id == "req_1"
    assert request.action == "act"
    assert request.status == "approved"
    assert request.id == "appr_fixe"

    minimal = ApprovalRequest.from_mapping({})
    assert minimal.agent_id == "unknown"
    assert minimal.action == "unknown"
    assert minimal.status == ApprovalStatus.PENDING.value


# ----------------------------------------------------------------------
# InMemoryApprovalStore
# ----------------------------------------------------------------------

def test_store_submit_and_get():
    """Une demande soumise est retrouvée par identifiant ; une absente vaut None."""
    store = InMemoryApprovalStore()
    request = ApprovalRequest(agent_id="agent_a", request_id="req_1", action="act")
    request_id = store.submit(request)
    assert request_id == request.id
    assert store.get(request_id) is request
    assert store.get("appr_inconnue") is None


def test_store_duplicate_submit_raises():
    """Une demande dont l'identifiant existe déjà est refusée."""
    store = InMemoryApprovalStore()
    request = ApprovalRequest(agent_id="agent_a", request_id="req_1", action="act")
    store.submit(request)
    with pytest.raises(ValueError):
        store.submit(request)


def test_store_approve_and_reject():
    """Une décision d'approbation consigne statut, motif, auteur et horodatage."""
    store = InMemoryApprovalStore()
    request = ApprovalRequest(agent_id="agent_a", request_id="req_1", action="act")
    request_id = store.submit(request)
    assert store.approve(request_id, reason="Autorisé", decided_by="operator") is True

    decided = store.get(request_id)
    assert decided.status == ApprovalStatus.APPROVED.value
    assert decided.reason == "Autorisé"
    assert decided.decided_by == "operator"
    assert decided.decided_at is not None

    # Une demande déjà décidée ne peut plus être modifiée
    assert store.approve(request_id, reason="Encore") is False
    assert store.reject(request_id, reason="Encore") is False


def test_store_reject_unknown():
    """Décider sur une demande absente retourne False."""
    store = InMemoryApprovalStore()
    assert store.reject("appr_inconnue") is False


def test_store_list_requests_filters_and_order():
    """`list_requests` trie de la plus récente à la plus ancienne et filtre."""
    store = InMemoryApprovalStore()
    r1 = ApprovalRequest(agent_id="agent_a", request_id="req_x", action="a1")
    r2 = ApprovalRequest(agent_id="agent_b", request_id="req_y", action="a2")
    r3 = ApprovalRequest(agent_id="agent_a", request_id="req_x", action="a3")
    store.submit(r1)
    store.submit(r2)
    store.submit(r3)

    assert [r.id for r in store.list_requests()] == [r3.id, r2.id, r1.id]
    assert [r.id for r in store.list_requests(limit=2)] == [r3.id, r2.id]

    store.approve(r2.id)
    assert [r.id for r in store.list_requests(status="approved")] == [r2.id]
    assert [r.id for r in store.list_requests(status="pending")] == [r3.id, r1.id]

    assert [r.id for r in store.list_requests(agent_id="agent_a")] == [r3.id, r1.id]
    assert [r.id for r in store.list_requests(request_id="req_x")] == [r3.id, r1.id]


def test_store_list_pending_oldest_first():
    """La file d'attente présente les demandes de la plus ancienne à la plus récente."""
    store = InMemoryApprovalStore()
    r1 = ApprovalRequest(agent_id="agent_a", request_id="req_1", action="a1")
    r2 = ApprovalRequest(agent_id="agent_b", request_id="req_2", action="a2")
    store.submit(r1)
    store.submit(r2)
    store.approve(r1.id)
    assert [r.id for r in store.list_pending()] == [r2.id]


def test_store_stats_and_count():
    """Les compteurs et statistiques reflètent l'état de la file."""
    store = InMemoryApprovalStore()
    r1 = ApprovalRequest(agent_id="agent_a", request_id="req_1", action="a1")
    r2 = ApprovalRequest(agent_id="agent_b", request_id="req_2", action="a2")
    store.submit(r1)
    store.submit(r2)
    store.approve(r1.id)

    assert store.count() == 2
    assert store.count(status="pending") == 1
    assert store.count(status="approved") == 1

    stats = store.stats()
    assert stats["total"] == 2
    assert stats["pending"] == 1
    assert stats["approved"] == 1
    assert stats["rejected"] == 0
    assert stats["expired"] == 0
    assert stats["by_status"]["approved"] == 1


def test_store_clear():
    """La purge vide la file et retourne le nombre de demandes supprimées."""
    store = InMemoryApprovalStore()
    store.submit(ApprovalRequest(agent_id="agent_a", request_id="req_1", action="a1"))
    store.submit(ApprovalRequest(agent_id="agent_b", request_id="req_2", action="a2"))
    assert store.clear() == 2
    assert store.count() == 0
    assert store.stats()["total"] == 0


# ----------------------------------------------------------------------
# ApprovalManagerImpl
# ----------------------------------------------------------------------

def test_manager_normal_flow():
    """La façade enchaîne soumission, consultation et décision sans erreur."""
    manager = ApprovalManagerImpl()
    request = ApprovalRequest(agent_id="agent_a", request_id="req_1", action="act")
    request_id = manager.submit(request)
    assert request_id == request.id
    assert manager.get(request_id) is request
    assert manager.get("appr_inconnue") is None
    assert manager.count() == 1
    assert len(manager.list_requests()) == 1
    assert len(manager.list_pending()) == 1
    assert manager.approve(request_id, reason="Autorisé", decided_by="operator") is True
    assert len(manager.list_pending()) == 0
    assert manager.count(status="approved") == 1
    assert manager.stats()["approved"] == 1


def test_manager_best_effort_on_broken_store():
    """Un backend défaillant ne fait jamais lever la façade : valeurs vides."""
    class BrokenStore:
        def submit(self, request):
            raise RuntimeError("backend indisponible")

        def get(self, request_id):
            raise RuntimeError("backend indisponible")

        def list_requests(self, limit=100, status=None, agent_id=None, request_id=None):
            raise RuntimeError("backend indisponible")

        def list_pending(self, limit=100):
            raise RuntimeError("backend indisponible")

        def count(self, status=None):
            raise RuntimeError("backend indisponible")

        def stats(self):
            raise RuntimeError("backend indisponible")

        def clear(self):
            raise RuntimeError("backend indisponible")

        def approve(self, request_id, reason=None, decided_by=None):
            raise RuntimeError("backend indisponible")

        def reject(self, request_id, reason=None, decided_by=None):
            raise RuntimeError("backend indisponible")

    manager = ApprovalManagerImpl(store=BrokenStore())
    request = ApprovalRequest(agent_id="agent_a", request_id="req_1", action="act")
    assert manager.submit(request) is None
    assert manager.get("appr_1") is None
    assert manager.list_requests() == []
    assert manager.list_pending() == []
    assert manager.count() == 0
    assert manager.stats() == {}
    assert manager.clear() == 0
    assert manager.approve("appr_1") is False
    assert manager.reject("appr_1") is False


# ----------------------------------------------------------------------
# EngineRegistry
# ----------------------------------------------------------------------

def test_registry_approval_available():
    """Le registre construit le moteur d'approbation à la demande."""
    registry = EngineRegistry()
    engine = registry.get("approval")
    assert engine is not None
    assert engine.__class__.__name__ == "ApprovalManagerImpl"
    # La construction est paresseuse et idempotente
    assert registry.try_get("approval") is engine
    assert "approval" in registry.available_engines()


def test_shared_registry_approval():
    """Le registre partagé expose le même moteur d'approbation."""
    shared = get_shared_registry()
    engine = shared.approval
    assert engine is not None
    assert engine.__class__.__name__ == "ApprovalManagerImpl"


# ----------------------------------------------------------------------
# AgentContext
# ----------------------------------------------------------------------

def test_context_submit_approval():
    """Le raccourci soumet une demande complète auprès du moteur."""
    manager = ApprovalManagerImpl()
    registry = _StubRegistry({"approval": manager})
    context = AgentContext(request="Faire X", agent_id="agent_ctx", registry=registry)
    request_id = context.submit_approval(
        "agent:agent_ctx", description="Décision sensible", confidence=0.8
    )
    assert request_id is not None
    assert request_id.startswith("appr_")
    request = manager.get(request_id)
    assert request.status == ApprovalStatus.PENDING.value
    assert request.agent_id == "agent_ctx"
    assert request.description == "Décision sensible"
    assert request.confidence == 0.8


def test_context_approve_approval():
    """L'approbation via le contexte décide la demande et la trace."""
    manager = ApprovalManagerImpl()
    registry = _StubRegistry({"approval": manager})
    context = AgentContext(request="Faire X", agent_id="agent_ctx", registry=registry)
    request_id = context.submit_approval("agent:agent_ctx")
    assert context.approve_approval(request_id, reason="Autorisé", decided_by="operator") is True
    request = manager.get(request_id)
    assert request.status == ApprovalStatus.APPROVED.value
    assert request.reason == "Autorisé"
    assert request.decided_by == "operator"
    # Une demande déjà décidée ne peut pas être re-décidée
    assert context.approve_approval(request_id) is False


def test_context_reject_approval():
    """Le refus via le contexte décide la demande et conserve son auteur."""
    manager = ApprovalManagerImpl()
    registry = _StubRegistry({"approval": manager})
    context = AgentContext(request="Faire X", agent_id="agent_ctx", registry=registry)
    request_id = context.submit_approval("agent:agent_ctx")
    assert context.reject_approval(request_id, reason="Refusé", decided_by="auditor") is True
    request = manager.get(request_id)
    assert request.status == ApprovalStatus.REJECTED.value
    assert request.decided_by == "auditor"


def test_context_approval_unavailable():
    """Sans moteur d'approbation, les raccourcis retournent des valeurs vides."""
    context = AgentContext(request="Faire X", agent_id="agent_ctx", registry=_StubRegistry({}))
    assert context.submit_approval("agent:agent_ctx") is None
    assert context.approve_approval("appr_1") is False
    assert context.reject_approval("appr_1") is False


# ----------------------------------------------------------------------
# BaseAgent : portillon d'approbation
# ----------------------------------------------------------------------

class _GatedAgent(BaseAgent):
    """Agent dont l'action passe par le portillon d'approbation humaine."""

    agent_id = "gated_test_agent"
    approval_required = True
    approval_description = "Action sensible à faire valider"
    approval_confidence = 0.85

    def perform(self, context):
        return {"action": "effectuée"}


class _NormalAgent(BaseAgent):
    """Agent ordinaire, sans portillon (comportement historique)."""

    agent_id = "normal_test_agent"

    def perform(self, context):
        return {"done": True}


def test_base_agent_default_requires_no_approval():
    """Par défaut, aucun agent n'est soumis au portillon (rétro-compatibilité)."""
    assert _NormalAgent.approval_required is False


def test_base_agent_normal_success():
    """Un agent non portillonné retourne un succès sans demande d'approbation."""
    agent = _NormalAgent()
    context = AgentContext(
        request="Tâche simple",
        agent_id=_NormalAgent.agent_id,
        registry=_StubRegistry({}),
    )
    result = agent.run(context)
    assert result["status"] == "success"
    assert result["result"] == {"done": True}
    assert result["agent"] == "normal_test_agent"
    assert "approval_request_id" not in result


def test_base_agent_gated_requires_approval():
    """Une action portillonnée est suspendue avec une demande d'approbation."""
    agent = _GatedAgent()
    manager = ApprovalManagerImpl()
    registry = _StubRegistry({"approval": manager})
    context = AgentContext(
        request="Tâche sensible",
        agent_id=_GatedAgent.agent_id,
        registry=registry,
    )
    result = agent.run(context)
    assert result["status"] == "requires_approval"
    approval_request_id = result["approval_request_id"]
    assert approval_request_id is not None
    assert approval_request_id.startswith("appr_")

    # L'action est suspendue, pas exécutée
    request = manager.get(approval_request_id)
    assert request.status == ApprovalStatus.PENDING.value
    assert request.action == "agent:gated_test_agent"
    assert request.description == "Action sensible à faire valider"
    assert request.confidence == 0.85


def test_base_agent_gated_portillon_indisponible_erreur():
    """Sans portillon, une action sensible échoue : elle ne peut être validée."""
    agent = _GatedAgent()
    context = AgentContext(
        request="Tâche sensible",
        agent_id=_GatedAgent.agent_id,
        registry=_StubRegistry({}),
    )
    result = agent.run(context)
    assert result["status"] == "error"
    assert "portillon" in result["error"]


# ----------------------------------------------------------------------
# RetryManager : statuts terminaux
# ----------------------------------------------------------------------

def test_retry_requires_approval_is_terminal():
    """Une action en attente d'approbation n'est jamais ré-exécutée."""
    calls = []

    def callable(agent_config, input_data):
        calls.append(1)
        return {
            "agent": "agent_x",
            "status": "requires_approval",
            "approval_request_id": "appr_1",
        }

    manager = RetryManager(max_attempts=3, delay_seconds=0)
    result = manager.execute_with_retry(callable, {"id": "agent_x"}, "data")
    assert result["status"] == "requires_approval"
    assert len(calls) == 1


def test_retry_success_is_terminal():
    """Un succès termine immédiatement les tentatives."""
    calls = []

    def callable(agent_config, input_data):
        calls.append(1)
        return {"agent": "agent_x", "status": "success", "result": "ok"}

    manager = RetryManager(max_attempts=3, delay_seconds=0)
    result = manager.execute_with_retry(callable, {"id": "agent_x"}, "data")
    assert result["status"] == "success"
    assert len(calls) == 1


def test_retry_skipped_is_terminal():
    """Un agent ignoré (skipped) ne déclenche pas de nouvelle tentative."""
    calls = []

    def callable(agent_config, input_data):
        calls.append(1)
        return {"agent": "agent_x", "status": "skipped"}

    manager = RetryManager(max_attempts=3, delay_seconds=0)
    result = manager.execute_with_retry(callable, {"id": "agent_x"}, "data")
    assert result["status"] == "skipped"
    assert len(calls) == 1


def test_retry_error_is_retried():
    """Une vraie erreur est retentée jusqu'à la limite configurée."""
    calls = []

    def callable(agent_config, input_data):
        calls.append(1)
        return {"agent": "agent_x", "status": "error", "error": "boom"}

    manager = RetryManager(max_attempts=3, delay_seconds=0)
    result = manager.execute_with_retry(callable, {"id": "agent_x"}, "data")
    assert result["status"] == "error"
    assert len(calls) == 3


# ----------------------------------------------------------------------
# ResultAggregator : agrégation des actions en attente
# ----------------------------------------------------------------------

def test_aggregate_all_success():
    """Tous les agents réussis : résultat agrégé combiné."""
    aggregator = ResultAggregator()
    combined = aggregator.aggregate([
        {"agent": "a", "status": "success", "result": "x"},
        {"agent": "b", "status": "success", "result": "y"},
    ])
    assert combined["status"] == "success"
    assert combined["aggregated_result"] == ["x", "y"]


def test_aggregate_requires_approval():
    """Une action en attente d'approbation suspend le statut global."""
    aggregator = ResultAggregator()
    combined = aggregator.aggregate([
        {"agent": "a", "status": "success", "result": "x"},
        {"agent": "b", "status": "requires_approval", "approval_request_id": "appr_1"},
    ])
    assert combined["status"] == "requires_approval"
    assert combined["approval_request_ids"] == ["appr_1"]
    # La partie réussie reste consultable
    assert combined["aggregated_result"] == ["x"]


def test_aggregate_requires_approval_without_success():
    """Sans succès, la partie agrégée reste vide mais le statut est suspendu."""
    aggregator = ResultAggregator()
    combined = aggregator.aggregate([
        {"agent": "b", "status": "requires_approval", "approval_request_id": "appr_1"},
    ])
    assert combined["status"] == "requires_approval"
    assert combined["approval_request_ids"] == ["appr_1"]
    assert combined["aggregated_result"] == []


def test_aggregate_errors_priority():
    """Une erreur prime sur une demande d'approbation dans le statut global."""
    aggregator = ResultAggregator()
    combined = aggregator.aggregate([
        {"agent": "a", "status": "success", "result": "x"},
        {"agent": "b", "status": "requires_approval", "approval_request_id": "appr_1"},
        {"agent": "c", "status": "error", "error": "boom"},
    ])
    assert combined["status"] == "partial_success"
    assert combined["errors"] == ["boom"]


def test_aggregate_empty():
    """Aucun agent exécuté : succès sans résultat."""
    aggregator = ResultAggregator()
    combined = aggregator.aggregate([])
    assert combined["status"] == "success"
    assert combined["aggregated_result"] is None
