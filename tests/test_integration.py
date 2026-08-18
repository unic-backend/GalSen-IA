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

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.base_agent import AgentResult, BaseAgent
from src.agent.context import AgentContext
from src.agent.runtime import AgentRuntime
from src.integration.engine_registry import (
    ENGINE_NAMES,
    EngineRegistry,
    EngineUnavailableError,
)
from src.router.router_engine import RouterEngine

# Agents declared in agents/registry.yaml, excluding the orchestrator itself and
# `organizer`, whose normal outcome is `requires_approval` rather than `success`:
# it proposes file moves and is gated by construction (VOLET 34, ch. 11). It is
# covered by tests/test_agents_personal.py.
AGENT_IDS = (
    "planner", "researcher", "coder", "reviewer", "tester",
    "security", "documentation", "deployment", "monitor",
    "project_manager", "opportunity",
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
    """The terminal tool must run allowed commands and reject the others.

    L'outil est appelé **directement**, plus par `AgentContext.use_tool` : ce
    chemin est désormais celui de l'exécution sans témoin (phase 39.3) et il
    refuse `terminal` hors de sa borne pré-approuvée. Le sujet de ce test reste
    la liste blanche et l'absence de shell — ces deux garanties sont intactes.
    Le refus par le chemin des agents est vérifié par le test suivant.
    """
    print("Testing terminal tool...")
    from src.tools.terminal.tool import TerminalTool

    tool = TerminalTool({
        "allowed_commands": ["python", "python3", "py", "pytest", "git", "echo"],
        "timeout": 120,
    })

    allowed = tool.execute(["python", "--version"])
    assert allowed["success"] is True

    # Appelé directement, l'outil lève ; `use_tool` traduisait cette exception
    # en `{"status": "error"}`. Le refus est le même, sa forme change.
    with pytest.raises(ValueError, match="non autoris"):
        tool.execute(["rm", "-rf", "/"])

    # Shell metacharacters are arguments, never a second command
    # On utilise python au lieu de 'echo' car 'echo' est un builtin du shell sur Windows
    literal = tool.execute(["python", "-c", "print('a && whoami')"])
    assert literal["success"] is True
    assert "whoami" in literal["stdout"]

    print("[OK] Terminal tool enforces its allowlist and runs without a shell")


def test_terminal_is_gated_on_the_agent_path_except_within_its_bound():
    """
    Le chemin des agents n'ouvre `terminal` que dans sa borne pré-approuvée.

    `python -m pytest` passe — c'est la raison d'être de l'agent testeur.
    `python --version` et `python -c` ne passent pas, et c'est le point : la
    borne approuvée est une commande, pas l'exécutable qui la porte.
    """
    context = AgentContext(request="test", agent_id="test")

    for commande in (["python", "--version"], ["python", "-c", "print(1)"]):
        refus = context.use_tool("terminal", commande)
        assert refus["status"] == "error", commande
        assert "sans témoin refusée" in refus["error"], commande

    from src.tool.capabilities import load_capabilities, may_run_unattended

    autorise, motif = may_run_unattended(
        "terminal", load_capabilities(),
        arguments=["python", "-m", "pytest", "tests/test_integration.py", "-q"],
    )
    assert autorise is True
    assert "python -m pytest" in motif

    print("[OK] Terminal is gated on the agent path outside its approved bound")


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
def test_router_runs_the_declared_pipeline():
    """The Router Engine must run every declared agent, in order.

    Le workflow `revue` ne déclare pas `agent_selection`, donc son pipeline
    s'exécute en entier : c'est là que se vérifie la capacité brute de
    l'orchestrateur, indépendamment de la sélection.
    """
    print("Testing Router Engine pipeline...")
    router = RouterEngine()

    response = router.process_request(
        "Verifier la qualite et la securite du projet",
        user_id="test_user",
        workflow_id="revue",
    )

    assert response["status"] in ("success", "partial_success")
    assert response["metadata"]["failed_agents"] == 0, "Des agents ont échoué dans le pipeline"

    executed = [result["agent"] for result in response["agent_results"]]
    assert executed == ["reviewer", "security"], f"Ordre d'exécution inattendu: {executed}"
    assert response["metadata"]["decision"]["applied"] is False

    print(f"[OK] Router executed {len(executed)} agents in {response['execution_time_seconds']}s")


def test_router_restricts_the_pipeline_to_the_request():
    """Sur `standard`, la recommandation du planificateur restreint l'exécution.

    C'est le branchement demandé par le backlog : le pipeline complet tournait
    pour toute demande, `tester` compris, soit 43 s sur 45 s mesurées.
    """
    print("Testing planner-driven selection...")
    router = RouterEngine()

    # Sans « production » : ce mot porte l'intention de déploiement, qui
    # mobilise légitimement `tester` — préparer une mise en production sans
    # connaître l'état des tests serait la vitesse préférée à la vérité.
    response = router.process_request("Surveiller les logs et les metriques")

    executed = [result["agent"] for result in response["agent_results"]]
    assert response["metadata"]["decision"]["applied"] is True
    assert "monitor" in executed
    # L'agent le plus coûteux ne tourne pas pour une demande de supervision.
    assert "tester" not in executed, f"Pipeline non restreint: {executed}"
    # Le planificateur ouvre toujours : c'est lui qui produit la décision.
    assert executed[0] == "planner"


def test_agents_see_previous_results():
    """An agent must be able to read what the agents before it produced."""
    print("Testing result propagation between agents...")
    router = RouterEngine()

    # La demande mobilise le déploiement **et** la supervision : depuis que la
    # sélection s'applique, un agent non recommandé ne tourne plus, et ce test
    # a besoin des deux pour vérifier la propagation dans les deux sens.
    response = router.process_request(
        "Preparer un deploiement du projet et surveiller les logs"
    )

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


def test_runtime_delegue_au_seul_orchestrateur():
    """The Agent Runtime must run through the Router Engine, not beside it.

    This assertion changed on purpose. It used to require the runtime to execute
    **every** agent of the workflow — which is exactly what made it a second,
    slower truth: it ran the whole pipeline whatever the request, while the
    Router Engine runs what the planner selected. Pinning the old count would
    have kept the duplication alive under a green test.
    """
    print("Testing Agent Runtime delegation...")
    runtime = AgentRuntime()

    result = runtime.execute_task("Analyser l'etat du projet", user_id="test_user")

    assert result["status"] in ("success", "partial_success")
    assert result["metadata"]["failed_agents"] == 0, "Des agents ont échoué dans le runtime"
    # Le pipeline exécuté est celui décidé par le planificateur : au moins un
    # agent, jamais plus que le registre complet.
    executes = result["metadata"]["total_agents_executed"]
    assert 1 <= executes <= len(AGENT_IDS)
    # La trace de décision n'existait pas dans l'ancien chemin : sa présence
    # prouve que c'est bien l'orchestrateur unique qui a tourné.
    assert "decision" in result["metadata"]
    # Et le contrat historique tient : la clé est `task_input`, pas `user_request`.
    assert result["task_input"] == "Analyser l'etat du projet"
    assert "user_request" not in result

    print(f"[OK] Runtime executed {executes} agents "
          f"in {result['execution_time_seconds']}s")


def test_runtime_et_router_donnent_la_meme_execution():
    """Un seul chemin d'exécution : les deux entrées doivent converger.

    C'est la vérification qui empêche la duplication de revenir. Si quelqu'un
    redonne un pipeline propre au runtime, les deux résultats divergeront ici.
    """
    from src.router.router_engine import RouterEngine

    demande = "Analyser l'etat du projet"
    par_le_runtime = AgentRuntime().execute_task(demande, user_id="test_user")
    par_le_router = RouterEngine().process_request(demande, user_id="test_user")

    assert (
        [r.get("agent") for r in par_le_runtime["agent_results"]]
        == [r.get("agent") for r in par_le_router["agent_results"]]
    )
    assert (
        par_le_runtime["metadata"]["total_agents_executed"]
        == par_le_router["metadata"]["total_agents_executed"]
    )


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
        test_router_runs_the_declared_pipeline,
        test_agents_see_previous_results,
        test_runtime_delegue_au_seul_orchestrateur,
        test_runtime_et_router_donnent_la_meme_execution,
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
