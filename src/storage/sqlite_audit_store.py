"""
Stockage SQLite du journal d'audit (ADR-005).

Le journal vivait en mémoire du processus : **il disparaissait à chaque
redémarrage**. Tant que rien n'était déployé, cela ne coûtait rien. Le jour où
la plateforme sert, c'est la propriété la plus importante qu'un journal puisse
avoir qui manque : celle d'exister encore quand on vient chercher ce qui s'est
passé. Une clé révoquée, un accès refusé, une action d'agent approuvée —
autant de faits qu'on ne consulte qu'**après**, et souvent après un incident
qui a lui-même redémarré le service.

Suit le motif des sept autres magasins : `prepare_connection` pour les PRAGMA,
un `RLock`, du JSON pour les champs composés, et le fichier ramené à 0600.

Un point de conception : les filtres sont traduits en SQL plutôt qu'appliqués
en Python après lecture. Un journal se lit avec des filtres — « les échecs de
cet agent depuis hier » — et tout ramener pour trier ensuite ferait grossir le
coût avec le journal lui-même, c'est-à-dire au pire moment.
"""

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from src.audit_engine.interfaces import AuditStore
from src.audit_engine.types import AuditEvent, AuditEventType, AuditStatus
from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file

DEFAULT_FILENAME = "audit.sqlite"

_COLONNES = (
    "id", "event_type", "action", "agent_id", "request_id", "user_request",
    "model_id", "confidence", "knowledge_sources", "status",
    "execution_time_seconds", "detail", "metadata", "timestamp",
)


