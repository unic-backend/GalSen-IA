"""
Stockage en mémoire des événements d'audit.

Implémentation ``InMemoryAuditStore`` conforme au contrat ``AuditStore``.
Thread-safe (verrou RLock), tri du plus récent au plus ancien, filtres
par type/statut/identifiants/intervalle de temps, recherche textuelle
insensible à la casse et statistiques agrégées.
"""

import threading
from typing import Any, Dict, List, Optional

from .interfaces import AuditStore
from .types import AuditEvent


class InMemoryAuditStore(AuditStore):
    """Stockage des événements d'audit dans un dictionnaire en mémoire."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._events: Dict[str, AuditEvent] = {}
        self._order: List[str] = []

    def save(self, event: AuditEvent) -> str:
        with self._lock:
            self._events[event.id] = event
            self._order.append(event.id)
        return event.id

    def get(self, event_id: str) -> Optional[AuditEvent]:
        with self._lock:
            return self._events.get(event_id)

    def list_events(self, limit: int = 100, **filters: Any) -> List[AuditEvent]:
        with self._lock:
            matched = [self._events[event_id] for event_id in reversed(self._order)]
        if filters:
            matched = [event for event in matched if self._matches(event, filters)]
        return matched[:limit]

    def search_events(self, query: str, limit: int = 50) -> List[AuditEvent]:
        needle = query.strip().lower()
        if not needle:
            return []
        with self._lock:
            matched = [
                self._events[event_id]
                for event_id in reversed(self._order)
                if self._contains(self._events[event_id], needle)
            ]
        return matched[:limit]

    def count(self, **filters: Any) -> int:
        with self._lock:
            if not filters:
                return len(self._order)
            return sum(1 for event in self._events.values() if self._matches(event, filters))

    def clear(self) -> int:
        with self._lock:
            total = len(self._order)
            self._events.clear()
            self._order.clear()
        return total

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._order)
            by_status: Dict[str, int] = {}
            by_type: Dict[str, int] = {}
            by_agent: Dict[str, int] = {}
            timed_events: List[float] = []
            oldest: Optional[float] = None
            newest: Optional[float] = None
            for event_id in self._order:
                event = self._events[event_id]
                by_status[event.status.value] = by_status.get(event.status.value, 0) + 1
                by_type[event.event_type.value] = by_type.get(event.event_type.value, 0) + 1
                agent = event.agent_id or "unknown"
                by_agent[agent] = by_agent.get(agent, 0) + 1
                if event.execution_time_seconds is not None:
                    timed_events.append(event.execution_time_seconds)
                if oldest is None or event.timestamp < oldest:
                    oldest = event.timestamp
                if newest is None or event.timestamp > newest:
                    newest = event.timestamp
        result: Dict[str, Any] = {
            "total_events": total,
            "by_status": by_status,
            "by_type": by_type,
            "by_agent": by_agent,
        }
        if timed_events:
            result["average_execution_time_seconds"] = sum(timed_events) / len(timed_events)
        if oldest is not None:
            result["oldest_timestamp_unix"] = oldest
        if newest is not None:
            result["newest_timestamp_unix"] = newest
        if oldest is not None and newest is not None:
            result["time_span_seconds"] = newest - oldest
        return result

    @staticmethod
    def _contains(event: AuditEvent, needle: str) -> bool:
        """Vérifie si la requête apparaît dans un des champs textuels."""
        haystack = (
            event.user_request,
            event.action,
            event.detail,
            event.agent_id,
            event.model_id,
            event.request_id,
        )
        return any(value and needle in value.lower() for value in haystack)

    @staticmethod
    def _matches(event: AuditEvent, filters: Dict[str, Any]) -> bool:
        """Vérifie qu'un événement satisfait tous les filtres fournis."""
        for key, expected in filters.items():
            if key in ("event_type", "status"):
                actual = getattr(event, key).value
                if hasattr(expected, "value"):
                    expected = expected.value
                if actual != expected:
                    return False
            elif key == "since":
                if event.timestamp < expected:
                    return False
            elif key == "until":
                if event.timestamp > expected:
                    return False
            elif getattr(event, key, None) != expected:
                return False
        return True
