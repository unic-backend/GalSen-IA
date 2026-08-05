"""
Tool Engine for GalSen IA.

Provides a unified interface for discovering, executing, and managing tools.
"""

import logging
from typing import Any, Dict, List, Optional
from .tool_loader import ToolLoader
from .tool_executor import ToolExecutor


class ToolEngine:
    """
    Central engine for managing and executing tools in GalSen IA.

    The ToolEngine is responsible for:
    - Loading tool configurations from the registry
    - Providing tool discovery capabilities
    - Executing tools synchronously and asynchronously
    - Managing tool lifecycle (caching, reloading)
    """

    def __init__(self, registry_path: str):
        """
        Initialize the tool engine.

        Args:
            registry_path: Path to the tools registry YAML file.
        """
        self.logger = logging.getLogger(__name__)
        self.tool_loader = ToolLoader(registry_path)
        self.tool_executor = ToolExecutor(registry_path)
        self.logger.info("ToolEngine initialized successfully.")

    def execute_tool(self, tool_id: str, *args, **kwargs) -> Any:
        """
        Execute a tool synchronously.

        Args:
            tool_id: The identifier of the tool to execute.
            *args: Positional arguments to pass to the tool.
            **kwargs: Keyword arguments to pass to the tool.

        Returns:
            The result of the tool execution.

        Raises:
            ValueError: If the tool is not found or not enabled.
            Exception: Propagates any exception from the tool execution.
        """
        return self.tool_executor.execute(tool_id, *args, **kwargs)

    async def execute_tool_async(self, tool_id: str, *args, **kwargs) -> Any:
        """
        Execute a tool asynchronously.

        Args:
            tool_id: The identifier of the tool to execute.
            *args: Positional arguments to pass to the tool.
            **kwargs: Keyword arguments to pass to the tool.

        Returns:
            The result of the tool execution.

        Raises:
            ValueError: If the tool is not found or not enabled or asyncio.TimeoutError from the tool execution.
        """
        return await self.tool_executor.async_execute(tool_id, *args, **kwargs)

    def is_tool_enabled(self, tool_id: str) -> bool:
        """
        Check if a tool is enabled.

        Args:
            tool_id: The identifier of the tool to check.

        Returns:
            True if the tool exists and is enabled, False otherwise.
        """
        return self.tool_loader.is_tool_enabled(tool_id)

    def get_tool_info(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific tool.

        Args:
            tool_id: The identifier of the tool.

        Returns:
            Dictionary containing tool information, or None if not found.
        """
        config = self.tool_loader.get_tool_config(tool_id)
        if config is None:
            return None

        # Return a safe copy of the config (excluding sensitive data if any)
        return {
            'id': config.get('id'),
            'enabled': config.get('enabled', False),
            'category': config.get('category'),
            'module': config.get('module'),
            'class': config.get('class'),
            # Note: we don't return the full config for security reasons
            # but we can return a sanitized version if needed
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available tools.

        Returns:
            A list of dictionaries, each containing information about a tool.
        """
        tools = []
        for tool_id in self.tool_loader.get_all_tool_configs():
            info = self.get_tool_info(tool_id)
            if info:
                tools.append(info)
        return tools

    def list_enabled_tools(self) -> List[Dict[str, Any]]:
        """
        List all enabled tools.

        Returns:
            A list of dictionaries for enabled tools.
        """
        return [t for t in self.list_tools() if t['enabled']]

    def reload_tool(self, tool_id: str) -> None:
        """
        Reload a specific tool (useful after configuration changes).

        Args:
            tool_id: The identifier of the tool to reload.
        """
        self.tool_executor.reload_tool(tool_id)
        self.logger.info(f"Tool '{tool_id}' reloaded.")

    def reload_all_tools(self) -> None:
        """
        Reload all tools.
        """
        # Clear the executor's cache, which will force recreation on next use
        self.tool_executor.shutdown()
        self.logger.info("All tools reloaded.")

    def get_tool_categories(self) -> List[str]:
        """
        Get a list of all unique tool categories.

        Returns:
            List of category strings.
        """
        categories = set()
        for tool_info in self.list_tools():
            category = tool_info.get('category')
            if category:
                categories.add(category)
        return sorted(list(categories))

    def get_tools_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all tools in a specific category.

        Args:
            category: The category to filter by.

        Returns:
            List of tool information dictionaries for the specified category.
        """
        return [t for t in self.list_tools() if t.get('category') == category]