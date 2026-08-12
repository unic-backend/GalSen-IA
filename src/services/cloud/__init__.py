"""
Service de stockage cloud.

Permet de téléverser, lister, télécharger et gérer des fichiers dans
le cloud GalSen IA. Le backend par défaut est le stockage local en
mémoire ; S3, GCS et Azure peuvent être branchés via le contrat
`CloudManager`.

Depuis ADR-016, ce service ne stocke plus rien : il traduit les routes
`/cloud/*`, dépréciées, vers le service de fichiers.

Référence : VOLET 02, Chapitre 09 (Integration).
"""

from .interfaces import CloudManager
from .manager import CloudManagerImpl
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
    "CloudSyncResult",
    "generate_cloud_file_id",
]