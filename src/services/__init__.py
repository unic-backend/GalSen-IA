"""
Services backend GalSen IA.

Regroupe les services de la couche applicative : notifications, recherche
unifiée et gestion de fichiers. Chaque service suit le même pattern que
les moteurs (interfaces abstraites + implémentation mémoire + façade
best-effort).

Référence : VOLET 02, Chapitres 03 (Backend Architecture),
07 (Data Architecture), 09 (Integration Architecture).
"""

from .file import (
    DEFAULT_MAX_FILE_SIZE,
    FileCategory,
    FileItem,
    FileManager,
    FileManagerImpl,
    FileStore,
    FileUploadResult,
    InMemoryFileStore as InMemoryFileStoreImpl,
    generate_file_id,
)
from .notification import (
    InMemoryNotificationStore as InMemoryNotificationStoreImpl,
    Notification,
    NotificationManager,
    NotificationManagerImpl,
    NotificationPriority,
    NotificationStore,
    NotificationType,
)
from .search import (
    SearchManager,
    SearchManagerImpl,
    SearchProvider,
    SearchQuery,
    SearchResponse,
    SearchResultItem,
    SearchSort,
    SearchSource,
)

__all__ = [
    # Notification
    "Notification",
    "NotificationManager",
    "NotificationManagerImpl",
    "NotificationPriority",
    "NotificationStore",
    "NotificationType",
    "InMemoryNotificationStoreImpl",
    # Search
    "SearchManager",
    "SearchManagerImpl",
    "SearchProvider",
    "SearchQuery",
    "SearchResponse",
    "SearchResultItem",
    "SearchSort",
    "SearchSource",
    # File
    "DEFAULT_MAX_FILE_SIZE",
    "FileCategory",
    "FileItem",
    "FileManager",
    "FileManagerImpl",
    "FileStore",
    "FileUploadResult",
    "InMemoryFileStoreImpl",
    "generate_file_id",
]