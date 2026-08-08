"""
Persistance SQLite pour GalSen IA (ADR-005).

Le répertoire de données est configurable via la variable d'environnement
GALSEN_DATA_DIR (défaut : "data"). La sélection du backend de stockage des
moteurs se fait via GALSEN_STORAGE_BACKEND ("in-memory" par défaut, ou
"sqlite").
"""

from .base_repository import BaseRepository
from .sqlite_store import SQLiteMemoryStore
from .sqlite_model_store import SQLiteModelStore
from .sqlite_knowledge_store import SQLiteKnowledgeStore
from .sqlite_notification_store import SQLiteNotificationStore
from .sqlite_calendar_store import SQLiteCalendarStore
from .sqlite_email_store import SQLiteEmailStore
from .sqlite_cloud_store import SQLiteCloudStore
from .sqlite_file_store import SQLiteFileStore
from .paths import default_sqlite_path

__all__ = [
    "BaseRepository",
    "SQLiteMemoryStore",
    "SQLiteModelStore",
    "SQLiteKnowledgeStore",
    "SQLiteNotificationStore",
    "SQLiteCalendarStore",
    "SQLiteEmailStore",
    "SQLiteCloudStore",
    "SQLiteFileStore",
    "default_sqlite_path",
]
