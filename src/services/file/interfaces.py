"""
Contrats du service de fichiers.

Définit les interfaces abstraites `FileStore` et `FileManager`.
Tout backend de stockage (mémoire, disque, S3, MinIO) peut être branché
à l'avenir sans modifier le code appelant.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import FileCategory, FileItem, FileSummary, FileUploadResult


class FileStore(ABC):
    """Contrat de stockage des fichiers."""

    @abstractmethod
    def save(self, file: FileItem) -> str:
        """Enregistre un fichier et retourne son identifiant."""

    @abstractmethod
    def get(self, file_id: str) -> Optional[FileItem]:
        """Retourne un fichier par identifiant, ou None si absent."""

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[FileItem]:
        """Retourne un fichier par nom exact, ou None si absent."""

    @abstractmethod
    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        content_type: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> List[FileSummary]:
        """
        Retourne les fichiers filtrés, du plus récent au plus ancien,
        **sans leur contenu** (ADR-016).

        Lister ne charge pas les octets : `FileItem` les porte, si bien que
        lister cent fichiers les lisait tous pour une réponse qui les jette.
        Le contenu se demande fichier par fichier, avec `get`.
        """

    @abstractmethod
    def delete(self, file_id: str) -> bool:
        """Supprime un fichier ; retourne False si absent."""

    @abstractmethod
    def update_metadata(
        self,
        file_id: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """Met à jour les métadonnées d'un fichier ; retourne False si absent."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées sur les fichiers."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime tous les fichiers et retourne le nombre supprimé."""

    @abstractmethod
    def count(self) -> int:
        """Retourne le nombre total de fichiers."""

    @abstractmethod
    def total_size(self) -> int:
        """Retourne la taille totale des fichiers stockés."""


class FileManager(ABC):
    """Contrat du gestionnaire de fichiers, façade du service."""

    @abstractmethod
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

    @abstractmethod
    def get_file(self, file_id: str) -> Optional[FileItem]:
        """Retourne un fichier par identifiant, ou None si absent."""

    @abstractmethod
    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        content_type: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> List[FileSummary]:
        """Retourne les fichiers filtrés, **sans leur contenu** (ADR-016)."""

    @abstractmethod
    def delete_file(self, file_id: str) -> bool:
        """Supprime un fichier ; retourne False si absent."""

    @abstractmethod
    def update_metadata(
        self,
        file_id: str,
        metadata: Dict[str, Any],
    ) -> bool:
        """Met à jour les métadonnées d'un fichier."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime tous les fichiers et retourne le nombre supprimé."""