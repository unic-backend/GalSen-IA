"""
Memory Retriever for GalSen IA.

Abstract base class for memory retrieval and an in-memory implementation.
"""

import abc
import re
import time
from typing import Any, List, Optional, Tuple
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
        query_terms = set(self._normalize_text(query).split())
        for item in items:
            # Only consider items with string content for text matching
            if isinstance(item.content, str):
                content_terms = set(self._normalize_text(item.content).split())
                # Simple Jaccard similarity
                intersection = len(query_terms & content_terms)
                union = len(query_terms | content_terms)
                score = intersection / union if union > 0 else 0.0
            else:
                # For non-string content, we can't do text matching, so score 0
                score = 0.0

            if score >= min_score:
                scored_items.append((item, score))

        # Sort by score descending
        scored_items.sort(key=lambda x: x[1], reverse=True)
        return scored_items[:limit]

    def retrieve_by_id(self, item_id: str) -> Optional[MemoryItem]:
        """Retrieve a memory item by its ID."""
        return self._store.get(item_id)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching: lowercase and remove punctuation."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return text