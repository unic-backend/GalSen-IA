"""
Contrats du moteur d'audit.

Définit les interfaces abstraites ``AuditStore`` (persistance des
événements) et ``AuditManager`` (point d'entrée métier). Tout backend de
stockage (mémoire, SQLite, base de données, service externe) peut être
brancché à l'avenir sans modifier le code appelant.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .types import AuditEvent


class AuditStore(ABC):
    """Stockage persistant des événements d'audit."""

    @abstractmethod
    def save(self, event: AuditEvent) -> str:
        """Enregistre un événement et retourne son identifiant."""

    @abstractmethod
    def get(self, event_id: str) -> Optional[AuditEvent]:
        """Retourne un événement par son identifiant, ou ``None``."""

    @abstractmethod
    def list_events(self, limit: int = 100, **filters: Any) -> List[AuditEvent]:
        """Liste les événements (du plus récent au plus ancien)."""

    @abstractmethod
    def search_events(self, query: str, limit: int = 50) -> List[AuditEvent]:
        """Recherche des événements dont un champ contient la requête."""

    @abstractmethod
    def count(self, **filters: Any) -> int:
        """Compte les événements correspondant aux filtres."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime tous les événements et retourne leur nombre."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Statistiques agrégées sur les événements stockés."""


class AuditManager(ABC):
    """Point d'entrée métier du système d'audit."""

    @abstractmethod
    def record(self, event: AuditEvent) -> str:
        """
        Consigne un événement d'audit.

        Garantie : la consignation ne lève jamais d'exception. En cas
        d'échec, retourne une chaîne vide et journalise l'erreur.
        """

    @abstractmethod
    def get_event(self, event_id: str) -> Optional[AuditEvent]:
        """Retourne un événement par son identifiant, ou ``None``."""

    @abstractmethod
    def list_events(self, limit: int = 100, **filters: Any) -> List[AuditEvent]:
        """Liste les événements (du plus récent au plus ancien)."""

    @abstractmethod
    def search_events(self, query: str, limit: int = 50) -> List[AuditEvent]:
        """Recherche des événements dont un champ contient la requête."""

    @abstractmethod
    def count(self, **filters: Any) -> int:
        """Compte les événements correspondant aux filtres."""

    @abstractmethod
    def clear(self) -> int:
        """Supprime tous les événements et retourne leur nombre."""

    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Statistiques agrégées sur les événements stockés."""

    @abstractmethod
    def export_json(self, limit: int = 1000) -> str:
        """Exporte les événements au format JSON (chaîne)."""
