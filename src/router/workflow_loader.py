"""
Workflow Loader for the Router Engine.

Charge les workflows depuis le registre de workflows.
"""

import logging
import yaml
import os
from typing import Any, Dict, Iterable, List, Optional

from .workflow_validator import ProblemeWorkflow, blocking_errors, validate_registry


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
        self._registry: Dict[str, Any] = {}
        self._problems: List[ProblemeWorkflow] = []
        self._logger = logging.getLogger(__name__)
        self._load_workflows()

    def _load_workflows(self) -> None:
        """Charge les workflows depuis le fichier YAML."""
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data:
                    self._registry = data
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

    def validate(self, agents_connus: Iterable[str],
                 journaliser: bool = True) -> List[ProblemeWorkflow]:
        """
        Valide le registre chargé contre les agents réellement enregistrés.

        La validation n'a pas lieu au chargement : le chargeur ne connaît pas la
        liste des agents, et la lui faire deviner recréerait le couplage que le
        registre déclaratif évite. C'est l'appelant qui la déclenche, une fois.

        Args:
            agents_connus: identifiants des agents enregistrés
            journaliser: écrit chaque problème dans le journal

        Returns:
            La liste des problèmes trouvés (erreurs et avertissements).
        """
        self._problems = validate_registry(self._registry, agents_connus)
        if journaliser:
            for probleme in self._problems:
                detail = probleme.to_dict()
                niveau = self._logger.error if probleme.gravite == "error" else self._logger.warning
                niveau("Workflow '%s' — %s", detail["workflow"], detail["message"])
        return self._problems

    def get_problems(self, workflow_id: Optional[str] = None) -> List[ProblemeWorkflow]:
        """Retourne les problèmes trouvés lors de la dernière validation."""
        if workflow_id is None:
            return list(self._problems)
        return [p for p in self._problems if p.workflow == workflow_id]

    def is_executable(self, workflow_id: str) -> bool:
        """
        Indique si un workflow peut être exécuté sans produire un résultat trompeur.

        Un workflow sans étape ou citant un agent inexistant n'est pas
        exécutable : le premier rapporterait un succès sans rien faire, le second
        s'arrêterait à mi-parcours.
        """
        return not blocking_errors(self.get_problems(workflow_id))
