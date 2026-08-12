"""
Fournisseur d'embeddings local, en processus (ADR-015).

Le modèle tourne **sur cette machine**, sans clé et sans réseau au moment
d'encoder. Ce n'est pas une préférence : une API d'embeddings hébergée enverrait
chez un tiers *chaque mémoire stockée et chaque document indexé* — un export plus
large et plus continu que d'envoyer une invite. ADR-014 l'exclut pour la
génération ; ADR-015 l'exclut a fortiori ici.

`sentence-transformers` n'est pas dans `requirements.txt` parce qu'il tire
**PyTorch** : de ~200 Mo (roue CPU) à ~2,5 Go (CUDA). L'exploitant qui veut la
recherche sémantique installe `requirements-embeddings.txt` sciemment, et l'image
de production reste ce que la v0.1.0 a livré.

**Non vérifié dans l'environnement de développement** : l'encodage réel.
`huggingface.co` répond 403 à travers le mandataire, donc les poids ne peuvent
pas être récupérés ici. Ce qui est vérifié, c'est que l'absence de la
bibliothèque est **rapportée** et non contournée — et c'est justement le
comportement qui compte tant que personne n'a installé le paquet.
"""

import logging
import os
from typing import List, Optional, Sequence

from .interfaces import EmbeddingProvider, EmbeddingProviderInfo, EmbeddingUnavailable

logger = logging.getLogger(__name__)

MODEL_VARIABLE = "GALSEN_EMBEDDING_MODEL"

# Multilingue et léger : il couvre le français, et sa taille le rend utilisable
# sur les machines que ce projet vise réellement.
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Dimension du modèle par défaut. Annoncée avant chargement pour que
# `check_availability()` puisse répondre sans télécharger 90 Mo ; corrigée par la
# valeur réelle du modèle dès qu'il est chargé.
DEFAULT_DIMENSION = 384


class SentenceTransformersEmbedder(EmbeddingProvider):
    """Encodeur local reposant sur `sentence-transformers`."""

    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        """
        Prépare le fournisseur sans rien charger.

        Args:
            model_name: Modèle à servir ; `GALSEN_EMBEDDING_MODEL` sinon.
            device: Appareil de calcul ; laissé au choix de la bibliothèque sinon.
        """
        self._model_name = model_name or os.getenv(MODEL_VARIABLE, "").strip() or DEFAULT_MODEL
        self._device = device
        self._model = None
        self._dimension = DEFAULT_DIMENSION

    @property
    def provider_id(self) -> str:
        """Identifiant stable du fournisseur."""
        return "sentence_transformers"

    @property
    def model_name(self) -> str:
        """Modèle servi."""
        return self._model_name

    @property
    def dimension(self) -> int:
        """Taille des vecteurs ; valeur réelle du modèle une fois chargé."""
        return self._dimension

    def _charger(self):
        """
        Charge le modèle au premier usage.

        Le chargement est paresseux : construire le fournisseur ne doit rien
        coûter, sinon le registre ne pourrait pas l'interroger au démarrage.
        """
        if self._model is not None:
            return self._model

        from sentence_transformers import SentenceTransformer  # import tardif volontaire

        self._model = SentenceTransformer(self._model_name, device=self._device)
        dimension = self._model.get_sentence_embedding_dimension()
        if dimension:
            # La dimension annoncée avant chargement n'était qu'une supposition
            # raisonnable ; celle du modèle fait foi.
            self._dimension = int(dimension)
        logger.info(
            "Modèle d'embeddings chargé : %s (dimension %d)", self._model_name, self._dimension
        )
        return self._model

    def check_availability(self) -> EmbeddingProviderInfo:
        """Retourne l'état du fournisseur, sans jamais lever ni télécharger."""
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            return EmbeddingProviderInfo(
                provider_id=self.provider_id,
                model_name=self._model_name,
                dimension=0,
                available=False,
                reason=EmbeddingUnavailable.MISSING_DEPENDENCY,
                detail=(
                    "'sentence-transformers' n'est pas installé. "
                    "pip install -r requirements-embeddings.txt pour activer la "
                    "recherche sémantique (ADR-015). La recherche lexicale "
                    "continue de fonctionner d'ici là."
                ),
            )

        return EmbeddingProviderInfo(
            provider_id=self.provider_id,
            model_name=self._model_name,
            dimension=self._dimension,
            available=True,
        )

    def embed(self, textes: Sequence[str]) -> List[List[float]]:
        """
        Encode des textes en vecteurs normalisés.

        Args:
            textes: Textes à encoder.

        Returns:
            Un vecteur par texte, dans le même ordre.

        Raises:
            RuntimeError: Si la bibliothèque manque ou si le modèle ne charge pas.
        """
        if not textes:
            return []

        try:
            modele = self._charger()
        except ImportError as erreur:
            raise RuntimeError(
                "Encodage impossible : 'sentence-transformers' n'est pas installé "
                "(ADR-015)."
            ) from erreur
        except Exception as erreur:
            raise RuntimeError(
                f"Encodage impossible : le modèle « {self._model_name} » n'a pas "
                f"pu être chargé ({erreur})."
            ) from erreur

        vecteurs = modele.encode(
            list(textes),
            # La normalisation est faite ici, une fois, pour que le magasin
            # puisse chercher par produit scalaire sans renormaliser.
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return [[float(valeur) for valeur in vecteur] for vecteur in vecteurs]
