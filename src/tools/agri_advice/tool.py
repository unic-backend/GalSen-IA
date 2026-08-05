"""
Outil de conseil agricole pour GalSen IA.

Fournit une interface pour obtenir des conseils agricoles adaptés aux contextes sénégalais,
en français ou en wolof, en utilisant les modèles de langage disponibles.

Opérations disponibles : `get_advice` (obtenir un conseil agricole basé sur une question).

Exemple:
    tool.execute("get_advice", "Quand faut-il planter le mil dans la région de Thiès ?")
    tool.execute("get_advice", "Quelles sont les maladies courantes du riz ?", language="wo")
"""

import logging
from typing import Any, Dict, Optional

from src.tool.base import BaseTool

logger = logging.getLogger(__name__)

class AgriAdviceTool(BaseTool):
    """
    Outil de conseil agricole pour GalSen IA.

    Opérations disponibles : `get_advice` (obtenir un conseil agricole basé sur une question).

    Exemple:
        tool.execute("get_advice", "Quand faut-il planter le mil dans la région de Thiès ?")
        tool.execute("get_advice", "Quelles sont les maladies courantes du riz ?", language="wo")
    """

    def __init__(self, config: dict = None):
        """
        Initialise l'outil de conseil agricole.

        Args:
            config: Configuration avec les clés optionnelles :
                    - model_id: ID du modèle à utiliser (optionnel, sinon sélection automatique)
                    - language: langue de réponse par défaut ('fr' ou 'wo', défaut 'fr')
        """
        super().__init__(config)
        self.default_language = self.config.get('language', 'fr') if self.config else 'fr'
        self.model_id = self.config.get('model_id') if self.config else None
        self._model_manager = None
        logger.debug("AgriAdviceTool initialisé.")

    @property
    def model_manager(self):
        """
        Retourne le gestionnaire de modèles partagé de la plateforme.

        L'outil passe par le registre commun plutôt que d'instancier son propre
        gestionnaire : sans cela, les modèles enregistrés par un agent seraient
        invisibles depuis l'outil.
        """
        if self._model_manager is None:
            from src.integration.engine_registry import get_shared_registry
            self._model_manager = get_shared_registry().model
        return self._model_manager

    def _op_get_advice(
        self, question: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Génère un conseil agricole basé sur la question posée.

        Args:
            question: Question agricole en français ou en wolof.
            **kwargs: Options supplémentaires :
                - language: langue de réponse ('fr' ou 'wo', overridable)
                - model_id: modèle spécifique à utiliser (overrides config)
                - max_tokens: nombre maximum de tokens à générer (optionnel)
                - temperature: température de génération (optionnel)

        Returns:
            Dictionnaire contenant :
                - "status": str, `ready` si le conseil est exploitable
                - "answer": str, conseil généré (vide si aucun modèle n'a répondu)
                - "language": str, langue utilisée pour la réponse
                - "model_used": str ou None, nom du modèle utilisé
                - "detail": str, présent seulement quand aucun conseil n'a pu être produit

        Raises:
            ValueError: Si la question est vide
        """
        if not isinstance(question, str) or not question.strip():
            raise ValueError("La question doit être une chaîne non vide")

        language = kwargs.get('language', self.default_language)
        model_id = kwargs.get('model_id', self.model_id)
        max_tokens = kwargs.get('max_tokens')
        temperature = kwargs.get('temperature')

        # Construire un prompt adapté au contexte agricole sénégalais
        lang_instruction = {
            'fr': 'Réponds en français.',
            'wo': 'Zëgg Wolof.'  # Wolof for "Answer in Wolof"
        }.get(language, 'Réponds en français.')

        prompt = f"""Tu es un expert agricole spécialisé dans les contextes sénégalais.
{lang_instruction}
Question : {question}
Conseil :"""

        # Préparer les paramètres de génération
        gen_params = {}
        if max_tokens is not None:
            gen_params["max_tokens"] = max_tokens
        if temperature is not None:
            gen_params["temperature"] = temperature

        manager = self.model_manager
        model_item = self._resolve_model(manager, model_id, language)
        if model_item is None:
            # Aucun modèle disponible n'est une information, pas une panne :
            # l'agent appelant doit pouvoir le constater et se rabattre ailleurs.
            return {
                "status": "unavailable",
                "answer": "",
                "language": language,
                "model_used": None,
                "detail": manager.unavailability_reason() or "Aucun modèle sélectionnable",
            }

        # `generate` est l'API synchrone du moteur : elle porte un statut, là où
        # `generate_text_with_fallback` est une coroutine qu'un outil ne peut pas attendre.
        response = manager.generate(model_item, prompt, **gen_params)
        result = response.to_dict()

        logger.debug(f"Conseil agricole généré pour question : {question[:50]}...")
        return {
            "status": result.get("status"),
            "answer": (result.get("text") or "").strip(),
            "language": language,
            "model_used": model_item.name,
            **({"detail": result["detail"]} if result.get("detail") else {}),
        }

    def _resolve_model(self, manager, model_id: Optional[str], language: str):
        """
        Détermine le modèle à utiliser : celui imposé, sinon la sélection automatique.

        Args:
            manager: Gestionnaire de modèles de la plateforme
            model_id: Nom du modèle imposé, ou None
            language: Langue de réponse attendue

        Returns:
            Le modèle retenu, ou None si aucun n'est disponible
        """
        if model_id:
            return manager.get_model(model_id) or manager._model_registry.to_model_item(model_id)

        return manager.select_model_for_task({
            "domain": "agriculture",
            "region": "Senegal",
            "language": language,
        })

    def available_operations(self) -> list[str]:
        """Retourne la liste des opérations prises en charge."""
        return ["get_advice"]

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur l'outil de conseil agricole.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération.

        Raises:
            ValueError: Opération inconnue.
        """
        if not args:
            raise ValueError("Une opération est requise (get_advice)")

        operation = str(args[0]).lower()
        operation_args = args[1:]

        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. "
                f"Opérations disponibles: {', '.join(self.available_operations())}"
            )

        return handler(*operation_args, **kwargs)