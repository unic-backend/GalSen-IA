"""
Provider registry for the GalSen IA Model Engine.

Holds every provider the platform knows about and answers two questions: which
providers exist, and which of them can serve a request right now.

Adding a provider means registering it here. Nothing else in the engine needs to
change, which is the point of the provider contract.
"""

import logging
import threading
from typing import Dict, List, Optional

from .anthropic_provider import AnthropicProvider
from .base import ModelDescriptor, ModelProvider, ProviderInfo, ProviderStatus
from .google_provider import GoogleProvider
from .local_provider import LocalProvider
from .openai_provider import OpenAIProvider


class ProviderRegistry:
    """
    Registre des fournisseurs de modèles.

    Exemple:
        registry = ProviderRegistry()
        registry.available_providers()          # ceux qui peuvent répondre
        registry.find_provider_for("gpt-4")     # celui qui propose ce modèle
    """

    def __init__(self, register_defaults: bool = True):
        """
        Initialise le registre.

        Args:
            register_defaults: Enregistre les fournisseurs livrés avec le moteur.
                Passer False permet de partir d'un registre vide, pour les tests
                ou pour un déploiement à fournisseurs entièrement personnalisés.
        """
        self._providers: Dict[str, ModelProvider] = {}
        self._logger = logging.getLogger(__name__)
        # Le registre est consulté depuis les agents parallèles
        self._lock = threading.RLock()

        if register_defaults:
            self._register_default_providers()

    def _register_default_providers(self) -> None:
        """Enregistre les fournisseurs fournis avec le moteur."""
        for provider_class in (OpenAIProvider, AnthropicProvider, GoogleProvider, LocalProvider):
            try:
                self.register(provider_class())
            except Exception as error:
                # Un fournisseur qui ne s'instancie pas ne doit pas empêcher
                # les autres d'être disponibles
                self._logger.warning(
                    f"Fournisseur '{provider_class.__name__}' non enregistré: {error}"
                )

    def register(self, provider: ModelProvider) -> None:
        """
        Enregistre un fournisseur.

        Args:
            provider: Fournisseur à enregistrer

        Raises:
            ValueError: Si le fournisseur n'a pas d'identifiant exploitable
        """
        if not provider.provider_id or provider.provider_id == "base":
            raise ValueError(
                f"Le fournisseur {type(provider).__name__} doit définir un provider_id propre"
            )

        with self._lock:
            if provider.provider_id in self._providers:
                self._logger.info(f"Fournisseur '{provider.provider_id}' remplacé")
            self._providers[provider.provider_id] = provider
            self._logger.debug(f"Fournisseur enregistré: {provider.provider_id}")

    def unregister(self, provider_id: str) -> bool:
        """
        Retire un fournisseur du registre.

        Args:
            provider_id: Identifiant du fournisseur

        Returns:
            True si le fournisseur était enregistré
        """
        with self._lock:
            return self._providers.pop(provider_id, None) is not None

    def get(self, provider_id: str) -> Optional[ModelProvider]:
        """
        Retourne un fournisseur par son identifiant.

        Args:
            provider_id: Identifiant du fournisseur

        Returns:
            Le fournisseur, ou None s'il est inconnu
        """
        with self._lock:
            return self._providers.get(provider_id)

    def list_providers(self) -> List[ModelProvider]:
        """Retourne tous les fournisseurs enregistrés."""
        with self._lock:
            return list(self._providers.values())

    def provider_ids(self) -> List[str]:
        """Retourne les identifiants de tous les fournisseurs enregistrés."""
        with self._lock:
            return sorted(self._providers)

    def available_providers(self) -> List[ModelProvider]:
        """
        Retourne les fournisseurs capables de servir une requête.

        Returns:
            Les fournisseurs dont l'état est `READY`. La liste est vide tant
            qu'aucun fournisseur n'est configuré, ce qui est l'état attendu du
            projet aujourd'hui.
        """
        return [provider for provider in self.list_providers() if provider.is_available()]

    def status_report(self) -> Dict[str, ProviderInfo]:
        """
        Retourne l'état détaillé de chaque fournisseur.

        Returns:
            Pour chaque identifiant, son état et le motif s'il est indisponible
        """
        return {
            provider.provider_id: provider.check_availability()
            for provider in self.list_providers()
        }

    def find_provider_for(self, model_name: str) -> Optional[ModelProvider]:
        """
        Trouve le fournisseur proposant un modèle donné.

        Un fournisseur disponible est toujours préféré à un fournisseur qui
        propose le même modèle sans pouvoir répondre.

        Args:
            model_name: Nom du modèle recherché

        Returns:
            Le fournisseur correspondant, ou None si aucun ne propose ce modèle
        """
        candidates = [
            provider for provider in self.list_providers()
            if provider.supports_model(model_name)
        ]
        if not candidates:
            return None

        for provider in candidates:
            if provider.is_available():
                return provider

        return candidates[0]

    def list_all_models(self) -> List[ModelDescriptor]:
        """
        Retourne le catalogue complet, tous fournisseurs confondus.

        Returns:
            Tous les descripteurs de modèles connus
        """
        descriptors: List[ModelDescriptor] = []
        for provider in self.list_providers():
            try:
                descriptors.extend(provider.list_models())
            except Exception as error:
                # Un catalogue illisible ne doit pas masquer ceux des autres
                self._logger.warning(
                    f"Catalogue du fournisseur '{provider.provider_id}' illisible: {error}"
                )
        return descriptors

    def has_available_provider(self) -> bool:
        """Indique si au moins un fournisseur peut servir une requête."""
        return any(provider.is_available() for provider in self.list_providers())

    def unavailability_summary(self) -> str:
        """
        Résume pourquoi aucun fournisseur n'est disponible.

        Ce message est destiné à l'utilisateur final : il doit dire quoi faire,
        pas seulement constater l'échec.

        Returns:
            Une explication lisible, ou une chaîne vide si un fournisseur répond
        """
        if self.has_available_provider():
            return ""

        reports = self.status_report()
        if not reports:
            return "Aucun fournisseur de modèles n'est enregistré."

        reasons = [
            f"{info.display_name}: {info.detail}"
            for info in reports.values() if info.detail
        ]
        return (
            "Aucun fournisseur de modèles n'est disponible. "
            + " | ".join(reasons)
        )
