"""
Stockage SQLite des demandes d'approbation (ADR-005, ADR-006).

Les demandes vivaient en mémoire du processus. Le portillon d'approbation
devient obligatoire pour toute écriture de code (VOLET 31) : une demande perdue
au redémarrage, c'est une modification qui attend une décision que plus personne
ne peut prendre — ou pire, une décision **déjà accordée** qui disparaît, et un
agent qui redemande ce qui avait été refusé.

Suit le motif des autres magasins : `prepare_connection`, un `RLock`, du JSON
pour les métadonnées, le fichier en 0600.

Une garantie est portée par le schéma plutôt que par le code : une décision ne
s'applique qu'à une demande **en attente**. `_decide` filtre sur le statut dans
son `UPDATE`, donc deux décisions concurrentes ne peuvent pas toutes deux
réussir — la seconde ne modifie aucune ligne et retourne False, ce qui est
exactement le comportement du magasin mémoire sous verrou.
"""

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from src.approval_engine.interfaces import ApprovalStore
from src.approval_engine.types import ApprovalRequest, ApprovalStatus
from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file

DEFAULT_FILENAME = "approvals.sqlite"

_COLONNES = (
    "id", "agent_id", "request_id", "action", "description", "confidence",
    "metadata", "status", "created_at", "decided_at", "reason", "decided_by",
)


