"""
Model tool for GalSen IA.

Exposes the Model Engine through the Tool Engine, so an agent can reach models
the same way it reaches the filesystem or the web — one uniform interface, and
one place where availability is reported.

Generation returns a status rather than raising: an agent must be able to see
that no provider answered and fall back to deterministic work, which is the
platform's behaviour today.
"""

import logging
from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

logger = logging.getLogger(__name__)


class ModelTool(BaseTool):
    """
    Outil donnant accès au moteur de modèles.

    Opérations : `generate`, `status`, `catalogue`, `select`, `explain`,
    `capabilities`, `available`.

    Exemple:
        tool.execute("status")
        tool.execute("generate", "Résume ce texte", task_type="summarization")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil.

        Args:
            config: Configuration avec les clés optionnelles :
                - `max_tokens`: longueur maximale par défaut des générations
                - `temperature`: température par défaut
        """
        super().__init__(config)
        self.default_max_tokens = int(self.config.get("max_tokens", 1024))
        self.default_temperature = float(self.config.get("temperature", 0.7))
        self._engine = None

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération du moteur de modèles.

        Args:
            *args: L'opération, puis ses arguments éventuels
            **kwargs: Options propres à l'opération

        Returns:
            Résultat de l'opération

        Raises:
            ValueError: Opération inconnue
        """
        if not args:
            raise ValueError("Une opération est requise (generate, status, catalogue, ...)")

        operation = str(args[0]).lower()
        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. "
                f"Opérations disponibles: {', '.join(self.available_operations())}"
            )

        return handler(*args[1:], **kwargs)

    def available_operations(self) -> List[str]:
        """Retourne la liste des opérations prises en charge."""
        return sorted(
            name[len("_op_"):] for name in dir(self)
            if name.startswith("_op_") and callable(getattr(self, name))
        )

    # ------------------------------------------------------------------
    # Opérations
    # ------------------------------------------------------------------
    def _op_generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Génère du texte.

        Args:
            prompt: Invite envoyée au modèle
            **kwargs: `task_type`, `complexity`, `max_tokens`, `temperature`,
                `model_name` pour imposer un modèle précis

        Returns:
            Dictionnaire portant le statut de la génération. Le texte n'est
            exploitable que si `status` vaut `ready`.
        """
        if not prompt or not str(prompt).strip():
            raise ValueError("L'invite ne peut pas être vide")

        engine = self._get_engine()

        model_item = self._resolve_model(engine, kwargs)
        if model_item is None:
            return {
                "status": "unavailable",
                "text": "",
                "detail": engine.unavailability_reason() or "Aucun modèle sélectionnable",
            }

        response = engine.generate(
            model_item,
            prompt,
            max_tokens=kwargs.get("max_tokens", self.default_max_tokens),
            temperature=kwargs.get("temperature", self.default_temperature),
            system_prompt=kwargs.get("system_prompt"),
        )
        return response.to_dict()

    def _op_status(self, **kwargs) -> Dict[str, Any]:
        """Retourne l'état de tous les fournisseurs."""
        engine = self._get_engine()
        return {
            "providers": engine.get_provider_status(),
            "any_available": engine.has_available_provider(),
            "detail": engine.unavailability_reason(),
        }

    def _op_available(self, **kwargs) -> bool:
        """Indique si une génération est possible."""
        return self._get_engine().has_available_provider()

    def _op_catalogue(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Retourne le catalogue des modèles connus.

        Args:
            **kwargs: `available_only` pour ne retenir que les modèles utilisables
        """
        return self._get_engine().list_catalogue(
            available_only=bool(kwargs.get("available_only", False))
        )

    def _op_select(self, **kwargs) -> Dict[str, Any]:
        """
        Sélectionne automatiquement le fournisseur adapté à une tâche.

        Args:
            **kwargs: Exigences de la tâche (`task_type`, `complexity`, ...)
        """
        return self._get_engine().select_provider_for_task(dict(kwargs))

    def _op_explain(self, **kwargs) -> Dict[str, Any]:
        """Détaille le raisonnement de sélection pour une tâche."""
        return self._get_engine().explain_selection(dict(kwargs))

    def _op_capabilities(self, model_name: str, **kwargs) -> Dict[str, Any]:
        """
        Retourne les capacités d'un modèle du catalogue.

        Args:
            model_name: Nom du modèle

        Raises:
            ValueError: Si le modèle est absent du catalogue
        """
        engine = self._get_engine()

        model_item = engine._model_registry.to_model_item(model_name)
        if model_item is None:
            raise ValueError(f"Modèle '{model_name}' absent du catalogue")

        return engine._cd.discover_capabilities(model_item)

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _get_engine(self):
        """
        Retourne le moteur de modèles partagé de la plateforme.

        L'outil passe par le registre commun plutôt que d'instancier son propre
        moteur : sans cela, les modèles enregistrés par un agent seraient
        invisibles depuis l'outil.
        """
        if self._engine is None:
            from src.integration.engine_registry import get_shared_registry
            self._engine = get_shared_registry().model
        return self._engine

    def _resolve_model(self, engine, options: Dict[str, Any]):
        """Détermine le modèle à utiliser, imposé ou sélectionné automatiquement."""
        model_name = options.get("model_name")
        if model_name:
            return engine._model_registry.to_model_item(model_name)

        requirements = {
            key: options[key]
            for key in ("task_type", "complexity", "requires_vision", "min_context_window")
            if key in options
        }
        return engine.select_model_for_task(requirements)
