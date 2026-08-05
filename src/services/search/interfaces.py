"""
Contrats du service de recherche unifiée.

Définit les interfaces abstraites `SearchProvider` (source individuelle)
et `SearchManager` (orchestrateur multi-source). Tout moteur de recherche
(knowledge, memory, document, vision) peut être branché en implémentant
`SearchProvider`.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import SearchQuery, SearchResultItem, SearchResponse, SearchSource


class SearchProvider(ABC):
    """
    Contrat pour une source de recherche individuelle.

    Chaque moteur (knowledge, memory, document, vision) implémente
    cette interface pour pouvoir être interrogé par le SearchManager.
    """

    @property
    @abstractmethod
    def source(self) -> SearchSource:
        """Retourne la source que ce fournisseur représente."""

    @abstractmethod
    def search(self, query: SearchQuery) -> List[SearchResultItem]:
        """
        Exécute une recherche sur cette source.

        Args:
            query: La requête de recherche avec filtres.

        Returns:
            Liste des résultats triés par pertinence.
        """


class SearchManager(ABC):
    """Contrat du gestionnaire de recherche unifiée."""

    @abstractmethod
    def register_provider(self, provider: SearchProvider) -> None:
        """Enregistre un fournisseur de recherche."""

    @abstractmethod
    def search(self, query: SearchQuery) -> SearchResponse:
        """
        Exécute une recherche sur toutes les sources disponibles.

        Les résultats sont fusionnés et triés par score de pertinence.

        Args:
            query: La requête de recherche avec filtres.

        Returns:
            Réponse complète avec résultats fusionnés.
        """

    @abstractmethod
    def search_single_source(
        self, source: SearchSource, query: SearchQuery
    ) -> List[SearchResultItem]:
        """
        Exécute une recherche sur une source spécifique.

        Args:
            source: La source ciblée.
            query: La requête de recherche.

        Returns:
            Liste des résultats de cette source.
        """