class SQLiteApprovalStore(ApprovalStore):
    """Magasin de demandes d'approbation persistant."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """
        Args:
            db_path: Fichier SQLite ; `GALSEN_DATA_DIR/approvals.sqlite` par défaut.
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
                CREATE TABLE IF NOT EXISTS approval_requests (
                    id          TEXT PRIMARY KEY,
                    agent_id    TEXT NOT NULL,
                    request_id  TEXT,
                    action      TEXT NOT NULL,
                    description TEXT,
                    confidence  REAL,
                    metadata    TEXT NOT NULL DEFAULT '{}',
                    status      TEXT NOT NULL,
                    created_at  REAL NOT NULL,
                    decided_at  REAL,
                    reason      TEXT,
                    decided_by  TEXT
                )
                """
            )
            # « Qu'est-ce qui attend une décision » est la seule question posée
            # en boucle par une interface d'approbation.
            connexion.execute(
                "CREATE INDEX IF NOT EXISTS idx_approval_status "
                "ON approval_requests(status, created_at)"
            )
            connexion.commit()

    @staticmethod
    def _depuis_ligne(ligne) -> ApprovalRequest:
        """Reconstruit une demande depuis une ligne."""
        return ApprovalRequest(
            id=ligne[0],
            agent_id=ligne[1],
            request_id=ligne[2],
            action=ligne[3],
            description=ligne[4],
            confidence=ligne[5],
            metadata=json.loads(ligne[6]),
            status=ligne[7],
            created_at=ligne[8],
            decided_at=ligne[9],
            reason=ligne[10],
            decided_by=ligne[11],
        )

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    def submit(self, request: ApprovalRequest) -> str:
        """Enregistre une demande et retourne son identifiant."""
        with self._lock:
            connexion = self._connexion()
            connexion.execute(
                f"INSERT OR REPLACE INTO approval_requests ({','.join(_COLONNES)}) "
                f"VALUES ({','.join('?' * len(_COLONNES))})",
                (
                    request.id,
                    request.agent_id,
                    request.request_id,
                    request.action,
                    request.description,
                    request.confidence,
                    json.dumps(request.metadata, ensure_ascii=False),
                    request.status,
                    request.created_at,
                    request.decided_at,
                    request.reason,
                    request.decided_by,
                ),
            )
            connexion.commit()
        return request.id

    def _decide(
        self,
        request_id: str,
        new_status: str,
        reason: Optional[str],
        decided_by: Optional[str],
    ) -> bool:
        """
        Applique une décision humaine à une demande **en attente**.

        Le filtre sur le statut est dans l'`UPDATE` : deux décisions
        concurrentes ne peuvent pas toutes deux réussir, la seconde ne touche
        aucune ligne. Vérifier puis écrire en deux temps laisserait une fenêtre
        où une demande serait approuvée **et** rejetée.
        """
        with self._lock:
            connexion = self._connexion()
            curseur = connexion.execute(
                "UPDATE approval_requests SET status = ?, decided_at = ?, reason = ?, "
                "decided_by = ? WHERE id = ? AND status = ?",
                (new_status, time.time(), reason, decided_by, request_id,
                 ApprovalStatus.PENDING.value),
            )
            connexion.commit()
            return curseur.rowcount > 0

    def approve(self, request_id: str, reason: Optional[str] = None,
                decided_by: Optional[str] = None) -> bool:
        """Approuve une demande en attente."""
        return self._decide(request_id, ApprovalStatus.APPROVED.value, reason, decided_by)

    def reject(self, request_id: str, reason: Optional[str] = None,
               decided_by: Optional[str] = None) -> bool:
        """Rejette une demande en attente."""
        return self._decide(request_id, ApprovalStatus.REJECTED.value, reason, decided_by)

    def clear(self) -> int:
        """Vide le magasin ; retourne le nombre de demandes effacées."""
        with self._lock:
            connexion = self._connexion()
            compte = connexion.execute("SELECT COUNT(*) FROM approval_requests").fetchone()[0]
            connexion.execute("DELETE FROM approval_requests")
            connexion.commit()
        return compte

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        """Retourne une demande par identifiant."""
        with self._lock:
            ligne = self._connexion().execute(
                f"SELECT {','.join(_COLONNES)} FROM approval_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        return self._depuis_ligne(ligne) if ligne else None

    def list_requests(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """Retourne les demandes filtrées, de la plus récente à la plus ancienne."""
        clauses, parametres = [], []
        for colonne, valeur in (("status", status), ("agent_id", agent_id),
                                ("request_id", request_id)):
            if valeur is not None:
                clauses.append(f"{colonne} = ?")
                parametres.append(valeur)

        requete = f"SELECT {','.join(_COLONNES)} FROM approval_requests"
        if clauses:
            requete += " WHERE " + " AND ".join(clauses)
        requete += " ORDER BY created_at DESC LIMIT ?"
        parametres.append(limit)

        with self._lock:
            lignes = self._connexion().execute(requete, parametres).fetchall()
        return [self._depuis_ligne(ligne) for ligne in lignes]

    def list_pending(self, limit: int = 100) -> List[ApprovalRequest]:
        """
        Retourne les demandes en attente, **de la plus ancienne à la plus récente**.

        L'ordre est inverse de `list_requests` à dessein : une file d'attente se
        traite par le début, et c'est le comportement du magasin mémoire.
        """
        with self._lock:
            lignes = self._connexion().execute(
                f"SELECT {','.join(_COLONNES)} FROM approval_requests "
                "WHERE status = ? ORDER BY created_at ASC LIMIT ?",
                (ApprovalStatus.PENDING.value, limit),
            ).fetchall()
        return [self._depuis_ligne(ligne) for ligne in lignes]

    def count(self, status: Optional[str] = None) -> int:
        """Compte les demandes, éventuellement filtrées par statut."""
        with self._lock:
            if status is None:
                return self._connexion().execute(
                    "SELECT COUNT(*) FROM approval_requests"
                ).fetchone()[0]
            return self._connexion().execute(
                "SELECT COUNT(*) FROM approval_requests WHERE status = ?", (status,)
            ).fetchone()[0]

    def stats(self) -> Dict[str, Any]:
        """Retourne le volume des demandes, par statut."""
        with self._lock:
            connexion = self._connexion()
            total = connexion.execute("SELECT COUNT(*) FROM approval_requests").fetchone()[0]
            par_statut = dict(connexion.execute(
                "SELECT status, COUNT(*) FROM approval_requests GROUP BY status"
            ).fetchall())
        return {
            "total_requests": total,
            "by_status": par_statut,
            "pending": par_statut.get(ApprovalStatus.PENDING.value, 0),
            "path": self.db_path,
        }

    def close(self) -> None:
        """Ferme la connexion mémoire, s'il y en a une."""
        with self._lock:
            if self._memoire is not None:
                self._memoire.close()
                self._memoire = None
