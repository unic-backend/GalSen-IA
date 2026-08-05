"""
Récupérateur de documents simple pour le moteur d'intelligence documentaire GalSen IA.
"""

from typing import List, Optional
from .interfaces import DocumentRetriever
from .types import DocumentItem, DocumentChunk


class SimpleRetriever(DocumentRetriever):
    """Récupérateur simple qui retourne des documents pertinents basés sur la recherche textuelle."""

    def __init__(self, indexer):
        """
        Initialise le récupérateur.

        Args:
            indexer: Indexeur de documents à utiliser pour la recherche
        """
        self._indexer = indexer

    def retrieve(self, query: str, document_id: Optional[str] = None, limit: int = 5) -> List[DocumentChunk]:
        """
        Récupère les chunks les plus pertinents pour une requête.

        Args:
            query: Chaîne de requête de recherche
            document_id: Si spécifié, limite la recherche à ce document
            limit: Nombre maximum de résultats à retourner

        Returns:
            Liste de DocumentChunk pertinents
        """
        # Utiliser l'indexeur pour trouver les documents pertinents
        results = self._indexer.search(query, limit=limit)

        chunks = []
        for doc, score in results:
            # Si un document spécifique est demandé, vérifier qu'on est sur le bon document
            if document_id is not None and doc.document_id != document_id:
                continue

            # Créer un chunk représentant une partie pertinente du document
            # Pour cette implémentation simple, nous retournons le début du document
            # Une implémentation plus avancée retournerait des passages spécifiques
            content_preview = doc.content[:300] + "..." if len(doc.content) > 300 else doc.content

            chunk = DocumentChunk(
                chunk_id=f"{doc.document_id}_retrieval",
                document_id=doc.document_id,
                content=content_preview,
                start_index=0,
                end_index=len(content_preview),
                metadata={
                    "retrieval_score": score,
                    "source": "document_preview"
                }
            )
            chunks.append(chunk)

            # Respecter la limite
            if len(chunks) >= limit:
                break

        return chunks