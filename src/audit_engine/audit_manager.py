"""
Gestionnaire du moteur d'audit.

``AuditManagerImpl`` est le point d'entrée métier du système d'audit.
Chaque méthode est protégée : la consignation d'un événement ne doit
jamais interrompre le déroulement normal de la plateforme.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .audit_store import InMemoryAuditStore
from .interfaces import AuditManager, AuditStore
from .types import AuditEvent

logger = logging.getLogger(__name__)


class AuditManagerImpl(AuditManager):
    """Implémentation du gestionnaire d'audit, tolérante aux pannes."""

    def __init__(self, store: Optional[AuditStore] = None) -> None:
        """
        Initialise le gestionnaire d'audit.

        Args:
            store: Stockage des événements (mémoire par défaut). Permet
                de brancher un backend persistant sans modifier l'appelant.
        """
        self._store = store or InMemoryAuditStore()
        self._logger = logger

    def record(self, event: AuditEvent) -> str:
        try:
            return self._store.save(event)
        except Exception as error:  # pragma: no cover - chemin de secours
            self._logger.warning(f"Consignation de l'audit impossible : {error}")
            return ""

    def get_event(self, event_id: str) -> Optional[AuditEvent]:
        try:
            return self._store.get(event_id)
        except Exception as error:  # pragma: no cover - chemin de secours
            self._logger.warning(f"Lecture de l'audit impossible : {error}")
            return None

    def list_events(self, limit: int = 100, **filters: Any) -> List[AuditEvent]:
        try:
            return self._store.list_events(limit=limit, **filters)
        except Exception as error:  # pragma: no cover - chemin de secours
            self._logger.warning(f"Liste des audits impossible : {error}")
            return []

    def search_events(self, query: str, limit: int = 50) -> List[AuditEvent]:
        try:
            return self._store.search_events(query, limit=limit)
        except Exception as error:  # pragma: no cover - chemin de secours
            self._logger.warning(f"Recherche dans les audits impossible : {error}")
            return []

    def count(self, **filters: Any) -> int:
        try:
            return self._store.count(**filters)
        except Exception as error:  # pragma: no cover - chemin de secours
            self._logger.warning(f"Comptage des audits impossible : {error}")
            return 0

    def clear(self) -> int:
        try:
            return self._store.clear()
        except Exception as error:  # pragma: no cover - chemin de secours
            self._logger.warning(f"Nettoyage des audits impossible : {error}")
            return 0

    def stats(self) -> Dict[str, Any]:
        try:
            return self._store.stats()
        except Exception as error:  # pragma: no cover - chemin de secours
            self._logger.warning(f"Statistiques d'audit impossibles : {error}")
            return {}

    def export_json(self, limit: int = 1000) -> str:
        try:
            events = self._store.list_events(limit=limit)
            payload = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total": len(events),
                "events": [event.to_dict() for event in events],
            }
            return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        except Exception as error:  # pragma: no cover - chemin de secours
            self._logger.warning(f"Export JSON des audits impossible : {error}")
            return ""
