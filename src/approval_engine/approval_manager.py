"""
Gestionnaire du moteur d'approbation.

Fournit `ApprovalManagerImpl`, une façade best-effort conforme à
`ApprovalManager` : chaque appel est protégé et ne lève jamais ; en cas
d'échec, un avertissement est journalisé et une valeur vide est retournée.
"""

import logging
from typing import Any, Dict, List, Optional

from .approval_store import InMemoryApprovalStore
from .interfaces import ApprovalManager, ApprovalStore
from .types import ApprovalRequest

logger = logging.getLogger(__name__)


class ApprovalManagerImpl(ApprovalManager):
    """Façade du moteur d'approbation, toujours disponible en mémoire."""

    def __init__(self, store: Optional[ApprovalStore] = None) -> None:
        self._store = store or InMemoryApprovalStore()
        self._logger = logging.getLogger(f"{__name__}.ApprovalManagerImpl")

    def submit(self, request: ApprovalRequest) -> Optional[str]:
        """Enregistre une demande et retourne son identifiant, ou None en cas d'échec."""
        try:
            return self._store.submit(request)
        except Exception as error:
            self._logger.warning("Échec de la soumission d'une demande : %s", error)
            return None

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        """Retourne une demande par identifiant, ou None si absente."""
        try:
            return self._store.get(request_id)
        except Exception as error:
            self._logger.warning("Échec de la lecture de la demande %s : %s", request_id, error)
            return None

    def list_requests(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """Retourne les demandes filtrées, de la plus récente à la plus ancienne."""
        try:
            return self._store.list_requests(
                limit=limit, status=status, agent_id=agent_id, request_id=request_id
            )
        except Exception as error:
            self._logger.warning("Échec du filtrage des demandes : %s", error)
            return []

    def list_pending(self, limit: int = 100) -> List[ApprovalRequest]:
        """Retourne les demandes en attente, de la plus ancienne à la plus récente."""
        try:
            return self._store.list_pending(limit=limit)
        except Exception as error:
            self._logger.warning("Échec de la lecture des demandes en attente : %s", error)
            return []

    def count(self, status: Optional[str] = None) -> int:
        """Compte les demandes, éventuellement filtrées par statut."""
        try:
            return self._store.count(status=status)
        except Exception as error:
            self._logger.warning("Échec du comptage des demandes : %s", error)
            return 0

    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées sur les demandes."""
        try:
            return self._store.stats()
        except Exception as error:
            self._logger.warning("Échec du calcul des statistiques : %s", error)
            return {}

    def clear(self) -> int:
        """Supprime toutes les demandes et retourne le nombre supprimé."""
        try:
            return self._store.clear()
        except Exception as error:
            self._logger.warning("Échec de la suppression des demandes : %s", error)
            return 0

    def approve(
        self,
        request_id: str,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> bool:
        """Approuve une demande en attente ; retourne False si impossible."""
        try:
            return self._store.approve(request_id, reason=reason, decided_by=decided_by)
        except Exception as error:
            self._logger.warning("Échec de l'approbation %s : %s", request_id, error)
            return False

    def reject(
        self,
        request_id: str,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> bool:
        """Refuse une demande en attente ; retourne False si impossible."""
        try:
            return self._store.reject(request_id, reason=reason, decided_by=decided_by)
        except Exception as error:
            self._logger.warning("Échec du refus %s : %s", request_id, error)
            return False
