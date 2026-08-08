"""
Contrats du service Cloud.

Définit les interfaces abstraites `CloudStore` et `CloudManager`.
Tout backend de stockage cloud (local, S3, GCS, Azure) peut être branché
à l'avenir sans modifier le code appelant.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import CloudFileItem, CloudProvider, CloudSyncResult


class CloudStore(ABC):
    """Contrat de stockage des fichiers cloud."""

    @abstractmethod
    def save(self, item: CloudFileItem, data: bytes) -> str:
        """Enregistre un fichier cloud et retourne son identifiant."""

    @abstractmethod
    def get(self, file_id: str) -> Optional[CloudFileItem]:
        """Retourne un fichier cloud par identifiant, ou None si absent."""

    @abstractmethod
    def get_data(self, file_id: str) -> Optional[bytes]:
        """Retourne les données binaires d'un fichier cloud."""

    @abstractmethod
    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> List[CloudFileItem]:
        """Retourne les fichiers filtrés, du plus récent au plus ancien."""

    @abstractmethod
    def delete(self, file_id: str) -> bool:
        """Supprime un fichier cloud ; retourne False si absent."""

    @abstractmethod
    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier ; retourne False si absent."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime tous les fichiers et retourne le nombre supprimé."""

    @abstractmethod
    def count(self) -> int:
        """Retourne le nombre total de fichiers."""

    @abstractmethod
    def total_size(self) -> int:
        """Retourne la taille totale des fichiers stockés."""


class CloudManager(ABC):
    """Contrat du gestionnaire cloud, façade du service."""

    @abstractmethod
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

    @abstractmethod
    def get_file(self, file_id: str) -> Optional[CloudFileItem]:
        """Retourne un fichier cloud par identifiant."""

    @abstractmethod
    def download(self, file_id: str) -> Optional[bytes]:
        """Télécharge les données d'un fichier cloud."""

    @abstractmethod
    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> List[CloudFileItem]:
        """Retourne les fichiers filtrés."""

    @abstractmethod
    def delete(self, file_id: str) -> bool:
        """Supprime un fichier cloud ; retourne False si absent."""

    @abstractmethod
    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime tous les fichiers et retourne le nombre supprimé."""