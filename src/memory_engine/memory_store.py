"""
Memory Store for GalSen IA.

Abstract base class for memory storage and an in-memory implementation.
"""

import abc
import threading
import time
from typing import Dict, List, Optional
from .types import MemoryItem, MemoryType, MemoryStatus


class BaseMemoryStore(abc.ABC):
    """Abstract base class for memory storage."""

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
    def clear(
        self,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> int:
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

    @abc.abstractmethod
    def cleanup_expired(self) -> int:
        """
        Remove expired memories.

        Returns:
            Number of memories removed.
        """
        pass


class InMemoryMemoryStore(BaseMemoryStore):
    """In-memory implementation of the memory store."""

    def __init__(self):
        """Initialize the in-memory store."""
        self._items: Dict[str, MemoryItem] = {}
        self._lock = threading.RLock()  # Reentrant lock for thread safety

    def save(self, item: MemoryItem) -> str:
        """Save a memory item to the store."""
        with self._lock:
            # If the item doesn't have an ID, one will be generated in __post_init__
            # but we ensure it's set here for consistency.
            if item.id is None:
                item.id = str(id(item))  # Fallback, though __post_init__post_init should set it
            self._items[item.id] = item
            return item.id

    def get(self, item_id: str) -> Optional[MemoryItem]:
        """Retrieve a memory item by its ID."""
        with self._lock:
            return self._items.get(item_id)

    def update(self, item: MemoryItem) -> bool:
        """Update an existing memory item."""
        with self._lock:
            if item.id in self._items:
                self._items[item.id] = item
                return True
            return False

    def delete(self, item_id: str) -> bool:
        """Delete a memory item by its ID."""
        with self._lock:
            if item_id in self._items:
                del self._items[item_id]
                return True
            return False

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
        """List memory items with optional filtering."""
        with self._lock:
            results = []
            for item in self._items.values():
                # Apply filters
                if memory_type is not None and item.memory_type != memory_type:
                    continue
                if user_id is not None and item.user_id != user_id:
                    continue
                if session_id is not None and item.session_id != session_id:
                    continue
                if agent_id is not None and item.agent_id != agent_id:
                    continue
                if status is not None and item.status != status:
                    continue
                if tags is not None:
                    # Check that all tags are present in the item's tags
                    if not all(tag in item.tags for tag in tags):
                        continue
                results.append(item)
            # Apply offset and limit
            return results[offset:offset + limit]

    def clear(
        self,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> int:
        """Clear memory items matching the criteria."""
        with self._lock:
            to_delete = []
            for item_id, item in self._items.items():
                if memory_type is not None and item.memory_type != memory_type:
                    continue
                if user_id is not None and item.user_id != user_id:
                    continue
                if session_id is not None and item.session_id != session_id:
                    continue
                if agent_id is not None and item.agent_id != agent_id:
                    continue
                to_delete.append(item_id)
            for item_id in to_delete:
                del self._items[item_id]
            return len(to_delete)

    def cleanup_expired(self) -> int:
        """Remove expired memories."""
        with self._lock:
            now = time.time()
            to_delete = []
            for item_id, item in self._items.items():
                if item.expires_at is not None and item.expires_at < now:
                    to_delete.append(item_id)
            for item_id in to_delete:
                del self._items[item_id]
            return len(to_delete)