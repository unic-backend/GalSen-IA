#!/usr/bin/env python3
"""
Test script for the Tool Engine.

The suite checks discovery, synchronous and asynchronous execution, and error
handling. It used to assert that tools failed to load because none were
implemented; now that the connectors exist, it asserts that they actually work.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tool.tool_engine import ToolEngine

# Connecteurs qui doivent être chargeables et exécutables
IMPLEMENTED_TOOLS = ("filesystem", "terminal", "git", "github", "web_search", "browser")


def build_engine() -> ToolEngine:
    """Instancie le moteur d'outils à partir du registre du projet."""
    registry_path = os.path.join(os.path.dirname(__file__), '..', 'tools', 'tools.yaml')
    return ToolEngine(registry_path)


def test_tool_discovery(engine: ToolEngine) -> None:
    """Vérifie que le moteur découvre les outils déclarés."""
    print("Testing tool discovery...")

    tools = engine.list_tools()
    assert len(tools) > 0, "Aucun outil découvert"
    assert len(engine.list_enabled_tools()) > 0

    categories = engine.get_tool_categories()
    assert "system" in categories and "development" in categories

    declared = {tool['id'] for tool in tools}
    for tool_id in IMPLEMENTED_TOOLS:
        assert tool_id in declared, f"L'outil '{tool_id}' est absent du registre"
        assert engine.is_tool_enabled(tool_id), f"L'outil '{tool_id}' est désactivé"

    print(f"[OK] Discovered {len(tools)} tools across {len(categories)} categories")


def test_tool_info(engine: ToolEngine) -> None:
    """Vérifie les informations exposées pour un outil."""
    print("Testing tool info...")

    info = engine.get_tool_info('filesystem')
    assert info is not None
    assert info['class'] == 'FileSystemTool'
    assert info['category'] == 'system'
    assert engine.get_tool_info('outil_inexistant') is None

    print("[OK] Tool info is exposed correctly")


def test_implemented_tools_load(engine: ToolEngine) -> None:
    """Vérifie que chaque connecteur implémenté se charge réellement."""
    print("Testing that implemented tools load...")

    for tool_id in IMPLEMENTED_TOOLS:
        tool_class = engine.tool_loader.get_tool_class(tool_id)
        assert tool_class is not None, f"La classe de l'outil '{tool_id}' est introuvable"

    print(f"[OK] All {len(IMPLEMENTED_TOOLS)} implemented tools load")


def test_synchronous_execution(engine: ToolEngine) -> None:
    """Vérifie une exécution synchrone réelle."""
    print("Testing synchronous execution...")

    result = engine.execute_tool('filesystem', 'read', 'README.md')
    assert result['line_count'] > 0
    assert 'GalSen' in result['content']

    command = engine.execute_tool('terminal', ['python', '--version'])
    assert command['success'] is True

    print("[OK] Tools execute synchronously")


def test_asynchronous_execution(engine: ToolEngine) -> None:
    """Vérifie une exécution asynchrone réelle."""
    print("Testing asynchronous execution...")

    async def run() -> dict:
        return await engine.execute_tool_async('filesystem', 'exists', 'README.md')

    assert asyncio.run(run()) is True

    print("[OK] Tools execute asynchronously")


def test_error_handling(engine: ToolEngine) -> None:
    """Vérifie que les erreurs sont explicites et typées."""
    print("Testing error handling...")

    try:
        engine.execute_tool('outil_inexistant')
        raise AssertionError("Un outil inconnu devrait être refusé")
    except ValueError as error:
        assert "not found or not enabled" in str(error)

    try:
        engine.execute_tool('filesystem', 'operation_inconnue')
        raise AssertionError("Une opération inconnue devrait être refusée")
    except ValueError as error:
        assert "inconnue" in str(error)

    # Un outil déclaré mais non implémenté reste signalé proprement
    # Note: Les outils 'browser' et 'api' sont maintenant implémentés.
    # On teste avec un ID d'outil inexistant dans le registre.
    try:
        engine.execute_tool('outil_inexistant_dans_le_registre')
        raise AssertionError("Un outil non implémenté devrait être refusé")
    except ValueError as error:
        assert "not found or not enabled" in str(error)

    print("[OK] Errors are reported with actionable messages")


def run_all_tests() -> bool:
    """Exécute tous les tests du moteur d'outils."""
    print("=" * 60)
    print("Running Tool Engine Tests")
    print("=" * 60)

    try:
        engine = build_engine()
        test_tool_discovery(engine)
        test_tool_info(engine)
        test_implemented_tools_load(engine)
        test_synchronous_execution(engine)
        test_asynchronous_execution(engine)
        test_error_handling(engine)

        print("=" * 60)
        print("[PASS] All tests passed!")
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