"""
Le contrat que tout fournisseur d'embeddings doit tenir (ADR-015).

Deux règles portent tout le reste :

1. **Un fournisseur indisponible le dit ; il ne rend jamais de vecteur.** Un
   vecteur inventé — nul, aléatoire, ou issu d'un repli lexical déguisé — se
   propage silencieusement : il produit des voisins plausibles, personne ne
   remarque rien, et la recherche ment. C'est le mode d'échec que
   `.claude/rules/verification.md` interdit nommément.
2. **Un vecteur porte l'espace dont il vient.** Le nom du modèle et la dimension
   voyagent avec lui, parce que comparer deux vecteurs de deux modèles rend un
   nombre parfaitement calculé et parfaitement dénué de sens.
"""

import abc
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence


class EmbeddingUnavailable(Enum):
    """Pourquoi un fournisseur ne peut pas travailler."""

    MISSING_DEPENDENCY = "missing_dependency"
    MODEL_NOT_LOADED = "model_not_loaded"
    DISABLED = "disabled"


@dataclass(frozen=True)
class EmbeddingProviderInfo:
    """
    État d'un fournisseur, et ce qu'il faut faire s'il ne répond pas.

    Attributes:
        provider_id: Identifiant stable du fournisseur.
        model_name: Modèle servi, tel qu'il sera inscrit avec chaque vecteur.
        dimension: Taille des vecteurs produits, 0 si le fournisseur est indisponible.
        available: True si le fournisseur peut encoder maintenant.
        reason: Motif d'indisponibilité, None s'il est disponible.
        detail: Ce que l'exploitant doit faire — un motif sans geste n'aide personne.
    """

    provider_id: str
    model_name: str
    dimension: int
    available: bool
    reason: Optional[EmbeddingUnavailable] = None
    detail: Optional[str] = None

    def to_dict(self) -> dict:
        """Sérialise l'état pour `/health` et les rapports de recherche."""
        donnees = {
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "dimension": self.dimension,
            "available": self.available,
        }
        if self.reason is not None:
            donnees["reason"] = self.reason.value
        if self.detail:
            donnees["detail"] = self.detail
        return donnees


class EmbeddingProvider(abc.ABC):
    """Fournisseur de représentations vectorielles."""

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Identifiant stable du fournisseur."""

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Modèle servi. Inscrit avec chaque vecteur, pour détecter un mélange d'espaces."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Taille des vecteurs produits."""

    @abc.abstractmethod
    def check_availability(self) -> EmbeddingProviderInfo:
        """Retourne l'état du fournisseur, sans lever."""

    @abc.abstractmethod
    def embed(self, textes: Sequence[str]) -> List[List[float]]:
        """
        Encode des textes en vecteurs **normalisés**.

        La normalisation est faite ici, une fois : elle rend le produit scalaire
        égal au cosinus, ce qui permet au magasin de chercher sans rien
        renormaliser à chaque requête.

        Args:
            textes: Textes à encoder.

        Returns:
            Un vecteur par texte, dans le même ordre.

        Raises:
            RuntimeError: Si le fournisseur est indisponible. Lever est correct
                ici : l'appelant a demandé un encodage, et rendre un vecteur
                faute de mieux serait exactement ce qu'il ne faut jamais faire.
        """

    def is_available(self) -> bool:
        """Indique si le fournisseur peut encoder maintenant."""
        return self.check_availability().available
