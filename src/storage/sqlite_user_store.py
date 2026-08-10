"""
Stockage SQLite des utilisateurs.

Implémente BaseRepository[User] avec SQLite pour la persistance.
Suit le pattern des stores SQLite existants (PRAGMA, RLock, sérialisation JSON).

Ajoute des méthodes spécifiques : get_by_email, get_by_oauth.
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base_repository import BaseRepository
from .paths import default_sqlite_path


@dataclass
class User:
    """Représente un utilisateur de la plateforme GalSen IA."""

    email: str
    name: str = ""
    role: str = "user"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    password_hash: Optional[str] = None
    oauth_provider: Optional[str] = None
    oauth_id: Optional[str] = None
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SQLiteUserStore(BaseRepository[User]):
    """Stockage d'utilisateurs soutenu par SQLite."""

    _COLUMNS = (
        "id", "email", "name", "password_hash", "role",
        "oauth_provider", "oauth_id", "is_active",
        "created_at", "updated_at", "metadata",
    )

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Initialise le magasin SQLite.

        Args:
            db_path: Chemin vers le fichier SQLite (défaut: users.sqlite).
        """
        self.db_path = db_path or default_sqlite_path("users.sqlite")
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        # Nom unique par instance : sans lui, toutes les bases ":memory:" du
        # processus partageraient le meme cache et donc les memes donnees.
        self._memory_uri = f"file:userstore_{uuid.uuid4().hex}?mode=memory&cache=shared"
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
        """Ouvre une connexion SQLite avec les PRAGMA requis."""
        if self.db_path == ":memory:":
            conn = sqlite3.connect(self._memory_uri, uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _initialize_db(self) -> None:
        """Crée la table des utilisateurs et ses index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    password_hash TEXT,
                    role TEXT NOT NULL DEFAULT 'user',
                    oauth_provider TEXT,
                    oauth_id TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL,
                    metadata TEXT
                )
            """)
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_oauth ON users(oauth_provider, oauth_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)"
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Conversion entité ↔ dictionnaire
    # ------------------------------------------------------------------

    def _item_to_dict(self, item: User) -> Dict[str, Any]:
        """Convertit un User en dictionnaire pour SQLite."""
        return {
            "id": item.id,
            "email": item.email,
            "name": item.name,
            "password_hash": item.password_hash,
            "role": item.role,
            "oauth_provider": item.oauth_provider,
            "oauth_id": item.oauth_id,
            "is_active": 1 if item.is_active else 0,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "metadata": json.dumps(item.metadata) if item.metadata else None,
        }

    def _dict_to_item(self, d: Dict[str, Any]) -> User:
        """Convertit une ligne SQLite en User."""
        metadata_raw = d.get("metadata")
        metadata = json.loads(metadata_raw) if metadata_raw else {}
        return User(
            id=d["id"],
            email=d["email"],
            name=d.get("name", ""),
            password_hash=d.get("password_hash"),
            role=d.get("role", "user"),
            oauth_provider=d.get("oauth_provider"),
            oauth_id=d.get("oauth_id"),
            is_active=bool(d.get("is_active", 1)),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at"),
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # CRUD — interface BaseRepository[User]
    # ------------------------------------------------------------------

    def save(self, entity: User) -> str:
        """Enregistre un utilisateur et retourne son identifiant."""
        entity.updated_at = time.time()

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                data = self._item_to_dict(entity)
                cursor.execute(
                    """INSERT OR REPLACE INTO users (
                        id, email, name, password_hash, role,
                        oauth_provider, oauth_id, is_active,
                        created_at, updated_at, metadata
                    ) VALUES (
                        :id, :email, :name, :password_hash, :role,
                        :oauth_provider, :oauth_id, :is_active,
                        :created_at, :updated_at, :metadata
                    )""",
                    data,
                )
                conn.commit()
            return entity.id

    def get(self, entity_id: str) -> Optional[User]:
        """Retourne un utilisateur par identifiant, ou None si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (entity_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._dict_to_item(dict(zip(self._COLUMNS, row)))

    def update(self, entity: User) -> bool:
        """Met à jour un utilisateur existant. Retourne False si absent."""
        entity.updated_at = time.time()
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                data = self._item_to_dict(entity)
                cursor.execute(
                    """UPDATE users SET
                        email = :email, name = :name, password_hash = :password_hash,
                        role = :role, oauth_provider = :oauth_provider,
                        oauth_id = :oauth_id, is_active = :is_active,
                        updated_at = :updated_at, metadata = :metadata
                    WHERE id = :id""",
                    data,
                )
                updated = cursor.rowcount > 0
                conn.commit()
            return updated

    def delete(self, entity_id: str) -> bool:
        """Supprime un utilisateur ; retourne False si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE id = ?", (entity_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
            return deleted

    def list_items(
        self,
        limit: int = 100,
        offset: int = 0,
        **filters: Any,
    ) -> List[User]:
        """Liste les utilisateurs avec filtrage et pagination."""
        where_clauses: List[str] = []
        params: List[Any] = []

        if filters.get("role") is not None:
            where_clauses.append("role = ?")
            params.append(filters["role"])
        if filters.get("is_active") is not None:
            where_clauses.append("is_active = ?")
            params.append(1 if filters["is_active"] else 0)
        if filters.get("search"):
            where_clauses.append("(email LIKE ? OR name LIKE ?)")
            like = f"%{filters['search']}%"
            params.extend([like, like])

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = f"""
                    SELECT * FROM users
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, [*params, limit, offset])
                rows = cursor.fetchall()
            return [self._dict_to_item(dict(zip(self._COLUMNS, row))) for row in rows]

    def clear(self, **filters: Any) -> int:
        """Supprime les utilisateurs correspondant aux critères."""
        where_clauses: List[str] = []
        params: List[Any] = []

        if filters.get("role") is not None:
            where_clauses.append("role = ?")
            params.append(filters["role"])

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM users {where_sql}", params)
                count = cursor.rowcount
                conn.commit()
            return count

    def count(self, **filters: Any) -> int:
        """Compte les utilisateurs correspondant aux critères."""
        where_clauses: List[str] = []
        params: List[Any] = []

        if filters.get("role") is not None:
            where_clauses.append("role = ?")
            params.append(filters["role"])
        if filters.get("is_active") is not None:
            where_clauses.append("is_active = ?")
            params.append(1 if filters["is_active"] else 0)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM users {where_sql}", params)
                return cursor.fetchone()[0]

    def exists(self, entity_id: str) -> bool:
        """Vérifie si un utilisateur existe."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM users WHERE id = ?", (entity_id,))
                return cursor.fetchone() is not None

    # ------------------------------------------------------------------
    # Méthodes spécifiques aux utilisateurs
    # ------------------------------------------------------------------

    def get_by_email(self, email: str) -> Optional[User]:
        """Retourne un utilisateur par son email, ou None si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM users WHERE email = ?",
                    (email.lower().strip(),),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._dict_to_item(dict(zip(self._COLUMNS, row)))

    def get_by_oauth(
        self, provider: str, oauth_id: str
    ) -> Optional[User]:
        """Retourne un utilisateur par son compte OAuth, ou None si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM users WHERE oauth_provider = ? AND oauth_id = ?",
                    (provider, oauth_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._dict_to_item(dict(zip(self._COLUMNS, row)))

    def is_email_taken(self, email: str) -> bool:
        """Vérifie si l'email est déjà utilisé par un autre utilisateur."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM users WHERE email = ?",
                    (email.lower().strip(),),
                )
                return cursor.fetchone() is not None
