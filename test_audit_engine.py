#!/usr/bin/env python3
"""
Tests du moteur d'audit de GalSen IA.

Couvre :
  - le générateur d'identifiants de requête
  - les modèles de données (AuditEvent, KnowledgeSourceRef)
  - le stockage en mémoire (filtres, recherche, statistiques)
  - le gestionnaire d'audit tolérant aux pannes
  - l'intégration avec AgentContext (consignation des actions courantes)
  - l'intégration avec EngineRegistry (moteur 'audit' exposé)
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agent.context import AgentContext
from src.audit_engine.audit_manager import AuditManagerImpl
from src.audit_engine.audit_store import InMemoryAuditStore
from src.audit_engine.interfaces import AuditStore
from src.audit_engine.types import (
    AuditEvent,
    AuditEventType,
    AuditStatus,
    KnowledgeSourceRef,
    generate_request_id,
)
from src.integration.engine_registry import ENGINE_NAMES, EngineRegistry


# ----------------------------------------------------------------------
# Registre factice pour isoler AgentContext du vrai registre
# ----------------------------------------------------------------------
class _StubRegistry:
    """Registre factice : ne fournit que les moteurs demandés par le test."""

    def __init__(self, engines=None):
        self._engines = engines or {}

    def try_get(self, name):
        return self._engines.get(name)


class _FakeKnowledgeItem:
    """Connaissance minimale renvoyée par le moteur de connaissances factice."""

    def __init__(self, item_id, content, confidence):
        self.id = item_id
        self.content = content
        self.confidence = confidence
        self.tags = ["test"]


class _FakeKnowledgeEngine:
    """Moteur de connaissances factice renvoyant un résultat fixe."""

    def __init__(self):
        self.searched_queries = []

    def search_knowledge(self, query, limit=5):
        self.searched_queries.append(query)
        return [
            _FakeKnowledgeItem(
                "k1", "Le riz est la culture principale du Sénégal.", 0.9
            )
        ]


class _FakeModelItem:
    """Modèle sélectionné par le moteur de modèles factice."""

    def __init__(self, model_id):
        self.model_id = model_id


class _FakeModelEngine:
    """Moteur de modèles factice produisant une réponse fixe."""

    def select_model_for_task(self, requirements):
        return _FakeModelItem("model-local-test")

    async def generate_text(self, model_item, prompt):
        return "Réponse générée par le test."


class _FakeToolEngine:
    """Moteur d'outils factice : un outil actif, un outil désactivé."""

    def is_tool_enabled(self, tool_id):
        return tool_id != "disabled_tool"

    def execute_tool(self, tool_id, *args, **kwargs):
        return {"echo": tool_id}


class _BrokenStore(AuditStore):
    """Stockage d'audit qui échoue systématiquement, pour tester la tolérance."""

    def save(self, event):
        raise RuntimeError("stockage indisponible")

    def get(self, event_id):
        return None

    def list_events(self, limit=100, **filters):
        return []

    def search_events(self, query, limit=50):
        return []

    def count(self, **filters):
        return 0

    def clear(self):
        return 0

    def stats(self):
        return {}


def _make_manager():
    """Construit un gestionnaire d'audit neuf, isolé de tout état partagé."""
    return AuditManagerImpl(InMemoryAuditStore())


# ----------------------------------------------------------------------
# Identifiants de requête
# ----------------------------------------------------------------------
def test_generate_request_id_format():
    """L'identifiant est préfixé par 'req_' et suivi de douze hexadécimaux."""
    request_id = generate_request_id()
    assert request_id.startswith("req_")
    assert len(request_id) == len("req_") + 12
    int(request_id[len("req_"):], 16)


def test_generate_request_id_uniqueness():
    """Deux appels successifs produisent des identifiants distincts."""
    assert generate_request_id() != generate_request_id()


# ----------------------------------------------------------------------
# KnowledgeSourceRef
# ----------------------------------------------------------------------
def test_knowledge_source_ref_to_dict_omits_empty_fields():
    """Les champs vides ne sont pas sérialisés."""
    ref = KnowledgeSourceRef(id="src1", title="Rapport officiel")
    payload = ref.to_dict()
    assert payload == {"id": "src1", "title": "Rapport officiel"}


