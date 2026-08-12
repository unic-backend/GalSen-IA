"""
Memory Indexer for GalSen IA.

Abstract base class for memory indexing and an in-memory implementation.
"""

import abc
from typing import Dict, Set
from .types import MemoryItem, MemoryType


class BaseMemoryIndexer(abc.ABC):
    """Abstract base class for memory indexing."""

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

    @abc.abstractmethod
    def find_by_tag(self, tag: str) -> Set[str]:
        """
        Find item IDs by tag.

        Args:
            tag: The tag to search for.

        Returns:
            Set of item IDs that have the given tag.
        """
        pass

    @abc.abstractmethod
    def find_by_type(self, memory_type: MemoryType) -> Set[str]:
        """
        Find item IDs by memory type.

        Args:
            memory_type: The memory type to search for.

        Returns:
            Set of item IDs of the given type.
        """
        pass


class InMemoryMemoryIndexer(BaseMemoryIndexer):
    """In-memory implementation of the memory indexer."""

    def __init__(self):
        """Initialize the indexer with empty indices."""
        self._type_index: Dict[MemoryType, Set[str]] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._lock = __import__('threading').RLock()  # Use threading.RLock for reentrancy

    def index(self, item: MemoryItem) -> None:
        """Index a memory item."""
        with self._lock:
            # Index by type
            if item.memory_type not in self._type_index:
                self._type_index[item.memory_type] = set()
            self._type_index[item.memory_type].add(item.id)

            # Index by tags
            for tag in item.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(item.id)

    def deindex(self, item_id: str) -> None:
        """Remove a memory item from the index."""
        with self._lock:
            # We need to remove the item from all indices.
            # Since we don't store the item here, we have to iterate over all indices.
            # This is inefficient but acceptable for a simple implementation.
            # In a real implementation, we might store the item's types and tags with the item id.
            for type_key in list(self._type_index.keys()):
                if item_id in self._type_index[type_key]:
                    self._type_index[type_key].discard(item_id)
                    if not self._type_index[type_key]:
                        del self._type_index[type_key]

            for tag_key in list(self._tag_index.keys()):
                if item_id in self._tag_index[tag_key]:
                    self._tag_index[tag_key].discard(item_id)
                    if not self._tag_index[tag_key]:
                        del self._tag_index[tag_key]

    def update_index(self, item: MemoryItem) -> None:
        """Update the index for a memory item."""
        self.deindex(item.id)
        self.index(item)

    def clear_index(self) -> None:
        """Clear the entire index."""
        with self._lock:
            self._type_index.clear()
            self._tag_index.clear()

    def find_by_tag(self, tag: str) -> Set[str]:
        """Find item IDs by tag."""
        with self._lock:
            return self._tag_index.get(tag, set()).copy()

    def find_by_type(self, memory_type: MemoryType) -> Set[str]:
        """Find item IDs by memory type."""
        with self._lock:
            return self._type_index.get(memory_type, set()).copy()