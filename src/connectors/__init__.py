"""
Couche de connecteurs externes.

Un connecteur est le propriétaire, côté plateforme, d'un système externe :
messagerie, calendrier, stockage, authentification, paiement. Il répond à trois
questions sans déclencher la moindre action métier — qui es-tu, es-tu configuré,
réponds-tu — ce qui permet d'auditer un déploiement sans envoyer d'e-mail ni
écrire un fichier.

La couche démarre vide : chaque connecteur concret arrive avec ses propres tests.

Référence : ADR-007, VOLET 02 chapitre 09 (Integration Architecture).
"""

from .interfaces import Connector, ConnectorRegistryContract
from .registry import (
    ConnectorRegistry,
    get_shared_connector_registry,
    reset_shared_connector_registry,
)
from .types import (
    ConnectorCheck,
    ConnectorDescription,
    ConnectorKind,
    ConnectorStatus,
)

__all__ = [
    "Connector",
    "ConnectorCheck",
    "ConnectorDescription",
    "ConnectorKind",
    "ConnectorRegistry",
    "ConnectorRegistryContract",
    "ConnectorStatus",
    "get_shared_connector_registry",
    "reset_shared_connector_registry",
]