def test_knowledge_source_ref_from_mapping_round_trip():
    """from_mapping reconstitue la référence et ignore les champs inconnus."""
    source = KnowledgeSourceRef(
        id="src2",
        source_category="official",
        priority="high",
        confidence=0.95,
        citation="Rapport 2025",
    )
    rebuilt = KnowledgeSourceRef.from_mapping(source.to_dict())
    assert rebuilt.id == "src2"
    assert rebuilt.source_category == "official"
    assert rebuilt.priority == "high"
    assert rebuilt.confidence == 0.95
    assert rebuilt.citation == "Rapport 2025"


# ----------------------------------------------------------------------
# AuditEvent.to_dict
# ----------------------------------------------------------------------
def test_audit_event_to_dict_full_serialization():
    """Un événement complet est sérialisé avec tous ses champs et valeurs."""
    event = AuditEvent(
        event_type=AuditEventType.AGENT,
        action="agent:planner",
        agent_id="planner",
        request_id="req_abc123",
        user_request="Planifier le projet",
        model_id="model-local-test",
        confidence=0.8,
        knowledge_sources=[{"id": "src1"}],
        status=AuditStatus.FAILURE,
        execution_time_seconds=1.25,
        detail="Échec du plan",
        metadata={"engines_used": ["memory"]},
        timestamp=1_700_000_000.0,
    )
    payload = event.to_dict()
    assert payload["id"] == event.id
    assert payload["event_type"] == "agent"
    assert payload["action"] == "agent:planner"
    assert payload["status"] == "failure"
    assert payload["agent_id"] == "planner"
    assert payload["request_id"] == "req_abc123"
    assert payload["user_request"] == "Planifier le projet"
    assert payload["model_id"] == "model-local-test"
    assert payload["confidence"] == 0.8
    assert payload["knowledge_sources"] == [{"id": "src1"}]
    assert payload["execution_time_seconds"] == 1.25
    assert payload["detail"] == "Échec du plan"
    assert payload["metadata"] == {"engines_used": ["memory"]}
    # L'horodatage est présent au format ISO (UTC) et en secondes Unix
    assert "T" in payload["timestamp"]
    assert payload["timestamp"].endswith("+00:00")
    assert payload["timestamp_unix"] == 1_700_000_000.0


def test_audit_event_to_dict_omits_empty_fields():
    """Les champs facultatifs vides ne sont pas présents dans la sérialisation."""
    event = AuditEvent(event_type=AuditEventType.REQUEST, action="execute_task")
    payload = event.to_dict()
    for key in ("agent_id", "request_id", "user_request", "model_id",
                "confidence", "knowledge_sources", "execution_time_seconds",
                "detail", "metadata"):
        assert key not in payload
    # Les champs obligatoires sont toujours présents
    assert payload["event_type"] == "request"
    assert payload["action"] == "execute_task"
    assert payload["status"] == "success"


# ----------------------------------------------------------------------
# InMemoryAuditStore
# ----------------------------------------------------------------------
def test_store_save_and_get_round_trip():
    """Un événement sauvegardé est retrouvable par son identifiant."""
    store = InMemoryAuditStore()
    event = AuditEvent(event_type=AuditEventType.REQUEST, action="process_request")
    event_id = store.save(event)
    assert store.get(event_id) is event


def test_store_list_events_newest_first():
    """La liste retourne les événements du plus récent au plus ancien."""
    store = InMemoryAuditStore()
    first = store.save(AuditEvent(event_type=AuditEventType.AGENT, action="first"))
    second = store.save(AuditEvent(event_type=AuditEventType.TOOL, action="second"))
    events = store.list_events()
    assert [event.action for event in events] == ["second", "first"]
    assert store.list_events(limit=1)[0].action == "second"
    assert store.get(first) is not None and store.get(second) is not None


