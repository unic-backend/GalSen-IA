"""
Stockage en mémoire des demandes d'approbation.

Fournit `InMemoryApprovalStore`, une implémentation thread-safe du contrat
`ApprovalStore`. La file est conservée en mémoire pour la Phase 3 ; la
persistance (SQLite) est planifiée avec ADR-005 sans changer ce module.
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from .interfaces import ApprovalStore
from .types import ApprovalRequest, ApprovalStatus

logger = logging.getLogger(__name__)


class InMemoryApprovalStore(ApprovalStore):
    """File d'approbation en mémoire, thread-safe, conforme à `ApprovalStore`."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._requests: Dict[str, ApprovalRequest] = {}
        self._order: List[str] = []

    def submit(self, request: ApprovalRequest) -> str:
        """Enregistre une demande et retourne son identifiant."""
        with self._lock:
            if request.id in self._requests:
                raise ValueError(f"La demande {request.id} existe déjà.")
            self._requests[request.id] = request
            self._order.append(request.id)
            return request.id

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        """Retourne une demande par identifiant, ou None si absente."""
        with self._lock:
            return self._requests.get(request_id)

    def _matches(
        self,
        request: ApprovalRequest,
        status: Optional[str],
        agent_id: Optional[str],
        request_id: Optional[str],
    ) -> bool:
        """Vérifie si une demande correspond aux filtres fournis."""
        if status is not None and request.status != status:
            return False
        if agent_id is not None and request.agent_id != agent_id:
            return False
        if request_id is not None and request.request_id != request_id:
            return False
        return True

    def list_requests(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """Retourne les demandes filtrées, de la plus récente à la plus ancienne."""
        with self._lock:
            matched: List[ApprovalRequest] = []
            for request_id_key in reversed(self._order):
                if len(matched) >= limit:
                    break
                request = self._requests[request_id_key]
                if self._matches(request, status, agent_id, request_id):
                    matched.append(request)
            return matched

    def list_pending(self, limit: int = 100) -> List[ApprovalRequest]:
        """Retourne les demandes en attente, de la plus ancienne à la plus récente."""
        with self._lock:
            pending: List[ApprovalRequest] = []
            for request_id_key in self._order:
                if len(pending) >= limit:
                    break
                request = self._requests[request_id_key]
                if request.status == ApprovalStatus.PENDING.value:
                    pending.append(request)
            return pending

    def count(self, status: Optional[str] = None) -> int:
        """Compte les demandes, éventuellement filtrées par statut."""
        with self._lock:
            if status is None:
                return len(self._order)
            return sum(
                1
                for request in self._requests.values()
                if request.status == status
            )

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées sur les demandes."""
        with self._lock:
            total = len(self._order)
            counts = {
                item.value: sum(
                    1 for request in self._requests.values() if request.status == item.value
                )
                for item in ApprovalStatus
            }
            return {
                "total": total,
                "by_status": counts,
                "pending": counts.get(ApprovalStatus.PENDING.value, 0),
                "approved": counts.get(ApprovalStatus.APPROVED.value, 0),
                "rejected": counts.get(ApprovalStatus.REJECTED.value, 0),
                "expired": counts.get(ApprovalStatus.EXPIRED.value, 0),
            }

    def clear(self) -> int:
        """Supprime toutes les demandes et retourne le nombre supprimé."""
        with self._lock:
            count = len(self._order)
            self._requests.clear()
            self._order.clear()
            return count

    def _decide(
        self,
        request_id: str,
        new_status: str,
        reason: Optional[str],
        decided_by: Optional[str],
    ) -> bool:
        """Applique une décision humaine à une demande en attente."""
        with self._lock:
            request = self._requests.get(request_id)
            if request is None:
                return False
            if request.status != ApprovalStatus.PENDING.value:
                return False
            request.status = new_status
            request.decided_at = time.time()
            request.reason = reason
            request.decided_by = decided_by
            return True

    def approve(
        self,
        request_id: str,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> bool:
        """Approuve une demande en attente ; retourne False si impossible."""
        return self._decide(
            request_id, ApprovalStatus.APPROVED.value, reason, decided_by
        )

    def reject(
        self,
        request_id: str,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> bool:
        """Refuse une demande en attente ; retourne False si impossible."""
        return self._decide(
            request_id, ApprovalStatus.REJECTED.value, reason, decided_by
        )
