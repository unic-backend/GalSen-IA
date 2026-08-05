"""
Implémentation en mémoire du stockage de documents pour le moteur d'intelligence documentaire GalSen IA.
"""

import logging
import time
import uuid
from typing import List, Optional

from .interfaces import DocumentStore
from .types import DocumentItem, DocumentStatus


class InMemoryDocumentStore(DocumentStore):
    """Implémentation en mémoire du stockage de documents."""

    def __init__(self):
        """Initialise le magasin en mémoire."""
        self._documents: dict[str, DocumentItem] = {}
        self._logger = logging.getLogger(__name__)

    def save(self, document: DocumentItem) -> str:
        """Sauvegarde un document et retourne son ID."""
        # Un UUID garantit l'unicité même quand plusieurs documents sont
        # enregistrés dans la même milliseconde
        if not document.document_id:
            document.document_id = f"doc_{uuid.uuid4().hex}"

        # Mettre à jour la date de modification
        document.updated_at = time.time()

        # Sauvegarder
        self._documents[document.document_id] = document
        self._logger.info(f"Document sauvegardé avec l'ID: {document.document_id}")
        return document.document_id

    def get(self, document_id: str) -> Optional[DocumentItem]:
        """Récupère un document par son ID."""
        return self._documents.get(document_id)

    def update(self, document: DocumentItem) -> bool:
        """Met à jour un document existant."""
        if document.document_id not in self._documents:
            return False

        # Mettre à jour la date de modification
        document.updated_at = time.time()
        self._documents[document.document_id] = document
        return True

    def delete(self, document_id: str) -> bool:
        """Supprime un document."""
        if document_id in self._documents:
            del self._documents[document_id]
            return True
        return False

    def list_items(self, limit: int = 100, **filters) -> List[DocumentItem]:
        """Liste les documents avec des filtres optionnels."""
        results = list(self._documents.values())

        # Appliquer les filtres
        for key, value in filters.items():
            if key == "status":
                results = [doc for doc in results if doc.status.value == value]
            elif key == "document_type":
                results = [doc for doc in results if doc.document_type.value == value]
            elif key == "title":
                # Recherche partielle insensible à la casse dans le titre
                results = [doc for doc in results if value.lower() in doc.title.lower()]
            # Ajouter d'autres filtres selon les besoins

        # Limiter les résultats
        return results[:limit]

    def cleanup_expired(self) -> int:
        """Nettoie les documents expirés (ceux marqués comme supprimés depuis plus de 24h)."""
        # Pour cette implémentation simple, nous ne supprimons que les documents marqués comme DELETED
        # Une implémentation plus complète aurait un timestamp d'expiration
        expired_count = 0
        to_delete = []
        for doc_id, doc in self._documents.items():
            if doc.status == DocumentStatus.DELETED:
                # Dans une implémentation réelle, on vérifierait la date de suppression
                to_delete.append(doc_id)

        for doc_id in to_delete:
            del self._documents[doc_id]
            expired_count += 1

        return expired_count