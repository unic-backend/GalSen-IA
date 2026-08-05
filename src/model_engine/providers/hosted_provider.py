"""
Shared base for hosted model providers of GalSen IA.

Hosted providers (OpenAI, Anthropic, Google) all work the same way: a declared
catalogue of models, and an HTTP API reachable only with credentials.

Credentials are read exclusively from environment variables:
- OpenAI Provider: OPENAI_API_KEY
- Anthropic Provider: ANTHROPIC_API_KEY
- Google Provider: GOOGLE_API_KEY

A concrete provider therefore only declares its catalogue and implements
_call_api to make the actual API call.
"""

import abc
import os
from typing import List, Optional

from .base import (
    GenerationRequest,
    GenerationResponse,
    ModelDescriptor,
    ModelProvider,
    ProviderInfo,
    ProviderStatus,
    UnavailabilityReason,
)


class HostedProvider(ModelProvider):
    """
    Fournisseur distant nécessitant des informations d'authentification.

    Cette classe porte tout ce qui est commun aux fournisseurs hébergés. Une
    sous-classe n'a qu'à déclarer son identifiant et son catalogue.
    """

    requires_credentials = True

    # Nom de la variable d'environnement qui portera la clé, une fois le
    # support des identifiants décidé. Elle est déclarée ici pour que le
    # diagnostic indique quoi configurer, sans qu'aucune clé ne soit lue.
    credential_environment_variable: str = ""

    def check_availability(self) -> ProviderInfo:
        """
        Détermine si le fournisseur peut servir des requêtes.

        Returns:
            L'état du fournisseur. Vérifie la présence de la variable
            d'environnement requise pour les identifiants.
        """
        # Vérifier si la variable d'environnement d'authentification est définie
        api_key = os.environ.get(self.credential_environment_variable)
        if not api_key:
            return ProviderInfo(
                provider_id=self.provider_id,
                display_name=self.display_name,
                status=ProviderStatus.UNAVAILABLE,
                model_count=len(self.list_models()),
                requires_credentials=True,
                reason=UnavailabilityReason.NO_CREDENTIALS,
                detail=self._credentials_detail(),
            )

        # Si la clé est présente, on considère que le fournisseur pourrait être disponible
        # La vérification réelle de la validité de la clé sera faite lors de l'appel API
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            status=ProviderStatus.READY,
            model_count=len(self.list_models()),
            requires_credentials=True,
        )

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """
        Génère du texte.

        Args:
            request: Requête de génération

        Returns:
            Une réponse du fournisseur. Si les identifiants sont manquants,
            retourne une réponse `UNAVAILABLE`. Si les identifiants sont présents
            mais l'appel API échoue, retourne une réponse `UNAVAILABLE` avec
            la raison appropriée.
        """
        # Vérifier d'abord la disponibilité (vérifie les identifiants)
        availability = self.check_availability()
        if availability.status != ProviderStatus.READY:
            return GenerationResponse.unavailable(
                provider_id=self.provider_id,
                model_name=request.model_name,
                reason=availability.reason or UnavailabilityReason.NO_CREDENTIALS,
                detail=availability.detail or self._credentials_detail(),
            )

        # Les identifiants sont présents, tenter l'appel API
        try:
            return self._call_api(request)
        except Exception as error:
            # En cas d'erreur d'authentification ou autre, retourner UNAVAILABLE
            # Ne pas exposer les détails de l'erreur pour des raisons de sécurité
            return GenerationResponse.unavailable(
                provider_id=self.provider_id,
                model_name=request.model_name,
                reason=UnavailabilityReason.QUOTA_EXCEEDED if "429" in str(error) else UnavailabilityReason.UNAUTHORIZED,
                detail="Échec de l'authentification ou quota dépassé. Vérifiez votre clé API."
            )

    @abc.abstractmethod
    def list_models(self) -> List[ModelDescriptor]:
        """Retourne le catalogue des modèles proposés par le fournisseur."""

    def _call_api(self, request: GenerationRequest) -> GenerationResponse:
        """
        Appelle l'API du fournisseur.

        Cette méthode doit être implémentée par les sous-classes concrètes.
        Elle est appelée seulement lorsque les identifiants sont disponibles
        (vérifié par check_availability).

        Args:
            request: Requête de génération

        Returns:
            Réponse du fournisseur
        """
        # Cette méthode doit être overridée par les sous-classes
        # Retourner une indisponibilité par défaut pour éviter les erreurs
        return GenerationResponse.unavailable(
            provider_id=self.provider_id,
            model_name=request.model_name,
            reason=UnavailabilityReason.NO_CREDENTIALS,
            detail=self._credentials_detail(),
        )

    def _credentials_detail(self) -> str:
        """Explique ce qu'il manque et ce qu'il faudra configurer."""
        variable = self.credential_environment_variable or "la variable d'environnement dédiée"
        return (
            f"Les identifiants pour {self.display_name} sont attendus dans la variable d'environnement {variable}. "
            "Assurez-vous qu'elle est définie et contient une clé API valide."
        )
