"""
Stockage SQLite des événements de calendrier.

Implémente l'interface CalendarStore en utilisant SQLite pour la persistance.
"""

import json
import os
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from services.calendar.interfaces import CalendarStore
from services.calendar.types import CalendarEvent, EventStatus, EventVisibility
from storage.paths import default_sqlite_path


class SQLiteCalendarStore(CalendarStore):
    """Stockage d'événements de calendrier soutenu par SQLite."""

    _COLUMNS = (
        "id", "title", "start_time", "end_time", "description",
        "location", "organizer", "attendees", "status", "visibility",
        "recurrence", "metadata", "created_at", "updated_at",
    )

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or default_sqlite_path("service_calendar.sqlite")
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
        """Crée la table des événements et ses index."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    description TEXT,
                    location TEXT,
                    organizer TEXT,
                    attendees TEXT,
                    status TEXT NOT NULL,
                    visibility TEXT NOT NULL,
                    recurrence TEXT,
                    metadata TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cal_status ON calendar_events(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cal_organizer ON calendar_events(organizer)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cal_start_time ON calendar_events(start_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cal_created_at ON calendar_events(created_at DESC)")
            conn.commit()

    def _item_to_dict(self, item: CalendarEvent) -> Dict[str, Any]:
        """Convertit un CalendarEvent en dictionnaire pour SQLite."""
        return {
            "id": item.id,
            "title": item.title,
            "start_time": item.start_time,
            "end_time": item.end_time,
            "description": item.description,
            "location": item.location,
            "organizer": item.organizer,
            "attendees": json.dumps(item.attendees) if item.attendees else None,
            "status": item.status.value,
            "visibility": item.visibility.value,
            "recurrence": item.recurrence,
            "metadata": json.dumps(item.metadata) if item.metadata else None,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def _dict_to_item(self, row: tuple) -> CalendarEvent:
        """Convertit une ligne SQLite en CalendarEvent."""
        d = dict(zip(self._COLUMNS, row))
        return CalendarEvent(
            id=d["id"],
            title=d["title"],
            start_time=d["start_time"],
            end_time=d["end_time"],
            description=d.get("description"),
            location=d.get("location"),
            organizer=d.get("organizer"),
            attendees=json.loads(d["attendees"]) if d.get("attendees") else [],
            status=EventStatus(d["status"]),
            visibility=EventVisibility(d["visibility"]),
            recurrence=d.get("recurrence"),
            metadata=json.loads(d["metadata"]) if d.get("metadata") else {},
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    def save(self, event: CalendarEvent) -> str:
        """Enregistre un événement et retourne son identifiant."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                data = self._item_to_dict(event)
                cursor.execute(
                    """INSERT OR REPLACE INTO calendar_events (
                        id, title, start_time, end_time, description,
                        location, organizer, attendees, status, visibility,
                        recurrence, metadata, created_at, updated_at
                    ) VALUES (
                        :id, :title, :start_time, :end_time, :description,
                        :location, :organizer, :attendees, :status, :visibility,
                        :recurrence, :metadata, :created_at, :updated_at
                    )""",
                    data,
                )
                conn.commit()
            return event.id

    def get(self, event_id: str) -> Optional[CalendarEvent]:
        """Retourne un événement par identifiant, ou None si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM calendar_events WHERE id = ?", (event_id,))
                row = cursor.fetchone()
                if row is None:
                    return None
                return self._dict_to_item(row)

    def list_events(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        organizer: Optional[str] = None,
        start_after: Optional[str] = None,
        start_before: Optional[str] = None,
    ) -> List[CalendarEvent]:
        """Retourne les événements filtrés, triés par date de début."""
        where_clauses: List[str] = []
        params: List[Any] = []

        if status is not None:
            where_clauses.append("status = ?")
            params.append(status)
        if organizer is not None:
            where_clauses.append("organizer = ?")
            params.append(organizer)
        if start_after is not None:
            where_clauses.append("start_time >= ?")
            params.append(start_after)
        if start_before is not None:
            where_clauses.append("start_time <= ?")
            params.append(start_before)

        where_sql = " AND ".join(where_clauses)
        if where_sql:
            where_sql = "WHERE " + where_sql

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = f"""
                    SELECT * FROM calendar_events
                    {where_sql}
                    ORDER BY start_time ASC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, [*params, limit, offset])
                rows = cursor.fetchall()
            return [self._dict_to_item(row) for row in rows]

    def update(self, event_id: str, updates: Dict[str, Any]) -> bool:
        """Met à jour un événement partiellement ; retourne False si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Vérifier l'existence
                cursor.execute("SELECT id FROM calendar_events WHERE id = ?", (event_id,))
                if cursor.fetchone() is None:
                    return False

                set_parts: List[str] = []
                params: List[Any] = []
                for key, value in updates.items():
                    if key in ("id", "created_at"):
                        continue
                    if key == "status" and isinstance(value, EventStatus):
                        value = value.value
                    if key == "visibility" and isinstance(value, EventVisibility):
                        value = value.value
                    if key == "attendees":
                        value = json.dumps(value)
                    if key == "metadata":
                        value = json.dumps(value)
                    set_parts.append(f"{key} = ?")
                    params.append(value)

                set_parts.append("updated_at = ?")
                params.append(time.time())
                params.append(event_id)

                cursor.execute(
                    f"UPDATE calendar_events SET {', '.join(set_parts)} WHERE id = ?",
                    params,
                )
                conn.commit()
            return True

    def delete(self, event_id: str) -> bool:
        """Supprime un événement ; retourne False si absent."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
                deleted = cursor.rowcount > 0
                conn.commit()
            return deleted

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM calendar_events")
                total = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM calendar_events WHERE status = 'confirmed'")
                upcoming = cursor.fetchone()[0]
                cursor.execute("SELECT status, COUNT(*) FROM calendar_events GROUP BY status")
                by_status = dict(cursor.fetchall())
            return {"total": total, "upcoming": upcoming, "by_status": by_status}

    def clear(self) -> int:
        """Supprime tous les événements et retourne le nombre supprimé."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM calendar_events")
                count = cursor.rowcount
                conn.commit()
            return count

    def count(self) -> int:
        """Retourne le nombre total d'événements."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM calendar_events")
                return cursor.fetchone()[0]