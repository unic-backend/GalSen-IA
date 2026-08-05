"""
Moteur d'approbation humaine (Human Approval Gate).

Permet à un agent de suspendre une action dans l'état `requires_approval`
jusqu'à ce qu'un humain l'approuve ou la refuse. Chaque soumission et
chaque décision est traçable dans le moteur d'audit.

Référence : ADR-006 (Human Approval Gate).
"""

from .approval_manager import ApprovalManagerImpl
from .approval_store import InMemoryApprovalStore
from .interfaces import ApprovalManager, ApprovalStore
from .types import (
    ApprovalRequest,
    ApprovalStatus,
    generate_approval_request_id,
)

__all__ = [
    "ApprovalManager",
    "ApprovalManagerImpl",
    "ApprovalRequest",
    "ApprovalStatus",
    "ApprovalStore",
    "InMemoryApprovalStore",
    "generate_approval_request_id",
]
