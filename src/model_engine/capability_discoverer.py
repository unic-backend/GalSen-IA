"""
Découvreur de capacités pour le moteur de modèles GalSen IA.
"""

from typing import Dict, Any
from .types import ModelItem
from .interfaces import CapabilityDiscoverer


class StaticCapabilityDiscoverer(CapabilityDiscoverer):
    """
    Découvreur de capacités statique qui retourne des capacités prédéfinies
    basé sur le type de modèle et le fournisseur.
    """

    def __init__(self):
        """Initialise le découvreur de capacités."""
        # Base de connaissances des capacités des modèles
        # Dans une implémentation réelle, ceci pourrait venir d'un fichier de configuration
        # ou être découvert dynamiquement via des appels API
        self._capabilities_db = {
            # OpenAI GPT-4
            ("openai", "gpt-4"): {
                "context_window": 8192,
                "max_output_tokens": 4096,
                "supports_streaming": True,
                "supports_function_calling": True,
                "supports_vision": False,  # GPT-4 Vision serait différent
                "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"],
                "training_data_cutoff": "2023-09",
                "pricing_per_1k_tokens": {"input": 0.03, "output": 0.06},
                "special_features": ["reasoning", "creative_writing", "code_generation"]
            },
            # OpenAI GPT-3.5 Turbo
            ("openai", "gpt-3.5-turbo"): {
                "context_window": 4096,
                "max_output_tokens": 4096,
                "supports_streaming": True,
                "supports_function_calling": True,
                "supports_vision": False,
                "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"],
                "training_data_cutoff": "2021-09",
                "pricing_per_1k_tokens": {"input": 0.0015, "output": 0.002},
                "special_features": ["general_conversation", "basic_reasoning"]
            },
            # Anthropic Claude 3 Opus
            ("anthropic", "claude-3-opus"): {
                "context_window": 200000,
                "max_output_tokens": 4096,
                "supports_streaming": True,
                "supports_function_calling": False,  # À vérifier selon l'API
                "supports_vision": True,
                "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"],
                "training_data_cutoff": "2024-01",
                "pricing_per_1k_tokens": {"input": 0.015, "output": 0.075},
                "special_features": ["reasoning", "analysis", "creative_writing", "vision"]
            },
            # Anthropic Claude 3 Sonnet
            ("anthropic", "claude-3-sonnet"): {
                "context_window": 200000,
                "max_output_tokens": 4096,
                "supports_streaming": True,
                "supports_function_calling": False,
                "supports_vision": True,
                "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"],
                "training_data_cutoff": "2024-01",
                "pricing_per_1k_tokens": {"input": 0.003, "output": 0.015},
                "special_features": ["reasoning", "analysis", "basic_visual"]
            },
            # Anthropic Claude 3 Haiku
            ("anthropic", "claude-3-haiku"): {
                "context_window": 200000,
                "max_output_tokens": 4096,
                "supports_streaming": True,
                "supports_function_calling": False,
                "supports_vision": True,
                "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"],
                "training_data_cutoff": "2024-01",
                "pricing_per_1k_tokens": {"input": 0.00025, "output": 0.00125},
                "special_features": ["fast_response", "basic_reasoning"]
            },
            # Google Gemini Pro
            ("google", "gemini-pro"): {
                "context_window": 32768,
                "max_output_tokens": 8192,
                "supports_streaming": True,
                "supports_function_calling": True,
                "supports_vision": True,  # Gemini Pro Vision serait différent
                "supported_languages": ["en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh", "ar", "hi", "th", "vi"],
                "training_data_cutoff": "2024-01",
                "pricing_per_1k_tokens": {"input": 0.00025, "output": 0.0005},
                "special_features": ["reasoning", "multimodal", "code_generation"]
            },
            # Valeurs par défaut pour les modèles inconnus
            "default": {
                "context_window": 2048,
                "max_output_tokens": 512,
                "supports_streaming": False,
                "supports_function_calling": False,
                "supports_vision": False,
                "supported_languages": ["en"],
                "training_data_cutoff": "unknown",
                "pricing_per_1k_tokens": {"input": 0.0, "output": 0.0},
                "special_features": ["basic"]
            }
        }

    def _get_model_key(self, model_item: ModelItem) -> tuple:
        """
        Obtient la clé pour rechercher les capacités d'un modèle.

        Args:
            model_item: Modèle pour lequel obtenir la clé

        Returns:
            Tuple (fournisseur, nom_modèle) pour la recherche
        """
        provider = model_item.provider.lower()
        # Essayer d'utiliser le nom du modèle si disponible, sinon revenir au type
        model_name = model_item.name.lower() if model_item.name else model_item.model_type.value
        return (provider, model_name)

    def discover_capabilities(self, model_item: ModelItem) -> Dict[str, Any]:
        """
        Découvre les capacités d'un modèle.

        Args:
            model_item: Modèle pour lequel découvrir les capacités

        Returns:
            Dictionnaire des capacités du modèle
        """
        model_key = self._get_model_key(model_item)

        # Chercher dans la base de connaissances
        if model_key in self._capabilities_db:
            capabilities = self._capabilities_db[model_key].copy()
        else:
            # Essayer une recherche moins spécifique (juste par fournisseur et type)
            provider_key = (model_item.provider.lower(), model_item.model_type.value)
            if provider_key in self._capabilities_db:
                capabilities = self._capabilities_db[provider_key].copy()
            else:
                # Utiliser les capacités par défaut
                capabilities = self._capabilities_db["default"].copy()

        # Mettre à jour avec toute capacité spécifiée dans les métadonnées du modèle
        if "capabilities" in model_item.metadata:
            capabilities.update(model_item.metadata["capabilities"])

        # S'assurer que les champs critiques sont présents
        capabilities.setdefault("context_window", model_item.context_window)
        capabilities.setdefault("max_output_tokens", model_item.max_output_tokens)
        capabilities.setdefault("supported_features", model_item.metadata.get("supported_features", []))

        return capabilities

    def get_capabilities(self, model_item: ModelItem) -> Dict[str, Any]:
        """
        Récupère les capacités découvertes d'un modèle.
        Dans cette implémentation simple, c'est identique à discover_capabilities
        puisque nous ne mettons pas en cache les résultats.

        Args:
            model_item: Modèle pour lequel obtenir les capacités

        Returns:
            Dictionnaire des capacités du modèle
        """
        return self.discover_capabilities(model_item)

    def update_known_capabilities(self, model_key: tuple,
                                 capabilities: Dict[str, Any]) -> None:
        """
        Met à jour les capacités connues pour un modèle donné.
        Utile pour l'apprentissage ou la mise à jour dynamique.

        Args:
            model_key: Tuple (fournisseur, nom_modèle)
            capabilities: Dictionnaire des capacités à mettre à jour
        """
        self._capabilities_db[model_key] = capabilities

    def list_known_models(self) -> list:
        """
        Liste tous les modèles pour lesquels nous avons des connaissances de capacités.

        Returns:
            Liste des tuples (fournisseur, nom_modèle)
        """
        return [key for key in self._capabilities_db.keys() if key != "default"]