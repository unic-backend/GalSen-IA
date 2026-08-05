"""
Tool Loader for GalSen IA.

Loads tool configurations from the tools registry YAML file.
"""

import logging
import yaml
import os
from typing import Dict, Any, Optional, Type
from .base import BaseTool

logger = logging.getLogger(__name__)


class ToolLoader:
    """Loads and manages tool configurations from the registry."""

    def __init__(self, registry_path: str = None):
        """
        Initialize the tool loader.

        Args:
            registry_path: Path to the tools registry YAML file.
                           Si None, utilise le chemin par défaut 'tools/tools.yaml'.
        """
        if registry_path is None:
            # Chemin par défaut relatif à la racine du projet
            registry_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "tools", "tools.yaml"
            )
        self.registry_path = registry_path
        self._tools_config: Dict[str, Dict[str, Any]] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load the tools registry from the YAML file."""
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and 'tools' in data:
                    for tool_config in data['tools']:
                        tool_id = tool_config.get('id')
                        if tool_id:
                            self._tools_config[tool_id] = tool_config
        except FileNotFoundError:
            raise FileNotFoundError(f"Tools registry not found at {self.registry_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML in tools registry: {e}")

    def get_tool_config(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the configuration for a specific tool.

        Args:
            tool_id: The identifier of the tool.

        Returns:
            The tool configuration dictionary, or None if not found.
        """
        return self._tools_config.get(tool_id)

    def get_all_tool_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get configurations for all tools.

        Returns:
            A dictionary mapping tool IDs to their configurations.
        """
        return self._tools_config.copy()

    def is_tool_enabled(self, tool_id: str) -> bool:
        """
        Check if a tool is enabled.

        Args:
            tool_id: The identifier of the tool.

        Returns:
            True if the tool exists and is enabled, False otherwise.
        """
        config = self.get_tool_config(tool_id)
        return config is not None and config.get('enabled', False)

    def get_tool_class(self, tool_id: str) -> Optional[Type[BaseTool]]:
        """
        Get the tool class for a given tool ID.

        Args:
            tool_id: The identifier of the tool.

        Returns:
            The tool class (subclass of BaseTool), or None if not found or invalid.
        """
        config = self.get_tool_config(tool_id)
        if not config:
            logger.warning("Outil '%s' absent du registre %s.", tool_id, self.registry_path)
            return None

        module_path = config.get('module')
        class_name = config.get('class')
        if not module_path or not class_name:
            logger.warning(
                "Outil '%s' mal déclaré : 'module' et 'class' sont requis (module=%r, class=%r).",
                tool_id, module_path, class_name,
            )
            return None

        try:
            # Convert module path to absolute import relative to src
            # Assuming module_path is like "tools.filesystem.tool"
            full_module_path = f"src.{module_path}"
            module = __import__(full_module_path, fromlist=[class_name])
            return getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            # Un échec silencieux rendait un outil introuvable sans la moindre trace :
            # la cause réelle (dépendance manquante, classe renommée) est journalisée.
            logger.warning(
                "Chargement de l'outil '%s' impossible depuis %s.%s : %s: %s",
                tool_id, full_module_path, class_name, type(e).__name__, e,
            )
            return None