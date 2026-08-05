"""
Backward compatible entry point for agent modules.

Before the integration layer existed, the dispatcher called a module-level
`execute(input_data)` function on each agent. That contract is still supported:
every agent module keeps such a function, which builds a default context and
runs the agent class behind it.

New code should let the dispatcher pass an `AgentContext` instead, so that all
agents of a request share the same memory and the same session.
"""

from typing import Any, Dict, Optional, Type

from .base_agent import BaseAgent
from .context import AgentContext


def run_agent_module(
    agent_class: Type[BaseAgent],
    input_data: Any,
    context: Optional[AgentContext] = None,
) -> Dict[str, Any]:
    """
    Exécute un agent depuis le point d'entrée historique d'un module.

    Args:
        agent_class: Classe de l'agent à exécuter
        input_data: Donnée d'entrée, telle que transmise par le dispatcher
        context: Contexte fourni par l'orchestrateur ; un contexte par défaut
            est créé s'il est absent

    Returns:
        Résultat de l'agent au format standard
    """
    agent = agent_class()
    execution_context = context or AgentContext(
        request=input_data,
        agent_id=agent.agent_id,
    )
    return agent.run(execution_context)
