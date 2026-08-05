"""
Agent package for GalSen IA.

Exposes the agent runtime, the execution context handed to agents, and the base
class every agent derives from.
"""

from .base_agent import AgentResult, BaseAgent
from .context import AgentContext
from .runtime import AgentRuntime

__all__ = [
    "AgentContext",
    "AgentResult",
    "AgentRuntime",
    "BaseAgent",
]
