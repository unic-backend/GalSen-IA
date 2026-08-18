"""
Embeddings de GalSen IA (ADR-015).

Toute la récupération de la plateforme est lexicale : `MemoryRetriever` note par
similarité de Jaccard sur des ensembles de jetons, les fournisseurs de recherche
par proportion de termes retrouvés. « Comment soigner le mil malade ? » et
« traitement des maladies du sorgho » n'ont presque aucun jeton commun et sont
la même question.

Ce paquet apporte la représentation vectorielle qui lève ce plafond, sous la même
forme que les modèles (ADR-003) : une **interface**, des fournisseurs, un
registre. Le moteur n'importe jamais une bibliothèque de modèles directement — il
demande un fournisseur au registre, et reçoit `None` quand il n'y en a pas.

C'est ce qui permet à la plateforme de tourner **sans** `sentence-transformers`,
et de gagner la recherche sémantique en installant un paquet, sans changer un
seul appelant.
"""

from .interfaces import (
    EmbeddingProvider,
    EmbeddingProviderInfo,
    EmbeddingUnavailable,
)
from .registry import (
    EMBEDDING_MODEL_VARIABLE,
    active_embedder,
    embedding_status,
    reset_embedder,
    set_embedder,
)
from .vector_store import SQLiteVectorStore, Vector, VectorMatch

__all__ = [
    "EMBEDDING_MODEL_VARIABLE",
    "EmbeddingProvider",
    "EmbeddingProviderInfo",
    "EmbeddingUnavailable",
    "SQLiteVectorStore",
    "Vector",
    "VectorMatch",
    "active_embedder",
    "embedding_status",
    "reset_embedder",
    "set_embedder",
]
