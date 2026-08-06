#!/usr/bin/env python3
"""
Test script for the web search tool across its search types.

Reaching DuckDuckGo is not something the test can guarantee, so a network
failure is reported as skipped rather than failed: `.claude/rules/testing.md`
requires deterministic tests, and a suite that depends on the internet being up
would fail for reasons unrelated to the code.

The wiring checks below run offline and are the part that must always pass.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from src.tool.tool_engine import ToolEngine

SEARCH_TYPES = ("web", "news", "images", "videos")

# Errors that mean the network is unreachable, not that the tool is broken
NETWORK_ERROR_MARKERS = ("timed out", "urlopen error", "Failed to fetch", "Connection")


def build_engine() -> ToolEngine:
    """Instancie le moteur d'outils à partir du registre du projet."""
    registry_path = os.path.join(os.path.dirname(__file__), 'tools', 'tools.yaml')
    return ToolEngine(registry_path)


def test_tool_is_registered(engine: ToolEngine) -> None:
    """Vérifie que l'outil de recherche est correctement déclaré."""
    print("Testing web search tool registration...")

    info = engine.get_tool_info('web_search')
    assert info is not None, "L'outil 'web_search' est absent du registre"
    assert info['enabled'] is True, "L'outil 'web_search' est désactivé"
    assert info['class'] == 'WebSearchTool'
    assert engine.is_tool_enabled('web_search')

    print("[OK] Web search tool is registered and enabled")


def test_input_validation(engine: ToolEngine) -> None:
    """Vérifie que les entrées invalides sont refusées sans appel réseau."""
    print("Testing web search input validation...")

    for invalid_arguments, expected_error in (
        ((), ValueError),
        ((123,), TypeError),
    ):
        try:
            engine.execute_tool('web_search', *invalid_arguments)
            raise AssertionError(f"Entrée invalide acceptée: {invalid_arguments}")
        except expected_error:
            pass

    try:
        engine.execute_tool('web_search', 'requête', max_results=0)
        raise AssertionError("max_results=0 accepté")
    except ValueError:
        pass

    print("[OK] Invalid inputs are rejected")


def test_search_types(engine: ToolEngine) -> None:
    """
    Exécute une recherche pour chaque type pris en charge.

    Réseau injoignable : le test est ignoré, pas mis en échec — la suite ne doit
    pas dépendre de l'état d'internet (`.claude/rules/testing.md`).
    """
    if not run_search_types(engine):
        pytest.skip("Réseau injoignable : les recherches en direct sont ignorées")


def run_search_types(engine: ToolEngine) -> bool:
    """
    Exécute une recherche pour chaque type pris en charge.

    Cette fonction porte le résultat sous forme de booléen pour le mode script
    (`python test_search_types.py`) ; le test pytest au-dessus le traduit en
    « ignoré ». Un test qui retourne une valeur au lieu d'affirmer n'affirme
    rien, et pytest l'avertit à juste titre.

    Returns:
        True si le réseau a répondu, False si les recherches ont été ignorées
    """
    print("Testing search types...")

    for search_type in SEARCH_TYPES:
        try:
            results = engine.execute_tool(
                'web_search', 'Python programming',
                search_type=search_type, max_results=2,
            )
        except Exception as error:
            if any(marker in str(error) for marker in NETWORK_ERROR_MARKERS):
                print(f"[SKIP] Search type '{search_type}': network unreachable")
                return False
            raise

        assert isinstance(results, list), f"Le type '{search_type}' ne retourne pas une liste"
        for result in results:
            assert 'title' in result and 'url' in result, "Résultat sans titre ni URL"

        print(f"[OK] Search type '{search_type}' returned {len(results)} result(s)")

    return True


def run_all_tests() -> bool:
    """Exécute tous les tests de l'outil de recherche."""
    print("=" * 60)
    print("Running Web Search Types Tests")
    print("=" * 60)

    try:
        engine = build_engine()
        test_tool_is_registered(engine)
        test_input_validation(engine)
        network_available = run_search_types(engine)

        print("=" * 60)
        if network_available:
            print("[PASS] All tests passed!")
        else:
            print("[PASS] Offline tests passed (live searches skipped)")
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
