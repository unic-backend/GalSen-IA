"""
Découpeur de documents simple pour le moteur d'intelligence documentaire GalSen IA.
"""

from typing import List
from .interfaces import DocumentChunker
from .types import DocumentItem, DocumentChunk


class SimpleChunker(DocumentChunker):
    """Découpeur simple qui divise le texte en blocs de taille fixe."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        """
        Initialise le découpeur.

        Args:
            chunk_size: Taille maximale de chaque bloc (en caractères)
            overlap: Nombre de caractères de chevauchement entre les blocs consécutifs
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        if overlap >= chunk_size:
            raise ValueError("L'overlap doit être inférieur à la taille du chunk")

    def chunk(self, document: DocumentItem, **kwargs) -> List[DocumentChunk]:
        """
        Découpe un document en morceaux.

        Args:
            document: Document à découper
            **kwargs: Paramètres additionnels (chunk_size, overlap, etc.)

        Returns:
            Liste de DocumentChunk
        """
        # Utiliser les paramètres passés ou les valeurs par défaut
        chunk_size = kwargs.get('chunk_size', self.chunk_size)
        overlap = kwargs.get('overlap', self.overlap)

        if overlap >= chunk_size:
            raise ValueError("L'overlap doit être inférieur à la taille du chunk")

        text = document.content
        chunks = []

        start = 0
        chunk_index = 0

        while start < len(text):
            # La fin ne dépasse jamais chunk_size : c'est une garantie pour les appelants
            end = min(start + chunk_size, len(text))

            # Sauf pour le dernier chunk, on recule jusqu'à la dernière frontière de mot
            # pour éviter de couper un mot en deux
            if end < len(text):
                last_space = text.rfind(' ', start, end)
                # La coupure n'est retenue que si elle laisse un chunk substantiel,
                # sinon on préfère couper net plutôt que produire des miettes
                if last_space > start + chunk_size // 2:
                    end = last_space

            # Extraire le chunk
            chunk_text = text[start:end]

            # Créer le chunk
            chunk = DocumentChunk(
                chunk_id=f"{document.document_id}_chunk_{chunk_index}",
                document_id=document.document_id,
                content=chunk_text,
                start_index=start,
                end_index=end,
                metadata={
                    "chunk_index": chunk_index,
                    "chunk_size": len(chunk_text)
                }
            )
            chunks.append(chunk)
            chunk_index += 1

            if end >= len(text):
                break

            # Passer au chunk suivant avec chevauchement.
            # Le `max` garantit une progression stricte, donc l'absence de boucle infinie.
            start = max(end - overlap, start + 1)

        return chunks