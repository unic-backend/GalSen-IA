"""
Gestionnaire du service de recherche unifiée.

Fournit `SearchManagerImpl`, une façade qui orchestre la recherche
sur les moteurs enregistrés (knowledge, memory, document, vision).
Les résultats sont fusionnés et triés par pertinence.
"""

import logging
import time
from typing import Dict, List, Optional

from .interfaces import SearchManager, SearchProvider
from .types import (
    SearchQuery,
    SearchResponse,
    SearchResultItem,
    SearchSort,
    SearchSource,
)

logger = logging.getLogger(__name__)


class SearchManagerImpl(SearchManager):
    """
    Façade du service de recherche unifiée.

    Orchestre la recherche sur les sources enregistrées et fusionne
    les résultats par score de pertinence décroissant.
    """

    def __init__(self) -> None:
        self._providers: Dict[SearchSource, SearchProvider] = {}
        self._logger = logging.getLogger(f"{__name__}.SearchManagerImpl")

    def register_provider(self, provider: SearchProvider) -> None:
        """Enregistre un fournisseur de recherche."""
        try:
            self._providers[provider.source] = provider
            self._logger.info(
                "Fournisseur de recherche enregistré : %s", provider.source.value
            )
        except Exception as error:
            self._logger.warning(
                "Échec de l'enregistrement du fournisseur : %s", error
            )

    def registered_sources(self) -> List[SearchSource]:
        """Retourne les sources réellement branchées, dans l'ordre d'enregistrement."""
        return list(self._providers)

    def _get_score_weight(self, source: SearchSource) -> float:
        """Retourne le poids de score pour une source donnée."""
        weights = {
            SearchSource.KNOWLEDGE: 1.0,
            SearchSource.MEMORY: 0.9,
            SearchSource.DOCUMENT: 0.85,
            SearchSource.VISION: 0.8,
        }
        return weights.get(source, 0.8)

    def _sort_results(
        self, results: List[SearchResultItem], sort: SearchSort
    ) -> List[SearchResultItem]:
        """Trie les résultats selon le mode spécifié."""
        if sort == SearchSort.RELEVANCE:
            return sorted(results, key=lambda r: r.score, reverse=True)
        elif sort == SearchSort.DATE_DESC:
            return sorted(
                results,
                key=lambda r: r.created_at or 0,
                reverse=True,
            )
        elif sort == SearchSort.DATE_ASC:
            return sorted(
                results,
                key=lambda r: r.created_at or 0,
            )
        return results

    def _merge_results(
        self,
        all_results: List[SearchResultItem],
        query: SearchQuery,
    ) -> List[SearchResultItem]:
        """Fusionne et normalise les résultats multi-sources."""
        if not all_results:
            return []

        # Normaliser les scores par source (chaque source a son propre référentiel)
        # On applique un poids pour équilibrer les sources entre elles
        for item in all_results:
            weight = self._get_score_weight(item.source)
            item.score = item.score * weight

        # Trier
        sorted_results = self._sort_results(all_results, query.sort)

        # Filtrer par score minimum si demandé
        if query.min_score is not None:
            sorted_results = [
                r for r in sorted_results if r.score >= query.min_score
            ]

        return sorted_results

    def _build_provider_query(self, query: SearchQuery, source: SearchSource) -> SearchQuery:
        """Construit une requête adaptée à une source spécifique."""
        return SearchQuery(
            query=query.query,
            sources=[source],
            limit=query.limit * 2,  # Demander plus pour avoir une bonne fusion
            offset=0,
            sort=SearchSort.RELEVANCE,
            min_score=None,
            filters=query.filters,
            # Le rôle doit survivre à la reconstruction : l'oublier ici rendrait
            # toute recherche anonyme aux yeux des fournisseurs.
            role=query.role,
        )

    def search(self, query: SearchQuery) -> SearchResponse:
        """Exécute une recherche sur toutes les sources disponibles."""
        start_time = time.time()
        all_results: List[SearchResultItem] = []
        sources_used: List[str] = []

        # Déterminer les sources à interroger
        target_sources = query.sources or list(SearchSource)

        for source in target_sources:
            provider = self._providers.get(source)
            if provider is None:
                continue
            try:
                provider_query = self._build_provider_query(query, source)
                results = provider.search(provider_query)
                all_results.extend(results)
                sources_used.append(source.value)
            except Exception as error:
                self._logger.warning(
                    "Échec de la recherche sur la source %s : %s",
                    source.value,
                    error,
                )

        # Fusionner et trier
        merged = self._merge_results(all_results, query)

        # Paginer
        total = len(merged)
        paginated = merged[query.offset:query.offset + query.limit]

        execution_time = (time.time() - start_time) * 1000

        return SearchResponse(
            results=paginated,
            total=total,
            query=query.query,
            execution_time_ms=execution_time,
            sources_used=sources_used,
        )

    def search_single_source(
        self,
        source: SearchSource,
        query: SearchQuery,
    ) -> List[SearchResultItem]:
        """Exécute une recherche sur une source spécifique."""
        provider = self._providers.get(source)
        if provider is None:
            self._logger.warning("Aucun fournisseur pour la source : %s", source.value)
            return []
        try:
            return provider.search(query)
        except Exception as error:
            self._logger.warning(
                "Échec de la recherche sur la source %s : %s",
                source.value,
                error,
            )
            return []