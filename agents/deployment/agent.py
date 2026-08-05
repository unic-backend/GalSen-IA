"""
Deployment Agent for GalSen IA.

Answers one question before a release: is the project actually deployable right
now? It checks the repository state through the Git tool, verifies that the
files a deployment needs are present, and reports the blockers it found.

The agent never deploys. Deployment affects users, and triggering it stays a
human decision.
"""

from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module


class DeploymentAgent(BaseAgent):
    """Agent qui évalue si le projet est prêt à être déployé."""

    agent_id = "deployment"
    required_engines = ("tool", "memory", "knowledge")

    # Fichiers qu'un déploiement reproductible suppose présents
    EXPECTED_ARTIFACTS = (
        ("requirements.txt", "critical", "Les dépendances Python ne sont déclarées nulle part"),
        ("config/settings.yaml", "critical", "La configuration de la plateforme est absente"),
        ("README.md", "low", "Aucune documentation d'entrée pour les opérateurs"),
        (".gitignore", "high", "Sans .gitignore, des secrets peuvent être publiés"),
    )

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Évalue l'état de préparation au déploiement.

        Args:
            context: Contexte d'exécution

        Returns:
            État du dépôt, artefacts présents et manquants, blocages et verdict
        """
        repository = self._check_repository(context)
        artifacts = self._check_artifacts(context)
        test_state = self._check_test_state(context)

        blockers = self._collect_blockers(repository, artifacts, test_state)

        return {
            "repository": repository,
            "artifacts": artifacts,
            "test_state": test_state,
            "blockers": blockers,
            "verdict": {
                "deployable": not blockers,
                "reason": (
                    "Aucun blocage détecté" if not blockers
                    else f"{len(blockers)} blocage(s) à lever avant déploiement"
                ),
            },
        }

    def _check_repository(self, context: AgentContext) -> Dict[str, Any]:
        """Interroge le dépôt Git sur son état courant."""
        outcome = context.use_tool("git", "summary")
        if outcome.get("status") != "success":
            return {"available": False, "reason": outcome.get("error", "Outil git indisponible")}

        summary = outcome["result"]
        if not summary.get("is_repository"):
            return {"available": False, "reason": summary.get("reason")}

        return {
            "available": True,
            "branch": summary.get("branch"),
            "clean": summary.get("clean"),
            "uncommitted_changes": (
                summary.get("modified_count", 0) + summary.get("staged_count", 0)
            ),
            "untracked_files": summary.get("untracked_count", 0),
            "has_remote": bool(summary.get("remotes")),
        }

    def _check_artifacts(self, context: AgentContext) -> Dict[str, Any]:
        """Vérifie la présence des fichiers nécessaires à un déploiement."""
        present: List[str] = []
        missing: List[Dict[str, str]] = []

        for path, severity, explanation in self.EXPECTED_ARTIFACTS:
            outcome = context.use_tool("filesystem", "exists", path)
            if outcome.get("status") == "success" and outcome["result"]:
                present.append(path)
            else:
                missing.append({"path": path, "severity": severity, "reason": explanation})

        return {"present": present, "missing": missing}

    def _check_test_state(self, context: AgentContext) -> Dict[str, Any]:
        """
        Reprend le verdict de l'agent tester s'il s'est exécuté avant.

        L'agent de déploiement ne relance pas les tests : cela dupliquerait un
        travail déjà fait dans le pipeline.
        """
        tester_result = context.previous_result("tester")
        if not tester_result:
            return {
                "known": False,
                "reason": "L'agent tester n'a pas été exécuté dans cette requête",
            }

        verdict = (tester_result.get("result") or {}).get("verdict", {})
        return {
            "known": True,
            "passed": verdict.get("passed", False),
            "reason": verdict.get("reason"),
        }

    def _collect_blockers(
        self,
        repository: Dict[str, Any],
        artifacts: Dict[str, Any],
        test_state: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Rassemble tout ce qui interdit un déploiement immédiat."""
        blockers: List[Dict[str, str]] = []

        if not repository.get("available"):
            blockers.append({
                "category": "repository",
                "severity": "critical",
                "message": repository.get("reason", "Dépôt Git inexploitable"),
                "remediation": "Initialiser le dépôt Git et configurer un dépôt distant",
            })
        elif not repository.get("clean"):
            blockers.append({
                "category": "repository",
                "severity": "high",
                "message": (
                    f"{repository.get('uncommitted_changes', 0)} modification(s) non commitée(s)"
                ),
                "remediation": "Commiter ou remiser les changements avant de déployer",
            })

        for missing in artifacts["missing"]:
            if missing["severity"] in ("critical", "high"):
                blockers.append({
                    "category": "artifact",
                    "severity": missing["severity"],
                    "message": f"{missing['path']} absent: {missing['reason']}",
                    "remediation": f"Créer {missing['path']}",
                })

        if test_state.get("known") and not test_state.get("passed"):
            blockers.append({
                "category": "tests",
                "severity": "critical",
                "message": test_state.get("reason", "Des tests échouent"),
                "remediation": "Corriger les tests en échec",
            })
        elif not test_state.get("known"):
            blockers.append({
                "category": "tests",
                "severity": "high",
                "message": "Aucun résultat de test pour cette requête",
                "remediation": "Exécuter l'agent tester avant de déployer",
            })

        return blockers


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter

    Returns:
        Résultat de l'agent au format standard
    """
    return run_agent_module(DeploymentAgent, input_data)
