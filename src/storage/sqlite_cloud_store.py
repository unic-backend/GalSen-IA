"""
Stockage SQLite des fichiers cloud.

Implémente l'interface CloudStore avec deux tables :
- cloud_files : métadonnées du fichier
- cloud_data : données binaires séparées (évite de charger les blobs au listing)
"""

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from services.cloud.interfaces import CloudStore
from services.cloud.types import CloudFileItem, CloudProvider, CloudFileCategory
from storage.paths import default_sqlite_path


class SQLiteCloudStore(CloudStore):
    """Stockage de fichiers cloud soutenu par SQLite."""

    _COLUMNS = (
        "id", "name", "content_type", "size", "provider", "category",
        "path", "uploaded_by", "metadata", "created_at", "updated_at",
    )

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or default_sqlite_path("service_cloud.sqlite")
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._lock = threading.RLock()
        self._persistent_conn: Optional[sqlite3.Connection] = None
        self._initialize_db()
        if self.db_path == ":memory:":
            self._persistent_conn = self._get_connection()

    def close(self) -> None:
        """Ferme la connexion persistante (:memory:) si elle existe."""
        if self._persistent_conn is not None:
            self._persistent_conn.close()
            self._persistent_conn = None

    def _get_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _initialize_db(self) -> None:
        """Crée les tables cloud_files + cloud_data et leurs index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cloud_files (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    category TEXT NOT NULL,
                    path TEXT,
                    uploaded_by TEXT,
                    metadata TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cloud_data (
                    file_id TEXT PRIMARY KEY,
                    data BLOB NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloud_provider ON cloud_files(provider)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloud_category ON cloud_files(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloud_uploaded_by ON cloud_files(uploaded_by)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cloud_created_at ON cloud_files(created_at DESC)")
            conn.commit()

    def _item_to_dict(self, item: CloudFileItem) -> Dict[str, Any]:
        """Convertit un CloudFileItem en dictionnaire pour SQLite."""
        return {
            "id": item.id,
            "name": item.name,
            "content_type": item.content_type,
            "size": item.size,
            "provider": item.provider.value,
            "category": item.category.value,
            "path": item.path,
            "uploaded_by": item.uploaded_by,
            "metadata": json.dumps(item.metadata) if item.metadata else None,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def _dict_to_item(self, row: tuple) -> CloudFileItem:
        """Convertit une ligne SQLite en CloudFileItem."""
        d = dict(zip(self._COLUMNS, row))
        return CloudFileItem(
            id=d["id"],
            name=d["name"],
            content_type=d["content_type"],
            size=d["size"],
            provider=CloudProvider(d["provider"]),
            category=CloudFileCategory(d["category"]),
            path=d.get("path"),
            uploaded_by=d.get("uploaded_by"),
            metadata=json.loads(d["metadata"]) if d.get("metadata") else {},
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    def save(self, item: CloudFileItem, data: bytes) -> str:
        """Enregistre un fichier cloud et retourne son identifiant."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                row = self._item_to_dict(item)
                cursor.execute(
                    """INSERT OR REPLACE INTO cloud_files (
                        id, name, content_type, size, provider, category,
                        path, uploaded_by, metadata, created_at, updated_at
                    ) VALUES (
                        :id, :name, :content_type, :size, :provider, :category,
                        :path, :uploaded_by, :metadata, :created_at, :updated_at
                    )""",
                    row,
                )
                cursor.execute(
                    "INSERT INTO cloud_data (file_id, data) VALUES (?, ?)",
                    (item.id, data),
                )
                conn.commit()
            return item.id

    def get(self, file_id: str) -> Optional[CloudFileItem]:
        """Retourne un fichier cloud par identifiant (métadonnées seulement), ou None si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM cloud_files WHERE id = ?", (file_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._dict_to_item(row)

    def get_data(self, file_id: str) -> Optional[bytes]:
        """Retourne les données binaires d'un fichier cloud."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT data FROM cloud_data WHERE file_id = ?", (file_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                return row[0]

    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> List[CloudFileItem]:
        """Retourne les fichiers filtrés (métadonnées seulement), du plus récent au plus ancien."""
        where_clauses: List[str] = []
        params: List[Any] = []

        if provider is not None:
            where_clauses.append("provider = ?")
            params.append(provider)
        if category is not None:
            where_clauses.append("category = ?")
            params.append(category)
        if uploaded_by is not None:
            where_clauses.append("uploaded_by = ?")
            params.append(uploaded_by)

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = "WHERE " + where_sql

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = f"""
                    SELECT * FROM cloud_files
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, [*params, limit, offset])
                rows = cursor.fetchall()
            return [self._dict_to_item(row) for row in rows]

    def delete(self, file_id: str) -> bool:
        """Supprime un fichier cloud et ses données ; retourne False si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM cloud_files WHERE id = ?", (file_id,))
                if cursor.fetchone() is None:
                    return False
                cursor.execute("DELETE FROM cloud_data WHERE file_id = ?", (file_id,))
                cursor.execute("DELETE FROM cloud_files WHERE id = ?", (file_id,))
                conn.commit()
            return True

    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier ; retourne False si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT metadata FROM cloud_files WHERE id = ?", (file_id,))
                row = cursor.fetchone()
                if row is None:
                    return False
                existing = json.loads(row[0]) if row[0] else {}
                existing.update(metadata)
                cursor.execute(
                    "UPDATE cloud_files SET metadata = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(existing), time.time(), file_id),
                )
                conn.commit()
            return True

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM cloud_files")
                total = cursor.fetchone()[0]
                cursor.execute("SELECT COALESCE(SUM(size), 0) FROM cloud_files")
                total_size = cursor.fetchone()[0]
                cursor.execute("SELECT category, COUNT(*) FROM cloud_files GROUP BY category")
                by_category = dict(cursor.fetchall())
                cursor.execute("SELECT provider, COUNT(*) FROM cloud_files GROUP BY provider")
                by_provider = dict(cursor.fetchall())
            return {
                "total": total,
                "total_size": total_size,
                "by_category": by_category,
                "by_provider": by_provider,
            }

    def clear(self) -> int:
        """Supprime tous les fichiers et données cloud."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cloud_data")
                cursor.execute("DELETE FROM cloud_files")
                count = cursor.rowcount
                conn.commit()
            return count

    def count(self) -> int:
        """Retourne le nombre total de fichiers."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM cloud_files")
                return cursor.fetchone()[0]

    def total_size(self) -> int:
        """Retourne la taille totale des fichiers stockés."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COALESCE(SUM(size), 0) FROM cloud_files")
                return cursor.fetchone()[0]