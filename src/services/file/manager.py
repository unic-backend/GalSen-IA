"""
Gestionnaire du service de fichiers.

Fournit `FileManagerImpl`, une façade best-effort conforme à
`FileManager` : chaque appel est protégé et ne lève jamais ; en cas
d'échec, un avertissement est journalisé et une valeur vide est retournée.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from .interfaces import FileManager, FileStore
from .store import InMemoryFileStore
from .types import (
    DEFAULT_MAX_FILE_SIZE,
    FileItem,
    FileSummary,
    FileUploadResult,
    get_category_for_content_type,
)
from src.storage.paths import storage_backend

logger = logging.getLogger(__name__)


class FileManagerImpl(FileManager):
    """Façade du service de fichiers, toujours disponible en mémoire."""

    # ADR-016 fait du service de fichiers le seul chemin d'écriture de la
    # plateforme ; il porte donc les quatre magasins, dont les deux qui
    # n'existaient que sous le service `cloud`.
    BACKEND_ENV = "GALSEN_FILE_BACKEND"
    BACKENDS = ("in-memory", "sqlite", "filesystem", "s3")

    def __init__(self, store: Optional[FileStore] = None) -> None:
        self._logger = logging.getLogger(f"{__name__}.FileManagerImpl")
        self._store = store if store is not None else self._construire_magasin()

    def _construire_magasin(self) -> FileStore:
        """
        Construit le magasin demandé par la configuration.

        `GALSEN_FILE_BACKEND` prime sur `GALSEN_STORAGE_BACKEND` : `filesystem`
        et `s3` n'ont de sens que pour des fichiers, et les imposer aux autres
        services par la variable générale serait faux.

        Une valeur inconnue **n'est pas devinée** : elle est signalée et le
        magasin par défaut s'applique, comme partout ailleurs dans la
        configuration de la plateforme.
        """
        demande = os.getenv(self.BACKEND_ENV, "").strip().lower()
        if demande and demande not in self.BACKENDS:
            self._logger.error(
                "%s='%s' inconnu (valeurs acceptées : %s) — magasin par défaut appliqué",
                self.BACKEND_ENV, demande, ", ".join(self.BACKENDS),
            )
            demande = ""
        if not demande:
            demande = storage_backend()

        if demande == "sqlite":
            from src.storage.sqlite_file_store import SQLiteFileStore
            return SQLiteFileStore()
        if demande == "filesystem":
            from .store_fs import FileSystemFileStore
            return FileSystemFileStore()
        if demande == "s3":
            from .store_s3 import S3FileStore
            return S3FileStore()
        return InMemoryFileStore()

    def _validate_file(
        self,
        name: str,
        content_type: str,
        data: bytes,
        max_size: Optional[int],
    ) -> Optional[str]:
        """Valide un fichier et retourne un message d'erreur, ou None si valide."""
        if not name:
            return "Le nom du fichier est requis."
        if not data:
            return "Le contenu du fichier est vide."
        size_limit = max_size or DEFAULT_MAX_FILE_SIZE
        if len(data) > size_limit:
            size_mb = size_limit / (1024 * 1024)
            return f"Le fichier dépasse la taille maximale autorisée ({size_mb:.0f} Mo)."
        return None

    def upload_file(
        self,
        name: str,
        content_type: str,
        data: bytes,
        description: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        uploaded_by: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        max_size: Optional[int] = None,
    ) -> FileUploadResult:
        """Téléverse un fichier après validation."""
        try:
            # Valider
            error = self._validate_file(name, content_type, data, max_size)
            if error is not None:
                return FileUploadResult(success=False, error=error)

            # Créer l'entrée
            file = FileItem(
                name=name,
                content_type=content_type,
                size=len(data),
                data=data,
                category=get_category_for_content_type(content_type),
                description=description,
                tags=tags or {},
                uploaded_by=uploaded_by,
                source=source,
                metadata=metadata or {},
            )
            file_id = self._store.save(file)
            self._logger.info("Fichier téléversé : %s (%s, %d octets)", name, content_type, len(data))
            return FileUploadResult(success=True, file_id=file_id, file=file)
        except Exception as error:
            self._logger.warning("Échec du téléversement du fichier %s : %s", name, error)
            return FileUploadResult(success=False, error=str(error))

    def get_file(self, file_id: str) -> Optional[FileItem]:
        """Retourne un fichier par identifiant, ou None si absent."""
        try:
            return self._store.get(file_id)
        except Exception as error:
            self._logger.warning("Échec de la lecture du fichier %s : %s", file_id, error)
            return None

    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        content_type: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> List[FileSummary]:
        """Retourne les fichiers filtrés, **sans leur contenu** (ADR-016)."""
        try:
            return self._store.list_files(
                limit=limit,
                offset=offset,
                category=category,
                content_type=content_type,
                uploaded_by=uploaded_by,
            )
        except Exception as error:
            self._logger.warning("Échec du filtrage des fichiers : %s", error)
            return []

    def delete_file(self, file_id: str) -> bool:
        """Supprime un fichier ; retourne False si absent."""
        try:
            result = self._store.delete(file_id)
            if result:
                self._logger.info("Fichier supprimé : %s", file_id)
            return result
        except Exception as error:
            self._logger.warning("Échec de la suppression du fichier %s : %s", file_id, error)
            return False

    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier."""
        try:
            return self._store.update_metadata(file_id, metadata)
        except Exception as error:
            self._logger.warning(
                "Échec de la mise à jour des métadonnées du fichier %s : %s",
                file_id,
                error,
            )
            return False

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        try:
            return self._store.stats()
        except Exception as error:
            self._logger.warning("Échec du calcul des statistiques des fichiers : %s", error)
            return {}

    def clear(self) -> int:
        """Supprime tous les fichiers et retourne le nombre supprimé."""
        try:
            return self._store.clear()
        except Exception as error:
            self._logger.warning("Échec de la suppression des fichiers : %s", error)
            return 0