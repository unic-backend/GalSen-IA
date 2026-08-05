"""
Sélecteur de modèles pour le moteur de modèles GalSen IA.
"""

from typing import Optional, Dict, Any, List
from .types import ModelItem, ModelType
from .interfaces import ModelSelector
import logging


class SimpleModelSelector(ModelSelector):
    """Sélecteur de modèles simple basé sur des règles de base."""

    def __init__(self):
        """Initialise le sélecteur de modèles."""
        self._logger = logging.getLogger(__name__)

        # Priorité par défaut des types de modèles (valeur plus élevée = priorité plus élevée)
        self._default_priorities = {
            ModelType.OPENAI_GPT4: 100,
            ModelType.ANTHROPIC_CLAUDE3_OPUS: 95,
            ModelType.GOOGLE_GEMINI_PRO: 90,
            ModelType.OPENAI_GPT35: 80,
            ModelType.ANTHROPIC_CLAUDE3_SONNET: 75,
            ModelType.ANTHROPIC_CLAUDE3_HAIKU: 70,
            # Ajouter d'autres modèles selon les besoins
        }

    def select_model(self, items: List[ModelItem],
                     context: Optional[Dict[str, Any]] = None) -> Optional[ModelItem]:
        """
        Sélectionne le meilleur modèle parmi une liste.

        Args:
            items: Liste des modèles disponibles
            context: Contexte de sélection (ex: complexité de la tâche, contraintes)

        Returns:
            Le modèle sélectionné ou None si aucun ne convient
        """
        if not items:
            return None

        # Filtrer les modèles disponibles et en bonne santé
        available_models = [
            model for model in items
            if model.status.value in ["active", "available"]
        ]

        if not available_models:
            self._logger.warning("Aucun modèle disponible trouvé")
            return None

        # Si un contexte est fourni, appliquer des règles de sélection spécifiques
        if context:
            selected = self._apply_context_rules(available_models, context)
            if selected:
                return selected

        # Sinon, sélectionner basé sur la priorité et d'autres facteurs
        return self._select_by_priority_and_factors(available_models)

    def _apply_context_rules(self, models: List[ModelItem],
                            context: Dict[str, Any]) -> Optional[ModelItem]:
        """Applique des règles spécifiques basées sur le contexte."""
        task_type = context.get("task_type")
        complexity = context.get("complexity", "medium")
        max_cost = context.get("max_cost")
        required_capabilities = context.get("required_capabilities", [])

        # Filtrer par type de task si spécifié
        if task_type:
            # Par exemple, pour le raisonnement complexe, préférer les modèles plus puissants
            if task_type == "reasoning" and complexity == "high":
                preferred_types = [
                    ModelType.OPENAI_GPT4,
                    ModelType.ANTHROPIC_CLAUDE3_OPUS,
                    ModelType.GOOGLE_GEMINI_PRO
                ]
                filtered = [m for m in models if m.model_type in preferred_types]
                if filtered:
                    models = filtered

        # Filtrer par coût maximal si spécifié
        if max_cost is not None:
            # Dans une implémentation réelle, nous comparerions le coût estimé
            # Pour l'instant, nous supposons que tous les modèles sont dans les limites
            pass

        # Filtrer par capacités requises
        if required_capabilities:
            # Dans une implémentation réelle, nous vérifierions les capacités du modèle
            # Pour l'instant, nous supposons que tous les modèles ont les capacités requises
            pass

        # Sélectionner le meilleur parmi ceux restants
        if models:
            return self._select_by_priority_and_factors(models)
        return None

    def _select_by_priority_and_factors(self, models: List[ModelItem]) -> ModelItem:
        """Sélectionne un modèle basé sur la priorité et d'autres facteurs."""
        def model_score(model: ModelItem) -> float:
            score = 0.0

            # Facteur de priorité basé sur le type de modèle
            base_priority = self._default_priorities.get(model.model_type, 50)
            score += base_priority

            # Facteur de priorité explicite du modèle
            score += model.priority.value * 10  # Priorité de 0-3 -> 0-30 points

            # Facteur de fraîcheur (modèle récemment mis à jour = meilleur score)
            # Dans une implémentation réelle, nous pourrions préférer les modèles plus récents
            # ou ceux avec moins d'utilisation récente pour l'équilibrage de charge

            # Facteur de coût (coût inférieur = meilleur score)
            # Dans une implémentation réelle, nous utiliserions le coût réel par token

            # Facteur de performance (latence inférieure = meilleur score)
            # Dans une implémentation réelle, nous utiliserions les métriques de latence

            return score

        # Trier par score décroissant et retourner le meilleur
        scored_models = [(model, model_score(model)) for model in models]
        scored_models.sort(key=lambda x: x[1], reverse=True)

        return scored_models[0][0]

    def rank_models(self, models: List[ModelItem],
                   context: Optional[Dict[str, Any]] = None) -> List[ModelItem]:
        """
        Classe une liste de modèles du meilleur au pire pour un contexte donné.

        Args:
            models: Liste des modèles à classer
            context: Contexte de classement

        Returns:
            Liste des modèles classée du meilleur au pire
        """
        if not models:
            return []

        # Filtrer les modèles disponibles
        available_models = [
            model for model in models
            if model.status.value in ["active", "available"]
        ]

        if not available_models:
            return []

        # Appliquer le même algorithme de sélection mais retourner toute la liste classée
        def model_score(model: ModelItem) -> float:
            score = 0.0

            # Facteur de priorité basé sur le type de modèle
            base_priority = self._default_priorities.get(model.model_type, 50)
            score += base_priority

            # Facteur de priorité explicite du modèle
            score += model.priority.value * 10

            # Ajuster le score basé sur le contexte si fourni
            if context:
                task_type = context.get("task_type")
                complexity = context.get("complexity", "medium")

                if task_type == "reasoning" and complexity == "high":
                    # Bonus pour les modèles puissants
                    if model.model_type in [
                        ModelType.OPENAI_GPT4,
                        ModelType.ANTHROPIC_CLAUDE3_OPUS,
                        ModelType.GOOGLE_GEMINI_PRO
                    ]:
                        score += 20

            return score

        # Trier par score décroissant
        scored_models = [(model, model_score(model)) for model in available_models]
        scored_models.sort(key=lambda x: x[1], reverse=True)

        return [model for model, _ in scored_models]