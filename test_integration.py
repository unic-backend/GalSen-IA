#!/usr/bin/env python3
"""
Integration tests for the GalSen IA engine integration layer.

These tests check that the engines are actually connected to each other, which
the per-engine suites cannot see: each of those exercises one engine in
isolation, so an engine could work perfectly and still be unreachable from an
agent.

What is verified here:
  - the registry exposes every engine and survives a broken one
  - the context reaches memory, knowledge, documents, vision, tools and models
  - the four tool connectors work and refuse what they must refuse
  - every agent runs against real engines and returns the expected shape
  - the Router Engine and Agent Runtime share one context across a pipeline
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agent.base_agent import AgentResult, BaseAgent
from src.agent.context import AgentContext
from src.agent.runtime import AgentRuntime
from src.integration.engine_registry import (
    ENGINE_NAMES,
    EngineRegistry,
    EngineUnavailableError,
)
from src.router.router_engine import RouterEngine

# Agents declared in agents/registry.yaml, excluding the orchestrator itself
AGENT_IDS = (
    "planner", "researcher", "coder", "reviewer", "tester",
    "security", "documentation", "deployment", "monitor",
)


# ----------------------------------------------------------------------
# Engine registry
# ----------------------------------------------------------------------
def test_registry_exposes_every_engine():
    """Every declared engine must be reachable through the registry."""
    print("Testing engine registry availability...")
    registry = EngineRegistry()

    availability = registry.availability()
    assert set(availability) == set(ENGINE_NAMES)

    unavailable = [
        f"{name} ({state['reason']})"
        for name, state in availability.items() if not state["available"]
    ]
    assert not unavailable, f"Moteurs indisponibles: {unavailable}"

    print(f"[OK] All {len(ENGINE_NAMES)} engines are available")


def test_registry_caches_instances():
    """The registry must hand out the same instance, so state is shared."""
    print("Testing engine instance sharing...")
    registry = EngineRegistry()

    assert registry.memory is registry.memory
    assert registry.get("document") is registry.get("document")

    # After a reset a fresh instance is built
    first = registry.knowledge
    registry.reset()
    assert registry.knowledge is not first

    print("[OK] Engines are cached and resettable")


def test_registry_isolates_failures():
    """A broken engine must not raise anywhere except where it is used."""
    print("Testing engine failure isolation...")
    registry = EngineRegistry()

    try:
        registry.get("nonexistent_engine")
        raise AssertionError("Un moteur inconnu devrait être refusé")
    except EngineUnavailableError as error:
        assert error.engine_name == "nonexistent_engine"

    assert registry.try_get("nonexistent_engine") is None
    assert registry.is_available("nonexistent_engine") is False
    # The rest of the platform is unaffected
    assert registry.is_available("memory") is True

    print("[OK] Unknown engines fail without affecting the others")


# ----------------------------------------------------------------------
# Agent context
# ----------------------------------------------------------------------
def test_context_reaches_memory_and_knowledge():
    """The context must round-trip through the memory and knowledge engines."""
    print("Testing context access to memory and knowledge...")
    context = AgentContext(request="Agriculture au Senegal", agent_id="test")

    memory_id = context.remember("Le mil est cultive au Senegal", tags=["agriculture"])
    assert memory_id, "La mémorisation doit retourner un identifiant"

    recalled = context.recall("mil")
    assert any("mil" in str(item["content"]) for item in recalled)

    knowledge_id = context.add_knowledge("Le Senegal exporte de l'arachide", tags=["agriculture"])
    assert knowledge_id, "L'ajout de connaissance doit retourner un identifiant"

    found = context.search_knowledge("arachide")
    assert any("arachide" in item["content"] for item in found)

    print("[OK] Context reaches the memory and knowledge engines")


def test_context_reaches_document_engine():
    """The context must load and analyse a document end to end."""
    print("Testing context access to the document engine...")
    context = AgentContext(request="analyse", agent_id="test")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as handle:
        handle.write(
            "Le Senegal developpe son agriculture. "
            "La production de mil augmente chaque annee. "
            "Les exportations progressent."
        )
        temp_file = handle.name

    try:
        analysis = context.analyze_document(temp_file)

        assert analysis, "L'analyse ne doit pas être vide"
        assert analysis["type"] == "txt"
        assert analysis["word_count"] > 0
        assert analysis["valid"] is True
        assert analysis["summary"]

        print("[OK] Context reaches the document engine")
    finally:
        os.unlink(temp_file)


def test_context_reports_model_unavailability():
    """With no model registered, generation must say so instead of inventing text."""
    print("Testing context model handling...")
    context = AgentContext(request="test", agent_id="test")

    outcome = context.generate("Explique la photosynthese")

    assert outcome["status"] in ("success", "unavailable", "error")
    if outcome["status"] != "success":
        # An honest failure carries a reason and no fabricated text
        assert outcome["text"] == ""
        assert outcome["reason"]

    print(f"[OK] Model generation reported as '{outcome['status']}'")


def test_context_derivation_shares_state():
    """A derived context must keep the session, registry and history."""
    print("Testing context derivation...")
    context = AgentContext(request="test", agent_id="planner", user_id="u1")
    context.previous_results.append({"agent": "planner", "status": "success", "result": {"x": 1}})

    derived = context.derive("researcher")

    assert derived.agent_id == "researcher"
    assert derived.session_id == context.session_id
    assert derived.user_id == context.user_id
    assert derived.registry is context.registry
    assert derived.previous_result("planner") is not None

    print("[OK] Derived contexts share session, registry and history")


# ----------------------------------------------------------------------
# Tool connectors
# ----------------------------------------------------------------------
def test_filesystem_tool():
    """The filesystem tool must read the project and refuse to leave it."""
    print("Testing filesystem tool...")
    context = AgentContext(request="test", agent_id="test")

    read = context.use_tool("filesystem", "read", "README.md")
    assert read["status"] == "success"
    assert read["result"]["line_count"] > 0

    found = context.use_tool("filesystem", "search", "*.py", directory="src/tool")
    assert found["status"] == "success"
    assert any(path.endswith("tool_engine.py") for path in found["result"])

    # Path traversal is refused, and refusal is data rather than a crash
    escape = context.use_tool("filesystem", "read", "../../../etc/passwd")
    assert escape["status"] == "error"
    assert "hors du" in escape["error"]

    # Writing is disabled by configuration
    write = context.use_tool("filesystem", "write", "should_not_exist.txt", content="x")
    assert write["status"] == "error"
    assert not os.path.exists("should_not_exist.txt")

    print("[OK] Filesystem tool reads, searches and stays inside the project")


def test_terminal_tool():
    """The terminal tool must run allowed commands and reject the others."""
    print("Testing terminal tool...")
    context = AgentContext(request="test", agent_id="test")

    allowed = context.use_tool("terminal", ["python", "--version"])
    assert allowed["status"] == "success"
    assert allowed["result"]["success"] is True

    blocked = context.use_tool("terminal", ["rm", "-rf", "/"])
    assert blocked["status"] == "error"
    assert "non autoris" in blocked["error"]

    # Shell metacharacters are arguments, never a second command
    # On utilise python au lieu de 'echo' car 'echo' est un builtin du shell sur Windows
    literal = context.use_tool("terminal", ["python", "-c", "print('a && whoami')"])
    assert literal["status"] == "success"
    assert "whoami" in literal["result"]["stdout"]

    print("[OK] Terminal tool enforces its allowlist and runs without a shell")


def test_git_tool():
    """The git tool must report repository state without crashing when absent."""
    print("Testing git tool...")
    context = AgentContext(request="test", agent_id="test")

    summary = context.use_tool("git", "summary")
    assert summary["status"] == "success"
    assert "is_repository" in summary["result"]

    # Writing is disabled, so pushing is refused before git is even consulted
    push = context.use_tool("git", "push")
    assert push["status"] == "error"

    print(f"[OK] Git tool reports repository state (is_repository="
          f"{summary['result']['is_repository']})")


def test_github_tool():
    """The github tool must report its auth state and validate its inputs offline."""
    print("Testing github tool...")
    context = AgentContext(request="test", agent_id="test")

    auth = context.use_tool("github", "authenticated")
    assert auth["status"] == "success"
    assert "authenticated" in auth["result"]
    # The token is read from the environment, never from the configuration
    assert "GITHUB_TOKEN" in auth["result"]["checked_variables"]

    invalid = context.use_tool("github", "repository", "not-a-valid-repo")
    assert invalid["status"] == "error"
    assert "Format attendu" in invalid["error"]

    print("[OK] GitHub tool validates inputs and reads its token from the environment")


def test_unknown_tool_is_reported():
    """An unknown tool must be reported, not raised."""
    print("Testing unknown tool handling...")
    context = AgentContext(request="test", agent_id="test")

    outcome = context.use_tool("tool_that_does_not_exist")
    assert outcome["status"] == "error"
    assert outcome["tool"] == "tool_that_does_not_exist"

    print("[OK] Unknown tools are reported as errors")


# ----------------------------------------------------------------------
# Agents
# ----------------------------------------------------------------------
def test_every_agent_runs_against_real_engines():
    """Every agent must execute and return a well formed result."""
    print("Testing all agents against real engines...")
    import importlib

    for agent_id in AGENT_IDS:
        module = importlib.import_module(f"agents.{agent_id}.agent")
        result = module.execute("Analyser la securite du projet et documenter")

        assert result["status"] == "success", f"Agent '{agent_id}': {result.get('error')}"
        assert result["agent"] == agent_id
        assert isinstance(result["result"], dict), f"Agent '{agent_id}' ne retourne pas un dictionnaire"
        assert "duration_seconds" in result
        # An agent that declares no engine is not integrated
        assert result["engines_used"], f"Agent '{agent_id}' ne déclare aucun moteur"

    print(f"[OK] All {len(AGENT_IDS)} agents run against real engines")


def test_agents_produce_verifiable_output():
    """The analysis agents must produce findings anchored in real files."""
    print("Testing agent output is grounded in real data...")
    import importlib

    reviewer = importlib.import_module("agents.reviewer.agent").execute("revoir src")["result"]
    assert reviewer["files_reviewed"] > 0, "Le reviewer n'a analysé aucun fichier"
    for issue in reviewer["issues"]:
        assert os.path.isfile(issue["file"]), f"Problème signalé sur un fichier inexistant: {issue['file']}"
        assert issue["line"] >= 0

    security = importlib.import_module("agents.security.agent").execute("analyser la securite")["result"]
    assert security["files_scanned"] > 0, "L'agent de sécurité n'a scanné aucun fichier"
    assert security["repository_protections"]["env_ignored"] is True, ".env doit être couvert par .gitignore"

    monitor = importlib.import_module("agents.monitor.agent").execute("etat de la plateforme")["result"]
    assert monitor["engines_available"] == monitor["engines_total"], "Des moteurs sont indisponibles"

    print("[OK] Agent findings point at real files and real engine state")


def test_agent_errors_are_contained():
    """An agent that raises must return an error result, not propagate."""
    print("Testing agent error containment...")

    class FailingAgent(BaseAgent):
        """Agent qui échoue volontairement."""

        agent_id = "failing"
        required_engines = ("memory",)

        def perform(self, context):
            """Lève une exception pour vérifier son confinement."""
            raise RuntimeError("échec volontaire")

    result = FailingAgent().run(AgentContext(request="test", agent_id="failing"))

    assert result["status"] == AgentResult.STATUS_ERROR
    assert "échec volontaire" in result["error"]
    assert result["agent"] == "failing"

    print("[OK] Agent exceptions are converted into error results")


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------
def test_router_runs_the_full_pipeline():
    """The Router Engine must run every agent through the shared context."""
    print("Testing Router Engine pipeline...")
    router = RouterEngine()

    response = router.process_request(
        "Verifier la qualite et la securite du projet",
        user_id="test_user",
    )

    assert response["status"] in ("success", "partial_success")
    assert response["metadata"]["total_agents_executed"] == len(AGENT_IDS)
    assert response["metadata"]["failed_agents"] == 0, "Des agents ont échoué dans le pipeline"

    executed = [result["agent"] for result in response["agent_results"]]
    assert executed == list(AGENT_IDS), f"Ordre d'exécution inattendu: {executed}"

    print(f"[OK] Router executed {len(executed)} agents in {response['execution_time_seconds']}s")


def test_agents_see_previous_results():
    """An agent must be able to read what the agents before it produced."""
    print("Testing result propagation between agents...")
    router = RouterEngine()

    response = router.process_request("Preparer un deploiement du projet")

    deployment = next(
        result for result in response["agent_results"] if result["agent"] == "deployment"
    )
    # The deployment agent reuses the tester verdict instead of rerunning tests,
    # which is only possible if it actually saw the earlier result
    assert deployment["result"]["test_state"]["known"] is True, (
        "L'agent de déploiement n'a pas vu le résultat de l'agent tester"
    )

    monitor = next(
        result for result in response["agent_results"] if result["agent"] == "monitor"
    )
    assert monitor["result"]["pipeline"]["agents_executed"] > 0, (
        "L'agent de supervision n'a pas vu le déroulement du pipeline"
    )

    print("[OK] Agents read the results of the agents before them")


def test_runtime_runs_the_full_pipeline():
    """The Agent Runtime must run the same pipeline, including in parallel."""
    print("Testing Agent Runtime pipeline...")
    runtime = AgentRuntime()

    result = runtime.execute_task("Analyser l'etat du projet", user_id="test_user")

    assert result["status"] in ("success", "partial_success")
    assert result["metadata"]["failed_agents"] == 0, "Des agents ont échoué dans le runtime"
    assert result["metadata"]["total_agents_executed"] == len(AGENT_IDS)

    print(f"[OK] Runtime executed {result['metadata']['total_agents_executed']} agents "
          f"in {result['execution_time_seconds']}s")


def run_all_tests():
    """Run every integration test."""
    print("=" * 60)
    print("Running Engine Integration Tests")
    print("=" * 60)

    tests = (
        test_registry_exposes_every_engine,
        test_registry_caches_instances,
        test_registry_isolates_failures,
        test_context_reaches_memory_and_knowledge,
        test_context_reaches_document_engine,
        test_context_reports_model_unavailability,
        test_context_derivation_shares_state,
        test_filesystem_tool,
        test_terminal_tool,
        test_git_tool,
        test_github_tool,
        test_unknown_tool_is_reported,
        test_every_agent_runs_against_real_engines,
        test_agents_produce_verifiable_output,
        test_agent_errors_are_contained,
        test_router_runs_the_full_pipeline,
        test_agents_see_previous_results,
        test_runtime_runs_the_full_pipeline,
    )

    try:
        for test in tests:
            test()

        print("=" * 60)
        print(f"[PASS] All {len(tests)} integration tests passed!")
        print("=" * 60)
        return True
    except Exception as error:
        print("=" * 60)
        print(f"Test failed: {error}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return False


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
