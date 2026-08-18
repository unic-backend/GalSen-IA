"""
Agent package for GalSen IA.

Exposes the agent runtime, the execution context handed to agents, and the base
class every agent derives from.

`AgentRuntime` est un adaptateur : l'orchestration appartient à `RouterEngine`
(`src/router/`). Voir `src/agent/runtime.py` pour ce que la fusion a corrigé.
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
