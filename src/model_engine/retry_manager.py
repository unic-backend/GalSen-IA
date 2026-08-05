"""
Gestionnaire de nouvelle tentative pour le moteur de modèles GalSen IA.
"""

from typing import Any, Callable, Optional
from .types import ModelItem
from .interfaces import RetryManager
import time
import random
import logging


class ExponentialBackoffRetryManager(RetryManager):
    """
    Gestionnaire de nouvelle tentative avec backoff exponentiel et jitter.
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 60.0, exponential_base: float = 2.0,
                 jitter: bool = True):
        """
        Initialise le gestionnaire de nouvelle tentative.

        Args:
            max_retries: Nombre maximal de tentatives
            base_delay: Délai de base en secondes
            max_delay: Délai maximal en secondes
            exponential_base: Base pour le facteur de multiplication):.Base for exponential backoff
            jitter: Whether to add jitter to delay
        """
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._exponential_base = exponential_base
        self._jitter = jitter
        self._logger = logging.getLogger(__name__)

    def execute_with_retry(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Exécute une fonction avec mécanisme de nouvelle tentative.

        Args:
            func: Fonction à exécuter
            *args: Arguments positionnels pour la fonction
            **kwages: Arguments nommés pour la fonction

        Returns:
            Résultat de la fonction

        Raises:
            Exception: La dernière exception si toutes les tentatives échouent
        """
        last_exception = None

        for attempt in range(self._max_retries + 1):  # +1 pour la tentative initiale
            try:
                if attempt > 0:
                    self._logger.info(f"Tentative {attempt + 1}/{self._max_retries + 1}")
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self._max_retries:
                    # Dernière tentative échouée
                    self._logger.error(f"Toutes les {self._max_retries + 1} tentatives ont échoué. Dernière erreur: {str(e)}")
                    break

                # Calculer le délai avant la prochaine tentative
                delay = self.calculate_backoff(attempt)
                self._logger.warning(f"Tentative {attempt + 1} échouée: {str(e)}. Nouvelle tentative dans {delay:.2f} secondes.")
                time.sleep(delay)

        # Si nous arrivons ici, toutes les tentatives ont échoué
        raise last_exception

    def calculate_backoff(self, attempt: int) -> float:
        """
        Calcule le délai d'attente pour une nouvelle tentative.

        Args:
            attempt: Numéro de la tentative actuelle (0 pour la première tentative après l'échec initial)

        Returns:
            Délai d'attente en secondes
        """
        # Le délai de base augmente exponentiellement avec chaque tentative
        delay = self._base_delay * (self._exponential_base ** attempt)

        # Appliquer le délai maximal
        delay = min(delay, self._max_delay)

        # Ajouter du jitter pour éviter les thrashing de rétentative
        if self._jitter:
            # Jitter aléatoire entre 0% et 25% du délai
            jitter_amount = delay * 0.25 * random.random()
            delay += jitter_amount

        return max(0.0, delay)


class FixedDelayRetryManager(RetryManager):
    """
    Gestionnaire de nouvelle tentative avec délai fixe entre les tentatives.
    """

    def __init__(self, max_retries: int = 3, delay: float = 1.0):
        """
        Initialise le gestionnaire de nouvelle tentative.

        Args:
            max_retries: Nombre maximal de tentatives
            delay: Délai fixe entre les tentatives en secondes
        """
        self._max_retries = max_retries
        self._delay = delay
        self._logger = logging.getLogger(__name__)

    def execute_with_retry(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Exécute une fonction avec mécanisme de nouvelle tentative.

        Args:
            func: Fonction à exécuter
            *args: Arguments positionnels pour la fonction
            **kwargs: Arguments nommés pour la fonction

        Returns:
            Résultat de la fonction

        Raises:
            Exception: La dernière exception si toutes les tentatives échouent
        """
        last_exception = None

        for attempt in range(self._max_retries + 1):  # +1 pour la tentative initiale
            try:
                if attempt > 0:
                    self._logger.info(f"Tentative {attempt + 1}/{self._max_retries + 1}")
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == self._max_retries:
                    # Dernière tentative échouée
                    self._logger.error(f"Toutes les {self._max_retries + 1} tentatives ont échoué. Dernière erreur: {str(e)}")
                    break

                # Attendre avant la prochaine tentative
                self._logger.warning(f"Tentative {attempt + 1} échouée: {str(e)}. Nouvelle tentative dans {self._delay} secondes.")
                time.sleep(self._delay)

        # Si nous arrivons ici, toutes les tentatives ont échoué
        raise last_exception

    def calculate_backoff(self, attempt: int) -> float:
        """
        Calcule le délai d'attente pour une nouvelle tentative.

        Args:
            attempt: Numéro de la tentative actuelle (0 pour la première tentative après l'échec initial)

        Returns:
            Délai d'attente en secondes (toujours le délai fixe)
        """
        return self._delay