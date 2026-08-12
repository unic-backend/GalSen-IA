"""
Service de fichiers.

Permet de téléverser, lister, consulter et supprimer des fichiers dans
la plateforme GalSen IA. La validation des types MIME et des tailles est
intégrée au gestionnaire.

Référence : VOLET 02, Chapitres 03 (Backend), 07 (Data).
"""

from .interfaces import FileManager, FileStore
from .manager import FileManagerImpl
from .store import InMemoryFileStore
from .types import (
    DEFAULT_MAX_FILE_SIZE,
    CONTENT_TYPE_CATEGORIES,
    FileCategory,
    FileItem,
    FileSummary,
    FileUploadResult,
    FileValidationError,
    generate_file_id,
    get_category_for_content_type,
    is_content_type_allowed,
)

__all__ = [
    "CONTENT_TYPE_CATEGORIES",
    "DEFAULT_MAX_FILE_SIZE",
    "FileCategory",
    "FileItem",
    "FileSummary",
    "FileManager",
    "FileManagerImpl",
    "FileStore",
    "FileUploadResult",
    "FileValidationError",
    "InMemoryFileStore",
    "generate_file_id",
    "get_category_for_content_type",
    "is_content_type_allowed",
]