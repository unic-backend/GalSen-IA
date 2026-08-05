"""
Capability detection for the GalSen IA Model Engine.

Answers what a given model can do: context window, vision, function calling,
pricing. The answer is taken from the provider that actually serves the model,
because the provider is the authority on its own catalogue.

When the provider is unknown, the detector falls back to
`StaticCapabilityDiscoverer`, the table that existed before providers did. That
fallback is what keeps models registered by hand — including in the existing
tests — working exactly as before.
"""

import logging
from typing import Any, Dict, Optional

from .capability_discoverer import StaticCapabilityDiscoverer
from .interfaces import CapabilityDiscoverer
from .providers.provider_registry import ProviderRegistry
from .types import ModelItem


class CapabilityDetector(CapabilityDiscoverer):
    """
    Détecteur de capacités s'appuyant d'abord sur les fournisseurs.

    Il implémente le contrat `CapabilityDiscoverer` déjà utilisé par le moteur,
    et peut donc remplacer l'implémentation statique sans autre changement.
    """

    def __init__(
        self,
        provider_registry: Optional[ProviderRegistry] = None,
        fallback: Optional[CapabilityDiscoverer] = None,
    ):
        """
        Initialise le détecteur.

        Args:
            provider_registry: Registre consulté en premier
            fallback: Découvreur utilisé quand aucun fournisseur ne connaît le
                modèle, `StaticCapabilityDiscoverer` par défaut
        """
        self._provider_registry = provider_registry or ProviderRegistry()
        self._fallback = fallback or StaticCapabilityDiscoverer()
        self._logger = logging.getLogger(__name__)
        # Les capacités ne changent pas en cours d'exécution : les recalculer
        # à chaque sélection de modèle serait du gaspillage
        self._cache: Dict[str, Dict[str, Any]] = {}

    def discover_capabilities(self, model_item: ModelItem) -> Dict[str, Any]:
        """
        Découvre les capacités d'un modèle.

        Args:
            model_item: Modèle à analyser

        Returns:
            Les capacités du modèle, enrichies de leur origine
        """
        cache_key = f"{model_item.provider}:{model_item.name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        capabilities = self._detect(model_item)
        self._cache[cache_key] = capabilities
        return capabilities

    def get_capabilities(self, model_item: ModelItem) -> Dict[str, Any]:
        """
        Récupère les capacités d'un modèle.

        Args:
            model_item: Modèle à analyser

        Returns:
            Les capacités du modèle
        """
        return self.discover_capabilities(model_item)

    def supports(self, model_item: ModelItem, capability: str) -> bool:
        """
        Indique si un modèle possède une capacité donnée.

        Args:
            model_item: Modèle à analyser
            capability: Nom de la capacité, par exemple `supports_vision`

        Returns:
            True si la capacité est présente et active
        """
        capabilities = self.discover_capabilities(model_item)

        value = capabilities.get(capability)
        if isinstance(value, bool):
            return value
        # Une capacité peut aussi être annoncée dans les atouts du modèle
        return capability in capabilities.get("special_features", [])

    def meets_requirements(self, model_item: ModelItem, requirements: Dict[str, Any]) -> bool:
        """
        Vérifie qu'un modèle satisfait un ensemble d'exigences.

        Args:
            model_item: Modèle à évaluer
            requirements: Exigences, par exemple
                `{"min_context_window": 100000, "requires_vision": True}`

        Returns:
            True si toutes les exigences sont satisfaites
        """
        capabilities = self.discover_capabilities(model_item)

        minimum_context = requirements.get("min_context_window", 0)
        if capabilities.get("context_window", 0) < minimum_context:
            return False

        if requirements.get("requires_vision") and not capabilities.get("supports_vision"):
            return False
        if requirements.get("requires_function_calling") and not capabilities.get("supports_function_calling"):
            return False
        if requirements.get("requires_streaming") and not capabilities.get("supports_streaming"):
            return False

        required_language = requirements.get("language")
        if required_language:
            languages = capabilities.get("supported_languages", [])
            # Un modèle qui n'annonce aucune langue n'est pas écarté pour autant
            if languages and required_language not in languages:
                return False

        return True

    def clear_cache(self) -> None:
        """Vide le cache des capacités détectées."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _detect(self, model_item: ModelItem) -> Dict[str, Any]:
        """Interroge le fournisseur, puis le découvreur statique en dernier recours."""
        descriptor = self._describe_from_provider(model_item)
        if descriptor is not None:
            capabilities = descriptor.to_capabilities()
            capabilities["detection_source"] = f"provider:{descriptor.provider_id}"
            return capabilities

        capabilities = dict(self._fallback.discover_capabilities(model_item))
        capabilities["detection_source"] = "static_table"
        return capabilities

    def _describe_from_provider(self, model_item: ModelItem):
        """Cherche le descripteur du modèle auprès de son fournisseur."""
        provider = self._provider_registry.get(model_item.provider)
        if provider is not None:
            descriptor = provider.describe_model(model_item.name)
            if descriptor is not None:
                return descriptor

        # Le fournisseur déclaré est inconnu ou ne propose pas ce modèle :
        # un autre fournisseur peut malgré tout le servir
        provider = self._provider_registry.find_provider_for(model_item.name)
        return provider.describe_model(model_item.name) if provider else None
