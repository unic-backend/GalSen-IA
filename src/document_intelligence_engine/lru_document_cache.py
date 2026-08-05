"""
Cache LRU pour le moteur d'intelligence documentaire GalSen IA.
"""

import time
from collections import OrderedDict
from typing import Any, Optional, Tuple

from .interfaces import DocumentCache


class LRUDocumentCache(DocumentCache):
    """
    Cache à éviction LRU (Least Recently Used) avec durée de vie optionnelle.

    Quand la capacité est atteinte, l'entrée la moins récemment consultée est
    supprimée. Une entrée dont la durée de vie est dépassée est traitée comme
    absente et retirée à la première lecture.
    """

    def __init__(self, capacity: int = 100, default_ttl: Optional[float] = None):
        """
        Initialise le cache.

        Args:
            capacity: Nombre maximum d'entrées conservées
            default_ttl: Durée de vie par défaut en secondes, None pour aucune

        Raises:
            ValueError: Si la capacité n'est pas strictement positive
        """
        if capacity < 1:
            raise ValueError("La capacité du cache doit être au moins 1")

        self._capacity = capacity
        self._default_ttl = default_ttl
        # OrderedDict maintient l'ordre d'accès : le plus ancien est en tête
        self._entries: "OrderedDict[str, Tuple[Any, Optional[float]]]" = OrderedDict()

    def get(self, key: str) -> Any:
        """
        Récupère une valeur du cache.

        Args:
            key: Clé recherchée

        Returns:
            La valeur associée, ou None si elle est absente ou expirée
        """
        entry = self._entries.get(key)
        if entry is None:
            return None

        value, expires_at = entry
        if self._is_expired(expires_at):
            del self._entries[key]
            return None

        # L'entrée redevient la plus récemment utilisée
        self._entries.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        Stocke une valeur dans le cache.

        Args:
            key: Clé de l'entrée
            value: Valeur à conserver
            ttl: Durée de vie en secondes, None pour utiliser celle par défaut
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.time() + effective_ttl if effective_ttl is not None else None

        self._entries[key] = (value, expires_at)
        self._entries.move_to_end(key)

        if len(self._entries) > self._capacity:
            # popitem(last=False) retire l'entrée la moins récemment utilisée
            self._entries.popitem(last=False)

    def delete(self, key: str) -> bool:
        """
        Supprime une valeur du cache.

        Args:
            key: Clé à supprimer

        Returns:
            True si l'entrée existait
        """
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def clear(self) -> None:
        """Vide le cache."""
        self._entries.clear()

    def cleanup_expired(self) -> int:
        """
        Retire toutes les entrées expirées.

        Returns:
            Nombre d'entrées supprimées
        """
        expired_keys = [
            key for key, (_, expires_at) in self._entries.items()
            if self._is_expired(expires_at)
        ]
        for key in expired_keys:
            del self._entries[key]
        return len(expired_keys)

    def __len__(self) -> int:
        """Retourne le nombre d'entrées actuellement conservées."""
        return len(self._entries)

    def _is_expired(self, expires_at: Optional[float]) -> bool:
        """Indique si une échéance est dépassée."""
        return expires_at is not None and time.time() >= expires_at
