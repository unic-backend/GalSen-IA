"""
Agent Dispatcher for the Router Engine.

Responsible for dynamically loading and executing agents.

Two calling conventions are supported, in this order:

1. **Context based** — the module exposes a `BaseAgent` subclass. The dispatcher
   instantiates it and hands it the `AgentContext`, so the agent reaches the
   engines and shares the memory of the current request.
2. **Legacy** — the module exposes a plain `execute(input_data)` function. This
   is the contract that existed before the integration layer, and it keeps
   working so that older agents and tests are unaffected.

Whatever the convention, the result is checked against the output contract
(`output_validation`) before leaving this class. The legacy convention makes the
check necessary rather than defensive: `execute()` returns whatever its author
wrote, and a non-dictionary used to raise an `AttributeError` in the middle of
aggregation — failing the whole request, including the agents that had already
succeeded.
"""

import importlib
import inspect
import logging
from typing import Any, Dict, Optional, Type

from .output_validation import validated


class AgentDispatcher:
    """Dispatches requests to agents based on their module configuration."""

    def __init__(self):
        """Initialise le dispatcher d'agents."""
        self.logger = logging.getLogger(__name__)
        # Les classes trouvées sont conservées : l'import d'un module est coûteux
        # et le dispatcher est appelé pour chaque agent de chaque requête
        self._agent_classes: Dict[str, Optional[Type]] = {}

    def dispatch_by_id(
        self,
        agent_id: str,
        input_data: Any,
        context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Exécute un agent désigné par son identifiant.

        Sert la délégation d'agent à agent (VOLET 29) : un agent connaît le nom
        de celui qu'il sollicite, pas sa configuration. La configuration est lue
        dans le registre déclaré, jamais reconstruite ici — sinon un agent
        délégué tournerait avec des réglages différents de ceux qu'il a quand
        l'orchestrateur l'appelle.

        Args:
            agent_id: Identifiant de l'agent, tel que déclaré dans le registre.
            input_data: Données d'entrée.
            context: `AgentContext` de l'appelant, dérivé pour l'agent sollicité.

        Returns:
            Le résultat de l'agent, ou un résultat d'erreur si l'agent est inconnu.
        """
        import os

        from .agent_loader import AgentLoader

        racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        registre = AgentLoader(os.path.join(racine, "agents", "registry.yaml"))
        configuration = registre.get_all_agents().get(agent_id)

        if not configuration:
            return self._create_error_result(
                agent_id,
                f"Agent « {agent_id} » inconnu du registre : la délégation est refusée.",
            )
        return self.dispatch(configuration, input_data, context)

    def dispatch(
        self,
        agent_config: Dict[str, Any],
        input_data: Any,
        context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Exécute l'agent spécifié avec les données d'entrée.

        Args:
            agent_config: Configuration de l'agent provenant du registre.
            input_data: Données d'entrée pour l'agent.
            context: `AgentContext` fourni par l'orchestrateur. Quand il est
                absent, l'agent en construit un par défaut.

        Returns:
            Dictionnaire contenant le résultat de l'exécution de l'agent.
        """
        agent_id = agent_config.get('id', 'unknown')
        module_path = agent_config.get('module')

        # Le routeur est spécial : il ne doit pas être invoqué via le dispatcher
        if agent_id == 'router':
            self.logger.warning(
                "Tentative d'invoquer le routeur via le dispatcher. "
                "Cela devrait être géré par le RouterEngine."
            )
            return self._create_error_result(
                agent_id, "Le routeur ne peut pas être invoqué via le dispatcher."
            )

        if not module_path:
            self.logger.error(f"Aucun module spécifié pour l'agent '{agent_id}'")
            return self._create_error_result(
                agent_id, f"Aucun module spécifié pour l'agent '{agent_id}'"
            )

        try:
            module = importlib.import_module(module_path)
        except ImportError as error:
            self.logger.error(f"Erreur lors de l'importation de l'agent '{agent_id}': {error}")
            return self._create_error_result(
                agent_id, f"Erreur lors de l'importation du module: {error}"
            )

        try:
            agent_class = self._find_agent_class(module_path, module)

            if agent_class is not None:
                result = self._run_agent_class(agent_class, input_data, context)
            elif hasattr(module, 'execute'):
                result = module.execute(input_data)
            else:
                self.logger.error(
                    f"Le module '{module_path}' n'expose ni classe d'agent ni fonction 'execute'"
                )
                return self._create_error_result(
                    agent_id,
                    f"Le module '{module_path}' ne contient pas de fonction 'execute'",
                )

            # Frontière : c'est ici qu'une sortie d'agent entre dans la
            # plateforme. La valider une fois évite que chaque code en aval —
            # agrégateur, routeur, historique — se défende contre une forme
            # inattendue, ce qu'aucun d'eux ne faisait.
            verifie = validated(result, agent_id)
            if verifie is not result:
                self.logger.error(
                    "Agent '%s' : sortie rejetée — %s", agent_id, verifie["error"],
                )
                return verifie

            # Le message d'origine annonçait le succès quel que soit le statut
            # rendu, y compris pour une erreur.
            self.logger.info(
                "Agent '%s' exécuté ; statut : %s.", agent_id, verifie["status"],
            )
            return verifie

        except Exception as error:
            self.logger.error(f"Erreur lors de l'exécution de l'agent '{agent_id}': {error}")
            return self._create_error_result(agent_id, f"Erreur lors de l'exécution: {error}")

    def _find_agent_class(self, module_path: str, module: Any) -> Optional[Type]:
        """
        Cherche la classe d'agent exposée par un module.

        Args:
            module_path: Chemin du module, servant de clé de cache
            module: Module déjà importé

        Returns:
            La sous-classe concrète de `BaseAgent` du module, ou None
        """
        if module_path in self._agent_classes:
            return self._agent_classes[module_path]

        agent_class = None
        try:
            from ..agent.base_agent import BaseAgent

            for _, candidate in inspect.getmembers(module, inspect.isclass):
                # Seules les classes définies dans ce module comptent : celles
                # simplement importées appartiennent à un autre agent
                if (
                    issubclass(candidate, BaseAgent)
                    and candidate is not BaseAgent
                    and candidate.__module__ == module.__name__
                ):
                    agent_class = candidate
                    break
        except ImportError:
            # Sans la couche d'intégration, seul le contrat historique existe
            agent_class = None

        self._agent_classes[module_path] = agent_class
        return agent_class

    def _run_agent_class(
        self, agent_class: Type, input_data: Any, context: Optional[Any]
    ) -> Dict[str, Any]:
        """
        Instancie un agent de classe et l'exécute avec le contexte adéquat.

        Args:
            agent_class: Classe de l'agent
            input_data: Données d'entrée
            context: Contexte transmis par l'orchestrateur, éventuellement absent

        Returns:
            Résultat de l'agent
        """
        agent = agent_class()

        if context is None:
            from ..agent.context import AgentContext
            context = AgentContext(request=input_data, agent_id=agent.agent_id)
        else:
            # Le contexte porte l'identité de l'agent en cours pour tracer
            # correctement ses écritures en mémoire
            context = context.derive(agent.agent_id)

        return agent.run(context)

    def _create_error_result(self, agent_id: str, error_message: str) -> Dict[str, Any]:
        """
        Crée un résultat d'erreur standardisé.

        Args:
            agent_id: Identifiant de l'agent.
            error_message: Message d'erreur.

        Returns:
            Dictionnaire représentant le résultat d'erreur.
        """
        return {
            "agent": agent_id,
            "status": "error",
            "error": error_message,
            "result": None
        }
