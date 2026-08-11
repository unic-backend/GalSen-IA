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


class MemorySearchProvider(SearchProvider):
    """
    Expose le moteur de mémoire au service de recherche unifiée.

    La mémoire est **possédée**, pas seulement classifiée : chaque élément
    appartient à un sujet (ADR-010), et le critère de sortie C2 dit que les
    données d'un utilisateur sont les siennes. Un rôle ne suffit donc pas ici —
    un administrateur a le droit de lire beaucoup de choses, il n'a pas pour
    autant les souvenirs des autres.

    Sans sujet, ce fournisseur **ne cherche pas**. Il ne rend pas non plus
    « aucun résultat » sans rien dire : la source est absente de
    `sources_used`, ce que `/search/status` et la réponse laissent voir.
    """

    source = SearchSource.MEMORY

    def __init__(self, memory_manager: Any):
        """
        Args:
            memory_manager: le gestionnaire de mémoire à exposer
        """
        self._memory_manager = memory_manager
        self._logger = logging.getLogger(f"{__name__}.MemorySearchProvider")

    def search(self, query: SearchQuery) -> List[SearchResultItem]:
        """
        Recherche dans la mémoire du sujet de la requête.

        Une panne du moteur ne fait pas tomber la recherche unifiée : elle est
        journalisée et cette source ne rend rien.
        """
        if not query.subject:
            self._logger.info(
                "Recherche en mémoire ignorée : aucune requête sans sujet ne peut "
                "désigner des souvenirs, et les rendre tous serait une fuite."
            )
            return []

        try:
            trouves = self._memory_manager.search_memory(
                query=query.query, user_id=query.subject, limit=query.limit,
            )
        except Exception as error:
            self._logger.warning("Recherche en mémoire impossible : %s", error)
            return []

        resultats: List[SearchResultItem] = []
        for item, score in trouves:
            # Une mémoire dont le contenu n'est pas du texte n'a rien à rendre
            # comme résultat de recherche : le récupérateur l'écarte déjà, ce
            # test protège les appelants qui construiraient la liste autrement.
            if not isinstance(item.content, str):
                continue
            resultats.append(SearchResultItem(
                id=item.id,
                source=SearchSource.MEMORY,
                content=item.content,
                score=score,
                created_at=item.created_at,
                updated_at=item.updated_at,
                metadata={
                    "memory_type": item.memory_type.value,
                    "status": item.status.value,
                    # Le propriétaire n'est pas recopié : l'appelant est le
                    # sujet, le lui répéter n'apprend rien et l'écrire dans une
                    # réponse en fait une donnée de plus à protéger.
                    "tags": list(item.tags),
                },
            ))
        return resultats
