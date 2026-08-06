"""
Modèles de données de la couche de connecteurs externes.

Définit les types partagés : catégorie de connecteur, statut de vérification,
résultat d'une vérification et description d'un connecteur.

Ce module n'a aucune dépendance externe.

Référence : ADR-007, VOLET 02 chapitre 09 (Integration Architecture).
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ConnectorKind(str, Enum):
    """
    Catégorie d'un système externe.

    Les valeurs reprennent les intégrations nommées au chapitre 09 du VOLET 02,
    afin que la couverture réelle de la plateforme soit énumérable plutôt
    qu'implicite.
    """

    EMAIL = "email"
    CALENDAR = "calendar"
    STORAGE = "storage"
    AUTHENTICATION = "authentication"
    PAYMENT = "payment"
    OTHER = "other"


class ConnectorStatus(str, Enum):
    """État d'un connecteur au moment de sa vérification."""

    # Le système externe répond
    READY = "ready"
    # Aucune configuration : les variables d'environnement attendues sont absentes
    NOT_CONFIGURED = "not_configured"
    # Configuré, mais le système externe ne répond pas
    UNREACHABLE = "unreachable"
    # Configuré et joignable, mais les identifiants sont refusés
    UNAUTHORIZED = "unauthorized"
    # Échec inattendu : la vérification elle-même a échoué
    ERROR = "error"


@dataclass
class ConnectorCheck:
    """
    Résultat de la vérification d'un connecteur.

    Une vérification ne lève jamais : un système externe injoignable est une
    information que l'appelant doit pouvoir lire, pas une panne de la plateforme
    (ADR-007).
    """

    connector_id: str
    kind: ConnectorKind
    status: ConnectorStatus
    detail: str = ""
    latency_ms: Optional[float] = None
    checked_at: float = field(default_factory=time.time)

    @property
    def is_ready(self) -> bool:
        """Indique si le connecteur est utilisable."""
        return self.status is ConnectorStatus.READY

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat en dictionnaire."""
        result: Dict[str, Any] = {
            "connector_id": self.connector_id,
            "kind": self.kind.value,
            "status": self.status.value,
            "checked_at": datetime.fromtimestamp(self.checked_at, tz=timezone.utc).isoformat(),
        }
        if self.detail:
            result["detail"] = self.detail
        if self.latency_ms is not None:
            result["latency_ms"] = round(self.latency_ms, 2)
        return result


@dataclass
class ConnectorDescription:
    """
    Description d'un connecteur : ce qu'il est, ce qu'il lit, ce qu'il sait faire.

    Le chapitre 09 exige que chaque intégration soit documentée. Cette
    description vit à côté du code pour qu'elle ne puisse pas diverger, et elle
    ne contient jamais de valeur de secret — seulement le **nom** des variables
    d'environnement consultées (ADR-004).
    """

    connector_id: str
    kind: ConnectorKind
    summary: str
    environment_variables: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)
    owner: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la description en dictionnaire."""
        result: Dict[str, Any] = {
            "connector_id": self.connector_id,
            "kind": self.kind.value,
            "summary": self.summary,
            "environment_variables": list(self.environment_variables),
            "operations": list(self.operations),
        }
        if self.owner:
            result["owner"] = self.owner
        return result
