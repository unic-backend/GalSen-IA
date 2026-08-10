"""
Stockage SQLite pour le moteur de connaissances GalSen IA (ADR-005).

Réplique la sémantique de InMemoryKnowledgeStore : mêmes méthodes de contrat,
mêmes règles de filtrage, même ordre d'insertion (rowid = ordre de première
sauvegarde), même découpe par limite. Les enums sont stockés par leur valeur,
les listes/dictionnaires en JSON, les dates en ISO 8601.
"""

import json
import os
import sqlite3
import threading
import datetime
from typing import Any, Dict, List, Optional

from src.knowledge_engine.types import (
    KnowledgeItem, KnowledgeSource, KnowledgeType, ContentType,
    Language, SourceCategory, KnowledgePriority, KnowledgeDomain,
    KnowledgeSensitivity, KnowledgeStatus,
)
from src.knowledge_engine.interfaces import KnowledgeStore
from src.storage.encryption import decrypt, encrypt
from .paths import default_sqlite_path


class SQLiteKnowledgeStore(KnowledgeStore):
    """Implémentation SQLite du stockage de connaissances."""

    # Colonnes de la table "knowledge_items" (l'ordre définit aussi le SELECT).
    _COLUMNS = (
        "id", "content", "summary", "knowledge_type", "content_type",
        "language", "domain", "sensitivity", "status", "tags", "categories",
        "source_id", "source_type",
        "source_location", "source_accessed_at", "source_hash",
        "source_category", "source_title", "source_author", "source_url",
        "source_citation", "source_retrieved_at", "confidence", "version",
        "created_at", "updated_at", "metadata", "relations", "priority",
    )

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le stockage SQLite.

        Args:
            db_path: Chemin du fichier SQLite. Par défaut, résolu dans le
                répertoire de données configurable (GALSEN_DATA_DIR), à
                savoir "data/knowledge.sqlite". ":memory:" utilise une base
                partagée en mémoire.
        """
        self.db_path = db_path or default_sqlite_path("knowledge.sqlite")
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        self._lock = threading.RLock()
        self._persistent_conn: Optional[sqlite3.Connection] = None

        self._initialize_db()
        if self.db_path == ":memory:":
            # Base partagée : la connexion persistante garde la base en vie.
            self._persistent_conn = self._get_connection()

    # -- Connexion et schéma ------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        """
        Ouvre une connexion SQLite.

        En mode ":memory:", la base partagée permet à plusieurs connexions de
        voir les mêmes données (isolation des tests).
        """
        if self.db_path == ":memory:":
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        # Évite les erreurs "database is locked" lors de l'accès concurrent.
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _initialize_db(self) -> None:
        """Crée la table et les index si nécessaire."""
        columns = ", ".join(
            "id TEXT PRIMARY KEY" if col == "id"
            else f"{col} {self._sql_type(col)}"
            for col in self._COLUMNS
        )
        with self._get_connection() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS knowledge_items ({columns})")
            self._add_missing_columns(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kn_type ON knowledge_items (knowledge_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kn_language ON knowledge_items (language)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kn_priority ON knowledge_items (priority)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kn_updated ON knowledge_items (updated_at)")

    def _add_missing_columns(self, conn: sqlite3.Connection) -> None:
        """Ajoute les colonnes absentes d'une base créée par une version antérieure.

        Migration additive uniquement : aucune colonne n'est renommée ni supprimée,
        les lignes existantes reçoivent NULL et sont relues comme « non classé ».
        """
        present = {row[1] for row in conn.execute("PRAGMA table_info(knowledge_items)")}
        for col in self._COLUMNS:
            if col not in present:
                conn.execute(f"ALTER TABLE knowledge_items ADD COLUMN {col} {self._sql_type(col)}")

    @staticmethod
    def _sql_type(col: str) -> str:
        """Retourne le type SQL de chaque colonne."""
        real_cols = {"confidence"}
        integer_cols = {"version", "priority"}
        if col in integer_cols:
            return "INTEGER"
        if col in real_cols:
            return "REAL"
        return "TEXT"

    # -- Sérialisation ------------------------------------------------------

    def _source_to_dict(self, source: KnowledgeSource) -> Dict[str, Any]:
        """Convertit une source en dictionnaire plat."""
        return {
            "source_id": source.id,
            "source_type": source.type,
            "source_location": source.location,
            "source_accessed_at": source.accessed_at.isoformat(),
            "source_hash": source.hash,
            "source_category": source.source_category.value if source.source_category else None,
            "source_title": source.title,
            "source_author": source.author,
            "source_url": source.url,
            "source_citation": source.citation,
            "source_retrieved_at": source.retrieved_at.isoformat() if source.retrieved_at else None,
        }

    def _item_to_dict(self, knowledge: KnowledgeItem) -> Dict[str, Any]:
        """Convertit une connaissance en dictionnaire prêt pour SQLite."""
        data = {
            "id": knowledge.id,
            "content": encrypt(knowledge.content),
            "summary": knowledge.summary,
            "knowledge_type": knowledge.knowledge_type.value,
            "content_type": knowledge.content_type.value,
            "language": knowledge.language.value,
            "domain": knowledge.domain.value,
            "sensitivity": knowledge.sensitivity.value,
            "status": knowledge.status.value,
            "tags": json.dumps(knowledge.tags),
            "categories": json.dumps(knowledge.categories),
            "confidence": knowledge.confidence,
            "version": knowledge.version,
            "created_at": knowledge.created_at.isoformat(),
            "updated_at": knowledge.updated_at.isoformat(),
            "metadata": json.dumps(knowledge.metadata),
            "relations": json.dumps(knowledge.relations),
            "priority": knowledge.priority.value,
        }
        data.update(self._source_to_dict(knowledge.source))
        return data

    def _dict_to_item(self, data: Dict[str, Any]) -> KnowledgeItem:
        """Reconstruit une connaissance depuis un dictionnaire SQLite."""
        source = KnowledgeSource(
            id=data["source_id"],
            type=data["source_type"],
            location=data["source_location"],
            accessed_at=datetime.datetime.fromisoformat(data["source_accessed_at"]),
            hash=data["source_hash"],
            source_category=SourceCategory(data["source_category"]) if data["source_category"] else None,
            title=data["source_title"],
            author=data["source_author"],
            url=data["source_url"],
            citation=data["source_citation"],
            retrieved_at=datetime.datetime.fromisoformat(data["source_retrieved_at"]) if data["source_retrieved_at"] else None,
        )
        return KnowledgeItem(
            id=data["id"],
            content=decrypt(data["content"]),
            summary=data["summary"],
            knowledge_type=KnowledgeType(data["knowledge_type"]),
            content_type=ContentType(data["content_type"]),
            language=Language(data["language"]),
            # Une base écrite avant l'ajout du domaine renvoie NULL : non classé.
            domain=KnowledgeDomain(data["domain"]) if data.get("domain") else KnowledgeDomain.UNSPECIFIED,
            sensitivity=KnowledgeSensitivity(data["sensitivity"]) if data.get("sensitivity") else KnowledgeSensitivity.PUBLIC,
            status=KnowledgeStatus(data["status"]) if data.get("status") else KnowledgeStatus.DRAFT,
            tags=json.loads(data["tags"] or "[]"),
            categories=json.loads(data["categories"] or "[]"),
            source=source,
            confidence=data["confidence"],
            version=data["version"],
            created_at=datetime.datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.datetime.fromisoformat(data["updated_at"]),
            metadata=json.loads(data["metadata"] or "{}"),
            relations=json.loads(data["relations"] or "[]"),
            priority=KnowledgePriority(int(data["priority"])),
        )

    # -- Opérations CRUD ----------------------------------------------------

    def save(self, knowledge: KnowledgeItem) -> str:
        """Sauvegarde une connaissance et retourne son ID."""
        with self._lock:
            # S'assurer que l'ID existe
            if not knowledge.id:
                knowledge.id = f"kn{knowledge.compute_content_hash()[:12]}"

            # Ne pas écraser une version plus récente ou égale
            existing = self.get(knowledge.id)
            if existing and existing.version >= knowledge.version:
                return existing.id

            data = self._item_to_dict(knowledge)
            cols = ", ".join(self._COLUMNS)
            placeholders = ", ".join(f":{col}" for col in self._COLUMNS)
            sql = f"INSERT OR REPLACE INTO knowledge_items ({cols}) VALUES ({placeholders})"
            with self._get_connection() as conn:
                conn.execute(sql, data)
            return knowledge.id

    def get(self, knowledge_id: str) -> Optional[KnowledgeItem]:
        """Récupère une connaissance par son ID."""
        with self._lock:
            sql = f"SELECT {', '.join(self._COLUMNS)} FROM knowledge_items WHERE id = ?"
            with self._get_connection() as conn:
                row = conn.execute(sql, (knowledge_id,)).fetchone()
            if row is None:
                return None
            return self._dict_to_item(dict(zip(self._COLUMNS, row)))

    def update(self, knowledge: KnowledgeItem) -> bool:
        """Met à jour une connaissance existante."""
        with self._lock:
            existing = self.get(knowledge.id)
            if existing is None:
                return False
            # S'assurer que la version est plus récente
            if knowledge.version <= existing.version:
                return False

            data = self._item_to_dict(knowledge)
            sets = ", ".join(f"{col} = :{col}" for col in self._COLUMNS if col != "id")
            sql = f"UPDATE knowledge_items SET {sets} WHERE id = :id"
            with self._get_connection() as conn:
                cursor = conn.execute(sql, data)
            return cursor.rowcount > 0

    def delete(self, knowledge_id: str) -> bool:
        """Supprime une connaissance."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM knowledge_items WHERE id = ?", (knowledge_id,))
            return cursor.rowcount > 0

    def list_items(self, limit: int = 100, **filters) -> List[KnowledgeItem]:
        """
        Liste les connaissances avec filtres optionnels.

        Mêmes règles que InMemoryKnowledgeStore : le filtrage est répliqué en
        Python mot pour mot, l'ordre d'insertion est préservé (rowid).
        """
        with self._lock:
            sql = f"SELECT {', '.join(self._COLUMNS)} FROM knowledge_items ORDER BY rowid"
            with self._get_connection() as conn:
                rows = conn.execute(sql).fetchall()

            results = []
            for row in rows:
                knowledge = self._dict_to_item(dict(zip(self._COLUMNS, row)))
                match = True
                for key, value in filters.items():
                    if key == "knowledge_type":
                        if knowledge.knowledge_type.value != value:
                            match = False
                            break
                    elif key == "content_type":
                        if knowledge.content_type.value != value:
                            match = False
                            break
                    elif key == "language":
                        if knowledge.language.value != value:
                            match = False
                            break
                    elif key == "domain":
                        wanted = value.value if hasattr(value, "value") else value
                        if knowledge.domain.value != wanted:
                            match = False
                            break
                    elif key == "sensitivity":
                        wanted = value.value if hasattr(value, "value") else value
                        if knowledge.sensitivity.value != wanted:
                            match = False
                            break
                    elif key == "status":
                        wanted = value.value if hasattr(value, "value") else value
                        if knowledge.status.value != wanted:
                            match = False
                            break
                    elif key == "tags":
                        if isinstance(value, str):
                            if value not in knowledge.tags:
                                match = False
                                break
                        elif isinstance(value, list):
                            if not all(tag in knowledge.tags for tag in value):
                                match = False
                                break
                    elif key == "categories":
                        if isinstance(value, str):
                            if value not in knowledge.categories:
                                match = False
                                break
                        elif isinstance(value, list):
                            if not all(cat in knowledge.categories for cat in value):
                                match = False
                                break
                    elif key == "source_type":
                        if knowledge.source.type != value:
                            match = False
                            break
                    elif key == "min_confidence":
                        if knowledge.confidence < float(value):
                            match = False
                            break
                    elif key == "max_confidence":
                        if knowledge.confidence > float(value):
                            match = False
                            break
                    elif key == "priority":
                        wanted = value.value if hasattr(value, "value") else int(value)
                        current = knowledge.priority.value if hasattr(knowledge.priority, "value") else int(knowledge.priority)
                        if current != wanted:
                            match = False
                            break
                    elif key == "min_priority":
                        # "Au moins aussi fiable que" : on garde les priorités <= la valeur
                        minimum = value.value if hasattr(value, "value") else int(value)
                        current = knowledge.priority.value if hasattr(knowledge.priority, "value") else int(knowledge.priority)
                        if current > minimum:
                            match = False
                            break
                    elif key == "max_priority":
                        # "Au plus aussi fiable que" : on garde les priorités >= la valeur
                        maximum = value.value if hasattr(value, "value") else int(value)
                        current = knowledge.priority.value if hasattr(knowledge.priority, "value") else int(knowledge.priority)
                        if current < maximum:
                            match = False
                            break
                    elif key == "source_category":
                        wanted = value.value if hasattr(value, "value") else value
                        sc = knowledge.source.source_category
                        current = sc.value if sc is not None else "unknown"
                        if current != wanted:
                            match = False
                            break
                    elif key == "created_after":
                        if knowledge.created_at < datetime.datetime.fromisoformat(value):
                            match = False
                            break
                    elif key == "created_before":
                        if knowledge.created_at > datetime.datetime.fromisoformat(value):
                            match = False
                            break
                if match:
                    results.append(knowledge)
                    if len(results) >= limit:
                        break
            return results

    def count(self, **filters) -> int:
        """Compte les connaissances correspondant aux filtres."""
        return len(self.list_items(limit=10000, **filters))

    def cleanup_old_versions(self, keep_latest: int = 1) -> int:
        """
        Nettoie les anciennes versions.

        Comme l'implémentation en mémoire, une seule version par ID est
        conservée : rien à nettoyer, retourne toujours 0.
        """
        return 0

    def close(self) -> None:
        """Ferme la connexion persistante, le cas échéant."""
        with self._lock:
            if self._persistent_conn is not None:
                self._persistent_conn.close()
                self._persistent_conn = None
