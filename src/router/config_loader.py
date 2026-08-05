"""
Configuration Loader for the Router Engine.

Charge la configuration depuis le fichier settings.yaml.
"""

import yaml
import os
from typing import Dict, Any


class ConfigLoader:
    """Charge et gère la configuration de l'application."""

    def __init__(self, config_path: str):
        """
        Initialise le chargeur de configuration.

        Args:
            config_path: Chemin relatif ou absolu vers le fichier YAML de configuration.
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Charge la configuration depuis le fichier YAML."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Le fichier de configuration n'a pas été trouvé à {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Erreur lors de l'analyse du YAML de configuration: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Récupère une valeur de configuration par clé ponctuée.

        Args:
            key: Clé de configuration (ex: 'agents.registry').
            default: Valeur par défaut si la clé n'est pas trouvée.

        Returns:
            Valeur de la configuration ou la valeur par défaut.
        """
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def get_all(self) -> Dict[str, Any]:
        """
        Récupère toute la configuration.

        Returns:
            Dictionnaire contenant toute la configuration.
        """
        return self.config