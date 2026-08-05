"""
Contrats du moteur d'approbation.

Définit les interfaces abstraites `ApprovalStore` et `ApprovalManager`.
Tout backend de stockage (mémoire, SQLite, base de données, service externe)
peut être branché à l'avenir sans modifier le code appelant.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import ApprovalRequest


class ApprovalStore(ABC):
    """Contrat de stockage des demandes d'approbation."""

    @abstractmethod
    def submit(self, request: ApprovalRequest) -> str:
        """Enregistre une demande et retourne son identifiant."""

    @abstractmethod
    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        """Retourne une demande par identifiant, ou None si absente."""

    @abstractmethod
    def list_requests(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """Retourne les demandes filtrées, de la plus récente à la plus ancienne."""

    @abstractmethod
    def list_pending(self, limit: int = 100) -> List[ApprovalRequest]:
        """Retourne les demandes en attente, de la plus ancienne à la plus récente."""

    @abstractmethod
    def count(self, status: Optional[str] = None) -> int:
        """Compte les demandes, éventuellement filtrées par statut."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées sur les demandes."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime toutes les demandes et retourne le nombre supprimé."""

    @abstractmethod
    def approve(
        self,
        request_id: str,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> bool:
        """Approuve une demande en attente ; retourne False si impossible."""

    @abstractmethod
    def reject(
        self,
        request_id: str,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> bool:
        """Refuse une demande en attente ; retourne False si impossible."""


class ApprovalManager(ABC):
    """Contrat du gestionnaire d'approbation, façade du moteur."""

    @abstractmethod
    def submit(self, request: ApprovalRequest) -> Optional[str]:
        """Enregistre une demande et retourne son identifiant, ou None en cas d'échec."""

    @abstractmethod
    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        """Retourne une demande par identifiant, ou None si absente."""

    @abstractmethod
    def list_requests(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """Retourne les demandes filtrées, de la plus récente à la plus ancienne."""

    @abstractmethod
    def list_pending(self, limit: int = 100) -> List[ApprovalRequest]:
        """Retourne les demandes en attente, de la plus ancienne à la plus récente."""

    @abstractmethod
    def count(self, status: Optional[str] = None) -> int:
        """Compte les demandes, éventuellement filtrées par statut."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Retourne des statistiques agrégées sur les demandes."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime toutes les demandes et retourne le nombre supprimé."""

    @abstractmethod
    def approve(
        self,
        request_id: str,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> bool:
        """Approuve une demande en attente ; retourne False si impossible."""

    @abstractmethod
    def reject(
        self,
        request_id: str,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> bool:
        """Refuse une demande en attente ; retourne False si impossible."""
