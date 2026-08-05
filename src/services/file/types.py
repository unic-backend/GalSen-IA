"""
Modèles de données du service de fichiers.

Définit les types partagés : fichiers, métadonnées, catégories
de fichiers et générateur d'identifiants.

Ce module n'a aucune dépendance externe.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


def generate_file_id() -> str:
    """Génère un identifiant unique de fichier (préfixe ``file_``)."""
    return f"file_{uuid.uuid4().hex[:12]}"


class FileCategory(str, Enum):
    """Catégorie de fichier dans la plateforme GalSen IA."""

    DOCUMENT = "document"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DATA = "data"
    CONFIG = "config"
    LOG = "log"
    OTHER = "other"


# Catégories de contenu courantes avec leur catégorie associée
CONTENT_TYPE_CATEGORIES: Dict[str, FileCategory] = {
    # Documents
    "application/pdf": FileCategory.DOCUMENT,
    "application/msword": FileCategory.DOCUMENT,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileCategory.DOCUMENT,
    "application/vnd.ms-excel": FileCategory.DATA,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileCategory.DATA,
    "application/vnd.ms-powerpoint": FileCategory.DOCUMENT,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": FileCategory.DOCUMENT,
    "text/plain": FileCategory.DOCUMENT,
    "text/csv": FileCategory.DATA,
    "text/html": FileCategory.DOCUMENT,
    "text/markdown": FileCategory.DOCUMENT,
    "application/json": FileCategory.DATA,
    "application/xml": FileCategory.DATA,
    "application/yaml": FileCategory.CONFIG,
    # Images
    "image/jpeg": FileCategory.IMAGE,
    "image/png": FileCategory.IMAGE,
    "image/gif": FileCategory.IMAGE,
    "image/webp": FileCategory.IMAGE,
    "image/svg+xml": FileCategory.IMAGE,
    "image/tiff": FileCategory.IMAGE,
}

# Taille maximale par défaut (10 Mo)
DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024


def get_category_for_content_type(content_type: str) -> FileCategory:
    """Retourne la catégorie de fichier pour un type MIME donné."""
    return CONTENT_TYPE_CATEGORIES.get(content_type, FileCategory.OTHER)


def is_content_type_allowed(
    content_type: str,
    allowed_types: Optional[set] = None,
) -> bool:
    """Vérifie si un type MIME est autorisé."""
    if allowed_types is None:
        return True
    return content_type in allowed_types


@dataclass
class FileItem:
    """
    Fichier dans la plateforme GalSen IA.

    Stocke le contenu binaire, les métadonnées et la traçabilité
    du fichier. La persistence est en mémoire ; un backend de stockage
    (disque, S3, etc.) peut être branché ultérieurement.
    """

    name: str
    content_type: str
    size: int
    data: bytes
    category: FileCategory = FileCategory.OTHER
    description: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    uploaded_by: Optional[str] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=generate_file_id)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self, include_data: bool = False) -> Dict[str, Any]:
        """Sérialise le fichier en dictionnaire.

        Args:
            include_data: Si True, inclut le contenu binaire (base64).
                         Par défaut False pour éviter les réponses volumineuses.
        """
        import base64

        created_iso = datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat()
        updated_iso = datetime.fromtimestamp(self.updated_at, tz=timezone.utc).isoformat()

        result: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "content_type": self.content_type,
            "size": self.size,
            "category": self.category.value,
            "created_at": created_iso,
            "updated_at": updated_iso,
        }
        optional_fields = {
            "description": self.description,
            "uploaded_by": self.uploaded_by,
            "source": self.source,
        }
        for key, value in optional_fields.items():
            if value is not None:
                result[key] = value
        if self.tags:
            result["tags"] = self.tags
        if include_data:
            result["data"] = base64.b64encode(self.data).decode("utf-8")
        elif self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_mapping(cls, data: Dict[str, Any]) -> "FileItem":
        """Construit un fichier à partir d'un dictionnaire."""
        import base64

        raw_data = data.get("data", b"")
        if isinstance(raw_data, str):
            raw_data = base64.b64decode(raw_data)

        content_type = data.get("content_type", "application/octet-stream")
        category = get_category_for_content_type(content_type)

        return cls(
            name=data.get("name", "unknown"),
            content_type=content_type,
            size=data.get("size", len(raw_data)),
            data=raw_data,
            category=category,
            description=data.get("description"),
            tags=data.get("tags") or {},
            uploaded_by=data.get("uploaded_by"),
            source=data.get("source"),
            metadata=data.get("metadata") or {},
            id=data.get("id", generate_file_id()),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


@dataclass
class FileUploadResult:
    """Résultat d'un téléversement de fichier."""

    success: bool
    file_id: Optional[str] = None
    error: Optional[str] = None
    file: Optional[FileItem] = None


@dataclass
class FileValidationError:
    """Erreur de validation d'un fichier."""

    field: str
    message: str
    code: str