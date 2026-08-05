"""
Stockage SQLite pour le moteur de modèles GalSen IA (ADR-005).

Réplique la sémantique de InMemoryModelStore : mêmes méthodes de contrat,
mêmes règles de filtrage, même tri (updated_at décroissant), même découpe
par limite. La sérialisation s'appuie sur ModelItem.to_dict()/from_dict().
"""

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from src.model_engine.types import ModelItem, ModelStatus
from src.model_engine.interfaces import ModelStore
from .paths import default_sqlite_path


class SQLiteModelStore(ModelStore):
    """Implémentation SQLite du stockage de modèles."""

    # Colonnes de la table "models" (l'ordre définit aussi l'ordre du SELECT).
    _COLUMNS = (
        "model_id", "model_type", "provider", "name", "version",
        "priority", "status", "context_window", "max_output_tokens",
        "supported_features", "metadata", "created_at", "updated_at",
        "usage_count", "total_tokens_used", "total_cost", "avg_latency",
        "error_rate",
    )

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le stockage SQLite.

        Args:
            db_path: Chemin du fichier SQLite. Par défaut, résolu dans le
                répertoire de données configurable (GALSEN_DATA_DIR), à
                savoir "data/models.sqlite". ":memory:" utilise une base
                partagée en mémoire.
        """
        self.db_path = db_path or default_sqlite_path("models.sqlite")
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
            "model_id TEXT PRIMARY KEY" if col == "model_id"
            else f"{col} {self._sql_type(col)}"
            for col in self._COLUMNS
        )
        with self._get_connection() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS models ({columns})")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_models_type ON models (model_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_models_provider ON models (provider)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_models_status ON models (status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_models_priority ON models (priority)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_models_updated ON models (updated_at)")

    @staticmethod
    def _sql_type(col: str) -> str:
        """Retourne le type SQL de chaque colonne."""
        integer_cols = {
            "priority", "context_window", "max_output_tokens", "usage_count",
            "total_tokens_used",
        }
        real_cols = {"created_at", "updated_at", "total_cost", "avg_latency", "error_rate"}
        if col in integer_cols:
            return "INTEGER"
        if col in real_cols:
            return "REAL"
        return "TEXT"

    # -- Sérialisation ------------------------------------------------------

    def _item_to_dict(self, model: ModelItem) -> Dict[str, Any]:
        """Convertit un modèle en dictionnaire prêt pour SQLite."""
        data = model.to_dict()
        data["supported_features"] = json.dumps(model.supported_features)
        data["metadata"] = json.dumps(model.metadata)
        return data

    def _row_to_item(self, row: sqlite3.Row) -> ModelItem:
        """Reconstruit un modèle depuis une ligne SQLite."""
        data = dict(zip(self._COLUMNS, row))
        data["supported_features"] = json.loads(data["supported_features"] or "[]")
        data["metadata"] = json.loads(data["metadata"] or "{}")
        return ModelItem.from_dict(data)

    # -- Opérations CRUD ----------------------------------------------------

    def save(self, model: ModelItem) -> str:
        """Sauvegarde un modèle et retourne son ID."""
        with self._lock:
            model.updated_at = time.time()
            data = self._item_to_dict(model)
            placeholders = ", ".join(f":{col}" for col in self._COLUMNS)
            sql = f"INSERT OR REPLACE INTO models ({', '.join(self._COLUMNS)}) VALUES ({placeholders})"
            with self._get_connection() as conn:
                conn.execute(sql, data)
            return model.model_id

    def get(self, model_id: str) -> Optional[ModelItem]:
        """Récupère un modèle par son ID."""
        with self._lock:
            sql = f"SELECT {', '.join(self._COLUMNS)} FROM models WHERE model_id = ?"
            with self._get_connection() as conn:
                row = conn.execute(sql, (model_id,)).fetchone()
            if row is None:
                return None
            return self._row_to_item(row)

    def update(self, model: ModelItem) -> bool:
        """Met à jour un modèle existant."""
        with self._lock:
            if self.get(model.model_id) is None:
                return False
            model.updated_at = time.time()
            data = self._item_to_dict(model)
            sets = ", ".join(f"{col} = :{col}" for col in self._COLUMNS if col != "model_id")
            sql = f"UPDATE models SET {sets} WHERE model_id = :model_id"
            with self._get_connection() as conn:
                cursor = conn.execute(sql, data)
            return cursor.rowcount > 0

    def delete(self, model_id: str) -> bool:
        """Supprime un modèle."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM models WHERE model_id = ?", (model_id,))
            return cursor.rowcount > 0

    def list_items(self, limit: int = 100, **filters) -> List[ModelItem]:
        """
        Liste les modèles avec filtres optionnels.

        Mêmes règles que InMemoryModelStore : le filtrage est répliqué en
        Python mot pour mot pour garantir une parité comportementale exacte.
        """
        with self._lock:
            sql = f"SELECT {', '.join(self._COLUMNS)} FROM models"
            with self._get_connection() as conn:
                rows = conn.execute(sql).fetchall()
            models = [self._row_to_item(row) for row in rows]

            # Appliquer les filtres (réplication fidèle de la boucle en mémoire)
            if filters:
                filtered_models = []
                for model in models:
                    match = True
                    for key, value in filters.items():
                        if key == "model_type":
                            if model.model_type.value != value:
                                match = False
                                break
                        elif key == "provider":
                            if model.provider != value:
                                match = False
                                break
                        elif key == "status":
                            if model.status.value != value:
                                match = False
                                break
                        elif key == "priority":
                            if model.priority.value != value:
                                match = False
                                break
                        elif hasattr(model, key):
                            if getattr(model, key) != value:
                                match = False
                                break
                        else:
                            match = False
                            break
                    if match:
                        filtered_models.append(model)
                models = filtered_models

            # Trier par date de mise à jour (plus récent en premier)
            models.sort(key=lambda x: x.updated_at, reverse=True)

            # Limiter les résultats
            return models[:limit]

    def cleanup_expired(self) -> int:
        """Supprime les modèles marqués obsolètes et retourne le nombre supprimé."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM models WHERE status = ?", (ModelStatus.DEPRECATED.value,)
                )
            return cursor.rowcount

    def close(self) -> None:
        """Ferme la connexion persistante, le cas échéant."""
        with self._lock:
            if self._persistent_conn is not None:
                self._persistent_conn.close()
                self._persistent_conn = None
