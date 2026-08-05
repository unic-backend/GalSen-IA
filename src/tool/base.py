"""
Base Tool for GalSen IA.

Defines the interface that all tools must implement.
"""

import abc
from typing import Any, Dict
import asyncio


class BaseTool(abc.ABC):
    """Abstract base class for all tools in GalSen IA."""

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the tool with configuration.

        Args:
            config: Tool-specific configuration dictionary.
        """
        self.config = config or {}

    @abc.abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute the tool synchronously.

        Args:
            *args: Positional arguments for the tool execution.
            **kwargs: Keyword arguments for the tool execution.

        Returns:
            The result of the tool execution.
        """
        pass

    async def async_execute(self, *args, **kwargs) -> Any:
        """
        Execute the tool asynchronously.

        By default, runs the synchronous execute method in a thread pool.
        Tools can override this for native async implementation.

        Args:
            *args: Positional arguments for the tool execution.
            **kwargs: Keyword arguments for the tool execution.

        Returns:
            The result of the tool execution.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, *args, **kwargs)