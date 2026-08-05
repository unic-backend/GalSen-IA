"""
Model providers for GalSen IA.

Every provider implements the same contract, so the engine can add, replace or
remove one without any change above this package.
"""

from .anthropic_provider import AnthropicProvider
from .base import (
    GenerationRequest,
    GenerationResponse,
    ModelDescriptor,
    ModelProvider,
    ProviderInfo,
    ProviderStatus,
    ProviderUnavailableError,
    UnavailabilityReason,
)
from .google_provider import GoogleProvider
from .hosted_provider import HostedProvider
from .local_provider import LocalProvider
from .openai_provider import OpenAIProvider
from .provider_registry import ProviderRegistry

__all__ = [
    # Contrat
    "ModelProvider",
    "HostedProvider",
    "ModelDescriptor",
    "GenerationRequest",
    "GenerationResponse",
    "ProviderInfo",
    "ProviderStatus",
    "UnavailabilityReason",
    "ProviderUnavailableError",
    # Registre
    "ProviderRegistry",
    # Fournisseurs
    "AnthropicProvider",
    "GoogleProvider",
    "LocalProvider",
    "OpenAIProvider",
]
