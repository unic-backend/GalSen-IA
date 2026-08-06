"""
Interfaces pour le moteur de modèles GalSen IA.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, AsyncGenerator
from .types import ModelItem, ModelType, ModelPriority, ModelStatus
import time


class ModelStore(ABC):
    """Interface pour le stockage des modèles."""

    @abstractmethod
    def save(self, model: ModelItem) -> str:
        """Sauvegarde un modèle et retourne son ID."""
        pass

    @abstractmethod
    def get(self, model_id: str) -> Optional[ModelItem]:
        """Récupère un modèle par son ID."""
        pass

    @abstractmethod
    def update(self, model: ModelItem) -> bool:
        """Met à jour un modèle existant."""
        pass

    @abstractmethod
    def delete(self, model_id: str) -> bool:
        """Supprime un modèle."""
        pass

    @abstractmethod
    def list_items(self, limit: int = 100, **filters) -> List[ModelItem]:
        """Liste les modèles avec filtres optionnels."""
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """Nettoie les modèles expirés et retourne le nombre supprimé."""
        pass


class ModelSelector(ABC):
    """Interface pour la sélection de modèles."""

    @abstractmethod
    def select_model(self, task_requirements: Dict[str, Any],
                     available_models: List[ModelItem]) -> Optional[ModelItem]:
        """Sélectionne le meilleur modèle pour une tâche donnée."""
        pass


class ModelRouter(ABC):
    """Interface pour le routage des requêtes vers les modèles."""

    @abstractmethod
    def route_request(self, model_item: ModelItem, request: Dict[str, Any]) -> Any:
        """Route une requête vers un modèle spécifique."""
        pass

    @abstractmethod
    def route_with_fallback(self, model_candidates: List[ModelItem],
                           request: Dict[str, Any]) -> Any:
        """Route une requête avec mécanisme de fallback."""
        pass

    @abstractmethod
    def route_with_load_balancing(self, model_candidates: List[ModelItem],
                                 request: Dict[str, Any]) -> Any:
        """Route une requête avec équilibrage de charge."""
        pass


class ModelContextManager(ABC):
    """Interface pour la gestion du contexte des modèles."""

    @abstractmethod
    def manage_context(self, model_item: ModelItem, messages: List[Dict[str, str]],
                      max_tokens: int) -> List[Dict[str, str]]:
        """Gère le contexte pour respecter les limites de tokens."""
        pass

    @abstractmethod
    def truncate_history(self, messages: List[Dict[str, str]],
                        max_tokens: int) -> List[Dict[str, str]]:
        """Tronque l'historique pour tenir dans la limite de tokens."""
        pass


class PromptOptimizer(ABC):
    """Interface pour l'optimisation des prompts."""

    @abstractmethod
    def optimize_prompt(self, model_item: ModelItem, prompt: str,
                       task_type: str) -> str:
        """Optimise un prompt pour un modèle spécifique et un type de tâche."""
        pass


class ResponseValidator(ABC):
    """Interface pour la validation des réponses."""

    @abstractmethod
    def validate_response(self, model_item: ModelItem, response: Any,
                         expected_format: Optional[Dict[str, Any]] = None) -> bool:
        """Valide une réponse selon des critères spécifiques."""
        pass

    @abstractmethod
    def detect_hallucination(self, model_item: ModelItem, response: Any,
                            context: Optional[str] = None) -> float:
        """Détecte les hallucinations potentielles dans une réponse."""
        pass


class TokenTracker(ABC):
    """Interface pour le suivi des tokens."""

    @abstractmethod
    def track_usage(self, model_item: ModelItem, prompt_tokens: int,
                   completion_tokens: int) -> None:
        """Enregistre l'utilisation des tokens."""
        pass

    @abstractmethod
    def get_usage_stats(self, model_item: ModelItem) -> Dict[str, int]:
        """Récupère les statistiques d'utilisation des tokens."""
        pass


class CostTracker(ABC):
    """Interface pour le suivi des coûts."""

    @abstractmethod
    def track_cost(self, model_item: ModelItem, tokens_used: int,
                  operation_type: str) -> float:
        """Enregistre le coût d'une opération."""
        pass

    @abstractmethod
    def get_cost_stats(self, model_item: ModelItem) -> Dict[str, float]:
        """Récupère les statistiques de coûts."""
        pass


class RateLimiter(ABC):
    """Interface pour la gestion des limites de taux."""

    @abstractmethod
    def can_execute(self, model_item: ModelItem) -> bool:
        """Vérifie si une exécution est autorisée selon les limites de taux."""
        pass

    @abstractmethod
    def wait_if_needed(self, model_item: ModelItem) -> float:
        """Attend si nécessaire pour respecter les limites de taux."""
        pass

    @abstractmethod
    def reset_limits(self, model_item: ModelItem) -> None:
        """Réinitialise les limites de taux."""
        pass


