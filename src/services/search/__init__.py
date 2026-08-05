"""
Service de recherche unifiée.

Permet d'interroger plusieurs moteurs (knowledge, memory, document, vision)
avec une seule requête et d'obtenir des résultats fusionnés et triés par
pertinence.

Référence : VOLET 02, Chapitres 03 (Backend), 07 (Data).
"""

from .interfaces import SearchManager, SearchProvider
from .manager import SearchManagerImpl
from .types import (
    SearchQuery,
    SearchResponse,
    SearchResultItem,
    SearchSort,
    SearchSource,
    generate_search_id,
)

__all__ = [
    "SearchManager",
    "SearchManagerImpl",
    "SearchProvider",
    "SearchQuery",
    "SearchResponse",
    "SearchResultItem",
    "SearchSort",
    "SearchSource",
    "generate_search_id",
]