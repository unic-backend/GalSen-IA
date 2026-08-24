"""
Gestionnaire principal du moteur de modèles GalSen IA.
"""

from typing import Optional, Dict, Any, List, Tuple
from .types import ModelItem, ModelStatus
from .interfaces import (
    ModelStore, ModelManager
)
from .model_store import InMemoryModelStore
from .model_selector import SimpleModelSelector
from .model_router import FailoverModelRouter
from .model_context_manager import SimpleModelContextManager
from .prompt_optimizer import TemplateBasedPromptOptimizer
from .response_validator import BasicResponseValidator
from .token_tracker import InMemoryTokenTracker
from .cost_tracker import InMemoryCostTracker
from .rate_limiter import TokenBucketRateLimiter
from .retry_manager import ExponentialBackoffRetryManager
from .stream_handler import SimpleStreamHandler
from .parallel_executor import ThreadPoolParallelExecutor
from .response_ranker import WeightedResponseRanker
from .health_monitor import RollingWindowHealthMonitor
from .capability_detector import CapabilityDetector
from .model_registry import ModelRegistry
from .provider_selector import ProviderSelector
from .providers.base import (
    GenerationRequest, GenerationResponse, ProviderUnavailableError, UnavailabilityReason
)
from .providers.provider_registry import ProviderRegistry
import logging
import time
import asyncio
from src.storage.paths import sqlite_enabled


