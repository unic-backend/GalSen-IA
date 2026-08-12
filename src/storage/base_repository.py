"""
Repository de base pour le stockage persistant dans GalSen IA.

Définit l'interface abstraite BaseRepository qui fournit les opérations
CRUD standard pour toute entité persistante. Conforme à ADR-005.

Les sous-classes concrètes implémentent ces opérations pour un type
d'entité et un backend de stockage spécifiques (SQLite, in-memory, etc.).
"""

import abc
from typing import Any, Generic, List, Optional, TypeVar

# Type générique représentant l'entité persistée
T = TypeVar("T")


class BaseRepository(abc.ABC, Generic[T]):
    """
    Interface abstraite pour les repositories de stockage.

    Définit le contrat CRUD que tout backend de stockage doit respecter.
    Le paramètre de type T représente le type d'entité géré par le repository.

    Conforme à ADR-005 : cette abstraction permet de remplacer SQLite par
    PostgreSQL ou un autre backend sans modifier le code appelant.
    """

    @abc.abstractmethod
    def save(self, entity: T) -> str:
        """
        Sauvegarder une entité.

        Args:
            entity: L'entité à persister.

        Returns:
            L'identifiant unique de l'entité sauvegardée.
        """
        ...

    @abc.abstractmethod
    def get(self, entity_id: str) -> Optional[T]:
        """
        Récupérer une entité par son identifiant.

        Args:
            entity_id: L'identifiant de l'entité.

        Returns:
            L'entité trouvée, ou None si absente.
        """
        ...

    @abc.abstractmethod
    def update(self, entity: T) -> bool:
        """
        Mettre à jour une entité existante.

        Args:
            entity: L'entité avec les données mises à jour.

        Returns:
            True si l'entité a été mise à jour, False si non trouvée.
        """
        ...

    @abc.abstractmethod
    def delete(self, entity_id: str) -> bool:
        """
        Supprimer une entité par son identifiant.

        Args:
            entity_id: L'identifiant de l'entité à supprimer.

        Returns:
            True si supprimée, False si non trouvée.
        """
        ...

    @abc.abstractmethod
    def list_items(
        self,
        limit: int = 100,
        offset: int = 0,
        **filters: Any,
    ) -> List[T]:
        """
        Lister les entités avec filtrage et pagination optionnels.

        Args:
            limit: Nombre maximum d'entités à retourner.
            offset: Décalage pour la pagination.
            **filters: Filtres supplémentaires spécifiques à l'entité.

        Returns:
            Liste des entités correspondant aux critères.
        """
        ...

    @abc.abstractmethod
    def clear(self, **filters: Any) -> int:
        """
        Supprimer les entités correspondant aux critères.

        Args:
            **filters: Critères de filtrage pour la suppression.

        Returns:
            Nombre d'entités supprimées.
        """
        ...

    @abc.abstractmethod
    def count(self, **filters: Any) -> int:
        """
        Compter les entités correspondant aux critères.

        Args:
            **filters: Critères de filtrage pour le comptage.

        Returns:
            Nombre d'entités correspondantes.
        """
        ...

    @abc.abstractmethod
    def exists(self, entity_id: str) -> bool:
        """
        Vérifier si une entité existe.

        Args:
            entity_id: L'identifiant à vérifier.

        Returns:
            True si l'entité existe, False sinon.
        """
        ...
