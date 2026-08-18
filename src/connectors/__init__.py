"""
Couche de connecteurs externes.

Un connecteur est le propriétaire, côté plateforme, d'un système externe :
messagerie, calendrier, stockage, authentification, paiement. Il répond à trois
questions sans déclencher la moindre action métier — qui es-tu, es-tu configuré,
réponds-tu — ce qui permet d'auditer un déploiement sans envoyer d'e-mail ni
écrire un fichier.

Connecteurs disponibles : `SMTPEmailConnector` (messagerie),
`LocalDiskStorageConnector` (stockage sur disque).
Les suivants arrivent un par un, chacun avec ses propres tests.

Référence : ADR-007, VOLET 02 chapitre 09 (Integration Architecture).
"""

from .email_connector import SMTPEmailConnector
from .interfaces import Connector, ConnectorRegistryContract
from .storage_connector import LocalDiskStorageConnector, StorageAccessError
from .sdk import (
    VERSION_DU_CONTRAT,
    connector_contract,
    connector_refusal_rules,
)
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
    "VERSION_DU_CONTRAT",
    "connector_contract",
    "connector_refusal_rules",
    "Connector",
    "ConnectorCheck",
    "ConnectorDescription",
    "ConnectorKind",
    "ConnectorRegistry",
    "ConnectorRegistryContract",
    "ConnectorStatus",
    "LocalDiskStorageConnector",
    "SMTPEmailConnector",
    "StorageAccessError",
    "get_shared_connector_registry",
    "reset_shared_connector_registry",
]
