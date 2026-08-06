"""
Routeur de modèles pour le moteur de modèles GalSen IA.

Le routeur apporte ce que `ModelManagerImpl.generate()` ne fait pas : compter les
échecs par modèle, écarter temporairement un modèle qui tombe, basculer sur le
candidat suivant, et répartir la charge entre plusieurs modèles sains.

La génération elle-même ne lui appartient pas : elle lui est **injectée**. Le
routeur recevait auparavant un « chargeur de modèles » qui ne chargeait rien, et
retournait `"Réponse simulée du modèle X"` — un texte fabriqué qu'aucun appelant
n'aurait pu distinguer d'une vraie réponse. Il reçoit désormais la fonction de
génération réelle du gestionnaire.

Point important : le fournisseur ne lève pas quand il échoue, il retourne un
statut. Le routeur doit donc **interpréter la réponse** ; sans cela, une réponse
`unavailable` compterait comme un succès et la bascule ne se déclencherait jamais.
"""

from typing import Optional, Dict, Any, Callable, List, Tuple
from .types import ModelItem
from .interfaces import ModelRouter
from .providers.base import GenerationResponse, ProviderStatus
import logging
import time
import random


class ModelRoutingError(RuntimeError):
    """Levée quand un modèle n'a produit aucun texte exploitable."""


