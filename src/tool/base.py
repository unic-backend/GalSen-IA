"""
Base Tool for GalSen IA.

Defines the interface that all tools must implement.
"""

import abc
from typing import Any, Dict, List
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

    def available_operations(self) -> List[str]:
        """
        Retourne les opérations acceptées par `execute`, triées.

        Un appelant (API, agent, interface) doit pouvoir demander à un outil ce
        qu'il sait faire sans lire son code. L'implémentation par défaut déduit
        la liste des méthodes nommées `_op_<operation>`, la convention suivie
        par la majorité des outils. Un outil dont l'exécution ne se découpe pas
        en opérations nommées retourne une liste vide et documente ses
        arguments dans sa docstring `execute`.

        Returns:
            La liste triée des noms d'opérations.
        """
        return sorted(
            name[len("_op_"):]
            for name in dir(self)
            if name.startswith("_op_") and callable(getattr(self, name))
        )

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