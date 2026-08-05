"""
Execution Planner for the Router Engine.

Planifie l'exécution des agents selon le workflow défini.
"""

from typing import List, Dict, Any, Set
from .workflow_loader import WorkflowLoader


class ExecutionPlanner:
    """Planifie l'ordre d'exécution des agents."""

    def __init__(self, workflow_loader: WorkflowLoader):
        """
        Initialise le planificateur d'exécution.

        Args:
            workflow_loader: Instance du chargeur de workflows.
        """
        self.workflow_loader = workflow_loader

    def plan_execution(self, workflow_id: str = None) -> Dict[str, List[str]]:
        """
        Crée un plan d'exécution pour le workflow spécifié.

        Args:
            workflow_id: Identifiant du workflow. Si None, utilise le workflow par défaut.

        Returns:
            Dictionnaire contenant deux listes :
                - 'parallel': liste d'identifiants d'agents à exécuter en parallèle
                - 'sequential': liste d'identifiants d'agents à exécuter séquentiellement
        """
        if workflow_id is None:
            workflow_id = self.workflow_loader.get_default_workflow()

        workflow = self.workflow_loader.get_workflow(workflow_id)

        # Extraire les groupes d'exécution
        execution_config = workflow.get('execution', {})
        parallel_agents = execution_config.get('parallel_agents', [])
        sequential_agents = execution_config.get('sequential_agents', [])

        # S'assurer qu'il n'y a pas de doublons entre les groupes (optionnel)
        # On pourrait aussi vérifier que tous les agents du workflow sont présents dans l'un des groupes

        return {
            'parallel': parallel_agents,
            'sequential': sequential_agents
        }

    def get_agents_in_workflow(self, workflow_id: str = None) -> Set[str]:
        """
        Récupère l'ensemble des agents référencés dans un workflow.

        Args:
            workflow_id: Identifiant du workflow. Si None, utilise le workflow par défaut.

        Returns:
            Ensemble des identifiants d'agents présents dans le workflow.
        """
        if workflow_id is None:
            workflow_id = self.workflow_loader.get_default_workflow()

        workflow = self.workflow_loader.get_workflow(workflow_id)
        agents = set()

        # Ajouter les agents du pipeline (si défini)
        pipeline = workflow.get('pipeline', [])
        agents.update(pipeline)

        # Ajouter les agents des groupes d'exécution
        execution_config = workflow.get('execution', {})
        agents.update(execution_config.get('parallel_agents', []))
        agents.update(execution_config.get('sequential_agents', []))

        return agents