class ModelManagerImpl(ModelManager):
    """
    Implémentation concrète du gestionnaire de modèles qui coordonne
    tous les composants du moteur de modèles.
    """

    def __init__(self, provider_registry: Optional[ProviderRegistry] = None,
                 memory_manager: Optional[Any] = None,
                 store: Optional[ModelStore] = None):
        """
        Initialise le gestionnaire de modèles.

        Args:
            provider_registry: Registre des fournisseurs. Le registre par défaut
                n'inscrit que les fournisseurs souverains — serveur local et
                serveur au format compatible (ADR-014).
            memory_manager: Moteur de mémoire recevant l'historique des
                générations. Optionnel : sans lui, rien n'est consigné et le
                moteur de modèles reste utilisable seul.
            store: Stockage des modèles (par défaut: InMemoryModelStore, ou
                SQLite si GALSEN_STORAGE_BACKEND=sqlite, ADR-005).
        """
        # Initialiser tous les composants
        if store is not None:
            self._store = store
        elif sqlite_enabled():
            # Import différé pour éviter un import circulaire avec storage.
            from src.storage.sqlite_model_store import SQLiteModelStore
            self._store = SQLiteModelStore()
        else:
            self._store = InMemoryModelStore()
        self._selector = SimpleModelSelector()
        # Le routeur reçoit la génération réelle : c'est lui qui compte les échecs
        # et bascule d'un modèle à l'autre, pas lui qui appelle les fournisseurs.
        self._router = FailoverModelRouter(self.generate)
        self._context_manager = SimpleModelContextManager()
        self._po = TemplateBasedPromptOptimizer()
        self._rv = BasicResponseValidator()
        self._tt = InMemoryTokenTracker()
        self._ct = InMemoryCostTracker()
        self._rl = TokenBucketRateLimiter()
        self._rm = ExponentialBackoffRetryManager()
        self._sh = SimpleStreamHandler()
        self._pe = ThreadPoolParallelExecutor()
        self._rr = WeightedResponseRanker()
        self._hm = RollingWindowHealthMonitor()

        # Couche fournisseurs : c'est elle qui rend les modèles interchangeables
        self._provider_registry = provider_registry or ProviderRegistry()
        self._model_registry = ModelRegistry(self._provider_registry)
        self._provider_selector = ProviderSelector(self._provider_registry, self._model_registry)
        # Le détecteur interroge les fournisseurs et retombe sur la table
        # statique historique pour les modèles enregistrés à la main
        self._cd = CapabilityDetector(self._provider_registry)

        self._memory = memory_manager

        self._logger = logging.getLogger(__name__)
        self._logger.info(
            f"Gestionnaire de modèles initialisé "
            f"({len(self._provider_registry.provider_ids())} fournisseurs, "
            f"{len(self._model_registry.list_all())} modèles au catalogue)"
        )

    # Méthodes de gestion du stockage des modèles
    def register_model(self, model_item: ModelItem) -> str:
        """
        Enregistre un nouveau modèle.

        Args:
            model_item: Modèle à enregistrer

        Returns:
            ID du modèle enregistré
        """
        return self._store.save(model_item)

    def sovereignty_report(self) -> Dict[str, Any]:
        """
        Décrit l'état de la souveraineté du moteur (ADR-014).

        Exposé ici parce que le registre de fournisseurs est interne au moteur :
        `/health` a besoin du constat, pas de l'objet.
        """
        return self._provider_registry.sovereignty_report()

    def get_model(self, model_id: str) -> Optional[ModelItem]:
        """
        Récupère un modèle enregistré.

        Args:
            model_id: ID du modèle à récupérer

        Returns:
            Modèle correspondant à l'ID ou None si non trouvé
        """
        return self._store.get(model_id)

    def update_model(self, model_item: ModelItem) -> bool:
        """
        Met à jour un modèle enregistré.

        Args:
            model_item: Modèle avec les mises à jour

        Returns:
            True si la mise à jour a réussi, False sinon
        """
        return self._store.update(model_item)

    def unregister_model(self, model_id: str) -> bool:
        """
        Désenregistre un modèle.

        Args:
            model_id: ID du modèle à désenregistrer

        Returns:
            True si le désenregistrement a réussi, False sinon
        """
        return self._store.delete(model_id)

    def list_models(self, **filters) -> List[ModelItem]:
        """
        Liste tous les modèles enregistrés.

        Args:
            **filters: Filtres optionnels (model_type, provider, status, etc.)

        Returns:
            Liste des modèles correspondant aux filtres
        """
        return self._store.list_items(**filters)

    # Méthodes de sélection et de routage
    def select_model_for_task(self, task_requirements: Dict[str, Any]) -> Optional[ModelItem]:
        """
        Sélectionne le meilleur modèle pour une tâche donnée.

        Args:
            task_requirements: Exigences de la tâche (complexité, type, etc.)

        Returns:
            Meilleur modèle pour la tâche ou None si aucun ne convient
        """
        # Toute nouvelle sélection annule l'explication de la précédente : une
        # raison périmée survivrait à la mise en service d'un modèle.
        self._last_selection_failure = ""

        # Les modèles enregistrés explicitement priment sur le catalogue
        available_models = self.list_models(status=ModelStatus.ACTIVE.value)

        if available_models:
            return self._selector.select_model(available_models, task_requirements)

        # Aucun modèle enregistré : se rabattre sur le catalogue, en ne retenant
        # que ce qu'un fournisseur peut réellement servir. Sans fournisseur
        # disponible, la méthode retourne None, ce qui laisse l'appelant
        # annoncer une indisponibilité plutôt qu'un échec de génération.
        selection = self._provider_selector.select(task_requirements)
        if not selection.succeeded:
            # La raison est conservée, pas seulement journalisée : c'est elle
            # que l'appelant rendra à l'utilisateur. Sans cela, un serveur
            # Ollama actif dont le modèle a un contexte trop court produisait
            # un 503 « Aucun modèle sélectionnable », sans dire ce qui manque.
            self._last_selection_failure = selection.reason
            self._logger.warning(f"Aucun modèle sélectionnable: {selection.reason}")
            return None

        return self._model_registry.descriptor_to_model_item(selection.descriptor)

    # ------------------------------------------------------------------
    # Génération de texte
    # ------------------------------------------------------------------
    def generate(self, model_item: ModelItem, prompt: str, **kwargs) -> GenerationResponse:
        """
        Génère du texte et retourne une réponse structurée.

        C'est l'API à privilégier : le statut de la réponse dit si le texte est
        exploitable, ce qu'une chaîne de caractères ne peut pas exprimer.

        Args:
            model_item: Modèle à utiliser
            prompt: Invite envoyée au modèle
            **kwargs: `max_tokens`, `temperature`, `system_prompt`, `stop_sequences`

        Returns:
            La réponse du fournisseur. Quand le statut n'est pas `READY`, le
            texte est vide et `detail` explique quoi faire.
        """
        selection = self._provider_selector.select_provider_for_model(model_item.name)
        if not selection.succeeded:
            return GenerationResponse.unavailable(
                provider_id=model_item.provider,
                model_name=model_item.name,
                reason=UnavailabilityReason.NO_CREDENTIALS,
                detail=selection.reason,
            )

        request = GenerationRequest(
            prompt=prompt,
            model_name=model_item.name,
            max_tokens=kwargs.get("max_tokens", model_item.max_output_tokens),
            temperature=kwargs.get("temperature", 0.7),
            system_prompt=kwargs.get("system_prompt"),
            stop_sequences=kwargs.get("stop_sequences", []),
        )

        response = self._call_provider(
            selection.provider, request, model_item,
            # La route est celle que l'appelant a annoncée : c'est elle qui
            # permettra de dire quelle politique coûte quoi.
            route=kwargs.get("task_type") or "unspecified",
        )
        self._record_generation(model_item, prompt, response)
        return response

    async def generate_text(self, model_item: ModelItem, prompt: str,
                            **kwargs) -> str:
        """
        Génère du texte avec un modèle spécifique.

        Args:
            model_item: Modèle à utiliser
            prompt: Invite envoyée au modèle
            **kwargs: Options transmises au fournisseur

        Returns:
            Le texte généré

        Raises:
            ProviderUnavailableError: Si aucun fournisseur ne peut répondre.
                L'exception est préférée à une chaîne de substitution : un
                appelant qui attend du texte doit savoir qu'il n'y en a pas.
        """
        response = await asyncio.to_thread(self.generate, model_item, prompt, **kwargs)

        if not response.succeeded:
            raise ProviderUnavailableError(
                provider_id=response.provider_id or model_item.provider,
                reason=response.reason or UnavailabilityReason.NO_CREDENTIALS,
                detail=response.detail or "Aucun fournisseur disponible",
            )

        return response.text

    async def generate_text_with_source(self, prompt: str,
                                        task_requirements: Dict[str, Any],
                                        **kwargs) -> Tuple[str, str]:
        """
        Génère du texte **et nomme le modèle qui a répondu**.

        `generate_text_with_fallback` ne rend qu'une chaîne : *lequel* des
        candidats a abouti n'apparaît nulle part dans sa valeur de retour. Un
        appelant qui veut l'afficher n'a que deux options, et les deux sont
        mauvaises — deviner le premier de la liste, ce qui est faux dans le seul
        cas intéressant (quand le repli a servi), ou ne rien dire.

        Cette méthode existe pour qu'il en ait une troisième. Elle ne remplace
        pas l'autre : `generate_text_with_fallback` reste le chemin de ceux qui
        n'ont besoin que du texte.

        Args:
            prompt: Invite envoyée au modèle
            task_requirements: Exigences de la tâche
            **kwargs: Options transmises au fournisseur

        Returns:
            Le couple `(texte, nom du modèle)`.

        Raises:
            ProviderUnavailableError: Si aucun modèle candidat n'a pu répondre
        """
        candidates = self._fallback_candidates(task_requirements)
        if not candidates:
            raise ProviderUnavailableError(
                provider_id="aucun",
                reason=UnavailabilityReason.NO_CREDENTIALS,
                detail=self._provider_registry.unavailability_summary()
                or "Aucun modèle ne correspond aux exigences de la tâche",
            )

        last_detail = ""
        for model_item in candidates:
            response = await asyncio.to_thread(self.generate, model_item, prompt, **kwargs)
            if response.succeeded:
                return response.text, model_item.name

            last_detail = response.detail or ""
            self._logger.info(
                f"Modèle '{model_item.name}' indisponible, essai du suivant: {last_detail}"
            )

        raise ProviderUnavailableError(
            provider_id="aucun",
            reason=UnavailabilityReason.NO_CREDENTIALS,
            detail=last_detail or "Tous les modèles candidats ont échoué",
        )

    async def generate_text_with_fallback(self, prompt: str,
                                          task_requirements: Dict[str, Any],
                                          **kwargs) -> str:
        """
        Génère du texte en essayant les modèles adaptés jusqu'à en trouver un qui répond.

        Args:
            prompt: Invite envoyée au modèle
            task_requirements: Exigences de la tâche
            **kwargs: Options transmises au fournisseur

        Returns:
            Le texte généré par le premier modèle ayant abouti

        Raises:
            ProviderUnavailableError: Si aucun modèle candidat n'a pu répondre
        """
        # Une seule implémentation du repli, ici déléguée : deux boucles
        # identiques finiraient par diverger, et c'est la divergence entre
        # deux chemins censés faire la même chose qui a produit le défaut de
        # routage corrigé le 2026-08-24.
        texte, _ = await self.generate_text_with_source(
            prompt, task_requirements, **kwargs
        )
        return texte

    async def generate_text_with_load_balancing(self, prompt: str,
                                                task_requirements: Dict[str, Any],
                                                **kwargs) -> str:
        """
        Génère du texte en répartissant la charge entre les modèles disponibles.

        La répartition suit le compteur d'utilisation : le modèle le moins
        sollicité passe en premier, ce qui évite de saturer un seul fournisseur.

        Args:
            prompt: Invite envoyée au modèle
            task_requirements: Exigences de la tâche
            **kwargs: Options transmises au fournisseur

        Returns:
            Le texte généré

        Raises:
            ProviderUnavailableError: Si aucun modèle n'a pu répondre
        """
        candidates = self._fallback_candidates(task_requirements)
        if not candidates:
            raise ProviderUnavailableError(
                provider_id="aucun",
                reason=UnavailabilityReason.NO_CREDENTIALS,
                detail=self._provider_registry.unavailability_summary()
                or "Aucun modèle ne correspond aux exigences de la tâche",
            )

        balanced = sorted(candidates, key=lambda item: item.usage_count)

        last_detail = ""
        for model_item in balanced:
            response = await asyncio.to_thread(self.generate, model_item, prompt, **kwargs)
            if response.succeeded:
                return response.text
            last_detail = response.detail or ""

        raise ProviderUnavailableError(
            provider_id="aucun",
            reason=UnavailabilityReason.NO_CREDENTIALS,
            detail=last_detail or "Tous les modèles candidats ont échoué",
        )

    # ------------------------------------------------------------------
    # Fournisseurs et catalogue
    # ------------------------------------------------------------------
    def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Retourne l'état de chaque fournisseur enregistré.

        Returns:
            Pour chaque fournisseur, son état, son nombre de modèles et, s'il
            est indisponible, le motif exact
        """
        return {
            provider_id: info.to_dict()
            for provider_id, info in self._provider_registry.status_report().items()
        }

    def has_available_provider(self) -> bool:
        """Indique si au moins un fournisseur peut servir une génération."""
        return self._provider_registry.has_available_provider()

    def unavailability_reason(self) -> str:
        """
        Explique pourquoi aucune génération n'est possible.

        Deux causes distinctes, et la seconde était muette : ou bien aucun
        fournisseur ne répond, ou bien un fournisseur répond mais aucun de ses
        modèles ne satisfait les contraintes de la tâche. Le second cas est le
        plus probable en local — un serveur Ollama actif avec un modèle à
        contexte court — et c'est celui qui ne disait rien.

        Returns:
            Un message actionnable, ou une chaîne vide si la génération est
            possible.
        """
        resume = self._provider_registry.unavailability_summary()
        if resume:
            return resume
        return getattr(self, "_last_selection_failure", "")

    def list_catalogue(self, available_only: bool = False) -> List[Dict[str, Any]]:
        """
        Retourne le catalogue des modèles connus.

        Args:
            available_only: Ne retenir que les modèles réellement utilisables

        Returns:
            Les modèles du catalogue avec leurs caractéristiques
        """
        descriptors = (
            self._model_registry.find_models(available_only=True)
            if available_only else self._model_registry.list_all()
        )
        return [
            {
                "model_name": descriptor.model_name,
                "provider_id": descriptor.provider_id,
                "context_window": descriptor.context_window,
                "supports_vision": descriptor.supports_vision,
                "pricing_per_1k_tokens": descriptor.pricing_per_1k_tokens,
                "special_features": descriptor.special_features,
            }
            for descriptor in descriptors
        ]

    def select_provider_for_task(self, task_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sélectionne automatiquement le fournisseur adapté à une tâche.

        Args:
            task_requirements: Exigences de la tâche

        Returns:
            La sélection retenue, ou le motif pour lequel rien n'a été retenu
        """
        return self._provider_selector.select(task_requirements).to_dict()

    def explain_selection(self, task_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Détaille le raisonnement de sélection, pour le diagnostic.

        Args:
            task_requirements: Exigences de la tâche

        Returns:
            Les exigences déduites, l'état des fournisseurs et le choix final
        """
        return self._provider_selector.explain(task_requirements)

    def register_provider(self, provider) -> None:
        """
        Enregistre un fournisseur supplémentaire.

        Args:
            provider: Fournisseur respectant le contrat `ModelProvider`
        """
        self._provider_registry.register(provider)
        # Les capacités mises en cache reposaient sur l'ancien ensemble de fournisseurs
        self._cd.clear_cache()

    def generate_with_fallback(
        self, model_candidates: List[ModelItem], prompt: str, **kwargs
    ) -> GenerationResponse:
        """
        Génère du texte en essayant plusieurs modèles, du préféré au dernier recours.

        `generate()` interroge un modèle et retourne son statut. Cette méthode va
        plus loin : elle passe au candidat suivant quand un modèle ne répond pas,
        et retient les échecs pour écarter temporairement un modèle qui tombe
        souvent.

        Args:
            model_candidates: Modèles à essayer, dans l'ordre de préférence
            prompt: Invite envoyée au modèle
            **kwargs: `max_tokens`, `temperature`, `system_prompt`, `stop_sequences`

        Returns:
            La réponse du premier modèle qui produit du texte. Si aucun n'y
            parvient, une réponse de statut `UNAVAILABLE` portant la dernière
            raison rencontrée — jamais une exception, pour rester cohérent avec
            `generate()`.

        Raises:
            ValueError: Si aucun candidat n'est fourni. Une liste vide est une
                erreur de l'appelant, pas une indisponibilité de la plateforme.
        """
        if not model_candidates:
            raise ValueError("Au moins un modèle candidat est requis.")

        request = {"prompt": prompt, **kwargs}
        try:
            return self._router.route_with_fallback(model_candidates, request)
        except Exception as error:
            self._logger.warning("Bascule épuisée : %s", error)
            return GenerationResponse.unavailable(
                provider_id=model_candidates[-1].provider,
                model_name=model_candidates[-1].name,
                reason=UnavailabilityReason.UNREACHABLE,
                detail=str(error),
            )

    def sync_catalogue_to_store(self, available_only: bool = True) -> List[str]:
        """
        Enregistre les modèles du catalogue dans le stockage du moteur.

        Args:
            available_only: N'enregistrer que les modèles réellement utilisables

        Returns:
            Les identifiants des modèles enregistrés
        """
        registered: List[str] = []
        for model_item in self._model_registry.build_all_model_items(available_only=available_only):
            if self.get_model(model_item.model_id) is None:
                registered.append(self.register_model(model_item))
        return registered

    # ------------------------------------------------------------------
    # Utilitaires internes de génération
    # ------------------------------------------------------------------
    def _call_provider(self, provider, request: GenerationRequest,
                       model_item: ModelItem,
                       route: str = "unspecified") -> GenerationResponse:
        """
        Appelle un fournisseur en appliquant les protections du moteur.

        Limitation de débit, nouvelles tentatives, suivi des jetons, des coûts
        et de la santé sont appliqués ici, de sorte qu'un fournisseur n'ait
        jamais à s'en préoccuper.
        """
        if not self._rl.can_execute(model_item):
            waited = self._rl.wait_if_needed(model_item)
            self._logger.debug(f"Limitation de débit: attente de {waited:.2f}s")

        started_at = time.time()
        try:
            response = self._rm.execute_with_retry(provider.generate, request)
        except Exception as error:
            latency = time.time() - started_at
            self._hm.update_health(model_item, latency, success=False, error=str(error))
            self._logger.error(f"Fournisseur '{provider.provider_id}' en erreur: {error}")
            return GenerationResponse.unavailable(
                provider_id=provider.provider_id,
                model_name=request.model_name,
                reason=UnavailabilityReason.UNREACHABLE,
                detail=str(error),
            )

        latency = time.time() - started_at
        self._hm.update_health(
            model_item, latency,
            success=response.succeeded,
            error=response.detail if not response.succeeded else None,
        )

        if response.succeeded:
            self._tt.track_usage(model_item, response.prompt_tokens, response.completion_tokens)
            # Le coût est ventilé **par route** (VOLET 30, ch. 02). Le suiveur
            # sait ventiler par `operation_type` depuis le début, et tout le
            # monde lui passait la valeur par défaut : le coût total était connu,
            # et « qu'est-ce qui coûte cher » ne l'était pas. Une politique de
            # routage qu'on ne peut pas mesurer ne peut pas être améliorée.
            self._ct.track_cost(model_item, response.total_tokens, operation_type=f"route:{route}")
            model_item.usage_count += 1
            self.update_model(model_item)

        return response

    def _fallback_candidates(self, task_requirements: Dict[str, Any]) -> List[ModelItem]:
        """
        Construit la liste ordonnée des modèles à essayer pour une tâche.

        Les modèles déjà enregistrés dans le stockage passent en premier, puis
        ceux du catalogue servis par un fournisseur disponible.

        **Le catalogue est désormais trié par `ProviderSelector`** avant d'être
        ajouté. Il ne l'était pas : les modèles du catalogue arrivaient dans
        l'ordre du fournisseur, et comme `generate_text_with_fallback` essaie le
        premier qui répond, un serveur local en bonne santé répondait toujours
        avec le **premier modèle installé**, quelle que soit la tâche demandée.
        Toute la sélection par capacité vivait dans `ProviderSelector`, que ce
        chemin n'appelait pas — c'est-à-dire nulle part, du point de vue d'un
        utilisateur du chat.

        Rien n'est retiré de la liste : le modèle retenu passe devant, les
        autres restent derrière dans leur ordre d'origine. Le repli garde donc
        exactement la même portée qu'avant.
        """
        candidates: List[ModelItem] = []
        seen: set = set()

        stored = self.list_models(status=ModelStatus.ACTIVE.value)
        if stored:
            selected = self._selector.select_model(stored, task_requirements)
            if selected is not None:
                candidates.append(selected)
                seen.add(selected.model_id)

            for model_item in stored:
                if model_item.model_id not in seen:
                    candidates.append(model_item)
                    seen.add(model_item.model_id)

        for model_item in self._catalogue_trie(task_requirements):
            if model_item.model_id not in seen:
                candidates.append(model_item)
                seen.add(model_item.model_id)

        return candidates

    def _catalogue_trie(self, task_requirements: Dict[str, Any]) -> List[ModelItem]:
        """
        Retourne le catalogue disponible, le modèle adapté à la tâche en tête.

        Args:
            task_requirements: Exigences de la tâche, `task_type` compris

        Returns:
            Les modèles du catalogue. En cas d'échec de la sélection, l'ordre
            d'origine — router moins finement vaut mieux que ne plus router.
        """
        catalogue = self._model_registry.build_all_model_items(available_only=True)
        if len(catalogue) < 2 or not task_requirements:
            return catalogue

        try:
            from .provider_selector import ProviderSelector

            selection = ProviderSelector(
                provider_registry=self._provider_registry,
                model_registry=self._model_registry,
            ).select(task_requirements)
        except Exception as erreur:  # noqa: BLE001 - une sélection ratée ne doit rien bloquer
            self._logger.warning(
                "Tri du catalogue impossible (%s) : ordre du fournisseur conservé.", erreur
            )
            return catalogue

        if selection.descriptor is None:
            return catalogue

        attendu = f"{selection.descriptor.provider_id}:{selection.descriptor.model_name}"
        en_tete = [m for m in catalogue if m.model_id == attendu]
        return en_tete + [m for m in catalogue if m.model_id != attendu]

    def _record_generation(self, model_item: ModelItem, prompt: str,
                           response: GenerationResponse) -> None:
        """
        Consigne une génération dans le moteur de mémoire.

        L'historique des générations appartient à la mémoire, pas au moteur de
        modèles : ce dernier se contente de le lui transmettre quand une
        mémoire lui a été fournie. L'échec de cette écriture ne compromet
        jamais la génération elle-même.
        """
        if self._memory is None:
            return

        try:
            from ..memory_engine.types import MemoryItem, MemoryType

            self._memory.save_memory(MemoryItem(
                content={
                    "prompt": prompt,
                    "response": response.text,
                    "status": response.status.value,
                },
                memory_type=MemoryType.SESSION,
                agent_id="model_engine",
                tags=["generation", model_item.provider, model_item.name],
                metadata={
                    "model_id": model_item.model_id,
                    "total_tokens": response.total_tokens,
                    "latency_seconds": response.latency_seconds,
                },
            ))
        except Exception as error:
            self._logger.debug(f"Historique de génération non enregistré: {error}")

    # Méthodes utilitaires supplémentaires
    def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations détaillées d'un modèle.

        Args:
            model_id: ID du modèle

        Returns:
            Dictionnaire des informations du modèle ou None si non trouvé
        """
        model_item = self.get_model(model_id)
        if model_item is None:
            return None

        return {
            "model_id": model_item.model_id,
            "model_type": model_item.model_type.value,
            "provider": model_item.provider,
            "name": model_item.name,
            "version": model_item.version,
            "priority": model_item.priority.value,
            "status": model_item.status.value,
            "context_window": model_item.context_window,
            "max_output_tokens": model_item.max_output_tokens,
            "supported_features": model_item.supported_features,
            "metadata": model_item.metadata,
            "created_at": model_item.created_at,
            "updated_at": model_item.updated_at
        }

    def get_usage_stats(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les statistiques d'utilisation d'un modèle.

        Args:
            model_id: ID du modèle

        Returns:
            Dictionnaire des statistiques d'utilisation ou None si non trouvé
        """
        model_item = self.get_model(model_id)
        if model_item is None:
            return None

        return self._tt.get_usage_stats(model_item)

    def get_health_status(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère l'état de santé d'un modèle.

        Args:
            model_id: ID du modèle

        Returns:
            Dictionnaire de l'état de santé ou None si non trouvé
        """
        model_item = self.get_model(model_id)
        if model_item is None:
            return None

        return self._hm.get_health_status(model_item)

    def get_cost_stats(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les statistiques de coûts d'un modèle.

        Args:
            model_id: ID du modèle

        Returns:
            Dictionnaire des statistiques de coûts ou None si non trouvé
        """
        model_item = self.get_model(model_id)
        if model_item is None:
            return None

        return self._ct.get_cost_stats(model_item)

    def cleanup(self) -> None:
        """
        Nettoie les ressources.
        """
        self._pe.shutdown()
        self._logger.info("Gestionnaire de modèles nettoyé")