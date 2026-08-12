"""
Stockage SQLite des fichiers.

Implémente l'interface FileStore avec une table unique :
- files : métadonnées + données binaires (BLOB inline)

Les tags sont stockés en JSON et filtrés en Python (post-filter).
"""

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from src.services.file.interfaces import FileStore
from src.services.file.types import FileCategory, FileItem, FileSummary
from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file


class SQLiteFileStore(FileStore):
    """Stockage de fichiers soutenu par SQLite."""

    _COLUMNS = (
        "id", "name", "content_type", "size", "data", "category",
        "description", "tags", "uploaded_by", "source", "metadata",
        "created_at", "updated_at",
    )

    # Les mêmes colonnes sans le contenu (ADR-016). Lister faisait
    # `SELECT * FROM files`, et `*` inclut le BLOB : 30 fichiers de 2 Mo
    # faisaient lire 60 Mo pour une réponse qui jette les octets.
    _SUMMARY_COLUMNS = tuple(colonne for colonne in _COLUMNS if colonne != "data")

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or default_sqlite_path("service_files.sqlite")
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
        if self.db_path == ":memory:":
            return self._persistent_conn or sqlite3.connect("file::memory:?cache=shared", uri=True)
        conn = sqlite3.connect(self.db_path)
        prepare_connection(conn)
        return conn

    def _initialize_db(self) -> None:
        """Crée la table files et ses index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    data BLOB NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    tags TEXT,
                    uploaded_by TEXT,
                    source TEXT,
                    metadata TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_name ON files(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_category ON files(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_uploaded_by ON files(uploaded_by)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at DESC)")
            conn.commit()

    def _item_to_dict(self, item: FileItem) -> Dict[str, Any]:
        """Convertit un FileItem en dictionnaire pour SQLite."""
        return {
            "id": item.id,
            "name": item.name,
            "content_type": item.content_type,
            "size": item.size,
            "data": item.data,
            "category": item.category.value,
            "description": item.description,
            "tags": json.dumps(item.tags) if item.tags else None,
            "uploaded_by": item.uploaded_by,
            "source": item.source,
            "metadata": json.dumps(item.metadata) if item.metadata else None,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def _dict_to_item(self, row: tuple) -> FileItem:
        """Convertit une ligne SQLite en FileItem."""
        d = dict(zip(self._COLUMNS, row))
        return FileItem(
            id=d["id"],
            name=d["name"],
            content_type=d["content_type"],
            size=d["size"],
            data=d["data"],
            category=FileCategory(d["category"]),
            description=d.get("description"),
            tags=json.loads(d["tags"]) if d.get("tags") else {},
            uploaded_by=d.get("uploaded_by"),
            source=d.get("source"),
            metadata=json.loads(d["metadata"]) if d.get("metadata") else {},
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    def _dict_to_summary(self, row: tuple) -> FileSummary:
        """Convertit une ligne sans contenu en résumé de fichier."""
        d = dict(zip(self._SUMMARY_COLUMNS, row))
        return FileSummary(
            id=d["id"],
            name=d["name"],
            content_type=d["content_type"],
            size=d["size"],
            category=FileCategory(d["category"]),
            description=d.get("description"),
            tags=json.loads(d["tags"]) if d.get("tags") else {},
            uploaded_by=d.get("uploaded_by"),
            source=d.get("source"),
            metadata=json.loads(d["metadata"]) if d.get("metadata") else {},
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    def save(self, file: FileItem) -> str:
        """Enregistre un fichier et retourne son identifiant."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                data = self._item_to_dict(file)
                cursor.execute(
                    """INSERT INTO files (
                        id, name, content_type, size, data, category,
                        description, tags, uploaded_by, source, metadata,
                        created_at, updated_at
                    ) VALUES (
                        :id, :name, :content_type, :size, :data, :category,
                        :description, :tags, :uploaded_by, :source, :metadata,
                        :created_at, :updated_at
                    )""",
                    data,
                )
                conn.commit()
            return file.id

    def get(self, file_id: str) -> Optional[FileItem]:
        """Retourne un fichier par identifiant, ou None si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._dict_to_item(row)

    def get_by_name(self, name: str) -> Optional[FileItem]:
        """Retourne un fichier par nom exact, ou None si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM files WHERE name = ?", (name,))
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._dict_to_item(row)

    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        content_type: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> List[FileSummary]:
        """
        Retourne les fichiers filtrés, du plus récent au plus ancien, **sans
        leur contenu** (ADR-016).

        Le contenu se demande fichier par fichier, avec `get`.
        """
        where_clauses: List[str] = []
        params: List[Any] = []

        if category is not None:
            where_clauses.append("category = ?")
            params.append(category)
        if content_type is not None:
            where_clauses.append("content_type = ?")
            params.append(content_type)
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
                    SELECT {','.join(self._SUMMARY_COLUMNS)} FROM files
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, [*params, limit, offset])
                rows = cursor.fetchall()

            items = [self._dict_to_summary(row) for row in rows]

            # Post-filter pour les tags (clé-valeur JSON)
            if tags:
                def matches_tags(file: FileSummary) -> bool:
                    return all(
                        file.tags.get(key) == value
                        for key, value in tags.items()
                    )
                items = [item for item in items if matches_tags(item)]

            return items

    def delete(self, file_id: str) -> bool:
        """Supprime un fichier ; retourne False si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
            return deleted

    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier ; retourne False si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT metadata FROM files WHERE id = ?", (file_id,))
                row = cursor.fetchone()
                if row is None:
                    return False
                existing = json.loads(row[0]) if row[0] else {}
                existing.update(metadata)
                cursor.execute(
                    "UPDATE files SET metadata = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(existing), time.time(), file_id),
                )
                conn.commit()
            return True

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées sur les fichiers."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM files")
                total = cursor.fetchone()[0]
                cursor.execute("SELECT COALESCE(SUM(size), 0) FROM files")
                total_size = cursor.fetchone()[0]
                cursor.execute("SELECT category, COUNT(*) FROM files GROUP BY category")
                by_category = dict(cursor.fetchall())
                cursor.execute("SELECT content_type, COUNT(*) FROM files GROUP BY content_type")
                by_content_type = dict(cursor.fetchall())
            return {
                "total": total,
                "total_size": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "by_category": by_category,
                "by_content_type": by_content_type,
            }

    def clear(self) -> int:
        """Supprime tous les fichiers et retourne le nombre supprimé."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM files")
                count = cursor.rowcount
                conn.commit()
            return count

    def count(self) -> int:
        """Retourne le nombre total de fichiers."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM files")
                return cursor.fetchone()[0]

    def total_size(self) -> int:
        """Retourne la taille totale des fichiers stockés."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COALESCE(SUM(size), 0) FROM files")
                return cursor.fetchone()[0]