"""
Automatic provider selection for the GalSen IA Model Engine.

Given a task, decides which provider and which model should handle it. The
caller describes what the task needs; it never names a vendor.

Two rules drive the choice, in this order:
  1. A provider that cannot answer is never selected, whatever its qualities.
  2. Among providers that can answer, the cheapest model meeting the
     requirements wins. Cost matters here beyond accounting: the platform is
     built for contexts where per-token spend is a real constraint.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .model_registry import ModelRegistry
from .providers.base import ModelDescriptor, ModelProvider
from .providers.provider_registry import ProviderRegistry


@dataclass
class ProviderSelection:
    """Résultat d'une sélection automatique de fournisseur."""

    provider: Optional[ModelProvider]
    descriptor: Optional[ModelDescriptor]
    reason: str

    @property
    def succeeded(self) -> bool:
        """Indique qu'un fournisseur utilisable a été trouvé."""
        return self.provider is not None and self.descriptor is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit la sélection en dictionnaire."""
        return {
            "selected": self.succeeded,
            "provider_id": self.provider.provider_id if self.provider else None,
            "model_name": self.descriptor.model_name if self.descriptor else None,
            "reason": self.reason,
        }


class ProviderSelector:
    """
    Sélectionne automatiquement le fournisseur et le modèle d'une tâche.

    Exemple:
        selector = ProviderSelector(provider_registry, model_registry)
        selection = selector.select({"task_type": "reasoning", "complexity": "high"})
    """

    # Exigences déduites du type de tâche annoncé par l'appelant
    TASK_REQUIREMENTS = {
        "reasoning": {"preferred_features": ["reasoning"], "min_context_window": 8192},
        "analysis": {"preferred_features": ["analysis", "reasoning"], "min_context_window": 32000},
        "code_generation": {"preferred_features": ["code_generation"], "min_context_window": 8192},
        "summarization": {"preferred_features": ["long_context"], "min_context_window": 32000},
        "document_analysis": {"preferred_features": ["long_context"], "min_context_window": 100000},
        "vision": {"requires_vision": True},
        "conversation": {"preferred_features": ["general_conversation", "fast_response"]},
        "translation": {"preferred_features": ["general_conversation"]},
    }

    # Contexte minimal exigé selon la complexité annoncée
    COMPLEXITY_CONTEXT = {
        "simple": 4096,
        "medium": 8192,
        "high": 32000,
        "very_high": 100000,
    }

    def __init__(
        self,
        provider_registry: Optional[ProviderRegistry] = None,
        model_registry: Optional[ModelRegistry] = None,
    ):
        """
        Initialise le sélecteur.

        Args:
            provider_registry: Registre des fournisseurs
            model_registry: Catalogue des modèles
        """
        self._provider_registry = provider_registry or ProviderRegistry()
        self._model_registry = model_registry or ModelRegistry(self._provider_registry)
        self._logger = logging.getLogger(__name__)

    def select(self, task_requirements: Optional[Dict[str, Any]] = None) -> ProviderSelection:
        """
        Sélectionne le fournisseur et le modèle adaptés à une tâche.

        Args:
            task_requirements: Description de la tâche. Clés reconnues :
                `task_type`, `complexity`, `requires_vision`,
                `requires_function_calling`, `min_context_window`,
                `max_input_cost`, `preferred_provider`.

        Returns:
            La sélection, ou un résultat expliquant pourquoi rien n'a été retenu
        """
        requirements = self._resolve_requirements(task_requirements or {})

        if not self._provider_registry.has_available_provider():
            return ProviderSelection(
                provider=None,
                descriptor=None,
                reason=self._provider_registry.unavailability_summary(),
            )

        candidates = self._model_registry.find_models(
            min_context_window=requirements["min_context_window"],
            requires_vision=requirements["requires_vision"],
            requires_function_calling=requirements["requires_function_calling"],
            max_input_cost=requirements["max_input_cost"],
            available_only=True,
        )

        if not candidates:
            return ProviderSelection(
                provider=None,
                descriptor=None,
                reason=(
                    "Aucun modèle disponible ne satisfait les contraintes "
                    f"(contexte minimal {requirements['min_context_window']}, "
                    f"vision={requirements['requires_vision']})"
                ),
            )

        descriptor = self._pick_best(candidates, requirements)
        provider = self._provider_registry.get(descriptor.provider_id)

        if provider is None:
            return ProviderSelection(
                provider=None,
                descriptor=None,
                reason=f"Le fournisseur '{descriptor.provider_id}' n'est plus enregistré",
            )

        return ProviderSelection(
            provider=provider,
            descriptor=descriptor,
            reason=(
                f"{descriptor.model_name} retenu chez {provider.display_name}: "
                f"contexte {descriptor.context_window}, "
                f"coût {descriptor.pricing_per_1k_tokens.get('input', 0.0)}/1k jetons"
            ),
        )

    def select_provider_for_model(self, model_name: str) -> ProviderSelection:
        """
        Sélectionne le fournisseur servant un modèle nommé.

        Args:
            model_name: Nom du modèle demandé

        Returns:
            La sélection, ou un résultat expliquant l'échec
        """
        provider = self._provider_registry.find_provider_for(model_name)
        if provider is None:
            return ProviderSelection(
                provider=None,
                descriptor=None,
                reason=f"Aucun fournisseur ne propose le modèle '{model_name}'",
            )

        availability = provider.check_availability()
        if not provider.is_available():
            return ProviderSelection(
                provider=None,
                descriptor=None,
                reason=f"{provider.display_name}: {availability.detail}",
            )

        return ProviderSelection(
            provider=provider,
            descriptor=provider.describe_model(model_name),
            reason=f"{model_name} servi par {provider.display_name}",
        )

    def explain(self, task_requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Détaille le raisonnement de sélection, pour le diagnostic.

        Args:
            task_requirements: Description de la tâche

        Returns:
            Les exigences déduites, les fournisseurs consultés et le choix final
        """
        requirements = self._resolve_requirements(task_requirements or {})
        selection = self.select(task_requirements)

        return {
            "resolved_requirements": requirements,
            "provider_status": {
                provider_id: info.to_dict()
                for provider_id, info in self._provider_registry.status_report().items()
            },
            "candidate_count": len(
                self._model_registry.find_models(
                    min_context_window=requirements["min_context_window"],
                    requires_vision=requirements["requires_vision"],
                    available_only=True,
                )
            ),
            "selection": selection.to_dict(),
        }

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _resolve_requirements(self, task_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traduit une description de tâche en contraintes concrètes.

        Les exigences viennent désormais de `config/model_routing.yaml`
        (VOLET 30). Elles vivaient dans `TASK_REQUIREMENTS`, en dur : les changer
        demandait de modifier du code, alors que le bon réglage dépend des
        modèles réellement installés sur la machine. La table de classe reste
        comme filet, et sert si le fichier est absent.
        """
        from .routing_policy import shared_policy

        task_type = task_requirements.get("task_type", "conversation")
        complexity = task_requirements.get("complexity", "medium")

        modeles_servis = [
            descripteur.model_name
            for descripteur in self._model_registry.find_models(available_only=True)
        ]
        decision = shared_policy().decide(
            {**task_requirements, "task_type": task_type, "complexity": complexity},
            available_models=modeles_servis,
        )
        exigences = decision.requirements

        # Filet : si la politique n'a rien pour ce type, la table historique
        # fournit encore un profil plutôt que rien.
        profile = self.TASK_REQUIREMENTS.get(task_type, {})
        min_context = max(
            exigences.get("min_context_window", 0),
            profile.get("min_context_window", 0),
            self.COMPLEXITY_CONTEXT.get(complexity, 0),
            int(task_requirements.get("min_context_window", 0)),
        )

        return {
            "task_type": task_type,
            "complexity": complexity,
            "min_context_window": min_context,
            "requires_vision": bool(
                exigences.get("requires_vision")
                or task_requirements.get("requires_vision", profile.get("requires_vision", False))
            ),
            "requires_function_calling": bool(
                exigences.get("requires_function_calling")
                or task_requirements.get("requires_function_calling", False)
            ),
            "max_input_cost": exigences.get("max_input_cost"),
            "preferred_features": (
                exigences.get("preferred_features") or profile.get("preferred_features", [])
            ),
            "preferred_provider": task_requirements.get("preferred_provider"),
            # Ce que la politique a décidé voyage avec les exigences : sans cela,
            # la réponse ne peut pas dire pourquoi ce modèle-là a été retenu.
            "prefer_cheapest": bool(exigences.get("prefer_cheapest")),
            "family": decision.family,
            "family_available": decision.family_available,
            "route_reason": decision.reason,
        }

    def _pick_best(
        self, candidates: List[ModelDescriptor], requirements: Dict[str, Any]
    ) -> ModelDescriptor:
        """
        Choisit le meilleur candidat.

        Les candidats arrivent déjà triés par coût croissant. Un fournisseur
        explicitement demandé et les atouts attendus par la tâche l'emportent
        sur ce classement, à condition de rester disponibles.
        """
        preferred_provider = requirements.get("preferred_provider")
        if preferred_provider:
            for descriptor in candidates:
                if descriptor.provider_id == preferred_provider:
                    return descriptor

        # La famille visée passe avant tout le reste : router une tâche de code
        # vers SamP alors que ToP est servi reviendrait à ignorer la décision
        # d'ADR-014. Quand aucun modèle de la famille n'est là, la politique l'a
        # déjà signalé et on continue avec les autres critères.
        famille = requirements.get("family")
        if famille:
            from .routing_policy import shared_policy

            politique = shared_policy()
            de_la_famille = [
                descripteur for descripteur in candidates
                if politique.family_of(descripteur.model_name) == famille
            ]
            if de_la_famille:
                candidates = de_la_famille

        # « Question simple → petit modèle » : pour une tâche ordinaire, le moins
        # cher des modèles capables suffit, et les candidats arrivent triés par
        # coût croissant. C'est la seule optimisation de coût qui ne dégrade rien.
        if requirements.get("prefer_cheapest"):
            return candidates[0]

        preferred_features = requirements.get("preferred_features", [])
        if preferred_features:
            for descriptor in candidates:
                if any(feature in descriptor.special_features for feature in preferred_features):
                    return descriptor

        # À défaut de préférence applicable, le moins cher convient
        return candidates[0]
