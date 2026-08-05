"""
Moteur d'audit de GalSen IA.

Trace structurée des actions importantes effectuées par la plateforme :
timestamp, request_id, agent_id, requête utilisateur, modèle utilisé,
niveau de confiance, sources de connaissance, statut d'exécution et
temps d'exécution.

Architecture réutilisable : les composants sont injectés via les contrats
``AuditStore`` et ``AuditManager``, ce qui permet de brancher un backend
persistant sans modifier le code appelant.
"""

from .audit_manager import AuditManagerImpl
from .audit_store import InMemoryAuditStore
from .interfaces import AuditManager, AuditStore
from .types import (
    AuditEvent,
    AuditEventType,
    AuditStatus,
    KnowledgeSourceRef,
    generate_request_id,
)

__all__ = [
    "AuditManager",
    "AuditManagerImpl",
    "AuditStore",
    "InMemoryAuditStore",
    "AuditEvent",
    "AuditEventType",
    "AuditStatus",
    "KnowledgeSourceRef",
    "generate_request_id",
]
