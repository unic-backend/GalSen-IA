"""
Optimiseur de prompts pour le moteur de modèles GalSen IA.
"""

from typing import Dict, Any, Optional
from .types import ModelItem
from .interfaces import PromptOptimizer


class TemplateBasedPromptOptimizer(PromptOptimizer):
    """
    Optimiseur de prompts basé sur des modèles spécifiques à chaque type de modèle.
    """

    def __init__(self):
        """Initialise l'optimiseur de prompts."""
        # Modèles de prompt pour différents types de tâches et modèles
        self._templates = {
            # Modèles OpenAI GPT
            ("openai", "reasoning"): "You are an expert AI assistant. Please think step by step and provide a detailed, logical response to the following query:\n\n{query}",
            ("openai", "creative"): "You are a creative AI assistant. Generate imaginative and engaging content for the following prompt:\n\n{query}",
            ("openai", "concise"): "Provide a clear and concise answer to the following question. Be direct and to the point:\n\n{query}",
            ("openai", "factual"): "You are a knowledgeable AI assistant. Provide accurate, fact-based information in response to the following query:\n\n{query}",

            # Modèles Anthropic Claude
            ("anthropic", "reasoning"): "You are Claude, an AI assistant created by Anthropic. Your task is to engage in careful, reasoned thinking to address the following question:\n\n{query}",
            ("anthropic", "creative"): "You are Claude, a creative AI assistant. Use your imagination and creativity to respond to the following prompt:\n\n{query}",
            ("anthropic", "concise"): "As Claude, provide a brief and direct response to the following question:\n\n{query}",
            ("anthropic", "factual"): "You are Claude, a knowledgeable AI assistant. Provide accurate information in response to the following query:\n\n{query}",

            # Modèles Google Gemini
            ("google", "reasoning"): "You are Gemini, an AI model created by Google. Approach the following problem with systematic reasoning and provide a well-structured answer:\n\n{query}",
            ("google", "creative"): "You are Gemini, a creative AI model. Generate original and engaging content for the following prompt:\n\n{query}",
            ("google", "concise"): "As Gemini, provide a concise response to the following question:\n\n{query}",
            ("google", "factual"): "You are Gemini, a knowledgeable AI model. Provide factual information in response to the following query:\n\n{query}",

            # Modèles par défaut
            ("default", "reasoning"): "Think step by step and solve the following problem:\n\n{query}",
            ("default", "creative"): "Be creative and original in your response to:\n\n{query}",
            ("default", "concise"): "Provide a brief and direct answer to:\n\n{query}",
            ("default", "factual"): "Provide accurate information in response to:\n\n{query}"
        }

        # Modèles de rôle pour différents types de modèles
        self._role_templates = {
            "openai": {"system": "You are a helpful assistant."},
            "anthropic": {"system": "You are Claude, an AI assistant created by Anthropic."},
            "google": {"system": "You are Gemini, an AI model created by Google."},
            "default": {"system": "You are a helpful AI assistant."}
        }

    def _get_model_family(self, model_item: ModelItem) -> str:
        """Détermine la famille du modèle à partir de l'élément de modèle."""
        provider_lower = model_item.provider.lower()
        if "openai" in provider_lower or "gpt" in provider_lower:
            return "openai"
        elif "anthropic" in provider_lower or "claude" in provider_lower:
            return "anthropic"
        elif "google" in provider_lower or "gemini" in provider_lower:
            return "google"
        else:
            return "default"

    def _detect_task_type(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Détecte le type de tâche à partir du prompt et du contexte.

        Args:
            prompt: Prompt original
            context: Contexte additionnel

        Returns:
            Type de tâche détecté (reasoning, creative, concise, factual, etc.)
        """
        # Si le type de tâche est spécifié dans le contexte, l'utiliser
        if context and "task_type" in context:
            return context["task_type"]

        # Sinon, essayer de déduire à partir du prompt
        prompt_lower = prompt.lower()

        # Mots indiquant un besoin de raisonnement
        reasoning_indicators = ["explique", "résous", "analyse", "compare", "évalue", "raisonne", "logique", "étapes", " étape ", "par conséquent", "donc", "puisque"]
        if any(indicator in prompt_lower for indicator in reasoning_indicators):
            return "reasoning"

        # Mots indiquant un besoin de créativité
        creative_indicators = ["créatif", "imagine", "invente", "histoire", "poème", "scénario", "original", "nouveau", "inventif"]
        if any(indicator in prompt_lower for indicator in creative_indicators):
            return "creative"

        # Mots indiquant un besoin de concision
        concise_indicators = ["bref", "court", "résume", "résumé", "en bref", "en peu de mots", "concise", "concis"]
        if any(indicator in prompt_lower for indicator in concise_indicators):
            return "concise"

        # Mots indiquant un besoin d'information factuelle
        factual_indicators = ["quel est", "quelle est", "quelques faits", "information", "fait", "vérité", "exact", "précis", "date", "nombre", "combien"]
        if any(indicator in prompt_lower for indicator in factual_indicators):
            return "factual"

        # Par défaut, retourner "general"
        return "general"

    def optimize_prompt(self, model_item: ModelItem, prompt: str,
                       task_type: Optional[str] = None,
                       context: Optional[Dict[str, Any]] = None) -> str:
        """
        Optimise un prompt pour un modèle spécifique et un type de tâche.

        Args:
            model_item: Modèle pour lequel optimiser le prompt
            prompt: Prompt original
            task_type: Type de tâche (optionnel, sera détecté si non fourni)
            context: Contexte additionnel (optionnel)

        Returns:
            Prompt optimisé
        """
        # Déterminer le type de tâche si non fourni
        if task_type is None:
            task_type = self._detect_task_type(prompt, context)

        # Déterminer la famille du modèle
        model_family = self._get_model_family(model_item)

        # Essayer de trouver un template spécifique
        template_key = (model_family, task_type)
        if template_key in self._templates:
            template = self._templates[template_key]
        else:
            # Essayer avec le type de tâche générique et la famille par défaut
            fallback_key = ("default", task_type)
            if fallback_key in self._templates:
                template = self._templates[fallback_key]
            else:
                # Dernier recours: utiliser le template par défaut
                template = self._templates[("default", "general")]

        # Formater le template avec le prompt
        optimized_prompt = template.format(query=prompt)

        # Ajouter des informations de contexte si disponibles et utiles
        if context:
            # Ajouter des contraintes de longueur si spécifiées
            if "max_length" in context:
                optimized_prompt += f"\n\nVeuillez limiter votre réponse à {context['max_length']} mots maximum."

            # Ajouter le format de sortie souhaité si spécifié
            if "output_format" in context:
                optimized_prompt += f"\n\nVeuillez formater votre réponse comme suit: {context['output_format']}"

        return optimized_prompt

    def get_system_message(self, model_item: ModelItem) -> str:
        """
        Obtient le message système approprié pour un modèle.

        Args:
            model_item: Modèle pour lequel obtenir le message système

        Returns:
            Message système approprié
        """
        model_family = self._get_model_family(model_item)
        return self._role_templates.get(model_family, self._role_templates["default"])["system"]