class FailoverModelRouter(ModelRouter):
    """Routeur de modèles avec mécanisme de basculement (failover)."""

    def __init__(self, generate: Callable[..., GenerationResponse]):
        """
        Initialise le routeur avec basculement.

        Args:
            generate: Fonction de génération réelle, de signature
                `(model_item, prompt, **kwargs) -> GenerationResponse`.
                Injectée plutôt qu'importée, pour que le routeur n'ait pas à
                connaître le gestionnaire qui le construit.
        """
        self._generate = generate
        self._logger = logging.getLogger(__name__)
        self._failure_counts: dict = {}  # Suivi des échecs par modèle
        self._last_failure_time: dict = {}  # Timestamp du dernier échec
        self._failure_threshold = 3  # Nombre d'échecs avant basculement
        self._reset_timeout = 300  # secondes (5 minutes) après lesquelles réinitialiser le compteur

    def _record_failure(self, model_id: str) -> None:
        """Enregistre un échec pour un modèle."""
        current_time = time.time()
        self._failure_counts[model_id] = self._failure_counts.get(model_id, 0) + 1
        self._last_failure_time[model_id] = current_time
        self._logger.warning(f"Échec enregistré pour le modèle {model_id}. Compteur: {self._failure_counts[model_id]}")

    def _reset_failure_count(self, model_id: str) -> None:
        """Réinitialise le compteur d'échecs pour un modèle."""
        if model_id in self._failure_counts:
            del self._failure_counts[model_id]
        if model_id in self._last_failure_time:
            del self._last_failure_time[model_id]

    def _is_model_healthy(self, model_id: str) -> bool:
        """Vérifie si un modèle est considéré comme sain basé sur son historique d'échecs."""
        # Réinitialiser le compteur si le timeout est écoulé
        if model_id in self._last_failure_time:
            if time.time() - self._last_failure_time[model_id] > self._reset_timeout:
                self._reset_failure_count(model_id)

        # Considérer sain si moins que le seuil d'échec
        failure_count = self._failure_counts.get(model_id, 0)
        return failure_count < self._failure_threshold

    def route_request(self, model_item: ModelItem, request: Dict[str, Any]) -> GenerationResponse:
        """
        Route une requête vers un modèle précis, en tenant son historique d'échecs.

        Args:
            model_item: Modèle à utiliser
            request: Requête portant `prompt` et les options de génération
                (`max_tokens`, `temperature`, `system_prompt`, `stop_sequences`)

        Returns:
            La réponse du fournisseur, dont le statut vaut `READY`.

        Raises:
            ValueError: Si la requête ne porte aucune invite.
            ModelRoutingError: Si le modèle n'a pas produit de texte exploitable.
                L'exception est le signal qu'attend `route_with_fallback` pour
                essayer le candidat suivant ; un statut non `READY` retourné tel
                quel arrêterait la bascule sur le premier modèle indisponible.
        """
        model_id = model_item.model_id

        prompt = request.get("prompt")
        if not prompt or not str(prompt).strip():
            raise ValueError("La requête doit porter une invite non vide ('prompt').")

        if not self._is_model_healthy(model_id):
            self._logger.warning(
                f"Modèle {model_id} considéré comme unhealthy, tentative malgré tout"
            )

        options = {
            cle: request[cle]
            for cle in ("max_tokens", "temperature", "system_prompt", "stop_sequences")
            if cle in request
        }

        try:
            response = self._generate(model_item, prompt, **options)
        except Exception as error:
            self._record_failure(model_id)
            self._logger.error(f"Erreur lors de l'appel au modèle {model_id}: {error}")
            raise

        if not response.succeeded:
            self._record_failure(model_id)
            detail = response.detail or (
                response.reason.value if response.reason else response.status.value
            )
            raise ModelRoutingError(f"Le modèle {model_id} n'a pas répondu : {detail}")

        self._reset_failure_count(model_id)
        return response

    def route_with_fallback(self, model_candidates: List[ModelItem],
                           request: Dict[str, Any]) -> GenerationResponse:
        """
        Route une requête avec mécanisme de basculement automatique.

        Args:
            model_candidates: Liste ordonnée de modèles à essayer (du préféré au moins préféré)
            request: Requête à envoyer au modèle

        Returns:
            Réponse du premier modèle qui réussit

        Raises:
            Exception: Si tous les modèles échouent
        """
        last_exception = None

        for model_item in model_candidates:
            try:
                return self.route_request(model_item, request)
            except Exception as e:
                last_exception = e
                self._logger.warning(f"Modèle {model_item.model_id} a échoué, essai du suivant: {str(e)}")
                continue  # Essayer le modèle suivant

        # Si tous les modèles ont échoué
        error_msg = f"Tous les modèles ont échoué. Dernière erreur: {last_exception}"
        self._logger.error(error_msg)
        raise ModelRoutingError(error_msg)

    def route_with_load_balancing(self, model_candidates: List[ModelItem],
                                 request: Dict[str, Any]) -> GenerationResponse:
        """
        Route une requête avec équilibrage de charge entre les modèles disponibles.

        Args:
            model_candidates: Liste de modèles candidats
            request: Requête à envoyer au modèle

        Returns:
            Réponse du modèle sélectionné
        """
        # Filtrer les modèles sains
        healthy_models = [
            model for model in model_candidates
            if self._is_model_healthy(model.model_id)
        ]

        if not healthy_models:
            # Si aucun modèle n'est sain, réinitialiser les compteurs et essayer quand même
            self._logger.warning("Aucun modèle sain trouvé, réinitialisation des compteurs d'échecs")
            for model in model_candidates:
                self._reset_failure_count(model.model_id)
            healthy_models = model_candidates

        # Sélectionner un modèle basé sur le poids inverse des échecs (moins d'échecs = plus de chances)
        weights = []
        for model in healthy_models:
            failure_count = self._failure_counts.get(model.model_id, 0)
            # Plus le nombre d'échecs est faible, plus le poids est élevé
            weight = max(1, 10 - failure_count)  # Poids entre 1 et 10
            weights.append(weight)

        # Sélection aléatoire pondérée
        selected_index = self._weighted_choice(range(len(healthy_models)), weights)
        selected_model = healthy_models[selected_index]

        self._logger.info(f"Modèle sélectionné par équilibrage de charge: {selected_model.model_id}")

        # Router la requête vers le modèle sélectionné
        return self.route_request(selected_model, request)

    def _weighted_choice(self, items: list, weights: list) -> int:
        """Sélectionne un élément aléatoirement basé sur des poids."""
        if len(items) != len(weights):
            raise ValueError("La longueur des éléments et des poids doit être identique")

        total = sum(weights)
        if total <= 0:
            return random.randint(0, len(items) - 1)

        r = random.uniform(0, total)
        upto = 0
        for i, w in enumerate(weights):
            if upto + w >= r:
                return i
            upto += w
        return len(items) - 1  # Fallback (ne devrait jamais arriver)