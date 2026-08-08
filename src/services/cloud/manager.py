"""
Gestionnaire du service Cloud.

Fournit `CloudManagerImpl`, une façade best-effort conforme à
`CloudManager` : chaque appel est protégé et ne lève jamais ; en cas
d'échec, un avertissement est journalisé et une valeur vide est retournée.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from .interfaces import CloudManager, CloudStore
from .store import InMemoryCloudStore
from .types import CloudFileItem, CloudFileCategory, CloudProvider, CloudSyncResult

logger = logging.getLogger(__name__)


def _infer_category(content_type: str) -> CloudFileCategory:
    """Déduit la catégorie d'un fichier depuis son type MIME."""
    type_map: Dict[str, CloudFileCategory] = {
        "application/pdf": CloudFileCategory.DOCUMENT,
        "application/msword": CloudFileCategory.DOCUMENT,
        "application/vnd.openxmlformats-officedocument": CloudFileCategory.DOCUMENT,
        "text/plain": CloudFileCategory.DOCUMENT,
        "text/html": CloudFileCategory.DOCUMENT,
        "text/csv": CloudFileCategory.DATA,
        "application/json": CloudFileCategory.DATA,
        "application/xml": CloudFileCategory.DATA,
        "image/": CloudFileCategory.IMAGE,
        "video/": CloudFileCategory.VIDEO,
        "audio/": CloudFileCategory.AUDIO,
        "application/zip": CloudFileCategory.ARCHIVE,
        "application/x-tar": CloudFileCategory.ARCHIVE,
        "application/gzip": CloudFileCategory.ARCHIVE,
    }

    for prefix, category in type_map.items():
        if content_type.startswith(prefix):
            return category
    return CloudFileCategory.OTHER


class CloudManagerImpl(CloudManager):
    """Façade du service cloud, toujours disponible en mémoire."""

    def __init__(self, store: Optional[CloudStore] = None) -> None:
        if store is not None:
            self._store = store
        elif os.getenv("GALSEN_STORAGE_BACKEND", "in-memory").lower() == "sqlite":
            from storage.sqlite_cloud_store import SQLiteCloudStore
            self._store = SQLiteCloudStore()
        else:
            self._store = InMemoryCloudStore()
        self._logger = logging.getLogger(f"{__name__}.CloudManagerImpl")

    def upload(
        self,
        name: str,
        content_type: str,
        data: bytes,
        provider: CloudProvider = CloudProvider.LOCAL,
        uploaded_by: Optional[str] = None,
        max_size: int = 100 * 1024 * 1024,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CloudSyncResult:
        """Téléverse un fichier vers le cloud."""
        if not name or not name.strip():
            return CloudSyncResult(False, "Le nom du fichier est requis.")
        if not data:
            return CloudSyncResult(False, "Les données du fichier sont vides.")
        if len(data) > max_size:
            return CloudSyncResult(
                False,
                f"Le fichier dépasse la taille maximale de {max_size} octets.",
            )

        try:
            category = _infer_category(content_type)
            item = CloudFileItem(
                name=name.strip(),
                content_type=content_type,
                size=len(data),
                provider=provider,
                category=category,
                uploaded_by=uploaded_by,
                metadata=metadata or {},
            )
            file_id = self._store.save(item, data)
            return CloudSyncResult(
                True,
                f"Fichier '{name}' téléversé avec succès.",
                file_id=file_id,
            )
        except Exception as error:
            self._logger.warning("Échec du téléversement '%s' : %s", name, error)
            return CloudSyncResult(False, f"Échec du téléversement : {error}")

    def get_file(self, file_id: str) -> Optional[CloudFileItem]:
        """Retourne un fichier cloud par identifiant."""
        try:
            return self._store.get(file_id)
        except Exception as error:
            self._logger.warning("Échec de la lecture du fichier cloud %s : %s", file_id, error)
            return None

    def download(self, file_id: str) -> Optional[bytes]:
        """Télécharge les données d'un fichier cloud."""
        try:
            return self._store.get_data(file_id)
        except Exception as error:
            self._logger.warning("Échec du téléchargement %s : %s", file_id, error)
            return None

    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> List[CloudFileItem]:
        """Retourne les fichiers filtrés."""
        try:
            return self._store.list_files(
                limit=limit,
                offset=offset,
                provider=provider,
                category=category,
                uploaded_by=uploaded_by,
            )
        except Exception as error:
            self._logger.warning("Échec du filtrage des fichiers cloud : %s", error)
            return []

    def delete(self, file_id: str) -> bool:
        """Supprime un fichier cloud ; retourne False si absent."""
        try:
            return self._store.delete(file_id)
        except Exception as error:
            self._logger.warning("Échec de la suppression du fichier cloud %s : %s", file_id, error)
            return False

    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier."""
        try:
            return self._store.update_metadata(file_id, metadata)
        except Exception as error:
            self._logger.warning("Échec de la mise à jour des métadonnées %s : %s", file_id, error)
            return False

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        try:
            return self._store.stats()
        except Exception as error:
            self._logger.warning("Échec du calcul des statistiques cloud : %s", error)
            return {}

    def clear(self) -> int:
        """Supprime tous les fichiers et retourne le nombre supprimé."""
        try:
            return self._store.clear()
        except Exception as error:
            self._logger.warning("Échec de la suppression des fichiers cloud : %s", error)
            return 0