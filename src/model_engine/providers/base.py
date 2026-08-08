"""
Provider contract for the GalSen IA Model Engine.

A provider is what actually talks to an AI model: OpenAI, Anthropic, a local
Ollama server. Everything above this file — selection, routing, tracking — works
against this contract and never against a specific vendor, which is what makes
providers interchangeable.

Credentials are deliberately out of scope for now. A provider that has no
credentials reports `ProviderStatus.UNAVAILABLE` and refuses to generate, rather
than returning text nobody produced. That refusal is the honest answer, and it
is what the rest of the platform is built to handle.
"""

import abc
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional


class ProviderStatus(Enum):
    """État d'un fournisseur de modèles."""

    # Le fournisseur peut recevoir des requêtes
    READY = "ready"
    # Le fournisseur est connu mais ne peut pas servir de requête
    UNAVAILABLE = "unavailable"
    # Le fournisseur a échoué de façon répétée et est mis à l'écart
    DEGRADED = "degraded"


class UnavailabilityReason(Enum):
    """Motif précis pour lequel un fournisseur ne peut pas servir de requête."""

    # Aucune information d'authentification n'est configurée
    NO_CREDENTIALS = "no_credentials"
    # La bibliothèque cliente du fournisseur n'est pas installée
    MISSING_DEPENDENCY = "missing_dependency"
    # Le service distant ne répond pas
    UNREACHABLE = "unreachable"
    # Le quota d'appels est épuisé
    QUOTA_EXCEEDED = "quota_exceeded"
    # Clé API invalide ou refusée
    UNAUTHORIZED = "unauthorized"
    # Le fournisseur a été désactivé par configuration
    DISABLED = "disabled"


class ProviderUnavailableError(RuntimeError):
    """
    Levée quand une génération est demandée à un fournisseur indisponible.

    Elle porte le motif exact, pour que l'appelant puisse distinguer une clé
    manquante d'une panne réseau et réagir différemment.
    """

    def __init__(self, provider_id: str, reason: UnavailabilityReason, detail: str):
        """
        Initialise l'erreur.

        Args:
            provider_id: Identifiant du fournisseur concerné
            reason: Motif de l'indisponibilité
            detail: Explication lisible et actionnable
        """
        super().__init__(f"Fournisseur '{provider_id}' indisponible ({reason.value}): {detail}")
        self.provider_id = provider_id
        self.reason = reason
        self.detail = detail


@dataclass
class ModelDescriptor:
    """
    Description d'un modèle proposé par un fournisseur.

    Ce sont les caractéristiques du modèle telles que le fournisseur les
    annonce : elles servent à la sélection automatique et à la détection de
    capacités, avant tout appel réseau.
    """

    model_name: str
    provider_id: str
    context_window: int
    max_output_tokens: int
    supports_streaming: bool = False
    supports_function_calling: bool = False
    supports_vision: bool = False
    supported_languages: List[str] = field(default_factory=list)
    # Tarifs pour 1000 jetons, clés `input` et `output`
    pricing_per_1k_tokens: Dict[str, float] = field(default_factory=dict)
    training_data_cutoff: Optional[str] = None
    special_features: List[str] = field(default_factory=list)

    def to_capabilities(self) -> Dict[str, Any]:
        """
        Convertit le descripteur au format de capacités du moteur.

        Le format retourné est celui qu'attendent déjà les composants existants
        (`CapabilityDiscoverer`), pour rester compatible avec eux.
        """
        return {
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "supports_streaming": self.supports_streaming,
            "supports_function_calling": self.supports_function_calling,
            "supports_vision": self.supports_vision,
            "supported_languages": list(self.supported_languages),
            "training_data_cutoff": self.training_data_cutoff,
            "pricing_per_1k_tokens": dict(self.pricing_per_1k_tokens),
            "special_features": list(self.special_features),
        }


