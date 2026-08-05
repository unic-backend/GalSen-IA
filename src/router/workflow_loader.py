"""
Workflow Loader for the Router Engine.

Charge les workflows depuis le registre de workflows.
"""

import yaml
import os
from typing import Dict, Any


class WorkflowLoader:
    """Charge et gère les workflows à partir du fichier de registre."""

    def __init__(self, registry_path: str):
        """
        Initialise le chargeur de workflows.

        Args:
            registry_path: Chemin relatif ou absolu vers le fichier YAML du registre de workflows.
        """
        self.registry_path = registry_path
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.default_workflow: str = ""
        self._load_workflows()

    def _load_workflows(self) -> None:
        """Charge les workflows depuis le fichier YAML."""
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data:
                    self.default_workflow = data.get('default_workflow', 'standard')
                    if 'workflows' in data:
                        self.workflows = data['workflows']
        except FileNotFoundError:
            raise FileNotFoundError(f"Le registre de workflows n'a pas été trouvé à {self.registry_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Erreur lors de l'analyse du YAML du registre de workflows: {e}")

    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """
        Récupère la configuration d'un workflow par son identifiant.

        Args:
            workflow_id: Identifiant du workflow.

        Returns:
            Dictionnaire contenant la configuration du workflow.

        Raises:
            KeyError: Si le workflow n'est pas trouvé.
        """
        if workflow_id not in self.workflows:
            raise KeyError(f"Workflow '{workflow_id}' non trouvé dans le registre.")
        return self.workflows[workflow_id]

    def get_default_workflow(self) -> str:
        """
        Récupère l'identifiant du workflow par défaut.

        Returns:
            Identifiant du workflow par défaut.
        """
        return self.default_workflow

    def get_all_workflows(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère tous les workflows chargés.

        Returns:
            Dictionnaire de tous les workflows, indexé par leur identifiant.
        """
        return self.workflows