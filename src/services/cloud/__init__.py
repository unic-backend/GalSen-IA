"""
Service de stockage cloud.

Permet de téléverser, lister, télécharger et gérer des fichiers dans
le cloud GalSen IA. Le backend par défaut est le stockage local en
mémoire ; S3, GCS et Azure peuvent être branchés via le contrat
`CloudStore`.

Référence : VOLET 02, Chapitre 09 (Integration).
"""

from .interfaces import CloudManager, CloudStore
from .manager import CloudManagerImpl
from .store import InMemoryCloudStore
from .store_fs import FileSystemCloudStore
from .store_s3 import S3CloudStore
from .types import (
    CloudFileCategory,
    CloudFileItem,
    CloudProvider,
    CloudStats,
    CloudSyncResult,
    generate_cloud_file_id,
)

__all__ = [
    "CloudFileCategory",
    "CloudFileItem",
    "CloudManager",
    "CloudManagerImpl",
    "CloudProvider",
    "CloudStats",
    "CloudStore",
    "CloudSyncResult",
    "FileSystemCloudStore",
    "InMemoryCloudStore",
    "S3CloudStore",
    "generate_cloud_file_id",
]