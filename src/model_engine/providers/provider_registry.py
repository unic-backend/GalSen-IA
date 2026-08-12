"""
Provider registry for the GalSen IA Model Engine.

Holds every provider the platform knows about and answers two questions: which
providers exist, and which of them can serve a request right now.

Adding a provider means registering it here. Nothing else in the engine needs to
change, which is the point of the provider contract.

**Souveraineté (ADR-014).** GalSen IA ne dépend d'aucun modèle tiers à
l'exécution. Le registre inscrivait pourtant OpenAI, Anthropic et Google par
défaut : ils restaient inertes faute de clé, mais *inerte n'est pas absent*, et
« personne n'a mis de clé » est un état, pas une garantie. En mode souverain —
le défaut — ces fournisseurs ne sont **pas inscrits**, et le registre refuse
qu'on les inscrive après coup : un fournisseur absent du registre ne peut être
choisi par aucun chemin.

Restent `LocalProvider` (Ollama) et `OpenAICompatibleProvider`. Le second n'est
pas une dépendance à OpenAI : c'est un **format de fil** que vLLM, llama.cpp,
LM Studio et le serveur du projet parlent tous. Le nom est à eux, le protocole
est public — mais si son URL pointe vers un service tiers, la souveraineté est
perdue par la porte de derrière, et c'est refusé aussi.
"""

import logging
import os
import threading
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .anthropic_provider import AnthropicProvider
from .base import ModelDescriptor, ModelProvider, ProviderInfo
from .google_provider import GoogleProvider
from .hosted_provider import HostedProvider
from .local_provider import LocalProvider
from .openai_compatible_provider import URL_VARIABLE, OpenAICompatibleProvider
from .openai_provider import OpenAIProvider

SOVEREIGN_MODE_VARIABLE = "GALSEN_SOVEREIGN_MODE"

# Fournisseurs qui servent le modèle d'un tiers, sur son infrastructure.
FOURNISSEURS_TIERS = (OpenAIProvider, AnthropicProvider, GoogleProvider)

# Fournisseurs qui servent un modèle que le projet héberge.
FOURNISSEURS_SOUVERAINS = (LocalProvider, OpenAICompatibleProvider)

# Hôtes qu'un déploiement souverain ne peut pas joindre, quelle que soit la
# porte empruntée. La liste ne prétend pas être exhaustive : elle ferme le
# détournement évident, qui est de pointer le fournisseur « compatible » vers le
# service dont il imite le format.
HOTES_TIERS = (
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.deepseek.com",
    "api.mistral.ai",
    "api.cohere.ai",
    "api.groq.com",
    "openrouter.ai",
)


def sovereign_mode() -> bool:
    """
    Indique si la plateforme refuse tout modèle tiers (ADR-014).

    Returns:
        True par défaut. La souveraineté n'est pas une option qu'on active :
        c'est l'état normal, et s'en écarter est la décision qui se déclare.
    """
    return os.getenv(SOVEREIGN_MODE_VARIABLE, "true").strip().lower() not in (
        "false", "0", "no",
    )