class SQLiteAuditStore(AuditStore):
    """Journal d'audit persistant."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Args:
            db_path: Fichier SQLite ; `GALSEN_DATA_DIR/audit.sqlite` par défaut.
        """
        self.db_path = db_path or default_sqlite_path(DEFAULT_FILENAME)
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._lock = threading.RLock()
        self._memoire: Optional[sqlite3.Connection] = None
        self._initialiser()
        secure_database_file(self.db_path)

    def _connexion(self) -> sqlite3.Connection:
        """Ouvre une connexion réglée comme les autres bases."""
        if self.db_path == ":memory:":
            if self._memoire is None:
                self._memoire = prepare_connection(
                    sqlite3.connect(":memory:", check_same_thread=False)
                )
            return self._memoire
        return prepare_connection(sqlite3.connect(self.db_path))

    def _initialiser(self) -> None:
        """Crée la table et ses index."""
        with self._lock:
            connexion = self._connexion()
            connexion.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id                     TEXT PRIMARY KEY,
                    event_type             TEXT NOT NULL,
                    action                 TEXT NOT NULL,
                    agent_id               TEXT,
                    request_id             TEXT,
                    user_request           TEXT,
                    model_id               TEXT,
                    confidence             REAL,
                    knowledge_sources      TEXT NOT NULL DEFAULT '[]',
                    status                 TEXT NOT NULL,
                    execution_time_seconds REAL,
                    detail                 TEXT,
                    metadata               TEXT NOT NULL DEFAULT '{}',
                    timestamp              REAL NOT NULL
                )
                """
            )
            # Les trois lectures qu'un journal reçoit vraiment : par requête
            # (une trace), par agent (un comportement), par date (un incident).
            connexion.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_request ON audit_events(request_id)"
            )
            connexion.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_events(agent_id)"
            )
            connexion.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(timestamp DESC)"
            )
            connexion.commit()

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    def save(self, event: AuditEvent) -> str:
        """Écrit un événement et retourne son identifiant."""
        with self._lock:
            connexion = self._connexion()
            connexion.execute(
                f"INSERT OR REPLACE INTO audit_events ({','.join(_COLONNES)}) "
                f"VALUES ({','.join('?' * len(_COLONNES))})",
                (
                    event.id,
                    event.event_type.value,
                    event.action,
                    event.agent_id,
                    event.request_id,
                    event.user_request,
                    event.model_id,
                    event.confidence,
                    json.dumps(event.knowledge_sources, ensure_ascii=False),
                    event.status.value,
                    event.execution_time_seconds,
                    event.detail,
                    json.dumps(event.metadata, ensure_ascii=False),
                    event.timestamp,
                ),
            )
            connexion.commit()
        return event.id

    def clear(self) -> int:
        """Vide le journal ; retourne le nombre d'événements effacés."""
        with self._lock:
            connexion = self._connexion()
            compte = connexion.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            connexion.execute("DELETE FROM audit_events")
            connexion.commit()
        return compte

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    @staticmethod
    def _depuis_ligne(ligne) -> AuditEvent:
        """Reconstruit un événement depuis une ligne."""
        return AuditEvent(
            id=ligne[0],
            event_type=AuditEventType(ligne[1]),
            action=ligne[2],
            agent_id=ligne[3],
            request_id=ligne[4],
            user_request=ligne[5],
            model_id=ligne[6],
            confidence=ligne[7],
            knowledge_sources=json.loads(ligne[8]),
            status=AuditStatus(ligne[9]),
            execution_time_seconds=ligne[10],
            detail=ligne[11],
            metadata=json.loads(ligne[12]),
            timestamp=ligne[13],
        )

    @staticmethod
    def _conditions(filters: Dict[str, Any]) -> tuple:
        """
        Traduit les filtres en SQL.

        Les mêmes clés que le magasin mémoire, pour que les deux répondent
        pareil : deux implémentations d'un contrat qui divergent, c'est le
        défaut que ce dépôt a déjà trouvé trois fois.
        """
        clauses, parametres = [], []
        for cle, attendu in filters.items():
            if hasattr(attendu, "value"):
                attendu = attendu.value
            if cle == "since":
                clauses.append("timestamp >= ?")
            elif cle == "until":
                clauses.append("timestamp <= ?")
            elif cle in _COLONNES:
                clauses.append(f"{cle} = ?")
            else:
                # Un filtre inconnu ne doit pas être ignoré en silence : il
                # rendrait plus de lignes que demandé, ce qu'un lecteur de
                # journal interpréterait comme une absence de filtre.
                raise ValueError(f"Filtre d'audit inconnu : {cle}")
            parametres.append(attendu)
        return clauses, parametres

    def get(self, event_id: str) -> Optional[AuditEvent]:
        """Retourne un événement par identifiant."""
        with self._lock:
            ligne = self._connexion().execute(
                f"SELECT {','.join(_COLONNES)} FROM audit_events WHERE id = ?", (event_id,)
            ).fetchone()
        return self._depuis_ligne(ligne) if ligne else None

    def list_events(self, limit: int = 100, **filters: Any) -> List[AuditEvent]:
        """Retourne les événements correspondant aux filtres, du plus récent au plus ancien."""
        clauses, parametres = self._conditions(filters)
        requete = f"SELECT {','.join(_COLONNES)} FROM audit_events"
        if clauses:
            requete += " WHERE " + " AND ".join(clauses)
        requete += " ORDER BY timestamp DESC LIMIT ?"
        parametres.append(limit)

        with self._lock:
            lignes = self._connexion().execute(requete, parametres).fetchall()
        return [self._depuis_ligne(ligne) for ligne in lignes]

    def search_events(self, query: str, limit: int = 50) -> List[AuditEvent]:
        """Cherche une chaîne dans les champs textuels d'un événement."""
        aiguille = query.strip().lower()
        if not aiguille:
            return []

        motif = f"%{aiguille}%"
        with self._lock:
            lignes = self._connexion().execute(
                f"SELECT {','.join(_COLONNES)} FROM audit_events WHERE "
                "LOWER(action) LIKE ? OR LOWER(COALESCE(detail,'')) LIKE ? OR "
                "LOWER(COALESCE(user_request,'')) LIKE ? OR "
                "LOWER(COALESCE(agent_id,'')) LIKE ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (motif, motif, motif, motif, limit),
            ).fetchall()
        return [self._depuis_ligne(ligne) for ligne in lignes]

    def count(self, **filters: Any) -> int:
        """Compte les événements correspondant aux filtres."""
        clauses, parametres = self._conditions(filters)
        requete = "SELECT COUNT(*) FROM audit_events"
        if clauses:
            requete += " WHERE " + " AND ".join(clauses)
        with self._lock:
            return self._connexion().execute(requete, parametres).fetchone()[0]

    def stats(self) -> Dict[str, Any]:
        """Retourne le volume du journal, par type et par statut."""
        with self._lock:
            connexion = self._connexion()
            total = connexion.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            par_type = dict(connexion.execute(
                "SELECT event_type, COUNT(*) FROM audit_events GROUP BY event_type"
            ).fetchall())
            par_statut = dict(connexion.execute(
                "SELECT status, COUNT(*) FROM audit_events GROUP BY status"
            ).fetchall())
        return {
            "total_events": total,
            "by_type": par_type,
            "by_status": par_statut,
            "path": self.db_path,
        }

    def close(self) -> None:
        """Ferme la connexion mémoire, s'il y en a une."""
        with self._lock:
            if self._memoire is not None:
                self._memoire.close()
                self._memoire = None
