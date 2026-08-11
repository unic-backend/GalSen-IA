"""
Magasin de mémoire SQLite pour GalSen IA.

Implémente l'interface MemoryStore en utilisant SQLite pour la persistance.
"""

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from src.memory_engine.types import MemoryItem, MemoryType, MemoryPriority, MemoryStatus
from src.storage.encryption import decrypt, encrypt
from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file
from src.memory_engine.interfaces import MemoryStore


class SQLiteMemoryStore(MemoryStore):
    """Magasin de mémoire soutenu par SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le magasin SQLite.

        Args:
            db_path: Chemin vers le fichier de base de données SQLite. Par
                défaut, `memory.sqlite` dans le répertoire de données configuré.

        Le chemin était écrit en dur (`data/memory.sqlite`), seul des huit
        magasins à ignorer `GALSEN_DATA_DIR` : un opérateur qui déplaçait le
        répertoire de données déplaçait sept bases et laissait celle des
        mémoires derrière, relative au répertoire courant. La valeur par défaut
        est inchangée quand la variable n'est pas posée, donc aucune base
        existante ne se perd.
        """
        self.db_path = db_path or default_sqlite_path("memory.sqlite")
        # S'assurer que le répertoire existe (sauf pour :memory:)
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        # Connexion persistante pour maintenir la base :memory: en vie
        # entre les appels à _get_connection() (le cache partagé détruit
        # la base quand la dernière connexion se ferme).
        self._persistent_conn: Optional[sqlite3.Connection] = None
        self._initialize_db()
        # Une base porte des mémoires, des connaissances et des e-mails ;
        # elle était créée en 0644, donc lisible par tout compte de la machine.
        secure_database_file(self.db_path)
        if db_path == ":memory:":
            self._persistent_conn = self._get_connection()

    def close(self) -> None:
        """Ferme la connexion persistante (pour :memory:) si elle existe."""
        if self._persistent_conn is not None:
            self._persistent_conn.close()
            self._persistent_conn = None

    def _get_connection(self) -> sqlite3.Connection:
        """Obtenir une connexion à la base de données.

        Pour les bases en mémoire (:memory:), utilise le cache partagé
        afin que toutes les connexions accèdent à la même base.
        """
        if self.db_path == ":memory:":
            # Le cache partagé permet de partager la base :memory: entre connexions
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        prepare_connection(conn)
        return conn

    def _initialize_db(self) -> None:
        """Créer la table des mémoires si elle n'existe pas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    agent_id TEXT,
                    tags TEXT, -- tableau JSON
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    expires_at REAL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT, -- objet JSON
                    version INTEGER NOT NULL
                )
                """
            )
            # Créer les index pour les filtres de requête courants
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_session_id ON memories(session_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_agent_id ON memories(agent_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_memory_type ON memories(memory_type)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_expires_at ON memories(expires_at)"
            )
            conn.commit()

    # Méthodes d'aide pour convertir entre MemoryItem et ligne DB
    def _item_to_dict(self, item: MemoryItem) -> dict:
        """Convertir un MemoryItem en dictionnaire pour le stockage."""
        return {
            "id": item.id,
            # Le contenu d'une mémoire est la donnée réelle : c'est lui qu'un
            # fichier de base copié livrerait en clair (VOLET 02 ch. 08).
            "content": encrypt(
                json.dumps(item.content) if not isinstance(item.content, str) else item.content
            ),
            "memory_type": item.memory_type.value,
            "user_id": item.user_id,
            "session_id": item.session_id,
            "agent_id": item.agent_id,
            "tags": json.dumps(item.tags),
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "expires_at": item.expires_at,
            "priority": item.priority.value,
            "status": item.status.value,
            "metadata": json.dumps(item.metadata),
            "version": item.version,
        }

    def _dict_to_item(self, row: tuple) -> MemoryItem:
        """Convertir une ligne de base de données en MemoryItem."""
        (
            id_val,
            content_json,
            memory_type_str,
            user_id,
            session_id,
            agent_id,
            tags_json,
            created_at,
            updated_at,
            expires_at,
            priority_str,
            status_str,
            metadata_json,
            version,
        ) = row

        # Déchiffrer avant d'interpréter : une base écrite avant l'activation
        # du chiffrement traverse sans marque et reste lisible.
        content_json = decrypt(content_json)

        # Déterminer si le contenu est JSON ou chaîne simple
        try:
            content = json.loads(content_json)
        except (json.JSONDecodeError, TypeError):
            content = content_json

        return MemoryItem(
            id=id_val,
            content=content,
            memory_type=MemoryType(memory_type_str),
            user_id=user_id,
            session_id=session_id,
            agent_id=agent_id,
            tags=json.loads(tags_json) if tags_json else [],
            created_at=created_at,
            updated_at=updated_at,
            expires_at=expires_at,
            priority=MemoryPriority(int(priority_str)),
            status=MemoryStatus(status_str),
            metadata=json.loads(metadata_json) if metadata_json else {},
            version=version,
        )

    # --- Implémentation de l'interface MemoryStore ---

    def save(self, item: MemoryItem) -> str:
        """Sauver un élément de mémoire dans le magasin."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            data = self._item_to_dict(item)
            # Utiliser INSERT OR REPLACE pour gérer les upserts basé sur la clé primaire
            cursor.execute(
                """
                INSERT OR REPLACE INTO memories (
                    id, content, memory_type, user_id, session_id, agent_id,
                    tags, created_at, updated_at, expires_at, priority, status,
                    metadata, version
                ) VALUES (
                    :id, :content, :memory_type, :user_id, :session_id, :agent_id,
                    :tags, :created_at, :updated_at, :expires_at, :priority, :status,
                    :metadata, :version
                )
                """,
                data,
            )
            conn.commit()
        return item.id

    def get(self, item_id: str) -> Optional[MemoryItem]:
        """Récupérer un élément de mémoire par son ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, content, memory_type, user_id, session_id, agent_id,
                       tags, created_at, updated_at, expires_at, priority, status,
                       metadata, version
                FROM memories
                WHERE id = ?
                """,
                (item_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._dict_to_item(row)

    def update(self, item: MemoryItem) -> bool:
        """Mettre à jour un élément de mémoire existant."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            data = self._item_to_dict(item)
            cursor.execute(
                """
                UPDATE memories SET
                    content = :content,
                    memory_type = :memory_type,
                    user_id = :user_id,
                    session_id = :session_id,
                    agent_id = :agent_id,
                    tags = :tags,
                    created_at = :created_at,
                    updated_at = :updated_at,
                    expires_at = :expires_at,
                    priority = :priority,
                    status = :status,
                    metadata = :metadata,
                    version = :version
                WHERE id = :id
                """,
                data,
            )
            updated = cursor.rowcount > 0
            conn.commit()
        return updated

    def delete(self, item_id: str) -> bool:
        """Supprimer un élément de mémoire par son ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (item_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
        return deleted

    def list_items(
        self,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[MemoryStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MemoryItem]:
        """Lister les éléments de mémoire avec filtrage optionnel."""
        where_clauses = []
        params: List[Any] = []

        if memory_type is not None:
            where_clauses.append("memory_type = ?")
            params.append(memory_type.value)
        if user_id is not None:
            where_clauses.append("user_id = ?")
            params.append(user_id)
        if session_id is not None:
            where_clauses.append("session_id = ?")
            params.append(session_id)
        if agent_id is not None:
            where_clauses.append("agent_id = ?")
            params.append(agent_id)
        if status is not None:
            where_clauses.append("status = ?")
            params.append(status.value)
        # Filtrage des tags : nous devons vérifier que tous les tags sont présents dans le tableau JSON.
        # Comme SQLite ne possède pas de fonction JSON contains native pour les tableaux, nous filtrerons en Python.
        # Nous récupérerons toutes les lignes correspondant aux autres filtres puis filtrerons par tags.
        # Pour simplifier, nous ignorerons les tags dans WHERE et filtrerons plus tard.
        # Ceci est acceptable pour des tailles de données modérées.
        # Si tags n'est pas None, nous gérerons après la récupération.

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = "WHERE " + where_sql

        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = f"""
                SELECT id, content, memory_type, user_id, session_id, agent_id,
                       tags, created_at, updated_at, expires_at, priority, status,
                       metadata, version
                FROM memories
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cursor.execute(query, params)
            rows = cursor.fetchall()

        items = [self._dict_to_item(row) for row in rows]

        # Appliquer le filtre de tags si nécessaire
        if tags is not None:
            def has_all_tags(item: MemoryItem) -> bool:
                return all(tag in item.tags for tag in tags)
            items = [item for item in items if has_all_tags(item)]

        return items

    def clear(
        self,
        memory_type: Optional[MemoryType] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> int:
        """Effacer les éléments de mémoire correspondant aux critères."""
        where_clauses = []
        params: List[Any] = []

        if memory_type is not None:
            where_clauses.append("memory_type = ?")
            params.append(memory_type.value)
        if user_id is not None:
            where_clauses.append("user_id = ?")
            params.append(user_id)
        if session_id is not None:
            where_clauses.append("session_id = ?")
            params.append(session_id)
        if agent_id is not None:
            where_clauses.append("agent_id = ?")
            params.append(agent_id)

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = "WHERE " + where_sql

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM memories {where_sql}",
                params,
            )
            deleted = cursor.rowcount
            conn.commit()
        return deleted

    def cleanup_expired(self) -> int:
        """Supprimer les mémoires expirées."""
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            deleted = cursor.rowcount
            conn.commit()
        return deleted