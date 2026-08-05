"""
Outil d'embeddings pour GalSen IA.

Fournit une interface pour générer des embeddings vectoriels à partir de texte
en utilisant des modèles de transformation de phrases (sentence-transformers).

Opérations disponibles : `embed` (générer des embeddings pour un ou plusieurs textes).

Exemple:
    tool.execute("embed", ["Bonjour le monde", "Comment allez-vous ?"])
    tool.execute("embed", "Bonjour le monde")
"""

import logging
from typing import Any, Dict, List, Optional, Union

from src.tool.base import BaseTool

logger = logging.getLogger(__name__)


class EmbeddingsTool(BaseTool):
    """
    Outil d'accès aux modèles d'embeddings pour GalSen IA.

    Opérations disponibles : `embed` (générer des embeddings pour un ou plusieurs textes).

    Exemple:
        tool.execute("embed", ["Bonjour le monde", "Comment allez-vous ?"])
        tool.execute("embed", "Bonjour le monde")
    """

    def __init__(self, config: dict = None):
        """
        Initialise l'outil d'embeddings.

        Args:
            config: Configuration avec les clés optionnelles :
                - `model_name`: nom du modèle sentence-transformers à utiliser
                               (par défaut : 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
                - `device`: appareil sur lequel charger le modèle (par défaut : None, choisit automatiquement)
                - `normalize_embeddings`: normaliser les embeddings à norme unitaire (par défaut : True)
        """
        super().__init__(config)
        self.model_name = self.config.get(
            "model_name",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        self.device = self.config.get("device", None)
        self.normalize_embeddings = self.config.get(
            "normalize_embeddings", True
        )
        self._model: Optional[object] = None  # We'll keep the type as object to avoid import
        logger.debug(
            f"EmbeddingsTool initialisé avec modèle {self.model_name}"
        )

    def _get_model(self):
        """
        Charge et retourne le modèle sentence-transformers (chargement paresseux).
        """
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:  # pragma: no cover
                logger.error(
                    "La bibliothèque 'sentence-transformers' n'est pas installée. "
                    "Veuillez l'installer pour utiliser l'outil d'embeddings."
                )
                raise e
            try:
                self._model = SentenceTransformer(
                    self.model_name, device=self.device
                )
                logger.info(
                    f"Modèle d'embeddings chargé : {self.model_name}"
                )
            except Exception as e:  # pragma: no cover
                logger.error(
                    f"Échec du chargement du modèle d'embeddings {self.model_name}: {e}"
                )
                raise
        return self._model

    def _op_embed(
        self, texts: Union[str, List[str]], **kwargs
    ) -> List[List[float]]:
        """
        Génère des embeddings pour un ou plusieurs textes.

        Args:
            texts: Une chaîne de caractères ou une liste de chaînes à embedder.
            **kwargs: Options supplémentaires (actuellement non utilisées).

        Returns:
            Liste d'embeddings (chaque embedding est une liste de floats).
            Si l'entrée est une seule chaîne, retourne une liste contenant un embedding.
        """
        if isinstance(texts, str):
            texts = [texts]
        elif not isinstance(texts, list):
            raise TypeError(
                "L'entrée doit être une chaîne ou une liste de chaînes"
            )

        if not texts:
            return []

        model = self._get_model()
        try:
            # Générer les embeddings
            embeddings = model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=self.normalize_embeddings,
            )
            # Convertir en liste de listes de floats
            return embeddings.tolist()
        except Exception as e:  # pragma: no cover
            logger.error(f"Erreur lors de la génération d'embeddings: {e}")
            raise

    def available_operations(self) -> List[str]:
        """Retourne la liste des opérations prises en charge."""
        return ["embed"]

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur l'outil d'embeddings.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération.

        Raises:
            ValueError: Opération inconnue.
        """
        if not args:
            raise ValueError(
                "Une opération est requise (embed)"
            )

        operation = str(args[0]).lower()
        operation_args = args[1:]

        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. "
                f"Opérations disponibles: {', '.join(self.available_operations())}"
            )

        return handler(*operation_args, **kwargs)