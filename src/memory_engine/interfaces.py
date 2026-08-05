"""
Memory Engine Interfaces for GalSen IA.

Defines abstract base classes that specify the contracts for memory engine components.
"""

import abc
from typing import Any, Dict, List, Optional, Tuple, Union
from .types import MemoryItem, MemoryType, MemoryPriority, MemoryStatus


class MemoryStore(abc.ABC):
    """Abstract base class for memory storage backends."""

    @abc.abstractmethod
    def save(self, item: MemoryItem) -> str:
        """
        Save a memory item to the store.

        Args:
            item: The memory item to save.

        Returns:
            The ID of the saved item.
        """
        pass

    @abc.abstractmethod
    def get(self, item_id: str) -> Optional[MemoryItem]:
        """
        Retrieve a memory item by its ID.

        Args:
            item_id: The ID of the item to retrieve.

        Returns:
            The memory item if found, None otherwise.
        """
        pass

    @abc.abstractmethod
    def update(self, item: MemoryItem) -> bool:
        """
        Update an existing memory item.

        Args:
            item: The memory item with updated content.

        Returns:
            True if the item was updated, False if not found.
        """
        pass

    @abc.abstractmethod
    def delete(self, item_id: str) -> bool:
        """
        Delete a memory item by its ID.

        Args:
            item_id: The ID of the item to delete.

        Returns:
            True if the item was deleted, False if not found.
        """
        pass

    @abc.abstractmethod
    def list_items(
        self,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[MemoryStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[MemoryItem]:
        """
        List memory items with optional filtering.

        Args:
            memory_type: Filter by memory type.
            user_id: Filter by user ID.
            session_id: Filter by session ID.
            agent_id: Filter by agent ID.
            tags: Filter by tags (must match all tags).
            status: Filter by status.
            limit: Maximum number of items to return.
            offset: Offset for pagination.

        Returns:
            List of matching memory items.
        """
        pass

    @abc.abstractmethod
    def clear(self,
              memory_type: Optional[MemoryType] = None,
              user_id: Optional[str] = None,
              session_id: Optional[str] = None,
              agent_id: Optional[str] = None) -> int:
        """
        Clear memory items matching the criteria.

        Args:
            memory_type: Clear only this type (None for all).
            user_id: Clear only for this user (None for all).
            session_id: Clear only for this session (None for all).
            agent_id: Clear only for this agent (None for all).

        Returns:
            Number of items cleared.
        """
        pass


class MemoryRetriever(abc.ABC):
    """Abstract base class for memory retrieval operations."""

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
            query: The search query (text or vector).
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


class MemoryIndexer(abc.ABC):
    """Abstract base class for memory indexing operations."""

    @abc.abstractmethod
    def index(self, item: MemoryItem) -> None:
        """
        Index a memory item for fast retrieval.

        Args:
            item: The memory item to index.
        """
        pass

    @abc.abstractmethod
    def deindex(self, item_id: str) -> None:
        """
        Remove a memory item from the index.

        Args:
            item_id: The ID of the item to remove from index.
        """
        pass

    @abc.abstractmethod
    def update_index(self, item: MemoryItem) -> None:
        """
        Update the index for a memory item.

        Args:
            item: The memory item with updated content.
        """
        pass

    @abc.abstractmethod
    def clear_index(self) -> None:
        """Clear the entire index."""
        pass


class MemorySummarizer(abc.ABC):
    """Abstract base class for memory summarization."""

    @abc.abstractmethod
    def summarize(self,
                  items: List[MemoryItem],
                  max_length: int = 500,
                  language: str = "fr") -> str:
        """
        Summarize a list of memory items.

        Args:
            items: List of memory items to summarize.
            max_length: Maximum length of the summary in characters.
            language: Language for the summary (e.g., "fr", "en").

        Returns:
            A summarized string.
        """
        pass

    @abc.abstractmethod
    def summarize_conversation(self,
                               conversation_id: str,
                               max_length: int = 500,
                               language: str = "fr") -> Optional[str]:
        """
        Summarize a conversation by its ID or session.

        Args:
            conversation_id: Identifier of the conversation (could be session_id).
            max_length: Maximum length of the summary.
            language: Language for the summary.

        Returns:
            A summarized string or None if not found.
        """
        pass


class MemoryRanker(abc.ABC):
    """Abstract base class for memory ranking."""

    @abc.abstractmethod
    def rank(self,
             items: List[MemoryItem],
             context: Optional[Dict[str, Any]] = None) -> List[Tuple[MemoryItem, float]]:
        """
        Rank memory items based on importance, relevance, etc.

        Args:
            items: List of memory items to rank.
            context: Optional context (e.g., current query, user intent) to influence ranking.

        Returns:
            List of tuples (memory_item, score) sorted by score descending.
        """
        pass

    @abc.abstractmethod
    def compute_score(self,
                      item: MemoryItem,
                      context: Optional[Dict[str, Any]] = None) -> float:
        """
        Compute a score for a single memory item.

        Args:
            item: The memory item to score.
            context: Optional context to influence scoring.

        Returns:
            A score between 0.0 and 1.0.
        """
        pass


class MemoryCache(abc.ABC):
    """Abstract base class for memory caching."""

    @abc.abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Get an item from the cache.

        Args:
            key: The cache key.

        Returns:
            The cached value or None if not present.
        """
        pass

    @abc.abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        Set an item in the cache.

        Args:
            key: The cache key.
            value: The value to cache.
            ttl: Time to live in seconds (None for no expiration).
        """
        pass

    @abc.abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete an item from the cache.

        Args:
            key: The cache key.

        Returns:
            True if the item was deleted, False if not found.
        """
        pass

    @abc.abstractmethod
    def clear(self) -> None:
        """Clear the entire cache."""
        pass


class MemoryManager(abc.ABC):
    """Abstract base class for the main memory management interface."""

    @abc.abstractmethod
    def save_memory(self, item: MemoryItem) -> str:
        """
        Save a memory item.

        Args:
            item: The memory item to save.

        Returns:
            The ID of the saved item.
        """
        pass

    @abc.abstractmethod
    def get_memory(self, item_id: str) -> Optional[MemoryItem]:
        """
        Retrieve a memory item by ID.

        Args:
            item_id: The ID of the item to retrieve.

        Returns:
            The memory item if found, None otherwise.
        """
        pass

    @abc.abstractmethod
    def update_memory(self, item: MemoryItem) -> bool:
        """
        Update a memory item.

        Args:
            item: The memory item with updated content.

        Returns:
            True if updated, False if not found.
        """
        pass

    @abc.abstractmethod
    def delete_memory(self, item_id: str) -> bool:
        """
        Delete a memory item by ID.

        Args:
            item_id: The ID of the item to delete.

        Returns:
            True if deleted, False if not found.
        """
        pass

    @abc.abstractmethod
    def search_memory(self,
                      query: str,
                      memory_type: Optional[MemoryType] = None,
                      user_id: Optional[str] = None,
                      session_id: Optional[str] = None,
                      agent_id: Optional[str] = None,
                      tags: Optional[List[str]] = None,
                      limit: int = 10) -> List[Tuple[MemoryItem, float]]:
        """
        Search for memories relevant to a query.

        Args:
            query: The search query.
            memory_type: Filter by memory type.
            user_id: Filter by user ID.
            session_id: Filter by session ID.
            agent_id: Filter by agent ID.
            tags: Filter by tags.
            limit: Maximum number of results.

        Returns:
            List of tuples (memory_item, relevance_score).
        """
        pass

    @abc.abstractmethod
    def forget_memory(self,
                      item_id: str) -> bool:
        """
        Forget (delete) a memory item.

        Args:
            item_id: The ID of the item to forget.

        Returns:
            True if forgotten, False if not found.
        """
        pass

    @abc.abstractmethod
    def consolidate_memory(self,
                           user_id: Optional[str] = None,
                           session_id: Optional[str] = None) -> int:
        """
        Consolidate memories (e.g., move short-term to long-term, summarize).

        Args:
            user_id: Consolidate for specific user (None for all).
            session_id: Consolidate for specific session (None for all).

        Returns:
            Number of memories processed.
        """
        pass

    @abc.abstractmethod
    def cleanup_expired(self) -> int:
        """
        Remove expired memories.

        Returns:
            Number of memories removed.
        """
        pass