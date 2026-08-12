"""
Agent Loader for the Router Engine.

Charge les agents depuis le registre d'agents.
"""

import yaml
import os
from typing import Dict, Any


class AgentLoader:
    """Charge et gère les agents à partir du fichier de registre."""

    def __init__(self, registry_path: str):
        """
        Initialise le chargeur d'agents.

        Args:
            registry_path: Chemin relatif ou absolu vers le fichier YAML du registre d'agents.
        """
        self.registry_path = registry_path
        self.agents: Dict[str, Dict[str, Any]] = {}
        self._load_agents()

    def _load_agents(self) -> None:
        """Charge les agents depuis le fichier YAML."""
        # Convertir le chemin relatif en absolu si nécessaire
        if not os.path.isabs(self.registry_path):
            # Supposons que le chemin soit relatif à la racine du projet
            # Nous pouvons déterminer la racine du projet en remontant depuis ce fichier
            # Mais pour simplicité, on supposera que le chemin est relatif au répertoire de travail actuel
            pass
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and 'agents' in data:
                    for agent in data['agents']:
                        self.agents[agent['id']] = agent
        except FileNotFoundError:
            raise FileNotFoundError(f"Le registre d'agents n'a pas été trouvé à {self.registry_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Erreur lors de l'analyse du YAML du registre d'agents: {e}")

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """
        Récupère la configuration d'un agent par son identifiant.

        Args:
            agent_id: Identifiant de l'agent.

        Returns:
            Dictionnaire contenant la configuration de l'agent.

        Raises:
            KeyError: Si l'agent n'est pas trouvé.
        """
        if agent_id not in self.agents:
            raise KeyError(f"Agent '{agent_id}' non trouvé dans le registre.")
        return self.agents[agent_id]

    def get_all_agents(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère tous les agents chargés.

        Returns:
            Dictionnaire de tous les agents, indexé par leur identifiant.
        """
        return self.agents

    def is_enabled(self, agent_id: str) -> bool:
        """
        Vérifie si un agent est activé.

        Args:
            agent_id: Identifiant de l'agent.

        Returns:
            True si l'agent est activé, False sinon.
        """
        agent = self.get_agent(agent_id)
        return agent.get('enabled', False)