@dataclass
class GenerationRequest:
    """Requête de génération adressée à un fournisseur."""

    prompt: str
    model_name: str
    max_tokens: int = 1024
    temperature: float = 0.7
    system_prompt: Optional[str] = None
    stop_sequences: List[str] = field(default_factory=list)
    stream: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResponse:
    """
    Réponse d'une génération.

    Le champ `status` est le point important : un appelant doit toujours le
    consulter avant `text`. Quand le statut n'est pas `READY`, `text` est vide,
    jamais rempli d'un contenu de substitution.
    """

    status: ProviderStatus
    text: str = ""
    provider_id: str = ""
    model_name: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_seconds: float = 0.0
    reason: Optional[UnavailabilityReason] = None
    detail: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    @property
    def succeeded(self) -> bool:
        """Indique si la génération a produit du texte exploitable."""
        return self.status == ProviderStatus.READY and bool(self.text)

    @property
    def total_tokens(self) -> int:
        """Nombre total de jetons consommés par la requête et la réponse."""
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> Dict[str, Any]:
        """Convertit la réponse en dictionnaire."""
        return {
            "status": self.status.value,
            "text": self.text,
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_seconds": round(self.latency_seconds, 4),
            "reason": self.reason.value if self.reason else None,
            "detail": self.detail,
            "created_at": self.created_at,
        }

    @classmethod
    def unavailable(
        cls,
        provider_id: str,
        model_name: str,
        reason: UnavailabilityReason,
        detail: str,
    ) -> "GenerationResponse":
        """
        Construit une réponse d'indisponibilité.

        Args:
            provider_id: Fournisseur concerné
            model_name: Modèle demandé
            reason: Motif de l'indisponibilité
            detail: Explication actionnable

        Returns:
            Réponse au statut `UNAVAILABLE`, sans texte
        """
        return cls(
            status=ProviderStatus.UNAVAILABLE,
            text="",
            provider_id=provider_id,
            model_name=model_name,
            reason=reason,
            detail=detail,
        )


@dataclass
class ProviderInfo:
    """État complet d'un fournisseur, pour le diagnostic."""

    provider_id: str
    display_name: str
    status: ProviderStatus
    model_count: int
    requires_credentials: bool
    reason: Optional[UnavailabilityReason] = None
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'état en dictionnaire."""
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "status": self.status.value,
            "model_count": self.model_count,
            "requires_credentials": self.requires_credentials,
            "reason": self.reason.value if self.reason else None,
            "detail": self.detail,
        }


class ModelProvider(abc.ABC):
    """
    Contrat que tout fournisseur de modèles doit respecter.

    Un fournisseur concret déclare son catalogue de modèles et sait générer du
    texte. Tout le reste — sélection, repli, suivi des coûts — est assuré par le
    moteur, ce qui permet d'ajouter un fournisseur sans toucher au moteur.
    """

    # Identifiant technique, utilisé dans `ModelItem.provider`
    provider_id: str = "base"

    # Nom lisible du fournisseur
    display_name: str = "Base Provider"

    # Le fournisseur a-t-il besoin d'informations d'authentification
    requires_credentials: bool = True

    @abc.abstractmethod
    def list_models(self) -> List[ModelDescriptor]:
        """
        Retourne le catalogue des modèles proposés par le fournisseur.

        Cette information est déclarative et ne nécessite aucun appel réseau :
        elle reste donc disponible même sans authentification.
        """

    @abc.abstractmethod
    def check_availability(self) -> ProviderInfo:
        """
        Détermine si le fournisseur peut servir des requêtes.

        Returns:
            L'état du fournisseur, avec le motif précis s'il est indisponible
        """

    @abc.abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """
        Génère du texte.

        Un fournisseur indisponible doit retourner une réponse au statut
        `UNAVAILABLE` plutôt que de lever une exception : l'indisponibilité est
        un état attendu du système, pas une anomalie.

        Args:
            request: Requête de génération

        Returns:
            Réponse de génération, dont le statut doit toujours être consulté
        """

    def describe_model(self, model_name: str) -> Optional[ModelDescriptor]:
        """
        Retourne le descripteur d'un modèle du catalogue.

        Args:
            model_name: Nom du modèle recherché

        Returns:
            Le descripteur correspondant, ou None si le modèle est inconnu
        """
        for descriptor in self.list_models():
            if descriptor.model_name == model_name:
                return descriptor
        return None

    def supports_model(self, model_name: str) -> bool:
        """Indique si le fournisseur propose un modèle donné."""
        return self.describe_model(model_name) is not None

    def is_available(self) -> bool:
        """Indique si le fournisseur peut servir des requêtes."""
        return self.check_availability().status == ProviderStatus.READY

    async def generate_stream(
        self, request: GenerationRequest
    ) -> AsyncGenerator[str, None]:
        """
        Génère du texte en flux.

        L'implémentation par défaut produit la réponse complète en un seul
        morceau. Un fournisseur qui gère nativement le flux doit surcharger
        cette méthode.

        Args:
            request: Requête de génération

        Yields:
            Les fragments de texte produits
        """
        response = self.generate(request)
        if response.succeeded:
            yield response.text

    def estimate_tokens(self, text: str) -> int:
        """
        Estime le nombre de jetons d'un texte.

        L'estimation par défaut suit la règle d'usage d'environ quatre
        caractères par jeton. Un fournisseur disposant d'un vrai tokeniseur doit
        surcharger cette méthode.

        Args:
            text: Texte à mesurer

        Returns:
            Nombre estimé de jetons
        """
        return max(1, len(text) // 4) if text else 0
