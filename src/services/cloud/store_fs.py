"""
Stockage persistant sur le système de fichiers pour le service Cloud.

Fournit `FileSystemCloudStore`, une implémentation du contrat `CloudStore`
qui stocke les fichiers sur le disque local. Les métadonnées sont dans un
fichier JSON, les données binaires dans un répertoire dédié.

```python
store = FileSystemCloudStore(data_dir="data/cloud")
manager = CloudManagerImpl(store=store)
```

Référence : VOLET 02, Chapitre 09 (Integration).
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from .interfaces import CloudStore
from .types import CloudFileItem, generate_cloud_file_id

logger = logging.getLogger(__name__)


class FileSystemCloudStore(CloudStore):
    """
    Stockage cloud persistant sur le système de fichiers.

    Les métadonnées des fichiers sont conservées dans un index JSON.
    Les données binaires sont stockées dans `data_dir / files / <id>`.
    Thread-safe via RLock. Persiste entre les redémarrages.
    """

    def __init__(self, data_dir: str = "data/cloud") -> None:
        self._data_dir = data_dir
        self._files_dir = os.path.join(data_dir, "files")
        self._index_path = os.path.join(data_dir, "index.json")
        self._lock = threading.RLock()
        self._items: Dict[str, CloudFileItem] = {}
        self._order: List[str] = []

        # Créer les répertoires et charger l'index existant
        os.makedirs(self._files_dir, exist_ok=True)
        self._load_index()

    def _index_path_abs(self) -> str:
        """Retourne le chemin absolu de l'index."""
        return os.path.abspath(self._index_path)

    def _load_index(self) -> None:
        """Charge l'index depuis le disque."""
        try:
            if os.path.exists(self._index_path):
                with open(self._index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._order = data.get("order", [])
                for item_data in data.get("items", []):
                    item = CloudFileItem.from_mapping(item_data)
                    self._items[item.id] = item
                logger.info(
                    "Index cloud chargé : %d fichiers depuis %s",
                    len(self._items), self._index_path_abs(),
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Impossible de charger l'index cloud : %s", e)
            self._items = {}
            self._order = []

    def _save_index(self) -> None:
        """Sauvegarde l'index sur le disque."""
        try:
            data = {
                "order": self._order,
                "items": [item.to_dict() for item in self._items.values()],
            }
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error("Impossible de sauvegarder l'index cloud : %s", e)
            raise

    def _file_path(self, file_id: str) -> str:
        """Retourne le chemin du fichier binaire."""
        return os.path.join(self._files_dir, file_id)

    def save(self, item: CloudFileItem, data: bytes) -> str:
        """Enregistre un fichier sur le disque et dans l'index."""
        with self._lock:
            if item.id in self._items:
                raise ValueError(f"Le fichier cloud {item.id} existe déjà.")

            # Écrire les données binaires
            file_path = self._file_path(item.id)
            try:
                with open(file_path, "wb") as f:
                    f.write(data)
            except OSError as e:
                raise IOError(f"Impossible d'écrire le fichier {file_path} : {e}")

            # Mettre à jour l'index
            self._items[item.id] = item
            self._order.append(item.id)
            self._save_index()

            return item.id

    def get(self, file_id: str) -> Optional[CloudFileItem]:
        """Retourne un fichier cloud par identifiant."""
        with self._lock:
            return self._items.get(file_id)

    def get_data(self, file_id: str) -> Optional[bytes]:
        """Retourne les données binaires d'un fichier."""
        with self._lock:
            if file_id not in self._items:
                return None
            file_path = self._file_path(file_id)
            try:
                with open(file_path, "rb") as f:
                    return f.read()
            except OSError:
                logger.warning("Fichier binaire manquant : %s", file_path)
                return None

    def _matches(
        self,
        item: CloudFileItem,
        provider: Optional[str],
        category: Optional[str],
        uploaded_by: Optional[str],
    ) -> bool:
        """Vérifie si un fichier correspond aux filtres."""
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
        """Supprime un fichier (index + binaire)."""
        with self._lock:
            if file_id not in self._items:
                return False

            # Supprimer le fichier binaire
            file_path = self._file_path(file_id)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError as e:
                logger.warning("Impossible de supprimer %s : %s", file_path, e)

            # Mettre à jour l'index
            del self._items[file_id]
            self._order = [fid for fid in self._order if fid != file_id]
            self._save_index()
            return True

    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier."""
        with self._lock:
            item = self._items.get(file_id)
            if item is None:
                return False
            item.metadata.update(metadata)
            item.updated_at = time.time()
            self._save_index()
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
        """Supprime tous les fichiers et l'index."""
        with self._lock:
            count = len(self._order)

            # Supprimer les fichiers binaires
            for file_id in self._order:
                file_path = self._file_path(file_id)
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except OSError:
                    pass

            self._items.clear()
            self._data: Dict = {}  # type: ignore
            self._order.clear()

            # Réinitialiser l'index
            try:
                if os.path.exists(self._index_path):
                    os.remove(self._index_path)
            except OSError:
                pass

            return count

    def count(self) -> int:
        """Retourne le nombre total de fichiers."""
        with self._lock:
            return len(self._order)

    def total_size(self) -> int:
        """Retourne la taille totale des fichiers stockés."""
        with self._lock:
            return sum(item.size for item in self._items.values())