"""
Moteur de connaissances : ce que la plateforme sait, et d'où elle le tient.

Responsabilités
    Organiser, valider, retrouver et gouverner les connaissances. Chaque élément
    porte son domaine, sa sensibilité, son statut dans le cycle de vie et la
    fiabilité de sa source (P1-P4). État complet et mesuré →
    `docs/architecture/knowledge.md`.

Interfaces publiques
    `KnowledgeManagerImpl` est le point d'entrée ; `interfaces.py` définit les
    contrats des composants remplaçables (store, indexer, retriever, validator,
    ranker, graph, cache). `knowledge_lifecycle.py` porte les transitions
    permises, `knowledge_security.py` la lecture par rôle,
    `knowledge_governance.py` et `knowledge_quality.py` les rapports.

Dépendances
    `src/storage/` pour la persistance SQLite (ADR-005). Aucune dépendance
    externe obligatoire.

Configuration
    `GALSEN_STORAGE_BACKEND`, `GALSEN_DATA_DIR`, `GALSEN_KNOWLEDGE_OWNERS`,
    `GALSEN_KNOWLEDGE_REVALIDATION_DAYS`.

Limites connues
    La base est vide : tous les rapports décrivent 0 élément. La recherche est
    lexicale — pas de recherche sémantique, pas d'analyse d'intention — et le
    score de pertinence est un recouvrement de termes. Une version de
    connaissance porte un numéro, pas un historique.
"""

from .types import (
    KnowledgeItem, KnowledgeSource, KnowledgeType, ContentType, Language,
    ConfidenceLevel, SourceCategory, KnowledgePriority, KnowledgeDomain,
    KnowledgeSensitivity, KnowledgeStatus
)
from .interfaces import (
    KnowledgeStore, KnowledgeLoader, KnowledgeIndexer, KnowledgeRetriever,
    KnowledgeValidator, KnowledgeGraph, KnowledgeCache, KnowledgeRanker,
    KnowledgeManager
)
from .knowledge_manager import KnowledgeManagerImpl

__all__ = [
    # Types
    "KnowledgeItem",
    "KnowledgeSource",
    "KnowledgeType",
    "ContentType",
    "Language",
    "ConfidenceLevel",
    "SourceCategory",
    "KnowledgePriority",
    "KnowledgeDomain",
    "KnowledgeSensitivity",
    "KnowledgeStatus",
    # Interfaces
    "KnowledgeStore",
    "KnowledgeLoader",
    "KnowledgeIndexer",
    "KnowledgeRetriever",
    "KnowledgeValidator",
    "KnowledgeGraph",
    "KnowledgeCache",
    "KnowledgeRanker",
    "KnowledgeManager",
    # Implémentations principales
    "KnowledgeManagerImpl"
]