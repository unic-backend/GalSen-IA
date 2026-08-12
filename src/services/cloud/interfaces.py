"""
Contrats du service Cloud.

Définit l'interface abstraite `CloudManager`.

`CloudStore` a été retiré avec les quatre magasins cloud (ADR-016) : ce
service ne stocke plus rien, il traduit les routes dépréciées `/cloud/*`
vers le service de fichiers. Le choix du magasin — mémoire, SQLite, disque,
S3 — se fait là-bas, par `GALSEN_FILE_BACKEND`.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import CloudFileItem, CloudProvider, CloudSyncResult


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