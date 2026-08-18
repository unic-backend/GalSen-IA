"""
Stockage SQLite des notifications.

Implémente l'interface NotificationStore en utilisant SQLite pour la persistance.
Suit le pattern des stores SQLite existants (PRAGMA, RLock, sérialisation JSON).
"""

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from src.services.notification.interfaces import NotificationStore
from src.services.notification.types import Notification, NotificationPriority, NotificationType
from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file


class SQLiteNotificationStore(NotificationStore):
    """Stockage de notifications soutenu par SQLite."""

    _COLUMNS = (
        "id", "notification_type", "title", "message", "priority",
        "recipient", "role", "source", "related_id", "metadata",
        "read", "read_at", "created_at",
    )

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Initialise le magasin SQLite.

        Args:
            db_path: Chemin vers le fichier SQLite (défaut: service_notifications.sqlite).
        """
        self.db_path = db_path or default_sqlite_path("service_notifications.sqlite")
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._lock = threading.RLock()
        self._persistent_conn: Optional[sqlite3.Connection] = None
        self._initialize_db()
        # Une base porte des mémoires, des connaissances et des e-mails ;
        # elle était créée en 0644, donc lisible par tout compte de la machine.
        secure_database_file(self.db_path)
        if self.db_path == ":memory:":
            self._persistent_conn = self._get_connection()

    def close(self) -> None:
        """Ferme la connexion persistante (:memory:) si elle existe."""
        if self._persistent_conn is not None:
            self._persistent_conn.close()
            self._persistent_conn = None

    def _get_connection(self) -> sqlite3.Connection:
        """Ouvre une connexion SQLite avec les PRAGMA requis."""
        if self.db_path == ":memory:":
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        prepare_connection(conn)
        return conn

    def _initialize_db(self) -> None:
        """Crée la table des notifications et ses index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    notification_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    recipient TEXT,
                    role TEXT,
                    source TEXT,
                    related_id TEXT,
                    metadata TEXT,
                    read INTEGER NOT NULL DEFAULT 0,
                    read_at REAL,
                    created_at REAL NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_created_at ON notifications(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_recipient ON notifications(recipient)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_type ON notifications(notification_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(read)")
            conn.commit()

    def _item_to_dict(self, item: Notification) -> Dict[str, Any]:
        """Convertit une Notification en dictionnaire pour SQLite."""
        return {
            "id": item.id,
            "notification_type": item.notification_type.value,
            "title": item.title,
            "message": item.message,
            "priority": item.priority.value,
            "recipient": item.recipient,
            "role": item.role,
            "source": item.source,
            "related_id": item.related_id,
            "metadata": json.dumps(item.metadata) if item.metadata else None,
            "read": 1 if item.read else 0,
            "read_at": item.read_at,
            "created_at": item.created_at,
        }

    def _dict_to_item(self, row: tuple) -> Notification:
        """Convertit une ligne SQLite en Notification."""
        d = dict(zip(self._COLUMNS, row))
        metadata = json.loads(d["metadata"]) if d.get("metadata") else {}
        return Notification(
            id=d["id"],
            notification_type=NotificationType(d["notification_type"]),
            title=d["title"],
            message=d["message"],
            priority=NotificationPriority(d["priority"]),
            recipient=d.get("recipient"),
            role=d.get("role"),
            source=d.get("source"),
            related_id=d.get("related_id"),
            metadata=metadata,
            read=bool(d["read"]),
            read_at=d.get("read_at"),
            created_at=d["created_at"],
        )

    def save(self, notification: Notification) -> str:
        """Enregistre une notification et retourne son identifiant."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                data = self._item_to_dict(notification)
                cursor.execute(
                    """INSERT OR REPLACE INTO notifications (
                        id, notification_type, title, message, priority,
                        recipient, role, source, related_id, metadata,
                        read, read_at, created_at
                    ) VALUES (
                        :id, :notification_type, :title, :message, :priority,
                        :recipient, :role, :source, :related_id, :metadata,
                        :read, :read_at, :created_at
                    )""",
                    data,
                )
                conn.commit()
            return notification.id

    def update(self, notification: Notification) -> bool:
        """Met à jour une notification existante ; False si elle n'existe pas.

        Explicite là où `save()` remplaçait silencieusement : l'appelant qui
        veut modifier le dit, et celui qui croit créer n'écrase rien par mégarde.
        """
        with self._lock:
            if self.get(notification.id) is None:
                return False
            self.save(notification)
            return True

    def get(self, notification_id: str) -> Optional[Notification]:
        """Retourne une notification par identifiant, ou None si absente."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM notifications WHERE id = ?",
                    (notification_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._dict_to_item(row)

    def list_notifications(
        self,
        limit: int = 100,
        offset: int = 0,
        unread_only: bool = False,
        notification_type: Optional[str] = None,
        recipient: Optional[str] = None,
        role: Optional[str] = None,
        min_priority: Optional[str] = None,
    ) -> List[Notification]:
        """Retourne les notifications filtrées, de la plus récente à la plus ancienne."""
        where_clauses: List[str] = []
        params: List[Any] = []

        if unread_only:
            where_clauses.append("read = 0")
        if notification_type is not None:
            where_clauses.append("notification_type = ?")
            params.append(notification_type)
        if recipient is not None:
            where_clauses.append("recipient = ?")
            params.append(recipient)
        if role is not None:
            where_clauses.append("role = ?")
            params.append(role)

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = "WHERE " + where_sql

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = f"""
                    SELECT * FROM notifications
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, [*params, limit, offset])
                rows = cursor.fetchall()

            items = [self._dict_to_item(row) for row in rows]

            # Filtre min_priority en Python (priorités relatives complexes)
            if min_priority is not None:
                ranking = {
                    "low": 1, "normal": 2, "high": 3, "urgent": 4,
                }
                min_val = ranking.get(min_priority, 0)
                items = [
                    n for n in items
                    if ranking.get(n.priority.value, 0) >= min_val
                ]

            return items

    def mark_read(self, notification_id: str) -> bool:
        """Marque une notification comme lue ; retourne False si absente."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE notifications SET read = 1, read_at = ? WHERE id = ? AND read = 0",
                    (time.time(), notification_id),
                )
                updated = cursor.rowcount > 0
                conn.commit()
            return updated

    def mark_all_read(self, recipient: Optional[str] = None) -> int:
        """Marque toutes les notifications comme lues pour un destinataire."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if recipient is not None:
                    cursor.execute(
                        "UPDATE notifications SET read = 1, read_at = ? WHERE recipient = ? AND read = 0",
                        (time.time(), recipient),
                    )
                else:
                    cursor.execute(
                        "UPDATE notifications SET read = 1, read_at = ? WHERE read = 0",
                        (time.time(),),
                    )
                count = cursor.rowcount
                conn.commit()
            return count

    def delete(self, notification_id: str) -> bool:
        """Supprime une notification ; retourne False si absente."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
            return deleted

    def stats(self, recipient: Optional[str] = None) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if recipient:
                    cursor.execute("SELECT COUNT(*) FROM notifications WHERE recipient = ?", (recipient,))
                    total = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM notifications WHERE read = 0 AND recipient = ?", (recipient,))
                    unread = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT notification_type, COUNT(*) FROM notifications WHERE recipient = ? GROUP BY notification_type",
                        (recipient,),
                    )
                    by_type = dict(cursor.fetchall())
                    cursor.execute(
                        "SELECT priority, COUNT(*) FROM notifications WHERE recipient = ? GROUP BY priority",
                        (recipient,),
                    )
                    by_priority = dict(cursor.fetchall())
                else:
                    cursor.execute("SELECT COUNT(*) FROM notifications")
                    total = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM notifications WHERE read = 0")
                    unread = cursor.fetchone()[0]
                    cursor.execute("SELECT notification_type, COUNT(*) FROM notifications GROUP BY notification_type")
                    by_type = dict(cursor.fetchall())
                    cursor.execute("SELECT priority, COUNT(*) FROM notifications GROUP BY priority")
                    by_priority = dict(cursor.fetchall())

            return {
                "total": total,
                "unread": unread,
                "by_type": by_type,
                "by_priority": by_priority,
            }

    def clear(self) -> int:
        """Supprime toutes les notifications et retourne le nombre supprimé."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM notifications")
                count = cursor.rowcount
                conn.commit()
            return count

    def count(self) -> int:
        """Retourne le nombre total de notifications."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM notifications")
                return cursor.fetchone()[0]