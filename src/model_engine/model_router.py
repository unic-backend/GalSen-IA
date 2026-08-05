"""
Routeur de modèles pour le moteur de modèles GalSen IA.
"""

from typing import Optional, Dict, Any, List, Tuple
from .types import ModelItem
from .interfaces import ModelRouter, ModelLoader
import logging
import time
import random


class FailoverModelRouter(ModelRouter):
    """Routeur de modèles avec mécanisme de basculement (failover)."""

    def __init__(self, model_loader: ModelLoader):
        """
        Initialise le routeur avec basculement.

        Args:
            model_loader: Chargeur de modèles à utiliser
        """
        self._model_loader = model_loader
        self._logger = logging.getLogger(__name__)
        self._failure_counts: dict = {}  # Suivi des échecs par modèle
        self._last_failure_time: dict = {}  # Timestamp du dernier échec
        self._failure_threshold = 3  # Nombre d'échecs avant basculement
        self._reset_timeout = 300  # secondes (5 minutes) après lesquelles réinitialiser le compteur

    def _record_failure(self, model_id: str) -> None:
        """Enregistre un échec pour un modèle."""
        current_time = time.time()
        self._failure_counts[model_id] = self._failure_counts.get(model_id, 0) + 1
        self._last_failure_time[model_id] = current_time
        self._logger.warning(f"Échec enregistré pour le modèle {model_id}. Compteur: {self._failure_counts[model_id]}")

    def _reset_failure_count(self, model_id: str) -> None:
        """Réinitialise le compteur d'échecs pour un modèle."""
        if model_id in self._failure_counts:
            del self._failure_counts[model_id]
        if model_id in self._last_failure_time:
            del self._last_failure_time[model_id]

    def _is_model_healthy(self, model_id: str) -> bool:
        """Vérifie si un modèle est considéré comme sain basé sur son historique d'échecs."""
        # Réinitialiser le compteur si le timeout est écoulé
        if model_id in self._last_failure_time:
            if time.time() - self._last_failure_time[model_id] > self._reset_timeout:
                self._reset_failure_count(model_id)

        # Considérer sain si moins que le seuil d'échec
        failure_count = self._failure_counts.get(model_id, 0)
        return failure_count < self._failure_threshold

    def route_request(self, model_item: ModelItem, request: Dict[str, Any]) -> Any:
        """
        Route une requête vers un modèle spécifique avec gestion des erreurs de base.

        Args:
            model_item: Modèle à utiliser
            request: Requête à envoyer au modèle

        Returns:
            Réponse du modèle

        Raises:
            Exception: Si le modèle échoue après les tentatives
        """
        model_id = model_item.model_id

        # Vérifier si le modèle est considéré comme sain
        if not self._is_model_healthy(model_id):
            self._logger.warning(f"Modèle {model_id} considéré comme unhealthy, tentative malgré tout")

        try:
            # Charger le modèle si nécessaire
            model_instance = self._model_loader.load_model(model_item)

            # Dans une implémentation réelle, nous appellerions le modèle ici
            # Par exemple:
            # if model_item.provider == "openai":
            #     response = model_instance.chat.completions.create(
            #         model=model_item.name,
            #         messages=request.get("messages", []),
            #         temperature=request.get("temperature", 0.7),
            #         max_tokens=request.get("max_tokens", 1000)
            #     )
            # elif model_item.provider == "anthropic":
            #     response = model_instance.messages.create(
            #         model=model_item.name,
            #         max_tokens=request.get("max_tokens", 1000),
            #         messages=request.get("messages", [])
            #     )

            # Pour l'instant, nous simulons une réponse
            response = {
                "model_id": model_id,
                "prompt": request.get("prompt", ""),
                "response": f"Réponse simulée du modèle {model_id}",
                "timestamp": time.time(),
                "tokens_used": len(str(request)) // 4  # Estimation très approximative
            }

            # Réinitialiser le compteur d'échecs en cas de succès
            self._reset_failure_count(model_id)

            return response

        except Exception as e:
            # Enregistrer l'échec
            self._record_failure(model_id)
            self._logger.error(f"Erreur lors de l'appel au modèle {model_id}: {str(e)}")
            raise  # Re-lever l'exception pour que le mécanisme de basculement puisse la gérer

    def route_with_fallback(self, model_candidates: List[ModelItem],
                           request: Dict[str, Any]) -> Any:
        """
        Route une requête avec mécanisme de basculement automatique.

        Args:
            model_candidates: Liste ordonnée de modèles à essayer (du préféré au moins préféré)
            request: Requête à envoyer au modèle

        Returns:
            Réponse du premier modèle qui réussit

        Raises:
            Exception: Si tous les modèles échouent
        """
        last_exception = None

        for model_item in model_candidates:
            try:
                return self.route_request(model_item, request)
            except Exception as e:
                last_exception = e
                self._logger.warning(f"Modèle {model_item.model_id} a échoué, essai du suivant: {str(e)}")
                continue  # Essayer le modèle suivant

        # Si tous les modèles ont échoué
        error_msg = f"Tous les modèles ont échoué. Dernière erreur: {str(last_exception)}"
        self._logger.error(error_msg)
        raise Exception(error_msg)

    def route_with_load_balancing(self, model_candidates: List[ModelItem],
                                 request: Dict[str, Any]) -> Any:
        """
        Route une requête avec équilibrage de charge entre les modèles disponibles.

        Args:
            model_candidates: Liste de modèles candidats
            request: Requête à envoyer au modèle

        Returns:
            Réponse du modèle sélectionné
        """
        # Filtrer les modèles sains
        healthy_models = [
            model for model in model_candidates
            if self._is_model_healthy(model.model_id)
        ]

        if not healthy_models:
            # Si aucun modèle n'est sain, réinitialiser les compteurs et essayer quand même
            self._logger.warning("Aucun modèle sain trouvé, réinitialisation des compteurs d'échecs")
            for model in model_candidates:
                self._reset_failure_count(model.model_id)
            healthy_models = model_candidates

        # Sélectionner un modèle basé sur le poids inverse des échecs (moins d'échecs = plus de chances)
        weights = []
        for model in healthy_models:
            failure_count = self._failure_counts.get(model.model_id, 0)
            # Plus le nombre d'échecs est faible, plus le poids est élevé
            weight = max(1, 10 - failure_count)  # Poids entre 1 et 10
            weights.append(weight)

        # Sélection aléatoire pondérée
        selected_index = self._weighted_choice(range(len(healthy_models)), weights)
        selected_model = healthy_models[selected_index]

        self._logger.info(f"Modèle sélectionné par équilibrage de charge: {selected_model.model_id}")

        # Router la requête vers le modèle sélectionné
        return self.route_request(selected_model, request)

    def _weighted_choice(self, items: list, weights: list) -> int:
        """Sélectionne un élément aléatoirement basé sur des poids."""
        if len(items) != len(weights):
            raise ValueError("La longueur des éléments et des poids doit être identique")

        total = sum(weights)
        if total <= 0:
            return random.randint(0, len(items) - 1)

        r = random.uniform(0, total)
        upto = 0
        for i, w in enumerate(weights):
            if upto + w >= r:
                return i
            upto += w
        return len(items) - 1  # Fallback (ne devrait jamais arriver)