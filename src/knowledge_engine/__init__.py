"""
Package du moteur de connaissances GalSen IA.
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