def test_store_filters_by_event_type_and_status():
    """Les filtres event_type et status acceptent chaînes et énumérations."""
    store = InMemoryAuditStore()
    store.save(AuditEvent(event_type=AuditEventType.REQUEST, action="a"))
    store.save(AuditEvent(event_type=AuditEventType.AGENT, action="b"))
    store.save(AuditEvent(event_type=AuditEventType.AGENT, action="c",
                          status=AuditStatus.FAILURE))
    assert len(store.list_events(event_type="agent")) == 2
    assert len(store.list_events(event_type=AuditEventType.REQUEST)) == 1
    assert len(store.list_events(event_type=AuditEventType.AGENT,
                                 status="failure")) == 1
    assert len(store.list_events(status=AuditStatus.SUCCESS)) == 2


def test_store_filters_by_ids():
    """Les filtres agent_id et request_id sélectionnent les événements attendus."""
    store = InMemoryAuditStore()
    store.save(AuditEvent(event_type=AuditEventType.AGENT, action="a",
                          agent_id="planner", request_id="req_1"))
    store.save(AuditEvent(event_type=AuditEventType.AGENT, action="b",
                          agent_id="coder", request_id="req_2"))
    assert len(store.list_events(agent_id="planner")) == 1
    assert len(store.list_events(request_id="req_2")) == 1
    assert len(store.list_events(agent_id="inconnu")) == 0


def test_store_filters_by_time_window():
    """Les filtres since/until bornent l'intervalle de temps des événements."""
    store = InMemoryAuditStore()
    store.save(AuditEvent(event_type=AuditEventType.REQUEST, action="old",
                          timestamp=100.0))
    store.save(AuditEvent(event_type=AuditEventType.REQUEST, action="mid",
                          timestamp=200.0))
    store.save(AuditEvent(event_type=AuditEventType.REQUEST, action="new",
                          timestamp=300.0))
    since = [event.action for event in store.list_events(since=150.0)]
    assert since == ["new", "mid"]
    until = [event.action for event in store.list_events(until=250.0)]
    assert until == ["mid", "old"]
    window = store.list_events(since=150.0, until=250.0)
    assert [event.action for event in window] == ["mid"]


def test_store_search_events_case_insensitive():
    """La recherche textuelle ignore la casse et couvre plusieurs champs."""
    store = InMemoryAuditStore()
    store.save(AuditEvent(event_type=AuditEventType.AGENT, action="agent:planner",
                          user_request="Bonjour GalSen", agent_id="planner"))
    store.save(AuditEvent(event_type=AuditEventType.GENERATION, action="generate",
                          model_id="model-local-test"))
    assert len(store.search_events("GALSEN")) == 1
    assert store.search_events("GALSEN")[0].action == "agent:planner"
    assert len(store.search_events("model-local")) == 1
    assert len(store.search_events("introuvable")) == 0


def test_store_count_with_and_without_filters():
    """count retourne le total, ou le nombre d'événements filtrés."""
    store = InMemoryAuditStore()
    store.save(AuditEvent(event_type=AuditEventType.REQUEST, action="a"))
    store.save(AuditEvent(event_type=AuditEventType.AGENT, action="b"))
    store.save(AuditEvent(event_type=AuditEventType.AGENT, action="c",
                          status=AuditStatus.FAILURE))
    assert store.count() == 3
    assert store.count(event_type="agent") == 2
    assert store.count(status="failure") == 1


def test_store_clear_empties_and_returns_count():
    """clear supprime tous les événements et retourne le nombre supprimé."""
    store = InMemoryAuditStore()
    store.save(AuditEvent(event_type=AuditEventType.REQUEST, action="a"))
    store.save(AuditEvent(event_type=AuditEventType.REQUEST, action="b"))
    assert store.clear() == 2
    assert store.count() == 0
    assert store.list_events() == []


def test_store_stats_aggregation():
    """Les statistiques agrègent statuts, types, agents et durées."""
    store = InMemoryAuditStore()
    store.save(AuditEvent(event_type=AuditEventType.AGENT, action="a",
                          agent_id="planner", status=AuditStatus.SUCCESS,
                          execution_time_seconds=1.0, timestamp=100.0))
    store.save(AuditEvent(event_type=AuditEventType.AGENT, action="b",
                          agent_id="coder", status=AuditStatus.FAILURE,
                          execution_time_seconds=3.0, timestamp=200.0))
    store.save(AuditEvent(event_type=AuditEventType.TOOL, action="c",
                          agent_id=None, status=AuditStatus.SUCCESS,
                          execution_time_seconds=None, timestamp=300.0))
    stats = store.stats()
    assert stats["total_events"] == 3
    assert stats["by_status"] == {"success": 2, "failure": 1}
    assert stats["by_type"] == {"agent": 2, "tool": 1}
    assert stats["by_agent"] == {"planner": 1, "coder": 1, "unknown": 1}
    # La moyenne ne porte que sur les événements chronométrés
    assert stats["average_execution_time_seconds"] == 2.0
    assert stats["oldest_timestamp_unix"] == 100.0
    assert stats["newest_timestamp_unix"] == 300.0
    assert stats["time_span_seconds"] == 200.0


