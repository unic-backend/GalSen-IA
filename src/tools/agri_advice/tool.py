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
from typing import Any, Dict

from src.model_engine.model_manager import ModelManagerImpl
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
        self.model_manager = ModelManagerImpl()
        self.default_language = self.config.get('language', 'fr') if self.config else 'fr'
        self.model_id = self.config.get('model_id') if self.config else None
        logger.debug("AgriAdviceTool initialisé.")

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
                - "answer": str, conseil généré
                - "language": str, langue utilisée pour la réponse
                - "model_used": str, ID du modèle utilisé
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

        try:
            # Utiliser le gestionnaire de modèles pour générer le texte
            answer = self.model_manager.generate_text_with_fallback(
                prompt=prompt,
                task_requirements={"domain": "agriculture", "region": "Senegal", "language": language},
                model_id=model_id,
                **gen_params
            )

            result = {
                "answer": answer.strip(),
                "language": language,
                "model_used": model_id or self.model_manager.get_default_model_name()
            }
            logger.debug(f"Conseil agricole généré pour question : {question[:50]}...")
            return result
        except Exception as e:
            logger.error(f"Erreur lors de la génération du conseil agricole : {e}")
            raise RuntimeError(f"Échec de génération du conseil : {e}")

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