def _hote_tiers(url: str) -> Optional[str]:
    """Retourne l'hôte tiers visé par une URL, ou None si elle n'en vise aucun."""
    if not url:
        return None
    hote = (urlparse(url if "://" in url else f"http://{url}").hostname or "").lower()
    return hote if hote in HOTES_TIERS else None


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
        """
        Enregistre les fournisseurs fournis avec le moteur.

        En mode souverain — le défaut — les fournisseurs tiers ne sont pas
        inscrits. `OpenAICompatibleProvider` reste en dernier : il est inactif
        tant que `GALSEN_OPENAI_COMPATIBLE_URL` n'est pas déclarée, donc son
        inscription ne change rien pour une installation qui ne s'en sert pas.
        """
        souverain = sovereign_mode()
        if souverain:
            classes = FOURNISSEURS_SOUVERAINS
        else:
            # L'écart doit se voir dans le journal : c'est la seule trace qu'un
            # opérateur aura d'une plateforme redevenue locataire d'un tiers.
            self._logger.warning(
                "%s désactivé : les fournisseurs tiers (%s) sont inscrits. La "
                "plateforme peut envoyer des requêtes hors de son infrastructure "
                "(ADR-014).",
                SOVEREIGN_MODE_VARIABLE,
                ", ".join(classe.__name__ for classe in FOURNISSEURS_TIERS),
            )
            classes = FOURNISSEURS_TIERS + FOURNISSEURS_SOUVERAINS

        for provider_class in classes:
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

        En mode souverain, un fournisseur tiers est refusé même inscrit à la
        main : ne pas les inscrire par défaut protégerait du hasard, pas d'un
        appel explicite, et la garantie d'ADR-014 doit tenir dans les deux cas.

        Args:
            provider: Fournisseur à enregistrer

        Raises:
            ValueError: Si le fournisseur n'a pas d'identifiant exploitable, ou
                s'il dépend d'un tiers alors que le mode souverain est actif.
        """
        if not provider.provider_id or provider.provider_id == "base":
            raise ValueError(
                f"Le fournisseur {type(provider).__name__} doit définir un provider_id propre"
            )

        if sovereign_mode():
            refus = self._motif_de_refus_souverain(provider)
            if refus:
                raise ValueError(refus)

        with self._lock:
            if provider.provider_id in self._providers:
                self._logger.info(f"Fournisseur '{provider.provider_id}' remplacé")
            self._providers[provider.provider_id] = provider
            self._logger.debug(f"Fournisseur enregistré: {provider.provider_id}")

    @staticmethod
    def _motif_de_refus_souverain(provider: ModelProvider) -> Optional[str]:
        """
        Retourne la raison de refuser un fournisseur en mode souverain.

        Deux portes, et les deux comptent : le fournisseur d'un service tiers,
        et le fournisseur « compatible » pointé vers ce même service — le format
        de fil est public, l'infrastructure derrière ne l'est pas.

        Returns:
            La raison du refus, ou None si le fournisseur est acceptable.
        """
        if isinstance(provider, HostedProvider):
            return (
                f"Mode souverain : le fournisseur « {provider.provider_id} » sert le "
                f"modèle d'un tiers, sur son infrastructure. GalSen IA ne dépend "
                f"d'aucun modèle tiers à l'exécution (ADR-014). "
                f"Pour comparer un modèle propre à une référence, déclarez "
                f"{SOVEREIGN_MODE_VARIABLE}=false, en connaissance de cause."
            )

        if isinstance(provider, OpenAICompatibleProvider):
            hote = _hote_tiers(os.environ.get(URL_VARIABLE, ""))
            if hote:
                return (
                    f"Mode souverain : {URL_VARIABLE} pointe vers « {hote} », un "
                    f"service tiers. Le format de fil est public, l'infrastructure "
                    f"derrière ne l'est pas (ADR-014)."
                )

        return None

    def sovereignty_report(self) -> Dict[str, object]:
        """
        Décrit l'état de la souveraineté, pour `/health`.

        Un opérateur doit pouvoir **constater** que sa plateforme ne dépend
        d'aucun tiers, pas seulement le lire dans un ADR. Aucun secret n'y
        figure : ni clé, ni URL — seulement l'hôte visé quand il est en cause,
        et il l'est justement parce qu'il ne devrait pas l'être.

        Returns:
            Le mode, les fournisseurs inscrits, et les fournisseurs tiers
            présents — qui doivent être zéro en mode souverain.
        """
        souverain = sovereign_mode()
        tiers = [
            provider.provider_id for provider in self.list_providers()
            if isinstance(provider, HostedProvider)
        ]
        rapport: Dict[str, object] = {
            "sovereign_mode": souverain,
            "providers": self.provider_ids(),
            "third_party_providers": tiers,
            "reference": "ADR-014",
        }
        hote = _hote_tiers(os.environ.get(URL_VARIABLE, ""))
        if hote:
            rapport["third_party_endpoint"] = hote
        return rapport

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
