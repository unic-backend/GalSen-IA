"""
Suiveur de tokens pour le moteur de modèles GalSen IA.
"""

from typing import Dict, Any, Optional
from .types import ModelItem
from .interfaces import TokenTracker
import threading
from collections import defaultdict
import time


class InMemoryTokenTracker(TokenTracker):
    """
    Suiveur de tokens en mémoire qui enregistre l'utilisation des tokens
    par modèle et fournit des statistiques.
    """

    def __init__(self):
        """Initialise le suiveur de tokens."""
        # Structure: {model_id: {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int, "last_updated": float}}
        self._usage_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "last_updated": time.time()
        })
        self._lock = threading.RLock()

    def track_usage(self, model_item: ModelItem, prompt_tokens: int,
                   completion_tokens: int) -> None:
        """
        Enregistre l'utilisation des tokens.

        Args:
            model_item: Modèle pour lequel enregistrer l'utilisation
            prompt_tokens: Nombre de tokens dans le prompt
            completion_tokens: Nombre de tokens dans la complétion
        """
        model_id = model_item.model_id
        total_tokens = prompt_tokens + completion_tokens

        with self._lock:
            data = self._usage_data[model_id]
            data["prompt_tokens"] += prompt_tokens
            data["completion_tokens"] += completion_tokens
            data["total_tokens"] += total_tokens
            data["last_updated"] = time.time()

            # Mettre à jour également le modèle lui-même si accessible
            # Ceci serait généralement fait dans le ModelManager
            # model_item.total_tokens_used += total_tokens

    def get_usage_stats(self, model_item: ModelItem) -> Dict[str, int]:
        """
        Récupère les statistiques d'utilisation des tokens.

        Args:
            model_item: Modèle pour lequel obtenir les statistiques

        Returns:
            Dictionnaire contenant les statistiques d'utilisation
        """
        model_id = model_item.model_id

        with self._lock:
            data = self._usage_data.get(model_id, {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "last_updated": time.time()
            })

            # Retourner une copie pour éviter les modifications externes
            return {
                "prompt_tokens": data["prompt_tokens"],
                "completion_tokens": data["completion_tokens"],
                "total_tokens": data["total_tokens"],
                "last_updated": data["last_updated"]
            }

    def get_total_usage(self) -> Dict[str, Any]:
        """
        Récupère l'utilisation totale des tokens pour tous les modèles.

        Returns:
            Dictionnaire contenant l'utilisation totale
        """
        with self._lock:
            total_prompt = 0
            total_completion = 0
            total_tokens = 0

            for data in self._usage_data.values():
                total_prompt += data["prompt_tokens"]
                total_completion += data["completion_tokens"]
                total_tokens += data["total_tokens"]

            return {
                "prompt_tokens": total_prompt,
                "completion_tokens": total_completion,
                "total_tokens": total_tokens,
                "model_count": len(self._usage_data)
            }

    def reset_usage(self, model_item: Optional[ModelItem] = None) -> None:
        """
        Réinitialise les statistiques d'utilisation.

        Args:
            model_item: Modèle spécifique à réinitialiser, ou None pour tous
        """
        with self._lock:
            if model_item is None:
                self._usage_data.clear()
            else:
                model_id = model_item.model_id
                if model_id in self._usage_data:
                    self._usage_data[model_id] = {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "last_updated": time.time()
                    }