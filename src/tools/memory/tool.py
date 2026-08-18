"""
Outil de mémoire pour GalSen IA.

Fournit une interface pour effectuer des opérations sur le système de mémoire
(stockage, recherche, récupération, mise à jour, suppression).
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import asdict

from src.tool.base import BaseTool
from src.memory_engine.memory_manager import MemoryManager
from src.memory_engine.types import (
    MemoryItem,
    MemoryType,
    MemoryPriority,
    MemoryStatus,
)

logger = logging.getLogger(__name__)


class MemoryTool(BaseTool):
    """
    Outil d'accès au système de mémoire de GalSen IA.

    Opérations disponibles : `store` (stocker un élément de mémoire),
    `retrieve` (récupérer par ID), `search` (rechercher par requête),
    `update` (mettre à jour), `delete` (supprimer), `list` (lister avec filtres).

    Exemple:
        tool.execute("store", {"content": "Bonjour", "memory_type": "short_term"})
        tool.execute("retrieve", "some-uuid")
        tool.execute("search", "Bonjour", memory_type="short_term", limit=5)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil de mémoire.

        Args:
            config: Configuration (actuellement inutilisée, réservée pour
                    de futures extensions).
        """
        super().__init__(config)
        # Créer une instance du gestionnaire de mémoire (en mémoire par défaut)
        self._memory_manager = MemoryManager()
        logger.debug("MemoryTool initialized.")

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur le système de mémoire.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération, dépendant de celle-ci.

        Raises:
            ValueError: Opération inconnue.
        """
        if not args:
            raise ValueError("Une opération est requise (store, retrieve, search, update, delete, list, ...)")

        operation = str(args[0]).lower()
        operation_args = args[1:]

        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. "
                f"Opérations disponibles: {', '.join(self.available_operations())}"
            )

        return handler(*operation_args, **kwargs)

    def available_operations(self) -> List[str]:
        """Retourne la liste des opérations prises en charge."""
        return sorted(
            name[len("_op_"):]
            for name in dir(self)
            if name.startswith("_op_") and callable(getattr(self, name))
        )

    # ------------------------------------------------------------------
    # Opérations
    # ------------------------------------------------------------------
    def _op_store(self, item_dict: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Stocke un nouvel élément de mémoire.

        Args:
            item_dict: Dictionnaire représentant l'élément de mémoire.
                       Les champs possibles sont ceux de MemoryItem :
                       content, memory_type, user_id, session_id, agent_id,
                       tags, expires_at, priority, metadata.
                       Le champ 'id' est optionnel ; s'il est absent, un nouvel
                       ID sera généré.
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Dictionnaire avec l'ID de l'élément stocké :
                {"id": "<uuid>"}
        """
        # Convertir les champs enum depuis les chaînes si nécessaire
        if "memory_type" in item_dict and isinstance(item_dict["memory_type"], str):
            try:
                item_dict["memory_type"] = MemoryType[item_dict["memory_type"].upper()]
            except KeyError:
                raise ValueError(f"Type de mémoire invalide: {item_dict['memory_type']}")
        if "priority" in item_dict and isinstance(item_dict["priority"], str):
            try:
                item_dict["priority"] = MemoryPriority[item_dict["priority"].upper()]
            except KeyError:
                raise ValueError(f"Priorité invalide: {item_dict['priority']}")
        # Note: status est généralement défini à ACTIVE par défaut ; on ne le change pas ici.

        item = MemoryItem(**item_dict)
        saved_id = self._memory_manager.save_memory(item)
        logger.info(f"Memory item stored with id: {saved_id}")
        return {"id": saved_id}

    def _op_retrieve(self, item_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Récupère un élément de mémoire par son ID.

        Args:
            item_id: L'ID de l'élément à récupérer.
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Dictionnaire représentant l'élément de mémoire, ou None si non trouvé.
        """
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("L'ID de l'élément doit être une chaîne non vide")
        item = self._memory_manager.get_memory(item_id)
        if item is None:
            return None
        # Convertir en dictionnaire pour la sérialisation
        item_dict = asdict(item)
        # Convertir les enums en leurs valeurs chaînes pour une meilleure lisibilité JSON
        item_dict["memory_type"] = item_dict["memory_type"].value
        item_dict["priority"] = item_dict["priority"].value
        item_dict["status"] = item_dict["status"].value
        logger.debug(f"Retrieved memory item: {item_id}")
        return item_dict

    def _op_search(
        self,
        query: str,
        memory_type: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Recherche des éléments de mémoire pertinents par rapport à une requête.

        Args:
            query: La chaîne de recherche.
            memory_type: Filtrer par type de mémoire (ex. "short_term").
            user_id: Filtrer par identifiant d'utilisateur.
            session_id: Filtrer par identifiant de session.
            agent_id: Filtrer par identifiant d'agent.
            tags: Liste de tags (tous doivent être présents).
            limit: Nombre maximum de résultats à retourner (défaut: 10).
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Liste de dictionnaires représentant les éléments de mémoire trouvés,
            chacun contenant les champs de l'élément ainsi qu'un champ '_score'
            représentant la pertinence.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("La requête de recherche doit être une chaîne non vide")

        # Convertir memory_type en enum si fourni
        mem_type_enum: Optional[MemoryType] = None
        if memory_type is not None:
            if isinstance(memory_type, str):
                try:
                    mem_type_enum = MemoryType[memory_type.upper()]
                except KeyError:
                    raise ValueError(f"Type de mémoire invalide pour la recherche: {memory_type}")
            else:
                mem_type_enum = memory_type  # déjà un enum

        results: List[Tuple[MemoryItem, float]] = self._memory_manager.search_memory(
            query=query,
            memory_type=mem_type_enum,
            user_id=user_id,
            session_id=session_id,
            agent_id=agent_id,
            tags=tags,
            limit=limit,
        )

        # Convertir chaque MemoryItem en dictionnaire
        output: List[Dict[str, Any]] = []
        for item, score in results:
            item_dict = asdict(item)
            item_dict["memory_type"] = item_dict["memory_type"].value
            item_dict["priority"] = item_dict["priority"].value
            item_dict["status"] = item_dict["status"].value
            item_dict["_score"] = score
            output.append(item_dict)

        logger.debug(f"Search for '{query}' returned {len(output)} results")
        return output

    def _op_delete(self, item_id: str, **kwargs) -> Dict[str, bool]:
        """
        Supprime un élément de mémoire par son ID.

        Args:
            item_id: L'ID de l'élément à supprimer.
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Dictionnaire indiquant le succès : {"deleted": true/false}
        """
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("L'ID de l'élément doit être une chaîne non vide")
        deleted = self._memory_manager.delete_memory(item_id)
        logger.info(f"Memory item deletion {'success' if deleted else 'failed'}: {item_id}")
        return {"deleted": deleted}

    def _op_update(self, item_dict: Dict[str, Any], **kwargs) -> Dict[str, bool]:
        """
        Met à jour un élément de mémoire existant.

        Args:
            item_dict: Dictionnaire représentant l'élément de mémoire avec les
                       champs à mettre à jour. L'ID doit être présent.
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Dictionnaire indiquant le succès : {"updated": true/false}
        """
        if not isinstance(item_dict, dict) or "id" not in item_dict:
            raise ValueError("Pour mettre à jour, un dictionnaire avec l'ID de l'élément est requis")
        item_id = item_dict["id"]
        if not isinstance(item_id, str) or not item_id.strip():
            raise ValueError("L'ID de l'élément doit être une chaîne non vide")

        # Convertir les champs enum depuis les chaînes si présents
        if "memory_type" in item_dict and isinstance(item_dict["memory_type"], str):
            try:
                item_dict["memory_type"] = MemoryType[item_dict["memory_type"].upper()]
            except KeyError:
                raise ValueError(f"Type de mémoire invalide: {item_dict['memory_type']}")
        if "priority" in item_dict and isinstance(item_dict["priority"], str):
            try:
                item_dict["priority"] = MemoryPriority[item_dict["priority"].upper()]
            except KeyError:
                raise ValueError(f"Priorité invalide: {item_dict['priority']}")
        # Le statut peut être mis à jour également
        if "status" in item_dict and isinstance(item_dict["status"], str):
            try:
                item_dict["status"] = MemoryStatus[item_dict["status"].upper()]
            except KeyError:
                raise ValueError(f"Statut invalide: {item_dict['status']}")

        item = MemoryItem(**item_dict)
        updated = self._memory_manager.update_memory(item)
        logger.info(f"Memory item update {'success' if updated else 'failed'}: {item_id}")
        return {"updated": updated}

    def _op_list(
        self,
        memory_type: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Liste les éléments de mémoire avec filtrage optionnel.

        Args:
            memory_type: Filtrer par type de mémoire.
            user_id: Filtrer par identifiant d'utilisateur.
            session_id: Filtrer par identifiant de session.
            agent_id: Filtrer par identifiant d'agent.
            tags: Liste de tags (tous doivent être présents).
            status: Filtrer par statut.
            limit: Nombre maximum d'éléments à retourner (défaut: 100).
            offset: Offset pour la pagination (défaut: 0).
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Liste de dictionnaires représentant les éléments de mémoire listés.
        """
        # Convertir les enums depuis les chaînes si fournis
        mem_type_enum: Optional[MemoryType] = None
        if memory_type is not None:
            if isinstance(memory_type, str):
                try:
                    mem_type_enum = MemoryType[memory_type.upper()]
                except KeyError:
                    raise ValueError(f"Type de mémoire invalide pour la liste: {memory_type}")
            else:
                mem_type_enum = memory_type

        status_enum: Optional[MemoryStatus] = None
        if status is not None:
            if isinstance(status, str):
                try:
                    status_enum = MemoryStatus[status.upper()]
                except KeyError:
                    raise ValueError(f"Statut invalide pour la liste: {status}")
            else:
                status_enum = status

        items: List[MemoryItem] = self._memory_manager.get_store().list_items(
            memory_type=mem_type_enum,
            user_id=user_id,
            session_id=session_id,
            agent_id=agent_id,
            tags=tags,
            status=status_enum,
            limit=limit,
            offset=offset,
        )

        output: List[Dict[str, Any]] = []
        for item in items:
            item_dict = asdict(item)
            item_dict["memory_type"] = item_dict["memory_type"].value
            item_dict["priority"] = item_dict["priority"].value
            item_dict["status"] = item_dict["status"].value
            output.append(item_dict)

        logger.debug(f"List operation returned {len(output)} items")
        return output

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    # Aucun utilitaire spécifique nécessaire pour cet outil.