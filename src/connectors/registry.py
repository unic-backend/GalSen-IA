"""
Registre des connecteurs externes.

Fournit `ConnectorRegistry`, l'inventaire des systèmes externes que la
plateforme sait joindre. Le registre est thread-safe et best-effort : un
connecteur dont la vérification échoue est rapporté en erreur, jamais propagé
à l'appelant.

Référence : ADR-007, VOLET 02 chapitre 09 (Integration Architecture).
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from .contract import verify_contract
from .interfaces import Connector, ConnectorRegistryContract
from .safety import privileges_of, verify_privileges
from .types import ConnectorCheck, ConnectorKind, ConnectorStatus

logger = logging.getLogger(__name__)


class ConnectorRegistry(ConnectorRegistryContract):
    """Inventaire des connecteurs externes, thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._connectors: Dict[str, Connector] = {}
        self._logger = logging.getLogger(f"{__name__}.ConnectorRegistry")

    def register(self, connector: Connector) -> None:
        """
        Enregistre un connecteur.

        Args:
            connector: Le connecteur à enregistrer

        Raises:
            ValueError: Si l'identifiant est vide ou déjà pris. Un doublon
                silencieux ferait disparaître une intégration sans trace, ce que
                le chapitre 09 interdit (« clear ownership of every integration »).
        """
        connector_id = connector.connector_id
        if not connector_id or not str(connector_id).strip():
            raise ValueError("Un connecteur doit avoir un identifiant non vide.")

        # Le contrat de données est exigé **ici**, au seul endroit par lequel
        # un connecteur devient atteignable. Le vérifier plus tard reviendrait
        # à le vérifier après le premier appel (VOLET 41).
        #
        # L'attribut est lu brut, et non par `contract_of` : celui-ci rend
        # `None` pour un contrat mal typé, et le message dirait alors « aucun
        # contrat » à quelqu'un qui en a écrit un. Un diagnostic faux coûte
        # plus cher qu'un diagnostic absent.
        verify_contract(connector_id, getattr(connector, "data_contract", None))

        # Les privilèges demandés sont vérifiés au même endroit et pour la même
        # raison : une demande excessive doit être refusée **avant** qu'un écran
        # de consentement ne soit montré à qui que ce soit (VOLET 42).
        verify_privileges(connector_id, privileges_of(connector))

        with self._lock:
            existing = self._connectors.get(connector_id)
            if existing is not None and existing is not connector:
                raise ValueError(f"Le connecteur '{connector_id}' est déjà enregistré.")
            self._connectors[connector_id] = connector

        self._logger.info(
            "Connecteur enregistré : %s (%s)", connector_id, connector.kind.value
        )

    def unregister(self, connector_id: str) -> bool:
        """Retire un connecteur ; retourne False s'il était absent."""
        with self._lock:
            return self._connectors.pop(connector_id, None) is not None

    def get(self, connector_id: str) -> Optional[Connector]:
        """Retourne un connecteur par identifiant, ou None s'il est inconnu."""
        with self._lock:
            return self._connectors.get(connector_id)

    def list_connectors(self, kind: Optional[ConnectorKind] = None) -> List[Connector]:
        """
        Retourne les connecteurs enregistrés, triés par identifiant.

        Args:
            kind: Ne retenir que cette catégorie, ou None pour tout retourner
        """
        with self._lock:
            connectors = list(self._connectors.values())

        if kind is not None:
            connectors = [c for c in connectors if c.kind is kind]
        return sorted(connectors, key=lambda c: c.connector_id)

    def kinds(self) -> List[ConnectorKind]:
        """Retourne les catégories effectivement couvertes, triées."""
        seen = {connector.kind for connector in self.list_connectors()}
        return sorted(seen, key=lambda k: k.value)

    def count(self) -> int:
        """Retourne le nombre de connecteurs enregistrés."""
        with self._lock:
            return len(self._connectors)

    def describe_all(self) -> List[Dict[str, Any]]:
        """Retourne la description de chaque connecteur, sans aucun appel réseau."""
        descriptions: List[Dict[str, Any]] = []
        for connector in self.list_connectors():
            try:
                descriptions.append(connector.describe().to_dict())
            except Exception as error:
                self._logger.warning(
                    "Description impossible pour '%s' : %s", connector.connector_id, error
                )
        return descriptions

    def check(self, connector_id: str) -> Optional[ConnectorCheck]:
        """
        Vérifie un connecteur précis.

        Returns:
            Le résultat de la vérification, ou None si l'identifiant est inconnu
        """
        connector = self.get(connector_id)
        if connector is None:
            return None
        return self._safe_check(connector)

    def check_all(self) -> Dict[str, Any]:
        """
        Vérifie tous les connecteurs et retourne un rapport agrégé.

        Returns:
            Un dictionnaire portant le total, le nombre de connecteurs prêts, la
            répartition par statut et le détail de chaque vérification.
        """
        checks = [self._safe_check(connector) for connector in self.list_connectors()]

        by_status: Dict[str, int] = {}
        for check in checks:
            by_status[check.status.value] = by_status.get(check.status.value, 0) + 1

        return {
            "total": len(checks),
            "ready": sum(1 for check in checks if check.is_ready),
            "by_status": by_status,
            "connectors": [check.to_dict() for check in checks],
        }

    def _safe_check(self, connector: Connector) -> ConnectorCheck:
        """
        Vérifie un connecteur sans jamais laisser l'exception remonter.

        Un connecteur mal écrit ne doit pas empêcher le rapport global d'être
        produit : son échec devient un statut `ERROR` parmi les autres.
        """
        started_at = time.time()
        try:
            check = connector.check()
        except Exception as error:
            self._logger.warning(
                "Vérification du connecteur '%s' en échec : %s", connector.connector_id, error
            )
            return ConnectorCheck(
                connector_id=connector.connector_id,
                kind=connector.kind,
                status=ConnectorStatus.ERROR,
                detail=f"{type(error).__name__}: {error}",
                latency_ms=(time.time() - started_at) * 1000,
            )

        if check.latency_ms is None:
            check.latency_ms = (time.time() - started_at) * 1000
        return check


# Registre partagé de la plateforme : une seule instance, comme `EngineRegistry`,
# pour qu'un connecteur enregistré au démarrage soit visible partout.
_shared_registry: Optional[ConnectorRegistry] = None
_shared_registry_lock = threading.Lock()


def get_shared_connector_registry() -> ConnectorRegistry:
    """Retourne le registre de connecteurs partagé par toute la plateforme."""
    global _shared_registry
    with _shared_registry_lock:
        if _shared_registry is None:
            _shared_registry = ConnectorRegistry()
        return _shared_registry


def reset_shared_connector_registry() -> None:
    """
    Réinitialise le registre partagé.

    Destiné aux tests : sans cela, un connecteur enregistré par un test resterait
    visible dans les suivants — le genre de fuite d'état qui fait échouer un
    fichier de tests selon l'ordre d'exécution.
    """
    global _shared_registry
    with _shared_registry_lock:
        _shared_registry = None