# ----------------------------------------------------------------------
# AuditManagerImpl
# ----------------------------------------------------------------------
def test_manager_record_and_get():
    """Le gestionnaire consigne un événement et le retrouve."""
    manager = _make_manager()
    event = AuditEvent(event_type=AuditEventType.REQUEST, action="execute_task",
                       request_id="req_abc")
    event_id = manager.record(event)
    assert event_id == event.id
    assert manager.get_event(event_id) is event
    assert manager.get_event("evt_inconnu") is None


def test_manager_list_search_count_clear():
    """Le gestionnaire délègue filtres, recherche et nettoyage au stockage."""
    manager = _make_manager()
    manager.record(AuditEvent(event_type=AuditEventType.AGENT, action="agent:planner",
                              user_request="Planifier"))
    manager.record(AuditEvent(event_type=AuditEventType.TOOL, action="tool:web_search",
                              user_request="Rechercher"))
    assert len(manager.list_events()) == 2
    assert len(manager.list_events(event_type="agent")) == 1
    assert len(manager.search_events("Rechercher")) == 1
    assert manager.count() == 2
    assert manager.count(event_type="tool") == 1
    assert manager.clear() == 2
    assert manager.count() == 0


def test_manager_stats():
    """Le gestionnaire expose les statistiques du stockage."""
    manager = _make_manager()
    manager.record(AuditEvent(event_type=AuditEventType.REQUEST, action="a",
                              execution_time_seconds=2.0))
    assert manager.stats()["total_events"] == 1
    assert manager.stats()["by_type"] == {"request": 1}


def test_manager_export_json_round_trip():
    """L'export JSON est lisible et conserve les accents (ensure_ascii=False)."""
    manager = _make_manager()
    manager.record(AuditEvent(event_type=AuditEventType.REQUEST, action="execute_task",
                              user_request="Bonjour, étude de marché au Sénégal",
                              confidence=0.85))
    payload = manager.export_json()
    data = json.loads(payload)
    assert data["total"] == 1
    assert data["events"][0]["action"] == "execute_task"
    assert data["events"][0]["confidence"] == 0.85
    assert "Sénégal" in payload


def test_manager_never_raises_on_broken_store():
    """Un stockage défaillant ne fait jamais échouer le gestionnaire."""
    manager = AuditManagerImpl(_BrokenStore())
    event = AuditEvent(event_type=AuditEventType.REQUEST, action="execute_task")
    assert manager.record(event) == ""
    assert manager.get_event(event.id) is None
    assert manager.list_events() == []
    assert manager.search_events("test") == []
    assert manager.count() == 0
    assert manager.clear() == 0
    assert manager.stats() == {}
    # L'export reste fonctionnel : il produit un JSON valide, vide, sans erreur
    data = json.loads(manager.export_json())
    assert data["total"] == 0
    assert data["events"] == []


# ----------------------------------------------------------------------
# Intégration AgentContext
# ----------------------------------------------------------------------
def test_context_record_audit_fills_identity_fields():
    """L'événement consigné porte l'identité du contexte et la requête."""
    manager = _make_manager()
    context = AgentContext(
        request="Quelle est la population du Sénégal ?",
        agent_id="researcher",
        registry=_StubRegistry({"audit": manager}),
        request_id="req_fixed_001",
    )
    event_id = context.record_audit(
        AuditEventType.REQUEST,
        "process_request",
        status=AuditStatus.SUCCESS,
        execution_time_seconds=0.5,
    )
    assert event_id is not None
    event = manager.get_event(event_id)
    assert event.agent_id == "researcher"
    assert event.request_id == "req_fixed_001"
    assert event.user_request == "Quelle est la population du Sénégal ?"
    assert event.status == AuditStatus.SUCCESS
    assert event.execution_time_seconds == 0.5


