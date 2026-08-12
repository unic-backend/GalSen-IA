"""
Cache de connaissances pour le moteur de connaissances GalSen IA.
"""

import time
import threading
from typing import Any, Optional
from collections import OrderedDict
from .interfaces import KnowledgeCache


class TTLCache(KnowledgeCache):
    """Cache avec TTL (Time To Live) et limite de taille LRU."""

    def __init__(self, maxsize: int = 1000, ttl: float = 3600.0):
        """
        Initialise le cache.

        Args:
            maxsize: Nombre maximum d'éléments dans le cache
            ttl: Durée de vie en secondes (0 pour pas d'expiration)
        """
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()  # key -> (value, expiry_time)
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def _is_expired(self, expiry: float) -> bool:
        """Vérifie si un élément est expiré."""
        if self._ttl <= 0:
            return False
        return time.time() >= expiry

    def _cleanup_expired(self) -> None:
        """Supprime les éléments expirés (appelé avec le verrou détenu)."""
        now = time.time()
        to_delete = []
        for key, (_, expiry) in self._cache.items():
            if self._ttl > 0 and now >= expiry:
                to_delete.append(key)
        for key in to_delete:
            del self._cache[key]

    def get(self, key: str) -> Optional[Any]:
        """Récupère une valeur du cache."""
        with self._lock:
            self._cleanup_expired()  # Nettoyage paresseux
            if key in self._cache:
                value, expiry = self._cache[key]
                # Mouvoir à la fin pour LRU (plus récemment utilisé)
                self._cache.move_to_end(key)
                self._hits += 1
                return value
            else:
                self._misses += 1
                return None

    def set(self, key: str, value: Any) -> None:
        """Ajoute ou met à jour une valeur dans le cache."""
        with self._lock:
            self._cleanup_expired()
            expiry = time.time() + self._ttl if self._ttl > 0 else float('inf')
            self._cache[key] = (value, expiry)
            self._cache.move_to_end(key)  # Nouvel élément = plus récemment utilisé
            # Appliquer la limite de taille
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)  # Supprimer le moins récemment utilisé

    def delete(self, key: str) -> bool:
        """Supprime une clé du cache. Retourne True si elle existait."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Vide complètement le cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def size(self) -> int:
        """Retourne le nombre actuel d'éléments dans le cache."""
        with self._lock:
            self._cleanup_expired()
            return len(self._cache)

    def stats(self) -> dict:
        """Retourne des statistiques d'utilisation du cache."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / max(1, total)
            return {
                "size": self.size(),
                "maxsize": self._maxsize,
                "ttl": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate
            }

    def keys(self) -> list[str]:
        """Retourne la liste des clés présentes dans le cache."""
        with self._lock:
            self._cleanup_expired()
            return list(self._cache.keys())