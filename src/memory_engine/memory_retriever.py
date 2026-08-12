"""
Memory Retriever for GalSen IA.

Abstract base class for memory retrieval and an in-memory implementation.
"""

import abc
import time
from typing import Any, Dict, List, Optional, Tuple
from src.text_normalization import tokenize
from .types import MemoryItem, MemoryType, MemoryStatus


class BaseMemoryRetriever(abc.ABC):
    """Abstract base class for memory retrieval."""

    @abc.abstractmethod
    def retrieve(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        min_score: float = 0.0
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Retrieve memories relevant to a query.

        Args:
            query: The search query (text).
            memory_type: Filter by memory type.
            user_id: Filter by user ID.
            session_id: Filter by session ID.
            agent_id: Filter by agent ID.
            tags: Filter by tags.
            limit: Maximum number of results.
            min_score: Minimum relevance score (0.0 to 1.0).

        Returns:
            List of tuples (memory_item, relevance_score).
        """
        pass

    @abc.abstractmethod
    def retrieve_by_id(self, item_id: str) -> Optional[MemoryItem]:
        """
        Retrieve a memory item by its ID.

        Args:
            item_id: The ID of the item to retrieve.

        Returns:
            The memory item if found, None otherwise.
        """
        pass


class InMemoryMemoryRetriever(BaseMemoryRetriever):
    """In-memory implementation of the memory retriever using simple text matching."""

    def __init__(self, store: 'InMemoryMemoryStore'):
        """
        Initialize the retriever with a reference to the store.

        Args:
            store: The memory store to retrieve from.
        """
        self._store = store

    def retrieve(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        min_score: float = 0.0
    ) -> List[Tuple[MemoryItem, float]]:
        """
        Retrieve memories relevant to a query using simple term frequency.

        Only ACTIVE memories are considered. Archiving is the lifecycle stage
        that takes a memory out of everyday use (VOLET 07 ch. 03); returning
        archived items would make it a label with no effect. Expired memories
        are excluded for the same reason: a retention date the retriever
        ignores is not a retention date.
        """
        # Get all items that match the filters
        items = self._store.list_items(
            memory_type=memory_type,
            user_id=user_id,
            session_id=session_id,
            agent_id=agent_id,
            tags=tags,
            status=MemoryStatus.ACTIVE,
            limit=10000,  # Get a large number to then score and limit
            offset=0
        )
        maintenant = time.time()
        items = [i for i in items if i.expires_at is None or i.expires_at >= maintenant]

        # Score each item based on the query
        scored_items = []
        query_terms = set(self._terms(query))
        for item in items:
            # Only consider items with string content for text matching
            if isinstance(item.content, str):
                content_terms = set(self._terms(item.content))
                # Simple Jaccard similarity
                intersection = len(query_terms & content_terms)
                union = len(query_terms | content_terms)
                score = intersection / union if union > 0 else 0.0
            else:
                # For non-string content, we can't do text matching, so score 0
                score = 0.0

            # Un score nul veut dire « aucun terme en commun ». Ces éléments
            # étaient rendus quand même, parce que le seuil par défaut valait
            # `0.0` et que le test était `>=` : chercher « xyzzy » rendait
            # **toutes** les mémoires du sujet, notées 0. L'appelant recevait
            # une liste de résultats et le contexte d'un agent se remplissait de
            # mémoires sans rapport, présentées comme pertinentes.
            #
            # Une mémoire dont le contenu n'est pas du texte tombe dans le même
            # cas : on ne peut pas la rapprocher d'une requête, donc elle n'est
            # pas un résultat de recherche. `list_items()` reste la façon de
            # tout obtenir.
            if score > 0.0 and score >= min_score:
                scored_items.append((item, score))

        # Sort by score descending
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return scored_items[:limit]

    def retrieve_with_method(
        self,
        query: str,
        **filtres
    ) -> Tuple[List[Tuple[MemoryItem, float]], Dict[str, Any]]:
        """
        Comme `retrieve`, mais dit **par quel chemin** le classement a été obtenu.

        `retrieve()` note par similarité de Jaccard : deux textes qui ne
        partagent aucun jeton ont un score nul, même quand ils disent la même
        chose. Avec un encodeur disponible (ADR-015), le classement passe par le
        sens ; sans encodeur, il reste lexical — et la différence est
        **rapportée**, jamais devinée par l'appelant.

        Args:
            query: Requête.
            **filtres: Mêmes filtres que `retrieve`.

        Returns:
            Le classement, et un rapport `{"method": ..., ...}`.
        """
        from src.embeddings.registry import active_embedder
        from src.embeddings.semantic_index import rank_or_fallback

        limit = filtres.get("limit", 10)
        min_score = filtres.get("min_score", 0.0)

        lexical = lambda: [(item.id, score) for item, score in self.retrieve(query, **filtres)]  # noqa: E731
        encodeur = active_embedder()
        if encodeur is None:
            classes, rapport = lexical(), {
                "method": "lexical",
                "reason": "Aucun encodeur disponible : classement par termes communs (ADR-015).",
            }
        else:
            # Les candidats sont les mémoires que les filtres laissent passer,
            # pas seulement celles qu'un score lexical aurait retenues : c'est
            # tout l'intérêt du chemin sémantique.
            candidats = self._candidats_textuels(**filtres)
            classes, rapport = rank_or_fallback(
                query, candidats, lexical, encodeur, "memory",
                limit=limit, min_score=min_score,
            )

        par_id = {item.id: item for item in self._items_par_id(classes)}
        resultats = [(par_id[item_id], score) for item_id, score in classes if item_id in par_id]
        return resultats, rapport

    def _candidats_textuels(self, **filtres) -> List[Tuple[str, str]]:
        """Retourne les mémoires textuelles que les filtres laissent passer."""
        items = self._store.list_items(
            memory_type=filtres.get("memory_type"),
            user_id=filtres.get("user_id"),
            session_id=filtres.get("session_id"),
            agent_id=filtres.get("agent_id"),
            tags=filtres.get("tags"),
            status=MemoryStatus.ACTIVE,
            limit=10000,
            offset=0,
        )
        maintenant = time.time()
        return [
            (item.id, item.content)
            for item in items
            if isinstance(item.content, str)
            and (item.expires_at is None or item.expires_at >= maintenant)
        ]

    def _items_par_id(self, classes: List[Tuple[str, float]]) -> List[MemoryItem]:
        """Retrouve les mémoires correspondant à un classement d'identifiants."""
        items = []
        for item_id, _ in classes:
            item = self._store.get(item_id)
            if item is not None:
                items.append(item)
        return items

    def retrieve_by_id(self, item_id: str) -> Optional[MemoryItem]:
        """Retrieve a memory item by its ID."""
        return self._store.get(item_id)

    @staticmethod
    def _terms(text: str) -> List[str]:
        """Découpe un texte en mots comparables.

        Même normalisation que l'index de connaissances : sans accents et sans
        marque de pluriel simple, appliquée des deux côtés. « pluviometrie »
        retrouve « pluviométrie », et « arachide » retrouve « arachides ».
        """
        return tokenize(text)