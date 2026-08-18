"""
Services backend GalSen IA.

Regroupe les services de la couche applicative : notifications, recherche
unifiée, gestion de fichiers, cloud, calendrier et email.
Chaque service suit le même pattern que les moteurs (interfaces abstraites
+ implémentation mémoire + façade best-effort).

Référence : VOLET 02, Chapitres 03 (Backend Architecture),
07 (Data Architecture), 09 (Integration Architecture).

Le client API SDK est dans ``src.client``.
"""

from .calendar import (
    CalendarEvent,
    CalendarEventResult,
    CalendarManager,
    CalendarManagerImpl,
    CalendarStore,
    EventStatus,
    EventVisibility,
    InMemoryCalendarStore as InMemoryCalendarStoreImpl,
    generate_event_id,
)
from .cloud import (
    CloudFileCategory,
    CloudFileItem,
    CloudManager,
    CloudManagerImpl,
    CloudProvider,
    CloudSyncResult,
    generate_cloud_file_id,
)
from .email import (
    EmailAttachment,
    EmailManager,
    EmailManagerImpl,
    EmailMessage,
    EmailSendResult,
    EmailStatus,
    EmailStore,
    InMemoryEmailStore as InMemoryEmailStoreImpl,
    generate_email_id,
)
from .file import (
    DEFAULT_MAX_FILE_SIZE,
    FileCategory,
    FileItem,
    FileSummary,
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
    # Cloud
    "CloudFileCategory",
    "CloudFileItem",
    "CloudManager",
    "CloudManagerImpl",
    "CloudProvider",
    "CloudSyncResult",
    "generate_cloud_file_id",
    # Calendar
    "CalendarEvent",
    "CalendarEventResult",
    "CalendarManager",
    "CalendarManagerImpl",
    "CalendarStore",
    "EventStatus",
    "EventVisibility",
    "InMemoryCalendarStoreImpl",
    "generate_event_id",
    # Email
    "EmailAttachment",
    "EmailManager",
    "EmailManagerImpl",
    "EmailMessage",
    "EmailSendResult",
    "EmailStatus",
    "EmailStore",
    "InMemoryEmailStoreImpl",
    "generate_email_id",
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
    "FileSummary",
    "FileManager",
    "FileManagerImpl",
    "FileStore",
    "FileUploadResult",
    "InMemoryFileStoreImpl",
    "generate_file_id",
]