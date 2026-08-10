"""
Fournisseurs de recherche (VOLET 14, chapitre 04 — enregistrement des sources).

Le service de recherche unifiée fusionne les résultats de fournisseurs
enregistrés. Le dépôt n'en contenait aucun : `POST /search` ne pouvait donc rien
trouver. Ce module apporte le premier, sur la seule source réellement indexée —
la base de connaissances.

Un fournisseur ne ré-implémente pas la recherche : il adapte le moteur qu'il
enveloppe au contrat du service. Toute règle de lecture reste celle du moteur,
contrôle d'accès compris.
"""

import logging
from typing import Any, List, Optional

from .interfaces import SearchProvider
from .types import SearchQuery, SearchResultItem, SearchSource

logger = logging.getLogger(__name__)


class KnowledgeSearchProvider(SearchProvider):
    """
    Expose le moteur de connaissances au service de recherche unifiée.

    Le rôle porté par la requête est transmis au moteur : une recherche ne donne
    pas plus de droits qu'une lecture directe, et sans rôle seule la
    connaissance publique remonte.
    """

    source = SearchSource.KNOWLEDGE

    def __init__(self, knowledge_manager: Any):
        """
        Args:
            knowledge_manager: le gestionnaire de connaissances à exposer
        """
        self._knowledge_manager = knowledge_manager
        self._logger = logging.getLogger(f"{__name__}.KnowledgeSearchProvider")

    def _to_timestamp(self, valeur) -> Optional[float]:
        """Convertit une date en horodatage, ou None si elle est absente."""
        return valeur.timestamp() if valeur is not None else None

    def search(self, query: SearchQuery) -> List[SearchResultItem]:
        """
        Recherche dans la base de connaissances et adapte les résultats.

        Une panne du moteur ne fait pas tomber la recherche unifiée : elle est
        journalisée et cette source ne rend rien, comme le prévoit le
        gestionnaire pour toute source défaillante.
        """
        try:
            trouves = self._knowledge_manager.search_knowledge_with_scores(
                query.query, limit=query.limit, role=query.role
            )
        except Exception as error:
            self._logger.warning("Recherche de connaissances impossible : %s", error)
            return []

        resultats: List[SearchResultItem] = []
        for item, score in trouves:
            resultats.append(SearchResultItem(
                id=item.id,
                source=SearchSource.KNOWLEDGE,
                content=item.content,
                score=score,
                title=item.summary,
                summary=item.summary,
                source_detail=item.source.location if item.source else None,
                created_at=self._to_timestamp(item.created_at),
                updated_at=self._to_timestamp(item.updated_at),
                # La classification voyage avec le résultat : sans elle,
                # l'appelant ne sait pas si ce qu'il lit est approuvé.
                metadata={
                    "domain": item.domain.value,
                    "status": item.status.value,
                    "sensitivity": item.sensitivity.value,
                    "confidence": item.confidence,
                    "priority": item.priority.value,
                },
            ))
        return resultats