class RetryManager(ABC):
    """Interface pour les stratégies de nouvelle tentative."""

    @abstractmethod
    def execute_with_retry(self, func, *args, **kwargs) -> Any:
        """Exécute une fonction avec mécanisme de nouvelle tentative."""
        pass

    @abstractmethod
    def calculate_backoff(self, attempt: int) -> float:
        """Calcule le délai d'attente pour une nouvelle tentative."""
        pass


class StreamHandler(ABC):
    """Interface pour la gestion des réponses en flux."""

    @abstractmethod
    async def handle_stream(self, model_item: ModelItem,
                           stream: AsyncGenerator) -> AsyncGenerator:
        """Traite un flux de réponse provenant d'un modèle."""
        pass

    @abstractmethod
    def collect_stream_response(self, stream: AsyncGenerator) -> str:
        """Collecte la réponse complète d'un flux."""
        pass


class ParallelExecutor(ABC):
    """Interface pour l'exécution parallèle de modèles."""

    @abstractmethod
    async def execute_parallel(self, model_items: List[ModelItem],
                              request: Dict[str, Any]) -> List[Any]:
        """Exécute une requête sur plusieurs modèles en parallèle."""
        pass

    @abstractmethod
    def execute_batch(self, model_items: List[ModelItem],
                     requests: List[Dict[str, Any]]) -> List[Any]:
        """Exécute un lot de requêtes sur plusieurs modèles."""
        pass


class ResponseRanker(ABC):
    """Interface pour le classement des réponses."""

    @abstractmethod
    def rank_responses(self, model_items: List[ModelItem],
                      responses: List[Any],
                      criteria: Dict[str, Any]) -> List[Tuple[ModelItem, Any, float]]:
        """Classe les réponses selon des critères donnés."""
        pass


class HealthMonitor(ABC):
    """Interface pour la surveillance de la santé des modèles."""

    @abstractmethod
    def update_health(self, model_item: ModelItem, latency: float,
                     success: bool, error: Optional[str] = None) -> None:
        """Met à jour les métriques de santé d'un modèle."""
        pass

    @abstractmethod
    def get_health_status(self, model_item: ModelItem) -> Dict[str, Any]:
        """Récupère l'état de santé d'un modèle."""
        pass

    @abstractmethod
    def is_healthy(self, model_item: ModelItem) -> bool:
        """Vérifie si un modèle est en bonne santé."""
        pass


class CapabilityDiscoverer(ABC):
    """Interface pour la découverte des capacités des modèles."""

    @abstractmethod
    def discover_capabilities(self, model_item: ModelItem) -> Dict[str, Any]:
        """Découvre les capacités d'un modèle."""
        pass

    @abstractmethod
    def get_capabilities(self, model_item: ModelItem) -> Dict[str, Any]:
        """Récupère les capacités découvertes d'un modèle."""
        pass


class ModelManager(ABC):
    """Interface principale du gestionnaire de modèles."""

    @abstractmethod
    def register_model(self, model_item: ModelItem) -> str:
        """Enregistre un nouveau modèle."""
        pass

    @abstractmethod
    def get_model(self, model_id: str) -> Optional[ModelItem]:
        """Récupère un modèle enregistré."""
        pass

    @abstractmethod
    def update_model(self, model_item: ModelItem) -> bool:
        """Met à jour un modèle enregistré."""
        pass

    @abstractmethod
    def unregister_model(self, model_id: str) -> bool:
        """Désenregistre un modèle."""
        pass

    @abstractmethod
    def list_models(self, **filters) -> List[ModelItem]:
        """Liste tous les modèles enregistrés."""
        pass

    @abstractmethod
    def select_model_for_task(self, task_requirements: Dict[str, Any]) -> Optional[ModelItem]:
        """Sélectionne le meilleur modèle pour une tâche donnée."""
        pass

    @abstractmethod
    async def generate_text(self, model_item: ModelItem, prompt: str,
                           **kwargs) -> str:
        """Génère du texte avec un modèle spécifique."""
        pass

    @abstractmethod
    async def generate_text_with_fallback(self, prompt: str,
                                         task_requirements: Dict[str, Any],
                                         **kwargs) -> str:
        """Génère du texte avec mécanisme de fallback."""
        pass

    @abstractmethod
    async def generate_text_with_load_balancing(self, prompt: str,
                                               task_requirements: Dict[str, Any],
                                               **kwargs) -> str:
        """Génère du texte avec équilibrage de charge."""
        pass

    @abstractmethod
    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations détaillées d'un modèle."""
        pass

    @abstractmethod
    def get_health_status(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Récupère l'état de santé d'un modèle."""
        pass

    @abstractmethod
    def get_usage_stats(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les statistiques d'utilisation d'un modèle."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Nettoie les ressources."""
        pass