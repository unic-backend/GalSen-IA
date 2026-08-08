"""
Stockage en mémoire des fichiers cloud.

Fournit `InMemoryCloudStore`, une implémentation thread-safe du contrat
`CloudStore`. Les fichiers sont conservés en mémoire ; la persistance
(S3, GCS, Azure) peut être ajoutée ultérieurement sans changer ce module.
"""

import logging
import threading
from typing import Any, Dict, List, Optional

from .interfaces import CloudStore
from .types import CloudFileItem

logger = logging.getLogger(__name__)


class InMemoryCloudStore(CloudStore):
    """Stockage de fichiers cloud en mémoire, thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: Dict[str, CloudFileItem] = {}
        self._data: Dict[str, bytes] = {}
        self._order: List[str] = []

    def save(self, item: CloudFileItem, data: bytes) -> str:
        """Enregistre un fichier cloud et retourne son identifiant."""
        with self._lock:
            if item.id in self._items:
                raise ValueError(f"Le fichier cloud {item.id} existe déjà.")
            self._items[item.id] = item
            self._data[item.id] = data
            self._order.append(item.id)
            return item.id

    def get(self, file_id: str) -> Optional[CloudFileItem]:
        """Retourne un fichier cloud par identifiant, ou None si absent."""
        with self._lock:
            return self._items.get(file_id)

    def get_data(self, file_id: str) -> Optional[bytes]:
        """Retourne les données binaires d'un fichier cloud."""
        with self._lock:
            return self._data.get(file_id)

    def _matches(
        self,
        item: CloudFileItem,
        provider: Optional[str],
        category: Optional[str],
        uploaded_by: Optional[str],
    ) -> bool:
        """Vérifie si un fichier correspond aux filtres fournis."""
        if provider is not None and item.provider.value != provider:
            return False
        if category is not None and item.category.value != category:
            return False
        if uploaded_by is not None and item.uploaded_by != uploaded_by:
            return False
        return True

    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> List[CloudFileItem]:
        """Retourne les fichiers filtrés, du plus récent au plus ancien."""
        with self._lock:
            matched: List[CloudFileItem] = []
            for item_id in reversed(self._order):
                item = self._items[item_id]
                if self._matches(item, provider, category, uploaded_by):
                    matched.append(item)
            return matched[offset:offset + limit]

    def delete(self, file_id: str) -> bool:
        """Supprime un fichier cloud ; retourne False si absent."""
        with self._lock:
            if file_id not in self._items:
                return False
            del self._items[file_id]
            del self._data[file_id]
            self._order = [fid for fid in self._order if fid != file_id]
            return True

    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier ; retourne False si absent."""
        with self._lock:
            item = self._items.get(file_id)
            if item is None:
                return False
            item.metadata.update(metadata)
            item.updated_at = __import__("time").time()
            return True

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        with self._lock:
            total = len(self._order)
            total_size = sum(item.size for item in self._items.values())
            by_category: Dict[str, int] = {}
            by_provider: Dict[str, int] = {}

            for item in self._items.values():
                c = item.category.value
                by_category[c] = by_category.get(c, 0) + 1
                p = item.provider.value
                by_provider[p] = by_provider.get(p, 0) + 1

            return {
                "total": total,
                "total_size": total_size,
                "by_category": by_category,
                "by_provider": by_provider,
            }

    def clear(self) -> int:
        """Supprime tous les fichiers et retourne le nombre supprimé."""
        with self._lock:
            count = len(self._order)
            self._items.clear()
            self._data.clear()
            self._order.clear()
            return count

    def count(self) -> int:
        """Retourne le nombre total de fichiers."""
        with self._lock:
            return len(self._order)

    def total_size(self) -> int:
        """Retourne la taille totale des fichiers stockés."""
        with self._lock:
            return sum(item.size for item in self._items.values())