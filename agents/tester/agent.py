"""
Tester Agent for GalSen IA.

Actually runs the project test suites through the terminal tool and reports what
happened. The verdict comes from process exit codes, not from an assumption:
a suite that fails is reported as failing, with its output.

Some suites exercise the Router Engine, which runs every agent — including this
one. Without protection the agent would launch itself endlessly, so nested
execution is detected and refused.
"""

import os
import re
from typing import Any, Dict, List, Optional

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module


class TesterAgent(BaseAgent):
    """Agent qui exécute les suites de tests et rend compte des résultats."""

    agent_id = "tester"
    required_engines = ("tool", "memory")

    # Délai maximum accordé à une suite, en secondes
    SUITE_TIMEOUT = 120

    # Nombre de caractères de sortie conservés pour une suite en échec
    FAILURE_OUTPUT_CHARS = 2000

    # Marqueur hérité par les processus fils, qui signale une exécution imbriquée.
    # Une suite qui passe par le Router Engine relance tous les agents, donc
    # celui-ci : sans ce garde-fou, l'agent se relancerait indéfiniment.
    REENTRANCY_FLAG = "GALSEN_TESTER_ACTIVE"

    # Suites qui exercent l'orchestrateur, et relancent donc tous les agents.
    # Les exécuter depuis un agent est circulaire : le résultat ne dit rien sur
    # l'orchestrateur, et coûte une exécution complète du pipeline. Elles sont
    # écartées sauf demande explicite via l'option `include_orchestration`.
    ORCHESTRATION_SUITES = ("test_router.py", "test_agent_runtime.py")

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Exécute les suites de tests du projet.

        Args:
            context: Contexte d'exécution

        Returns:
            Suites exécutées, résultat de chacune et verdict global
        """
        if os.environ.get(self.REENTRANCY_FLAG) == "1":
            return {
                "skipped": True,
                "reason": (
                    "Exécution imbriquée: cet agent tourne déjà dans une suite de tests. "
                    "Relancer les suites ici provoquerait une récursion infinie."
                ),
                "suites_executed": 0,
                "verdict": {"passed": True, "reason": "Tests délégués à l'exécution parente"},
            }

        suites = self._discover_suites(context)
        if not suites:
            return {
                "suites_found": 0,
                "executed": [],
                "verdict": {"passed": False, "reason": "Aucune suite de tests trouvée"},
            }

        requested = self._filter_requested(suites, context.request_text())
        runnable, excluded = self._exclude_orchestration_suites(requested, context)
        executions = self._run_suites(context, runnable)

        passed = [run for run in executions if run["passed"]]
        failed = [run for run in executions if not run["passed"]]

        return {
            "suites_found": len(suites),
            "suites_executed": len(executions),
            "suites_excluded": excluded,
            "passed_count": len(passed),
            "failed_count": len(failed),
            "executed": executions,
            "failed_suites": [run["suite"] for run in failed],
            "verdict": self._verdict(passed, failed),
        }

    def _exclude_orchestration_suites(
        self, suites: List[str], context: AgentContext
    ) -> tuple:
        """
        Écarte les suites qui relanceraient l'orchestrateur.

        Args:
            suites: Suites candidates
            context: Contexte, dont l'option `include_orchestration`

        Returns:
            Couple (suites à exécuter, suites écartées avec leur motif)
        """
        if context.options.get("include_orchestration", False):
            return suites, []

        runnable = []
        excluded = []

        for suite in suites:
            if suite.rsplit('/', 1)[-1] in self.ORCHESTRATION_SUITES:
                excluded.append({
                    "suite": suite,
                    "reason": "Suite d'orchestration: l'exécuter depuis un agent est circulaire",
                })
            else:
                runnable.append(suite)

        return runnable, excluded

    def _discover_suites(self, context: AgentContext) -> List[str]:
        """Trouve les suites de tests à la racine du projet."""
        outcome = context.use_tool("filesystem", "search", "test_*.py", directory=".", max_depth=1)
        return sorted(outcome["result"]) if outcome.get("status") == "success" else []

    def _filter_requested(self, suites: List[str], request: str) -> List[str]:
        """
        Restreint l'exécution aux suites citées dans la demande.

        Sans mention explicite, toutes les suites sont exécutées : c'est le
        comportement attendu d'une validation avant livraison.
        """
        normalized = request.lower()

        targeted = [
            suite for suite in suites
            if self._suite_subject(suite) in normalized
        ]

        return targeted or suites

    def _suite_subject(self, suite: str) -> str:
        """Extrait le sujet d'une suite: `test_memory_engine.py` donne `memory`."""
        name = suite.rsplit('/', 1)[-1]
        name = name[len("test_"):] if name.startswith("test_") else name
        name = name[: -len(".py")] if name.endswith(".py") else name
        return name.split('_')[0]

    def _run_suites(self, context: AgentContext, suites: List[str]) -> List[Dict[str, Any]]:
        """
        Exécute les suites en marquant l'environnement pendant toute la durée.

        Le marqueur est hérité par les processus fils : une suite qui déclenche
        le Router Engine verra donc que cet agent est déjà actif, et n'en
        relancera pas un second.
        """
        previous_value = os.environ.get(self.REENTRANCY_FLAG)
        os.environ[self.REENTRANCY_FLAG] = "1"

        try:
            return [self._run_suite(context, suite) for suite in suites]
        finally:
            # L'environnement du processus est restauré même en cas d'erreur,
            # sinon les exécutions suivantes se croiraient imbriquées
            if previous_value is None:
                os.environ.pop(self.REENTRANCY_FLAG, None)
            else:
                os.environ[self.REENTRANCY_FLAG] = previous_value

    def _run_suite(self, context: AgentContext, suite: str) -> Dict[str, Any]:
        """Exécute une suite et interprète son résultat."""
        outcome = context.use_tool(
            "terminal", ["python", suite], timeout=self.SUITE_TIMEOUT
        )

        if outcome.get("status") != "success":
            return {
                "suite": suite,
                "passed": False,
                "returncode": None,
                "reason": outcome.get("error", "Exécution impossible"),
                "assertions": 0,
            }

        execution = outcome["result"]
        passed = execution.get("success", False) and not execution.get("timed_out", False)
        output = f"{execution.get('stdout', '')}\n{execution.get('stderr', '')}"

        result: Dict[str, Any] = {
            "suite": suite,
            "passed": passed,
            "returncode": execution.get("returncode"),
            "timed_out": execution.get("timed_out", False),
            "assertions": self._count_assertions(output),
        }

        # La sortie n'est conservée que pour les échecs : c'est là qu'elle sert
        if not passed:
            result["output"] = output[-self.FAILURE_OUTPUT_CHARS:]

        return result

    def _count_assertions(self, output: str) -> int:
        """Compte les vérifications réussies signalées par la suite."""
        return len(re.findall(r'^\[OK\]', output, re.MULTILINE))

    def _verdict(self, passed: List[Dict[str, Any]], failed: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Conclut sur l'état des tests."""
        if failed:
            names = ', '.join(run["suite"] for run in failed)
            return {
                "passed": False,
                "reason": f"{len(failed)} suite(s) en échec: {names}",
                "action_required": "Corriger les échecs avant toute livraison",
            }

        return {
            "passed": True,
            "reason": f"Les {len(passed)} suites exécutées passent",
        }


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter

    Returns:
        Résultat de l'agent au format standard
    """
    return run_agent_module(TesterAgent, input_data)
