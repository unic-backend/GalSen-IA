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
from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module


class TesterAgent(BaseAgent):
    """Agent qui exécute les suites de tests et rend compte des résultats."""

    agent_id = "tester"
    required_engines = ("tool", "memory")

    # Délai maximum accordé à une suite, en secondes
    SUITE_TIMEOUT = 120

    # Délai du lot unique : il exécute toutes les suites retenues d'un coup.
    # Plus large qu'une suite seule, sans être infini — un lot qui dépasse ce
    # délai retombe sur l'exécution suite par suite, qui dira laquelle bloque.
    BATCH_TIMEOUT = 600

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
            return self._run_batch(context, suites)
        finally:
            # L'environnement du processus est restauré même en cas d'erreur,
            # sinon les exécutions suivantes se croiraient imbriquées
            if previous_value is None:
                os.environ.pop(self.REENTRANCY_FLAG, None)
            else:
                os.environ[self.REENTRANCY_FLAG] = previous_value

    def _run_batch(self, context: AgentContext, suites: List[str]) -> List[Dict[str, Any]]:
        """
        Exécute toutes les suites en **une seule** invocation de pytest.

        Un processus par suite payait l'import complet de la plateforme à chaque
        fois : 92 suites prenaient 97 s, dont l'essentiel en démarrages répétés.
        Un lot unique paie cet import une fois. Le verdict par suite est
        reconstruit depuis la sortie : pytest nomme le fichier de chaque échec.

        Retombe sur l'exécution suite par suite si le lot n'a pas pu tourner —
        un rapport détaillé vaut mieux qu'aucun rapport.
        """
        if not suites:
            return []

        outcome = context.use_tool(
            "terminal", ["python", "-m", "pytest", *suites, "-q"],
            timeout=self.BATCH_TIMEOUT,
        )
        if outcome.get("status") != "success":
            return [self._run_suite(context, suite) for suite in suites]

        execution = outcome["result"]
        sortie = f"{execution.get('stdout', '')}\n{execution.get('stderr', '')}"
        if execution.get("timed_out"):
            return [self._run_suite(context, suite) for suite in suites]

        # Fichiers cités dans les lignes d'échec : `tests/test_x.py::test_y FAILED`
        en_echec = set(re.findall(r'^(\S+\.py)(?:::\S+)? (?:FAILED|ERROR)', sortie, re.MULTILINE))
        en_echec |= set(re.findall(r'^(?:FAILED|ERROR) (\S+\.py)', sortie, re.MULTILINE))

        suites_en_echec = self._suites_citees(suites, en_echec)

        total_tests = self._count_tests(sortie)
        resultats: List[Dict[str, Any]] = []
        for suite in suites:
            echoue = suite in suites_en_echec
            resultat: Dict[str, Any] = {
                "suite": suite,
                "passed": not echoue,
                "returncode": execution.get("returncode"),
                "timed_out": False,
                "assertions": 0,
                # Le lot ne dit pas combien de tests chaque fichier a exécutés :
                # le total est rapporté à part plutôt qu'attribué au hasard.
                "tests": None,
            }
            if echoue:
                resultat["output"] = sortie[-self.FAILURE_OUTPUT_CHARS:]
            resultats.append(resultat)

        if total_tests == 0:
            for resultat in resultats:
                resultat["passed"] = False
                resultat["reason"] = "aucun test collecté : le lot n'a rien exécuté"
        return resultats

    def _suites_citees(self, suites: List[str], cites: set) -> set:
        """
        Associe les chemins cités par pytest aux suites réellement lancées.

        Le rapprochement se fait sur le **chemin résolu**, pas sur un suffixe de
        chaîne. C'était le défaut : pytest nomme un fichier relativement à sa
        propre racine, ce qui donne des chemins comme
        `../../../../../t/test_x.py`. Ni `suite.endswith(cite)` ni
        `cite.endswith(suite)` n'y répondent, donc une suite **en échec était
        rapportée comme réussie** — le pire résultat possible pour l'agent dont
        le métier est de dire ce qui échoue.

        Le repli par nom de fichier ne s'applique que si ce nom ne désigne
        qu'une seule suite du lot : deux `test_x.py` dans des dossiers
        différents attribueraient l'échec au hasard, et attribuer au hasard est
        pire que ne pas attribuer.

        Args:
            suites: Les suites passées à pytest, telles que reçues.
            cites: Les chemins relevés dans les lignes d'échec.

        Returns:
            Les suites du lot que pytest a citées en échec.
        """
        par_chemin = {os.path.realpath(suite): suite for suite in suites}

        noms = {}
        for suite in suites:
            noms.setdefault(os.path.basename(suite), []).append(suite)

        trouvees = set()
        for cite in cites:
            resolu = os.path.realpath(cite)
            if resolu in par_chemin:
                trouvees.add(par_chemin[resolu])
                continue
            homonymes = noms.get(os.path.basename(cite), [])
            if len(homonymes) == 1:
                trouvees.add(homonymes[0])
        return trouvees

    def _run_suite(self, context: AgentContext, suite: str) -> Dict[str, Any]:
        """Exécute une suite par pytest et interprète son résultat.

        L'agent lançait `python <suite>`, ce qui n'exécute que le bloc
        `__main__` du fichier : **20 des 92 suites en ont un**. Les 72 autres
        s'importaient sans lancer un seul test et sortaient à 0, donc l'agent les
        comptait comme réussies. Un rapport de tests qui compte des suites vides
        est exactement la fabrication que `.claude/rules/verification.md`
        interdit. `python -m pytest` exécute les tests, quel que soit le fichier.
        """
        outcome = context.use_tool(
            "terminal", ["python", "-m", "pytest", suite, "-q"], timeout=self.SUITE_TIMEOUT
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

        tests_executes = self._count_tests(output)
        result: Dict[str, Any] = {
            "suite": suite,
            "passed": passed,
            "returncode": execution.get("returncode"),
            "timed_out": execution.get("timed_out", False),
            "assertions": self._count_assertions(output),
            # Une suite qui ne collecte aucun test n'est pas une suite qui passe :
            # le compte est rapporté pour que « 92 suites vertes » veuille dire
            # quelque chose.
            "tests": tests_executes,
        }
        if tests_executes == 0:
            # Deux chemins mènent ici : pytest sort à 5 quand il ne collecte rien,
            # et sortait à 0 quand le fichier était exécuté comme un script. Dans
            # les deux cas la suite n'a rien vérifié, et doit le dire.
            result["passed"] = False
            result["reason"] = "aucun test collecté : la suite n'a rien exécuté"

        # La sortie n'est conservée que pour les échecs : c'est là qu'elle sert
        if not passed:
            result["output"] = output[-self.FAILURE_OUTPUT_CHARS:]

        return result

    def _count_assertions(self, output: str) -> int:
        """Compte les vérifications réussies signalées par la suite."""
        return len(re.findall(r'^\[OK\]', output, re.MULTILINE))

    def _count_tests(self, output: str) -> int:
        """Compte les tests réellement exécutés, d'après le résumé de pytest.

        Retourne 0 quand aucun résumé n'est trouvé : mieux vaut signaler une
        suite comme n'ayant rien exécuté que lui prêter des tests supposés.
        """
        total = 0
        for motif in (r'(\d+) passed', r'(\d+) failed', r'(\d+) error'):
            total += sum(int(n) for n in re.findall(motif, output))
        return total

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
