"""
Memory Cache for GalSen IA.

Abstract base class for memory caching and an LRU implementation.
"""

import abc
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional


class BaseMemoryCache(abc.ABC):
    """Abstract base class for memory caching."""

    @abc.abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Get an item from the cache.

        Args:
            key: The cache key.

        Returns:
            The cached value or None if not present or expired.
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


class LRUMemoryCache(BaseMemoryCache):
    """LRU (Least Recently Used) cache with optional TTL per item."""

    def __init__(self, max_size: int = 1000):
        """
        Initialize the LRU cache.

        Args:
            max_size: Maximum number of items in the cache.
        """
        self._max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._ttls: Dict[str, float] = {}  # key -> expiry time
        self._lock = threading.RLock()  # For thread safety

    def get(self, key: str) -> Optional[Any]:
        """Get an item from the cache, marking it as recently used."""
        with self._lock:
            if key not in self._cache:
                return None
            # Check if the item has expired
            expiry = self._ttls.get(key)
            if expiry is not None and time.time() > expiry:
                # Remove expired item
                self._delete_key(key)
                return None
            # Move to end to mark as recently used
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set an item in the cache."""
        with self._lock:
            # If key already exists, remove it first to reset order
            if key in self._cache:
                self._delete_key(key)
            # If cache is full, remove the least recently used item
            if len(self._cache) >= self._max_size:
                self._popitem(last=False)  # Remove first item (least recently used)
            # Insert the new item
            self._cache[key] = value
            self._cache.move_to_end(key)  # Ensure it's at the end (most recent)
            # Set TTL if provided
            if ttl is not None:
                self._ttls[key] = time.time() + ttl
            else:
                # Remove any existing TTL for this key
                self._ttls.pop(key, None)

    def delete(self, key: str) -> bool:
        """Delete an item from the cache."""
        with self._lock:
            if key in self._cache:
                self._delete_key(key)
                return True
            return False

    def clear(self) -> None:
        """Clear the entire cache."""
        with self._lock:
            self._cache.clear()
            self._ttls.clear()

    def _delete_key(self, key: str) -> None:
        """Delete a key from the cache and its TTL."""
        self._cache.pop(key, None)
        self._ttls.pop(key, None)

    def _popitem(self, last: bool = True) -> None:
        """
        Pop an item from the cache.

        Args:
            last: If True, pop from the end (most recent); if False, from the beginning (least recent).
        """
        if self._cache:
            key, _ = self._cache.popitem(last=last)
            self._ttls.pop(key, None)

    # Note: We could call _cleanup_expired periodically or on every operation,
    # but for simplicity, we only check on get. For a production system,
    # consider a background cleanup thread.