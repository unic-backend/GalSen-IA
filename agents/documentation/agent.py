"""
Documentation Agent for GalSen IA.

Checks that the documentation still describes the project as it is. It reads the
memory files through the Document Intelligence Engine and compares what they
claim against what exists in `src/`.

The agent reports gaps; it does not rewrite documentation. Documentation states
intent, and rewriting intent automatically would let the record drift from what
the team actually decided.
"""

import os
from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module


class DocumentationAgent(BaseAgent):
    """Agent qui contrôle la cohérence entre la documentation et le code."""

    agent_id = "documentation"
    required_engines = ("document", "tool", "knowledge", "memory")

    # Fichiers dont l'existence conditionne la mémoire du projet
    REQUIRED_MEMORY_FILES = (
        "docs/memory/vision.md",
        "docs/memory/current-objectives.md",
        "docs/memory/completed-work.md",
        "docs/memory/pending-work.md",
        "docs/memory/priorities.md",
        "docs/memory/knowledge-index.md",
    )

    REQUIRED_PROJECT_FILES = (
        "README.md",
        "CLAUDE.md",
        "docs/changelog/CHANGELOG.md",
        "docs/architecture/overview.md",
        "docs/tasks/TASKS.md",
    )

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Contrôle l'état de la documentation du projet.

        Args:
            context: Contexte d'exécution

        Returns:
            Fichiers présents et manquants, modules non documentés et actions requises
        """
        memory_state = self._check_files(context, self.REQUIRED_MEMORY_FILES)
        project_state = self._check_files(context, self.REQUIRED_PROJECT_FILES)
        analyzed = self._analyze_documentation(context)
        undocumented = self._find_undocumented_modules(context)

        missing = memory_state["missing"] + project_state["missing"]

        return {
            "memory_files": memory_state,
            "project_files": project_state,
            "documents_analyzed": analyzed,
            "undocumented_modules": undocumented,
            "actions_required": self._actions_required(missing, undocumented),
            "verdict": {
                "complete": not missing and not undocumented,
                "missing_count": len(missing),
                "undocumented_count": len(undocumented),
            },
        }

    def _check_files(self, context: AgentContext, expected: tuple) -> Dict[str, Any]:
        """Vérifie la présence et la taille des fichiers attendus."""
        present: List[Dict[str, Any]] = []
        missing: List[str] = []

        for path in expected:
            outcome = context.use_tool("filesystem", "stat", path)
            if outcome.get("status") == "success":
                info = outcome["result"]
                present.append({
                    "path": path,
                    "size": info["size"],
                    # Un fichier quasi vide existe sans documenter quoi que ce soit
                    "substantial": info["size"] > 200,
                })
            else:
                missing.append(path)

        return {
            "present": present,
            "missing": missing,
            "empty_or_thin": [item["path"] for item in present if not item["substantial"]],
        }

    def _analyze_documentation(self, context: AgentContext) -> List[Dict[str, Any]]:
        """Analyse les fichiers de mémoire via le moteur documentaire."""
        analyses: List[Dict[str, Any]] = []

        for path in self.REQUIRED_MEMORY_FILES:
            if not os.path.isfile(os.path.join(context.registry.project_root, path)):
                continue

            analysis = context.analyze_document(os.path.join(context.registry.project_root, path))
            if not analysis:
                continue

            analyses.append({
                "path": path,
                "title": analysis.get("title"),
                "word_count": analysis.get("word_count"),
                "language": analysis.get("language"),
                "summary": (analysis.get("summary") or "")[:200],
            })

        return analyses

    def _find_undocumented_modules(self, context: AgentContext) -> List[str]:
        """
        Repère les moteurs de `src/` absents de l'index des connaissances.

        L'index est le point d'entrée que Claude Code lit en premier : un module
        qui n'y figure pas est invisible pour les sessions suivantes.
        """
        index = context.use_tool("filesystem", "read", "docs/memory/knowledge-index.md")
        if index.get("status") != "success":
            return []

        index_content = index["result"]["content"]

        listing = context.use_tool("filesystem", "list", "src")
        if listing.get("status") != "success":
            return []

        undocumented: List[str] = []
        for entry in listing["result"]:
            if not entry["is_directory"] or entry["name"].startswith("_"):
                continue
            if entry["name"] not in index_content:
                undocumented.append(f"src/{entry['name']}")

        return undocumented

    def _actions_required(self, missing: List[str], undocumented: List[str]) -> List[Dict[str, str]]:
        """Traduit les manques constatés en actions concrètes."""
        actions: List[Dict[str, str]] = []

        for path in missing:
            actions.append({
                "action": "create",
                "target": path,
                "reason": "Fichier de documentation attendu par les règles du projet",
            })

        for module in undocumented:
            actions.append({
                "action": "index",
                "target": "docs/memory/knowledge-index.md",
                "reason": f"Le module {module} n'apparaît pas dans l'index des connaissances",
            })

        return actions


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter

    Returns:
        Résultat de l'agent au format standard
    """
    return run_agent_module(DocumentationAgent, input_data)