def test_context_record_audit_normalizes_strings():
    """Les chaînes 'tool' et 'error' sont converties en énumérations correctes."""
    manager = _make_manager()
    context = AgentContext(
        request="Test",
        agent_id="tester",
        registry=_StubRegistry({"audit": manager}),
    )
    event_id = context.record_audit("tool", "tool:web_search", status="error")
    event = manager.get_event(event_id)
    assert event.event_type == AuditEventType.TOOL
    assert event.status == AuditStatus.FAILURE


def test_context_record_audit_returns_none_without_audit_engine():
    """Sans moteur d'audit, la consignation retourne None sans exception."""
    context = AgentContext(
        request="Test",
        agent_id="tester",
        registry=_StubRegistry(),
    )
    assert context.record_audit(AuditEventType.REQUEST, "anything") is None
    assert context.audit is None


def test_context_derive_preserves_request_id():
    """Le contexte dérivé conserve l'identifiant de requête."""
    manager = _make_manager()
    context = AgentContext(
        request="Test",
        agent_id="parent",
        registry=_StubRegistry({"audit": manager}),
        request_id="req_preserved",
    )
    derived = context.derive("child")
    assert derived.request_id == "req_preserved"
    event_id = derived.record_audit(AuditEventType.AGENT, "agent:child")
    assert manager.get_event(event_id).request_id == "req_preserved"


def test_context_request_id_auto_generated():
    """Sans request_id fourni, le contexte en génère un unique."""
    first = AgentContext(request="A", agent_id="a", registry=_StubRegistry())
    second = AgentContext(request="B", agent_id="b", registry=_StubRegistry())
    assert first.request_id.startswith("req_")
    assert first.request_id != second.request_id


def test_context_search_knowledge_records_unavailable():
    """Sans moteur de connaissances, une recherche est consignée en UNAVAILABLE."""
    manager = _make_manager()
    context = AgentContext(
        request="Rechercher le climat du Sahel",
        agent_id="researcher",
        registry=_StubRegistry({"audit": manager}),
    )
    results = context.search_knowledge("climat sahel")
    assert results == []
    events = manager.list_events(event_type="knowledge")
    assert len(events) == 1
    assert events[0].action == "search_knowledge"
    assert events[0].status == AuditStatus.UNAVAILABLE


def test_context_search_knowledge_records_success():
    """Une recherche fructueuse consigne le nombre de résultats et la confiance."""
    manager = _make_manager()
    context = AgentContext(
        request="Rechercher la culture du riz",
        agent_id="researcher",
        registry=_StubRegistry({
            "audit": manager,
            "knowledge": _FakeKnowledgeEngine(),
        }),
    )
    results = context.search_knowledge("riz")
    assert len(results) == 1
    assert results[0]["id"] == "k1"
    events = manager.list_events(event_type="knowledge")
    assert len(events) == 1
    assert events[0].status == AuditStatus.SUCCESS
    assert events[0].confidence == 0.9
    assert events[0].knowledge_sources == [{"id": "k1", "confidence": 0.9}]


def test_context_add_knowledge_records_unavailable():
    """Sans moteur de connaissances, un ajout est consigné en UNAVAILABLE."""
    manager = _make_manager()
    context = AgentContext(
        request="Ajouter une connaissance",
        agent_id="researcher",
        registry=_StubRegistry({"audit": manager}),
    )
    assert context.add_knowledge("Le Sénégal a une façade atlantique.") is None
    events = manager.list_events(event_type="knowledge")
    assert len(events) == 1
    assert events[0].action == "add_knowledge"
    assert events[0].status == AuditStatus.UNAVAILABLE


