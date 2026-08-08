"""
Modèles de données du service Cloud.

Définit les types partagés : éléments de stockage cloud, fournisseurs,
catégories et générateur d'identifiants.

Ce module n'a aucune dépendance externe.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def generate_cloud_file_id() -> str:
    """Génère un identifiant unique de fichier cloud (préfixe ``cloud_``)."""
    return f"cloud_{uuid.uuid4().hex[:12]}"


class CloudProvider(Enum):
    """Fournisseur de stockage cloud supporté."""

    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"


class CloudFileCategory(Enum):
    """Catégorie d'un fichier stocké dans le cloud."""

    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DATA = "data"
    ARCHIVE = "archive"
    CODE = "code"
    OTHER = "other"


@dataclass
class CloudFileItem:
    """
    Élément de fichier dans le stockage cloud.

    Représente un fichier téléversé vers un fournisseur cloud.
    """

    name: str
    content_type: str
    size: int
    provider: CloudProvider = CloudProvider.LOCAL
    category: CloudFileCategory = CloudFileCategory.OTHER
    path: Optional[str] = None
    uploaded_by: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=generate_cloud_file_id)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        """Normalise le provider et la catégorie après l'initialisation."""
        if isinstance(self.provider, str):
            try:
                self.provider = CloudProvider(self.provider)
            except ValueError:
                self.provider = CloudProvider.LOCAL
        if isinstance(self.category, str):
            try:
                self.category = CloudFileCategory(self.category)
            except ValueError:
                self.category = CloudFileCategory.OTHER

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'élément en dictionnaire (sans les données binaires)."""
        created_iso = datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat()
        updated_iso = datetime.fromtimestamp(self.updated_at, tz=timezone.utc).isoformat()
        result: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "content_type": self.content_type,
            "size": self.size,
            "provider": self.provider.value,
            "category": self.category.value,
            "created_at": created_iso,
            "updated_at": updated_iso,
        }
        if self.path is not None:
            result["path"] = self.path
        if self.uploaded_by is not None:
            result["uploaded_by"] = self.uploaded_by
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "CloudFileItem":
        """Construit un élément à partir d'un dictionnaire."""
        raw_provider = data.get("provider", "local")
        if isinstance(raw_provider, CloudProvider):
            provider = raw_provider
        else:
            try:
                provider = CloudProvider(raw_provider)
            except ValueError:
                provider = CloudProvider.LOCAL

        raw_category = data.get("category", "other")
        if isinstance(raw_category, CloudFileCategory):
            category = raw_category
        else:
            try:
                category = CloudFileCategory(raw_category)
            except ValueError:
                category = CloudFileCategory.OTHER

        return cls(
            name=data.get("name", ""),
            content_type=data.get("content_type", "application/octet-stream"),
            size=data.get("size", 0),
            provider=provider,
            category=category,
            path=data.get("path"),
            uploaded_by=data.get("uploaded_by"),
            metadata=data.get("metadata") or {},
            id=data.get("id", generate_cloud_file_id()),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


@dataclass
class CloudSyncResult:
    """Résultat d'une opération de synchronisation cloud."""

    success: bool
    message: str
    file_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class CloudStats:
    """Statistiques agrégées du stockage cloud."""

    total: int
    total_size: int
    by_category: Dict[str, int]
    by_provider: Dict[str, int]