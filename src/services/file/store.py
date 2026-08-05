"""
Stockage en mémoire des fichiers.

Fournit `InMemoryFileStore`, une implémentation thread-safe du contrat
`FileStore`. Les fichiers sont conservés en mémoire ; la persistance
(disque, S3, MinIO) peut être ajoutée ultérieurement sans changer ce module.
"""

import logging
import threading
from typing import Any, Dict, List, Optional

from .interfaces import FileStore
from .types import FileItem

logger = logging.getLogger(__name__)


class InMemoryFileStore(FileStore):
    """Stockage de fichiers en mémoire, thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._files: Dict[str, FileItem] = {}
        self._order: List[str] = []

    def save(self, file: FileItem) -> str:
        """Enregistre un fichier et retourne son identifiant."""
        with self._lock:
            if file.id in self._files:
                raise ValueError(f"Le fichier {file.id} existe déjà.")
            self._files[file.id] = file
            self._order.append(file.id)
            return file.id

    def get(self, file_id: str) -> Optional[FileItem]:
        """Retourne un fichier par identifiant, ou None si absent."""
        with self._lock:
            return self._files.get(file_id)

    def get_by_name(self, name: str) -> Optional[FileItem]:
        """Retourne un fichier par nom exact, ou None si absent."""
        with self._lock:
            for file in self._files.values():
                if file.name == name:
                    return file
            return None

    def _matches(
        self,
        file: FileItem,
        category: Optional[str],
        content_type: Optional[str],
        uploaded_by: Optional[str],
        tags: Optional[Dict[str, str]],
    ) -> bool:
        """Vérifie si un fichier correspond aux filtres fournis."""
        if category is not None and file.category.value != category:
            return False
        if content_type is not None and file.content_type != content_type:
            return False
        if uploaded_by is not None and file.uploaded_by != uploaded_by:
            return False
        if tags:
            for key, value in tags.items():
                if file.tags.get(key) != value:
                    return False
        return True

    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        content_type: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> List[FileItem]:
        """Retourne les fichiers filtrés, du plus récent au plus ancien."""
        with self._lock:
            matched: List[FileItem] = []
            for file_id in reversed(self._order):
                file = self._files[file_id]
                if self._matches(file, category, content_type, uploaded_by, tags):
                    matched.append(file)
            return matched[offset:offset + limit]

    def delete(self, file_id: str) -> bool:
        """Supprime un fichier ; retourne False si absent."""
        with self._lock:
            if file_id not in self._files:
                return False
            del self._files[file_id]
            self._order = [fid for fid in self._order if fid != file_id]
            return True

    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier ; retourne False si absent."""
        import time

        with self._lock:
            file = self._files.get(file_id)
            if file is None:
                return False
            file.metadata.update(metadata)
            file.updated_at = time.time()
            return True

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées sur les fichiers."""
        with self._lock:
            total = len(self._order)
            total_size = sum(f.size for f in self._files.values())
            by_category: Dict[str, int] = {}
            by_content_type: Dict[str, int] = {}

            for file in self._files.values():
                cat = file.category.value
                by_category[cat] = by_category.get(cat, 0) + 1
                ct = file.content_type
                by_content_type[ct] = by_content_type.get(ct, 0) + 1

            return {
                "total": total,
                "total_size": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "by_category": by_category,
                "by_content_type": by_content_type,
            }

    def clear(self) -> int:
        """Supprime tous les fichiers et retourne le nombre supprimé."""
        with self._lock:
            count = len(self._order)
            self._files.clear()
            self._order.clear()
            return count

    def count(self) -> int:
        """Retourne le nombre total de fichiers."""
        with self._lock:
            return len(self._order)

    def total_size(self) -> int:
        """Retourne la taille totale des fichiers stockés."""
        with self._lock:
            return sum(f.size for f in self._files.values())