"""
Suiveur de coûts pour le moteur de modèles GalSen IA.
"""

from typing import Dict, Any, Optional
from .types import ModelItem, ModelType
from .interfaces import CostTracker
import threading
import time
from collections import defaultdict


class InMemoryCostTracker(CostTracker):
    """
    Suiveur de coûts en mémoire qui enregistre les coûts d'utilisation
    par modèle et fournit des statistiques.
    """

    def __init__(self):
        """Initialise le suiveur de coûts."""
        # Structure: {model_id: {"total_cost": float, "cost_breakdown": dict, "last_updated": float}}
        self._cost_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_cost": 0.0,
            "cost_breakdown": defaultdict(float),
            "last_updated": time.time()
        })
        self._lock = threading.RLock()

        # Coûts par défaut par 1K tokens (en USD) - à personnaliser selon les modèles réels
        # Ces valeurs sont des exemples et doivent être mises à jour avec les vrais tarifs
        self._default_cost_per_1k_tokens = {
            # OpenAI
            ModelType.OPENAI_GPT4: {"prompt": 0.03, "completion": 0.06},
            ModelType.OPENAI_GPT35: {"prompt": 0.0015, "completion": 0.002},
            # Anthropic
            ModelType.ANTHROPIC_CLAUDE3_OPUS: {"prompt": 0.015, "completion": 0.075},
            ModelType.ANTHROPIC_CLAUDE3_SONNET: {"prompt": 0.003, "completion": 0.015},
            ModelType.ANTHROPIC_CLAUDE3_HAIKU: {"prompt": 0.00025, "completion": 0.00125},
            # Google
            ModelType.GOOGLE_GEMINI_PRO: {"prompt": 0.0005, "completion": 0.0015},
            ModelType.GOOGLE_GEMINI_ULTRA: {"prompt": 0.001, "completion": 0.003},
            # Autres modèles (valeurs estimées)
            "default": {"prompt": 0.001, "completion": 0.002}
        }

    def _get_cost_rates(self, model_item: ModelItem) -> Dict[str, float]:
        """
        Obtient les taux de coût pour un modèle spécifique.

        Args:
            model_item: Modèle pour lequel obtenir les taux

        Returns:
            Dictionnaire contenant les taux de coût pour prompt et completion
        """
        # Essayer d'obtenir les taux spécifiques depuis les métadonnées du modèle
        custom_rates = model_item.metadata.get("cost_per_1k_tokens")
        if custom_rates and isinstance(custom_rates, dict):
            return custom_rates

        # Essayer d'obtenir les taux par type de modèle
        model_type = model_item.model_type
        if model_type in self._default_cost_per_1k_tokens:
            return self._default_cost_per_1k_tokens[model_type]

        # Retourner les taux par défaut
        return self._default_cost_per_1k_tokens["default"]

    def track_cost(self, model_item: ModelItem, tokens_used: int,
                  operation_type: str = "generation") -> float:
        """
        Enregistre le coût d'une opération.

        Args:
            model_item: Modèle pour lequel enregistrer le coût
            tokens_used: Nombre de tokens utilisés
            operation_type: Type d'opération (generation, embedding, etc.)

        Returns:
            Coût de l'opération en USD
        """
        model_id = model_item.model_id

        # Obtenir les taux de coût
        rates = self._get_cost_rates(model_item)

        # Pour simplifier, nous supposons que tous les tokens sont du même type
        # Dans une implémentation réelle, nous distinguerions prompt et completion tokens
        # Pour l'instant, nous utilisons un taux moyen ou le taux de completion par défaut
        cost_per_token = rates.get("completion", 0.002) / 1000.0  # Convertir de par 1K à par token

        # Calculer le coût
        cost = tokens_used * cost_per_token

        with self._lock:
            data = self._cost_data[model_id]
            data["total_cost"] += cost
            data["cost_breakdown"][operation_type] += cost
            data["last_updated"] = time.time()

            # Mettre à jour également le modèle lui-même si accessible
            # model_item.total_cost += cost

        return cost

    def get_cost_stats(self, model_item: ModelItem) -> Dict[str, Any]:
        """
        Récupère les statistiques de coûts.

        Args:
            model_item: Modèle pour lequel obtenir les statistiques

        Returns:
            Dictionnaire contenant les statistiques de coûts
        """
        model_id = model_item.model_id

        with self._lock:
            data = self._cost_data.get(model_id, {
                "total_cost": 0.0,
                "cost_breakdown": defaultdict(float),
                "last_updated": time.time()
            })

            # Retourner une copie pour éviter les modifications externes
            return {
                "total_cost": data["total_cost"],
                "cost_breakdown": dict(data["cost_breakdown"]),
                "last_updated": data["last_updated"]
            }

    def get_total_cost(self) -> float:
        """
        Récupère le coût total pour tous les modèles.

        Returns:
            Coût total en USD
        """
        with self._lock:
            total_cost = sum(data["total_cost"] for data in self._cost_data.values())
            return total_cost    # Document variable: self._ (this is a parameter)
    def reset_costs(self, model_item: Optional[ModelItem] = None) -> None:
        """
        Réinitialise les statistiques de coûts.

        Args:
            model_item: Modèle spécifique à réinitialiser, ou None pour tous
        """
        with self._lock:
            if model_item is None:
                self._cost_data.clear()
            else:
                model_id = model_item.model_id
                if model_id in self._cost_data:
                    self._cost_data[model_id] = {
                        "total_cost": 0.0,
                        "cost_breakdown": defaultdict(float),
                        "last_updated": time.time()
                    }

    def set_custom_rate(self, model_item: ModelItem, prompt_rate: float,
                       completion_rate: float) -> None:
        """
        Définit un taux de coût personnalisé pour un modèle spécifique.

        Args:
            model_item: Modèle pour lequel définir le taux
            prompt_rate: Coût par 1K tokens de prompt (en USD)
            completion_rate: Coût par 1K tokens de completion (en USD)
        """
        model_id = model_item.model_id
        with self._lock:
            if model_id not in self._cost_data:
                self._cost_data[model_id] = {
                    "total_cost": 0.0,
                    "cost_breakdown": defaultdict(float),
                    "last_updated": time.time()
                }

            # Stocker le taux personnalisé dans les métadonnées du modèle
            # Dans une implémentation réelle, nous mettrions à jour le modèle dans le magasin
            # Pour l'instant, nous le stockons dans notre propre structure
            if "custom_rates" not in self._cost_data[model_id]:
                self._cost_data[model_id]["custom_rates"] = {}

            self._cost_data[model_id]["custom_rates"] = {
                "prompt": prompt_rate,
                "completion": completion_rate
            }