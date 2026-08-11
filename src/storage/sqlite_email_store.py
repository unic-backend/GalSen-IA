"""
Stockage SQLite des messages électroniques.

Implémente l'interface EmailStore avec deux tables :
- emails : métadonnées du message
- email_attachments : pièces jointes binaires liées par FK
"""

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from src.services.email.interfaces import EmailStore
from src.services.email.types import EmailMessage, EmailAttachment, EmailStatus
from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file


class SQLiteEmailStore(EmailStore):
    """Stockage d'emails soutenu par SQLite."""

    _COLUMNS = (
        "id", "subject", "body", "sender", "recipients", "cc", "bcc",
        "reply_to", "is_html", "status", "metadata", "created_at", "sent_at",
    )

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or default_sqlite_path("service_email.sqlite")
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
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
        else:
            conn = sqlite3.connect(self.db_path)
        prepare_connection(conn)
        return conn

    def _initialize_db(self) -> None:
        """Crée les tables emails + attachments et leurs index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    recipients TEXT NOT NULL,
                    cc TEXT,
                    bcc TEXT,
                    reply_to TEXT,
                    is_html INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    metadata TEXT,
                    created_at REAL NOT NULL,
                    sent_at REAL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    data BLOB NOT NULL,
                    size INTEGER NOT NULL,
                    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_created_at ON emails(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attachments_email_id ON email_attachments(email_id)")
            conn.commit()

    def _item_to_dict(self, item: EmailMessage) -> Dict[str, Any]:
        """Convertit un EmailMessage en dictionnaire pour SQLite."""
        return {
            "id": item.id,
            "subject": item.subject,
            "body": item.body,
            "sender": item.sender,
            "recipients": json.dumps(item.recipients),
            "cc": json.dumps(item.cc) if item.cc else None,
            "bcc": json.dumps(item.bcc) if item.bcc else None,
            "reply_to": item.reply_to,
            "is_html": 1 if item.is_html else 0,
            "status": item.status.value,
            "metadata": json.dumps(item.metadata) if item.metadata else None,
            "created_at": item.created_at,
            "sent_at": item.sent_at,
        }

    def _dict_to_item(self, row: tuple, attachments: Optional[List[EmailAttachment]] = None) -> EmailMessage:
        """Convertit une ligne SQLite en EmailMessage."""
        d = dict(zip(self._COLUMNS, row))
        return EmailMessage(
            id=d["id"],
            subject=d["subject"],
            body=d["body"],
            sender=d["sender"],
            recipients=json.loads(d["recipients"]),
            cc=json.loads(d["cc"]) if d.get("cc") else [],
            bcc=json.loads(d["bcc"]) if d.get("bcc") else [],
            reply_to=d.get("reply_to"),
            attachments=attachments or [],
            is_html=bool(d["is_html"]),
            status=EmailStatus(d["status"]),
            metadata=json.loads(d["metadata"]) if d.get("metadata") else {},
            created_at=d["created_at"],
            sent_at=d.get("sent_at"),
        )

    def _load_attachments(self, email_id: str) -> List[EmailAttachment]:
        """Charge les pièces jointes d'un email."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT filename, content_type, data, size FROM email_attachments WHERE email_id = ?",
                (email_id,),
            )
            return [
                EmailAttachment(filename=r[0], content_type=r[1], data=r[2], size=r[3])
                for r in cursor.fetchall()
            ]

    def _save_attachments(self, email_id: str, attachments: List[EmailAttachment]) -> None:
        """Sauvegarde les pièces jointes d'un email."""
        if not attachments:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT INTO email_attachments (email_id, filename, content_type, data, size) VALUES (?, ?, ?, ?, ?)",
                [
                    (email_id, att.filename, att.content_type, att.data, att.size)
                    for att in attachments
                ],
            )
            conn.commit()

    def save(self, message: EmailMessage) -> str:
        """Enregistre un message et retourne son identifiant."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                data = self._item_to_dict(message)
                cursor.execute(
                    """INSERT OR REPLACE INTO emails (
                        id, subject, body, sender, recipients, cc, bcc,
                        reply_to, is_html, status, metadata, created_at, sent_at
                    ) VALUES (
                        :id, :subject, :body, :sender, :recipients, :cc, :bcc,
                        :reply_to, :is_html, :status, :metadata, :created_at, :sent_at
                    )""",
                    data,
                )
                conn.commit()
            self._save_attachments(message.id, message.attachments)
            return message.id

    def get(self, email_id: str) -> Optional[EmailMessage]:
        """Retourne un message par identifiant, ou None si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
            attachments = self._load_attachments(email_id)
            return self._dict_to_item(row, attachments)

    def list_emails(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> List[EmailMessage]:
        """Retourne les messages filtrés, du plus récent au plus ancien."""
        where_clauses: List[str] = []
        params: List[Any] = []

        if status is not None:
            where_clauses.append("status = ?")
            params.append(status)
        if sender is not None:
            where_clauses.append("sender = ?")
            params.append(sender)

        # Le filtre recipient vérifie à la fois recipients ET cc
        # On utilise SQL LIKE pour une recherche dans le JSON
        if recipient is not None:
            # Recherche dans le champ text JSON
            where_clauses.append("(recipients LIKE ? OR cc LIKE ?)")
            like_param = f"%{recipient}%"
            params.extend([like_param, like_param])

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = "WHERE " + where_sql

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = f"""
                    SELECT * FROM emails
                    {where_sql}
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, [*params, limit, offset])
                rows = cursor.fetchall()

            # Charger les messages sans pièces jointes pour le listing
            messages = []
            for row in rows:
                d = dict(zip(self._COLUMNS, row))
                messages.append(self._dict_to_item(row))

            # Filtrer en Python pour le recipient (vérification exacte)
            if recipient is not None:
                messages = [
                    m for m in messages
                    if recipient in m.recipients or recipient in m.cc
                ]

            return messages

    def update_status(self, email_id: str, status: str) -> bool:
        """Met à jour le statut d'un message ; retourne False si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Valider le statut
                try:
                    new_status = EmailStatus(status)
                except ValueError:
                    return False

                cursor.execute("SELECT id FROM emails WHERE id = ?", (email_id,))
                if cursor.fetchone() is None:
                    return False

                if new_status == EmailStatus.SENT:
                    cursor.execute(
                        "UPDATE emails SET status = ?, sent_at = ? WHERE id = ?",
                        (status, time.time(), email_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE emails SET status = ? WHERE id = ?",
                        (status, email_id),
                    )
                conn.commit()
            return True

    def delete(self, email_id: str) -> bool:
        """Supprime un message et ses pièces jointes ; retourne False si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Supprimer les pièces jointes d'abord (cascade optionnelle)
                cursor.execute("DELETE FROM email_attachments WHERE email_id = ?", (email_id,))
                cursor.execute("DELETE FROM emails WHERE id = ?", (email_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
            return deleted

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM emails")
                total = cursor.fetchone()[0]
                cursor.execute("SELECT status, COUNT(*) FROM emails GROUP BY status")
                by_status = dict(cursor.fetchall())
                cursor.execute("SELECT COUNT(DISTINCT sender) FROM emails")
                unique_senders = cursor.fetchone()[0]
            return {
                "total": total,
                "by_status": by_status,
                "unique_senders": unique_senders,
            }

    def clear(self) -> int:
        """Supprime tous les messages et pièces jointes."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM email_attachments")
                cursor.execute("DELETE FROM emails")
                count = cursor.rowcount
                conn.commit()
            return count

    def count(self) -> int:
        """Retourne le nombre total de messages."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM emails")
                return cursor.fetchone()[0]