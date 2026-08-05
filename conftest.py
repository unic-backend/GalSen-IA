"""
Configuration partagée pour pytest.

Fournit les fixtures communes utilisées par les tests du projet GalSen IA.
"""

import os
import pytest

# Chemin racine du projet
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="session")
def engine():
    """
    Construit un ToolEngine à partir du registre tools/tools.yaml.

    Utilisé par test_tool_engine.py, test_search_types.py et d'autres
    tests qui nécessitent une instance du moteur d'outils.
    """
    from src.tool.tool_engine import ToolEngine

    registry_path = os.path.join(PROJECT_ROOT, "tools", "tools.yaml")
    return ToolEngine(registry_path)
