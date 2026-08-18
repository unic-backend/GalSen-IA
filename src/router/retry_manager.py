"""
Retry Manager for the Router Engine.

Handles retry logic for failed agents based on workflow configuration.
"""

import logging
import time
from typing import Dict, Any, Callable


class RetryManager:
    """Gère les nouvelles tentatives pour les agents échoués."""

    def __init__(self, max_attempts: int = 3, delay_seconds: float = 1.0):
        """
        Initialise le gestionnaire de nouvelles tentatives.

        Args:
            max_attempts: Nombre maximum de tentatives (y compris la première tentative).
            delay_seconds: Délai entre les tentatives en secondes.
        """
        self.max_attempts = max_attempts
        self.delay_seconds = delay_seconds
        self.logger = logging.getLogger(__name__)

    def execute_with_retry(self,
                          agent_dispatcher_callable: Callable[..., Dict[str, Any]],
                          agent_config: Dict[str, Any],
                          input_data: Any,
                          *extra_arguments: Any) -> Dict[str, Any]:
        """
        Exécute un agent avec mécanisme de nouvelle tentative.

        Args:
            agent_dispatcher_callable: Fonction qui invoque l'agent (prend config et données d'entrée).
            agent_config: Configuration de l'agent.
            input_data: Données d'entrée pour l'agent.
            *extra_arguments: Arguments supplémentaires transmis tels quels à
                l'appelable, par exemple le contexte d'exécution partagé.

        Returns:
            Résultat de l'exécution de l'agent (après les tentatives éventuelles).
        """
        agent_id = agent_config.get('id', 'unknown')
        last_result = None

        # Statuts qui terminent l'exécution d'un agent : une nouvelle tentative
        # n'aurait pas de sens, qu'il s'agisse d'un succès, d'un agent ignoré ou
        # d'une action en attente d'approbation humaine (ADR-006).
        terminal_statuses = ("success", "skipped", "requires_approval")

        for attempt in range(1, self.max_attempts + 1):
            try:
                self.logger.info(f"Tentative {attempt}/{self.max_attempts} pour l'agent '{agent_id}'")
                result = agent_dispatcher_callable(agent_config, input_data, *extra_arguments)
                last_result = result

                if result.get('status') in terminal_statuses:
                    self.logger.info(f"Agent '{agent_id}' terminé à la tentative {attempt} (statut {result.get('status')})")
                    return result
                else:
                    self.logger.warning(f"Agent '{agent_id}' échoué à la tentative {attempt}: {result.get('error')}")

            except Exception as e:
                self.logger.error(f"Exception lors de la tentative {attempt} pour l'agent '{agent_id}': {e}")
                last_result = {
                    "agent": agent_id,
                    "status": "error",
                    "error": f"Exception lors de la tentative {attempt}: {e}",
                    "result": None
                }

            # Si ce n'est pas la dernière tentative, attendre avant de réessayer
            if attempt < self.max_attempts:
                self.logger.info(f"Attente de {self.delay_seconds} seconde(s) avant la prochaine tentative...")
                time.sleep(self.delay_seconds)

        # Si nous arrivons ici, toutes les tentatives ont échoué
        self.logger.error(f"Agent '{agent_id}' échoué après {self.max_attempts} tentatives")
        # Retourner le dernier résultat (qui devrait être une erreur)
        if last_result is None:
            last_result = {
                "agent": agent_id,
                "status": "error",
                "error": f"Échec après {self.max_attempts} tentatives sans résultat détaillé",
                "result": None
            }
        return last_result