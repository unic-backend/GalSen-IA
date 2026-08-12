"""
Coder Agent for GalSen IA.

Prepares a change before it is written: it locates the modules concerned by the
request, reads the conventions actually in use in the codebase, and produces a
change specification naming the files to touch and the patterns to follow.

Writing the code itself needs a language model. When none is registered, the
agent says so instead of returning invented code — a specification that is
honest about its limits is usable; fabricated code is not.
"""

import os
import re
from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module


class CoderAgent(BaseAgent):
    """Agent qui prépare et spécifie une modification du code."""

    agent_id = "coder"
    required_engines = ("tool", "memory", "knowledge", "model")

    # Domaines fonctionnels du projet et répertoires correspondants
    MODULE_KEYWORDS = {
        "document": "src/document_intelligence_engine",
        "vision": "src/vision_intelligence_engine",
        "image": "src/vision_intelligence_engine",
        "mémoire": "src/memory_engine",
        "memory": "src/memory_engine",
        "modèle": "src/model_engine",
        "model": "src/model_engine",
        "connaissance": "src/knowledge_engine",
        "knowledge": "src/knowledge_engine",
        "outil": "src/tool",
        "tool": "src/tool",
        "agent": "src/agent",
        "routeur": "src/router",
        "router": "src/router",
    }

    # Nombre de fichiers inspectés pour déduire les conventions du module
    CONVENTION_SAMPLE_SIZE = 5

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Produit la spécification de la modification demandée.

        Args:
            context: Contexte d'exécution

        Returns:
            Modules visés, conventions relevées, fichiers concernés et code produit
        """
        request = context.request_text()

        target_modules = self._identify_target_modules(request)
        existing_files = self._list_module_files(context, target_modules)
        conventions = self._detect_conventions(context, existing_files)
        # Les tâches que le planificateur a **assignées à cet agent**, et non la
        # simple présence d'un plan : `plan_followed: bool(plan)` disait vrai sur
        # l'existence du plan et faux sur son suivi. Personne ne lisait
        # l'assignation, alors que le planificateur l'écrit depuis le début.
        mes_taches = context.tasks_for()

        implementation = self._generate_implementation(context, request, target_modules, conventions)

        return {
            "request": request,
            "target_modules": target_modules,
            "existing_files": existing_files[:20],
            "file_count": len(existing_files),
            "conventions": conventions,
            "assigned_tasks": [tache.get("id") for tache in mes_taches],
            "plan_followed": bool(mes_taches),
            "implementation": implementation,
            "next_steps": self._next_steps(implementation),
        }

    def _identify_target_modules(self, request: str) -> List[str]:
        """Déduit les modules concernés à partir du vocabulaire de la demande."""
        normalized = request.lower()

        modules = []
        for keyword, module_path in self.MODULE_KEYWORDS.items():
            if keyword in normalized and module_path not in modules:
                modules.append(module_path)

        # Sans indice, on vise `src` : c'est le périmètre à explorer, pas une supposition
        return modules or ["src"]

    def _list_module_files(self, context: AgentContext, modules: List[str]) -> List[str]:
        """Liste les fichiers Python des modules visés."""
        files: List[str] = []

        for module_path in modules:
            outcome = context.use_tool("filesystem", "search", "*.py", directory=module_path)
            if outcome.get("status") == "success":
                files.extend(outcome["result"])

        return files

    def _detect_conventions(self, context: AgentContext, files: List[str]) -> Dict[str, Any]:
        """
        Relève les conventions réellement appliquées dans le code existant.

        Le but est de suivre le style du module modifié plutôt que d'appliquer
        un style générique : c'est la règle « reuse existing architecture ».
        """
        sample = files[:self.CONVENTION_SAMPLE_SIZE]
        if not sample:
            return {"analyzed_files": 0}

        docstring_count = 0
        french_comment_count = 0
        type_hint_count = 0
        total_functions = 0

        for path in sample:
            outcome = context.use_tool("filesystem", "read", path)
            if outcome.get("status") != "success":
                continue

            content = outcome["result"]["content"]
            functions = re.findall(r'^\s*def\s+\w+\([^)]*\)(\s*->\s*[^:]+)?:', content, re.MULTILINE)
            total_functions += len(functions)
            type_hint_count += sum(1 for annotation in functions if annotation)
            docstring_count += content.count('"""')
            french_comment_count += len(
                re.findall(r'#.*[àâçéèêëîïôùûü]', content, re.IGNORECASE)
            )

        return {
            "analyzed_files": len(sample),
            "functions_seen": total_functions,
            "type_hints_ratio": round(type_hint_count / total_functions, 2) if total_functions else 0.0,
            "docstring_blocks": docstring_count,
            "french_comments": french_comment_count,
            "expected_style": {
                "comments": "français",
                "docstrings": "obligatoires sur les fonctions publiques",
                "naming": "snake_case pour les fonctions, PascalCase pour les classes",
                "type_hints": "requis sur les signatures",
            },
        }

    def _generate_implementation(
        self,
        context: AgentContext,
        request: str,
        modules: List[str],
        conventions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Demande le code au moteur de modèles.

        Sans modèle disponible, l'agent retourne explicitement le motif du blocage
        au lieu de produire du code non vérifié.
        """
        prompt = (
            "Écris le code demandé en respectant les conventions du projet.\n"
            f"Demande: {request}\n"
            f"Modules concernés: {', '.join(modules)}\n"
            f"Conventions: {conventions.get('expected_style')}\n"
        )

        outcome = context.generate(prompt, {"task_type": "code_generation"})

        if outcome.get("status") == "success":
            return {"status": "generated", "code": outcome["text"], "model_id": outcome.get("model_id")}

        return {
            "status": "not_generated",
            "reason": outcome.get("reason", "Aucun modèle disponible"),
            "specification": {
                "modules_to_modify": modules,
                "conventions_to_follow": conventions.get("expected_style"),
                "requirement": request,
            },
        }

    def _next_steps(self, implementation: Dict[str, Any]) -> List[str]:
        """Indique la suite à donner selon ce qui a pu être produit."""
        if implementation.get("status") == "generated":
            return [
                "Faire relire le code par l'agent reviewer",
                "Exécuter les tests via l'agent tester",
                "Faire analyser les risques par l'agent security",
            ]

        return [
            "Enregistrer un modèle dans le moteur de modèles pour permettre la génération",
            "En attendant, la spécification produite permet une implémentation manuelle",
        ]


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter

    Returns:
        Résultat de l'agent au format standard
    """
    return run_agent_module(CoderAgent, input_data)
