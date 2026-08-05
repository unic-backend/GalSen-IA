"""
Model registry for the GalSen IA Model Engine.

The registry is the catalogue: every model the platform knows about, whatever
its provider, with its characteristics. It answers "what could we use", while
the `ModelStore` answers "what is currently registered for use".

Keeping the two apart matters: the catalogue stays complete even when no
provider is configured, so a task can still be matched to the model it would
need, and the platform can say precisely what is missing.
"""

import logging
from typing import Dict, List, Optional

from .providers.base import ModelDescriptor
from .providers.provider_registry import ProviderRegistry
from .types import ModelItem, ModelPriority, ModelStatus, ModelType


class ModelRegistry:
    """
    Catalogue des modèles connus de la plateforme.

    Exemple:
        registry = ModelRegistry(provider_registry)
        registry.find_models(min_context_window=100000, requires_vision=True)
        registry.to_model_item("claude-3-sonnet")
    """

    # Correspondance entre nom de modèle et type déclaré dans `ModelType`.
    # Un modèle absent de cette table reste utilisable : il est simplement
    # classé comme provenant d'un fournisseur non encore typé.
    _MODEL_TYPES = {
        "gpt-4": ModelType.OPENAI_GPT4,
        "gpt-4-turbo": ModelType.OPENAI_GPT4,
        "gpt-3.5-turbo": ModelType.OPENAI_GPT35,
        "claude-3-opus": ModelType.ANTHROPIC_CLAUDE3_OPUS,
        "claude-3-sonnet": ModelType.ANTHROPIC_CLAUDE3_SONNET,
        "claude-3-haiku": ModelType.ANTHROPIC_CLAUDE3_HAIKU,
        "gemini-1.5-pro": ModelType.GOOGLE_GEMINI_PRO,
        "gemini-1.5-flash": ModelType.GOOGLE_GEMINI_PRO,
    }

    # Priorité attribuée par défaut selon la place du modèle dans sa gamme
    _PRIORITY_BY_FEATURE = {
        "reasoning": ModelPriority.HIGH,
        "fast_response": ModelPriority.MEDIUM,
        "low_cost": ModelPriority.MEDIUM,
    }

    def __init__(self, provider_registry: Optional[ProviderRegistry] = None):
        """
        Initialise le catalogue.

        Args:
            provider_registry: Registre des fournisseurs alimentant le catalogue.
                Un registre par défaut est créé s'il n'est pas fourni.
        """
        self._provider_registry = provider_registry or ProviderRegistry()
        self._logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Consultation du catalogue
    # ------------------------------------------------------------------
    def list_all(self) -> List[ModelDescriptor]:
        """Retourne tous les modèles connus, tous fournisseurs confondus."""
        return self._provider_registry.list_all_models()

    def list_by_provider(self, provider_id: str) -> List[ModelDescriptor]:
        """
        Retourne les modèles d'un fournisseur.

        Args:
            provider_id: Identifiant du fournisseur

        Returns:
            Les modèles proposés, liste vide si le fournisseur est inconnu
        """
        provider = self._provider_registry.get(provider_id)
        return provider.list_models() if provider else []

    def describe(self, model_name: str) -> Optional[ModelDescriptor]:
        """
        Retourne le descripteur d'un modèle.

        Args:
            model_name: Nom du modèle

        Returns:
            Le descripteur, ou None si le modèle est inconnu du catalogue
        """
        for descriptor in self.list_all():
            if descriptor.model_name == model_name:
                return descriptor
        return None

    def find_models(
        self,
        min_context_window: int = 0,
        requires_vision: bool = False,
        requires_function_calling: bool = False,
        requires_streaming: bool = False,
        max_input_cost: Optional[float] = None,
        available_only: bool = False,
    ) -> List[ModelDescriptor]:
        """
        Recherche les modèles satisfaisant un ensemble de contraintes.

        Args:
            min_context_window: Taille de contexte minimale requise
            requires_vision: Le modèle doit accepter des images
            requires_function_calling: Le modèle doit gérer l'appel de fonctions
            requires_streaming: Le modèle doit gérer la génération en flux
            max_input_cost: Coût maximal accepté pour 1000 jetons d'entrée
            available_only: Ne retenir que les modèles servis par un fournisseur
                actuellement disponible

        Returns:
            Les modèles correspondants, du moins cher au plus cher
        """
        available_provider_ids = (
            {provider.provider_id for provider in self._provider_registry.available_providers()}
            if available_only else None
        )

        matches: List[ModelDescriptor] = []
        for descriptor in self.list_all():
            if descriptor.context_window < min_context_window:
                continue
            if requires_vision and not descriptor.supports_vision:
                continue
            if requires_function_calling and not descriptor.supports_function_calling:
                continue
            if requires_streaming and not descriptor.supports_streaming:
                continue
            if available_provider_ids is not None and descriptor.provider_id not in available_provider_ids:
                continue

            if max_input_cost is not None:
                if self._input_cost(descriptor) > max_input_cost:
                    continue

            matches.append(descriptor)

        # Le coût est le critère de départage le plus utile pour la plateforme
        matches.sort(key=self._input_cost)
        return matches

    def cheapest_model(self, **constraints) -> Optional[ModelDescriptor]:
        """
        Retourne le modèle le moins cher satisfaisant les contraintes.

        Args:
            **constraints: Contraintes transmises à `find_models`

        Returns:
            Le modèle le moins cher, ou None si aucun ne convient
        """
        matches = self.find_models(**constraints)
        return matches[0] if matches else None

    # ------------------------------------------------------------------
    # Passerelle vers le modèle de données du moteur
    # ------------------------------------------------------------------
    def to_model_item(self, model_name: str) -> Optional[ModelItem]:
        """
        Construit un `ModelItem` à partir du catalogue.

        C'est la passerelle entre le catalogue déclaratif et le modèle de
        données utilisé par le reste du moteur (stockage, sélection, suivi).

        Args:
            model_name: Nom du modèle du catalogue

        Returns:
            Un `ModelItem` prêt à être enregistré, ou None si le modèle est inconnu
        """
        descriptor = self.describe(model_name)
        if descriptor is None:
            return None

        return self.descriptor_to_model_item(descriptor)

    def descriptor_to_model_item(self, descriptor: ModelDescriptor) -> ModelItem:
        """
        Convertit un descripteur en `ModelItem`.

        Args:
            descriptor: Descripteur issu d'un fournisseur

        Returns:
            Le `ModelItem` correspondant
        """
        return ModelItem(
            model_id=f"{descriptor.provider_id}:{descriptor.model_name}",
            model_type=self._resolve_model_type(descriptor),
            provider=descriptor.provider_id,
            name=descriptor.model_name,
            version="catalogue",
            priority=self._resolve_priority(descriptor),
            status=ModelStatus.ACTIVE,
            context_window=descriptor.context_window,
            max_output_tokens=descriptor.max_output_tokens,
            supported_features=self._resolve_features(descriptor),
            metadata={
                "source": "model_registry",
                "pricing_per_1k_tokens": dict(descriptor.pricing_per_1k_tokens),
                "training_data_cutoff": descriptor.training_data_cutoff,
                "supported_languages": list(descriptor.supported_languages),
            },
        )

    def build_all_model_items(self, available_only: bool = False) -> List[ModelItem]:
        """
        Convertit tout le catalogue en `ModelItem`.

        Args:
            available_only: Ne retenir que les modèles servis par un fournisseur
                actuellement disponible

        Returns:
            Les modèles du catalogue au format du moteur
        """
        descriptors = (
            self.find_models(available_only=True) if available_only else self.list_all()
        )
        return [self.descriptor_to_model_item(descriptor) for descriptor in descriptors]

    def stats(self) -> Dict[str, object]:
        """
        Retourne un état synthétique du catalogue.

        Returns:
            Nombre de modèles, répartition par fournisseur, et modèles utilisables
        """
        descriptors = self.list_all()

        by_provider: Dict[str, int] = {}
        for descriptor in descriptors:
            by_provider[descriptor.provider_id] = by_provider.get(descriptor.provider_id, 0) + 1

        return {
            "total_models": len(descriptors),
            "models_by_provider": by_provider,
            "usable_models": len(self.find_models(available_only=True)),
            "providers": self._provider_registry.provider_ids(),
        }

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _input_cost(self, descriptor: ModelDescriptor) -> float:
        """Retourne le coût d'entrée pour 1000 jetons."""
        return descriptor.pricing_per_1k_tokens.get("input", 0.0)

    def _resolve_model_type(self, descriptor: ModelDescriptor) -> ModelType:
        """Déduit le type de modèle à partir de son nom et de son fournisseur."""
        known = self._MODEL_TYPES.get(descriptor.model_name)
        if known is not None:
            return known

        if descriptor.provider_id == "local":
            return ModelType.LOCAL_OLLAMA

        # Un modèle inconnu reste exploitable : il est typé comme provenant
        # d'un fournisseur non encore répertorié
        return ModelType.FUTURE_PROVIDER

    def _resolve_priority(self, descriptor: ModelDescriptor) -> ModelPriority:
        """Déduit une priorité par défaut à partir des atouts du modèle."""
        for feature, priority in self._PRIORITY_BY_FEATURE.items():
            if feature in descriptor.special_features:
                return priority
        return ModelPriority.MEDIUM

    def _resolve_features(self, descriptor: ModelDescriptor) -> List[str]:
        """Construit la liste des fonctionnalités au format attendu par le moteur."""
        features = ["text"]
        if descriptor.supports_vision:
            features.append("vision")
        if descriptor.supports_function_calling:
            features.append("function_calling")
        if descriptor.supports_streaming:
            features.append("streaming")
        features.extend(descriptor.special_features)
        return features