def test_context_use_tool_records_unavailable():
    """Sans moteur d'outils, l'exécution est consignée en UNAVAILABLE."""
    manager = _make_manager()
    context = AgentContext(
        request="Exécuter un outil",
        agent_id="coder",
        registry=_StubRegistry({"audit": manager}),
    )
    outcome = context.use_tool("web_search", "météo", api_key="cle-secrete-123")
    assert outcome["status"] == "error"
    events = manager.list_events(event_type="tool")
    assert len(events) == 1
    assert events[0].action == "tool:web_search"
    assert events[0].status == AuditStatus.UNAVAILABLE
    # Le secret est masqué dans les métadonnées consignées
    assert "cle-secrete-123" not in events[0].metadata["arguments"]
    assert "api_key=***" in events[0].metadata["arguments"]


def test_context_use_tool_records_skipped_for_disabled_tool():
    """Un outil désactivé est consigné en SKIPPED sans être exécuté."""
    manager = _make_manager()
    context = AgentContext(
        request="Exécuter un outil",
        agent_id="coder",
        registry=_StubRegistry({"audit": manager, "tool": _FakeToolEngine()}),
    )
    outcome = context.use_tool("disabled_tool")
    assert outcome["status"] == "error"
    events = manager.list_events(event_type="tool")
    assert len(events) == 1
    assert events[0].action == "tool:disabled_tool"
    assert events[0].status == AuditStatus.SKIPPED


def test_context_use_tool_records_success_and_redacts_secrets():
    """Un outil réussi est consigné en SUCCESS, sans divulguer les secrets."""
    manager = _make_manager()
    context = AgentContext(
        request="Exécuter un outil",
        agent_id="coder",
        registry=_StubRegistry({"audit": manager, "tool": _FakeToolEngine()}),
    )
    outcome = context.use_tool("echo", 1, password="toto", topic="actualité")
    assert outcome["status"] == "success"
    events = manager.list_events(event_type="tool")
    assert len(events) == 1
    assert events[0].status == AuditStatus.SUCCESS
    assert events[0].execution_time_seconds is not None
    arguments = events[0].metadata["arguments"]
    assert "password=***" in arguments
    assert "toto" not in arguments
    assert "topic=actualité" in arguments


def test_context_generate_records_unavailable_without_model_engine():
    """Sans moteur de modèles, la génération est consignée en UNAVAILABLE."""
    manager = _make_manager()
    context = AgentContext(
        request="Rédiger un résumé",
        agent_id="coder",
        registry=_StubRegistry({"audit": manager}),
    )
    outcome = context.generate("Résume ce texte")
    assert outcome["status"] == "unavailable"
    events = manager.list_events(event_type="generation")
    assert len(events) == 1
    assert events[0].status == AuditStatus.UNAVAILABLE
    assert "prompt_preview" in events[0].metadata


def test_context_generate_records_success_with_model_id():
    """Une génération réussie consigne le modèle utilisé et la durée."""
    manager = _make_manager()
    context = AgentContext(
        request="Rédiger un résumé",
        agent_id="coder",
        registry=_StubRegistry({"audit": manager, "model": _FakeModelEngine()}),
    )
    outcome = context.generate("Résume ce texte")
    assert outcome["status"] == "success"
    assert outcome["model_id"] == "model-local-test"
    events = manager.list_events(event_type="generation")
    assert len(events) == 1
    assert events[0].status == AuditStatus.SUCCESS
    assert events[0].model_id == "model-local-test"
    assert events[0].execution_time_seconds is not None
    assert events[0].metadata["output_length"] == len(outcome["text"])


# ----------------------------------------------------------------------
# Intégration EngineRegistry
# ----------------------------------------------------------------------
def test_registry_exposes_audit_engine():
    """Le registre construit le moteur d'audit et le cache."""
    registry = EngineRegistry()
    assert "audit" in ENGINE_NAMES
    engine = registry.try_get("audit")
    assert engine is not None
    assert isinstance(engine, AuditManagerImpl)
    assert registry.audit is engine
    assert registry.is_available("audit")


def test_registry_audit_engine_records_and_reads():
    """Un événement consigné via le registre est relisible par le même moteur."""
    registry = EngineRegistry()
    event_id = registry.audit.record(
        AuditEvent(event_type=AuditEventType.REQUEST, action="smoke_test",
                   request_id="req_smoke")
    )
    assert event_id
    event = registry.audit.get_event(event_id)
    assert event is not None
    assert event.action == "smoke_test"
    assert event.request_id == "req_smoke"
