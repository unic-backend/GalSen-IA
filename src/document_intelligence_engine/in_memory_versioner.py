"""
Gestionnaire de versions de documents pour le moteur d'intelligence
documentaire GalSen IA.
"""

from typing import Any, Dict, List, Optional

from .interfaces import DocumentStore, DocumentVersioner
from .types import DocumentItem


class SimpleVersioner(DocumentVersioner):
    """
    Versionneur qui matérialise chaque version comme un document à part entière,
    relié à la version précédente par `parent_id`.

    L'historique est donc reconstruit en suivant cette chaîne dans le stockage :
    aucun état parallèle n'est maintenu, et les versions restent accessibles par
    les mêmes API que les autres documents.
    """

    # Champs d'un document qu'une nouvelle version peut modifier
    _VERSIONABLE_FIELDS = ("content", "title", "status")

    def __init__(self, store: DocumentStore):
        """
        Initialise le versionneur.

        Args:
            store: Stockage contenant les documents et leurs versions
        """
        self._store = store

    def create_version(self, document: DocumentItem, changes: Dict[str, Any]) -> DocumentItem:
        """
        Crée une nouvelle version d'un document.

        La version retournée n'est pas encore enregistrée : c'est l'appelant
        (le gestionnaire de documents) qui décide de la persister.

        Args:
            document: Document servant de base à la nouvelle version
            changes: Champs modifiés (`content`, `title`, `status`) et
                éventuellement `comment` pour décrire le changement

        Returns:
            Nouvelle version du document, avec un numéro de version incrémenté
        """
        new_version = DocumentItem(
            document_id="",  # L'identifiant sera attribué à l'enregistrement
            document_type=document.document_type,
            title=document.title,
            content=document.content,
            raw_data=document.raw_data,
            metadata=document.metadata.copy(),
            status=document.status,
            version=document.version + 1,
            parent_id=document.document_id,
        )

        for field in self._VERSIONABLE_FIELDS:
            if field in changes:
                setattr(new_version, field, changes[field])

        new_version.metadata["is_version"] = True
        new_version.metadata["version_comment"] = changes.get("comment", "")

        return new_version

    def get_version_history(self, document_id: str) -> List[DocumentItem]:
        """
        Récupère l'historique complet des versions d'un document.

        L'historique est celui de la lignée entière : quelle que soit la version
        interrogée, on remonte au document d'origine puis on redescend toutes ses
        versions.

        Args:
            document_id: Identifiant d'une version quelconque du document

        Returns:
            Versions triées de la plus ancienne à la plus récente. Liste vide si
            le document est introuvable.
        """
        document = self._store.get(document_id)
        if document is None:
            return []

        root_id = self._find_root_id(document)
        lineage = [
            candidate for candidate in self._store.list_items()
            if self._root_id_of(candidate) == root_id
        ]

        lineage.sort(key=lambda item: (item.version, item.created_at))
        return lineage

    def _find_root_id(self, document: DocumentItem) -> str:
        """Remonte la chaîne des parents jusqu'au document d'origine."""
        current = document
        visited = {current.document_id}

        while current.parent_id:
            parent = self._store.get(current.parent_id)
            # Parent supprimé ou cycle : la remontée s'arrête ici
            if parent is None or parent.document_id in visited:
                break
            visited.add(parent.document_id)
            current = parent

        return current.document_id

    def _root_id_of(self, document: DocumentItem) -> Optional[str]:
        """Retourne l'identifiant du document d'origine de la lignée."""
        return self._find_root_id(document)
