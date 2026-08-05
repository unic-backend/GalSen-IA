"""
Model Engine for GalSen IA.

Manages AI models across providers behind one interface. Selection, routing,
cost and health tracking all work against the provider contract, never against
a specific vendor, so a provider can be added or replaced without touching the
engine.
"""

from .capability_detector import CapabilityDetector
from .capability_discoverer import StaticCapabilityDiscoverer
from .model_manager import ModelManagerImpl
from .model_registry import ModelRegistry
from .model_store import InMemoryModelStore
from .provider_selector import ProviderSelection, ProviderSelector
from .providers import (
    AnthropicProvider,
    GenerationRequest,
    GenerationResponse,
    GoogleProvider,
    HostedProvider,
    LocalProvider,
    ModelDescriptor,
    ModelProvider,
    OpenAIProvider,
    ProviderInfo,
    ProviderRegistry,
    ProviderStatus,
    ProviderUnavailableError,
    UnavailabilityReason,
)
from .types import ModelItem, ModelPriority, ModelStatus, ModelType

__all__ = [
    # Point d'entrée principal
    "ModelManagerImpl",
    # Contrat fournisseur
    "ModelProvider",
    "HostedProvider",
    "ModelDescriptor",
    "GenerationRequest",
    "GenerationResponse",
    "ProviderInfo",
    "ProviderStatus",
    "UnavailabilityReason",
    "ProviderUnavailableError",
    # Registres et sélection
    "ProviderRegistry",
    "ModelRegistry",
    "ProviderSelector",
    "ProviderSelection",
    "CapabilityDetector",
    "StaticCapabilityDiscoverer",
    "InMemoryModelStore",
    # Fournisseurs
    "AnthropicProvider",
    "GoogleProvider",
    "LocalProvider",
    "OpenAIProvider",
    # Modèle de données
    "ModelItem",
    "ModelPriority",
    "ModelStatus",
    "ModelType",
]
