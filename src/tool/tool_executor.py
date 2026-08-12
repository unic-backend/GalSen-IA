"""
Tool Executor for GalSen IA.

Executes tools synchronously and asynchronously.
"""

import logging
import os
from typing import Any, Dict
from .tool_loader import ToolLoader
from .base import BaseTool


class ToolExecutor:
    """Executes tools by dynamically loading and instantiating them."""

    def __init__(self, registry_path: str = None):
        """
        Initialize the tool executor.

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
        self.tool_loader = ToolLoader(registry_path)
        self.logger = logging.getLogger(__name__)
        self._tool_instances: Dict[str, BaseTool] = {}

    def execute(self, tool_id: str, *args, **kwargs) -> Any:
        """
        Execute a tool synchronously.

        Args:
            tool_id: The identifier of the tool to execute.
            *args: Positional arguments to pass to the tool's execute method.
            **kwargs: Keyword arguments to pass to the tool's execute method.

        Returns:
            The result of the tool execution.

        Raises:
            ValueError: If the tool is not found or not enabled.
            Exception: If there is an error during tool execution.
        """
        if not self.tool_loader.is_tool_enabled(tool_id):
            raise ValueError(f"Tool '{tool_id}' is not found or not enabled.")

        # Get or create the tool instance
        if tool_id not in self._tool_instances:
            tool_class = self.tool_loader.get_tool_class(tool_id)
            if tool_class is None:
                raise ValueError(f"Could not load class for tool '{tool_id}'.")
            config = self.tool_loader.get_tool_config(tool_id)
            self._tool_instances[tool_id] = tool_class(config.get('config', {}))

        tool_instance = self._tool_instances[tool_id]
        try:
            self.logger.debug(f"Executing tool '{tool_id}' synchronously.")
            return tool_instance.execute(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error executing tool '{tool_id}': {e}")
            raise

    async def async_execute(self, tool_id: str, *args, **kwargs) -> Any:
        """
        Execute a tool asynchronously.

        Args:
            tool_id: The identifier of the tool to execute.
            *args: Positional arguments to pass to the tool's execute method.
            **kwargs: Keyword arguments to pass to the tool's execute method.

        Returns:
            The result of the tool execution.

        Raises:
            ValueError: If the tool is not found or not enabled.
            Exception: If there is an error during tool execution.
        """
        if not self.tool_loader.is_tool_enabled(tool_id):
            raise ValueError(f"Tool '{tool_id}' is not found or not enabled.")

        # Get or create the tool instance
        if tool_id not in self._tool_instances:
            tool_class = self.tool_loader.get_tool_class(tool_id)
            if tool_class is None:
                raise ValueError(f"Could not load class for tool '{tool_id}'.")
            config = self.tool_loader.get_tool_config(tool_id)
            self._tool_instances[tool_id] = tool_class(config.get('config', {}))

        tool_instance = self._tool_instances[tool_id]
        try:
            self.logger.debug(f"Executing tool '{tool_id}' asynchronously.")
            # Use the tool's async_execute method (which may run in a thread pool by default)
            return await tool_instance.async_execute(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Error executing tool '{tool_id}' asynchronously: {e}")
            raise

    def reload_tool(self, tool_id: str) -> None:
        """
        Reload a tool instance (useful if configuration changed).

        Args:
            tool_id: The identifier of the tool to reload.
        """
        if tool_id in self._tool_instances:
            del self._tool_instances[tool_id]
        # The next call to execute or async_execute will recreate the instance

    def shutdown(self) -> None:
        """
        Shutdown the executor and clean up resources.
        """
        # Currently, we don't have any resources to clean up, but we can clear the cache
        self._tool_instances.clear()