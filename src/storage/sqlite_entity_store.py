"""
Magasin d'entités et de relations soutenu par SQLite (VOLET 36, ch. E).

Deux tables, des index sur `type`, `scope` et les deux extrémités. C'est tout ce
qu'exige l'ontologie : voisins, parcours typé jusqu'à la profondeur 3, filtrage
par portée et par sujet.

**Pas de base graphe.** Le dépôt tourne sur SQLite avec une instance (ADR-005,
ADR-009) et compte 0 entité aujourd'hui ; adopter une base graphe maintenant
serait choisir une infrastructure pour un volume qui n'existe pas. Les seuils
qui rouvriraient la question sont écrits dans `DECLENCHEUR_BASE_GRAPHE`, pas
laissés au goût de la prochaine personne.

Le filtrage et le parcours sont répliqués en Python à partir des lignes lues,
mot pour mot comme `InMemoryEntityStore` : deux implémentations d'une même règle
finissent par diverger, et ce dépôt a déjà payé ce mode de défaillance.
"""

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, Optional

from src.knowledge_engine.entities import Entity, InMemoryEntityStore, Relation
from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file


class SQLiteEntityStore(InMemoryEntityStore):
    """
    Magasin d'entités persistant.

    Il hérite des règles de lecture et de parcours de `InMemoryEntityStore` et
    ne redéfinit que l'écriture et le chargement : la logique de voisinage est
    identique par construction, pas par relecture.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise le magasin.

        Args:
            db_path: Fichier SQLite ; `entities.sqlite` dans le répertoire de
                données par défaut (`GALSEN_DATA_DIR`).
        """
        super().__init__()
        self.db_path = db_path or default_sqlite_path("entities.sqlite")
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._db_lock = threading.RLock()
        self._persistent_conn: Optional[sqlite3.Connection] = None
        self._initialize_db()
        # Une base d'entités porte des noms de personnes : elle est créée en
        # 0600 comme les autres, pas lisible par tout compte de la machine.
        secure_database_file(self.db_path)
        if self.db_path == ":memory:":
            self._persistent_conn = self._get_connection()
        self._load()

    def close(self) -> None:
        """Ferme la connexion persistante (base `:memory:`) si elle existe."""
        if self._persistent_conn is not None:
            self._persistent_conn.close()
            self._persistent_conn = None

    def _get_connection(self) -> sqlite3.Connection:
        """Ouvre une connexion préparée."""
        if self.db_path == ":memory:":
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        prepare_connection(conn)
        return conn

    def _initialize_db(self) -> None:
        """Crée les deux tables et leurs index."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    entity_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    label TEXT NOT NULL,
                    aliases TEXT,
                    scope TEXT,
                    subject TEXT,
                    sources TEXT NOT NULL,
                    confidence REAL,
                    properties TEXT,
                    version INTEGER,
                    created_at REAL,
                    updated_at REAL
                );
                CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
                CREATE INDEX IF NOT EXISTS idx_entities_scope ON entities(scope);
                CREATE INDEX IF NOT EXISTS idx_entities_subject ON entities(subject);

                CREATE TABLE IF NOT EXISTS relations (
                    relation_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    sources TEXT NOT NULL,
                    confidence REAL,
                    valid_from TEXT,
                    valid_to TEXT,
                    version INTEGER,
                    created_at REAL
                );
                CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
                CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
                CREATE INDEX IF NOT EXISTS idx_relations_name ON relations(relation);
                """
            )

    def _load(self) -> None:
        """Charge la base en mémoire, pour que lecture et parcours soient communs."""
        with self._get_connection() as conn:
            for ligne in conn.execute(
                "SELECT entity_id, type, label, aliases, scope, subject, sources, "
                "confidence, properties, version, created_at, updated_at FROM entities"
            ):
                entite = Entity.from_dict({
                    "entity_id": ligne[0], "type": ligne[1], "label": ligne[2],
                    "aliases": json.loads(ligne[3] or "[]"), "scope": ligne[4] or "global",
                    "subject": ligne[5] or "unspecified",
                    "sources": json.loads(ligne[6] or "[]"), "confidence": ligne[7],
                    "properties": json.loads(ligne[8] or "{}"), "version": ligne[9] or 1,
                    "created_at": ligne[10] or time.time(), "updated_at": ligne[11] or time.time(),
                })
                self._entities[entite.entity_id] = entite

            for ligne in conn.execute(
                "SELECT relation_id, source_id, target_id, relation, sources, "
                "confidence, valid_from, valid_to, version, created_at FROM relations"
            ):
                lien = Relation.from_dict({
                    "relation_id": ligne[0], "source_id": ligne[1], "target_id": ligne[2],
                    "relation": ligne[3], "sources": json.loads(ligne[4] or "[]"),
                    "confidence": ligne[5], "valid_from": ligne[6], "valid_to": ligne[7],
                    "version": ligne[8] or 1, "created_at": ligne[9] or time.time(),
                })
                self._relations[lien.relation_id] = lien

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------
    def save_entity(self, entity: Entity) -> str:
        """Enregistre l'entité en mémoire **et** sur disque."""
        identifiant = super().save_entity(entity)
        enregistree = self._entities[identifiant]
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO entities (entity_id, type, label, aliases, "
                "scope, subject, sources, confidence, properties, version, created_at, "
                "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    enregistree.entity_id, enregistree.type.value, enregistree.label,
                    json.dumps(list(enregistree.aliases)), enregistree.scope,
                    enregistree.subject.value, json.dumps(list(enregistree.sources)),
                    enregistree.confidence, json.dumps(enregistree.properties),
                    enregistree.version, enregistree.created_at, enregistree.updated_at,
                ),
            )
        return identifiant

    def save_relation(self, relation: Relation) -> str:
        """Enregistre la relation, après la même vérification des extrémités."""
        identifiant = super().save_relation(relation)
        with self._db_lock, self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO relations (relation_id, source_id, target_id, "
                "relation, sources, confidence, valid_from, valid_to, version, "
                "created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    relation.relation_id, relation.source_id, relation.target_id,
                    relation.relation, json.dumps(list(relation.sources)),
                    relation.confidence, relation.valid_from, relation.valid_to,
                    relation.version, relation.created_at,
                ),
            )
        return identifiant

    def delete_entity(self, entity_id: str) -> bool:
        """Supprime l'entité et les relations qui la touchent, des deux côtés."""
        supprimee = super().delete_entity(entity_id)
        if not supprimee:
            return False
        with self._db_lock, self._get_connection() as conn:
            conn.execute("DELETE FROM entities WHERE entity_id = ?", (entity_id,))
            conn.execute(
                "DELETE FROM relations WHERE source_id = ? OR target_id = ?",
                (entity_id, entity_id),
            )
        return True

    def report(self) -> Dict[str, Any]:
        """Décrit le magasin, en nommant son support réel."""
        rapport = super().report()
        rapport["backend"] = "sqlite"
        rapport["db_path"] = self.db_path
        return rapport
