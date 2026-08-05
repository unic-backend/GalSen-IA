"""
Détecteur de doublons pour le moteur d'intelligence documentaire GalSen IA.
"""

from typing import List, Tuple

from .interfaces import DocumentDuplicateDetector
from .text_utils import jaccard_similarity
from .types import DocumentItem


class SimpleDuplicateDetector(DocumentDuplicateDetector):
    """
    Détecteur de doublons basé sur la similarité de Jaccard des mots.

    Deux documents sont considérés comme doublons lorsque la proportion de mots
    qu'ils partagent dépasse un seuil configurable.
    """

    DEFAULT_THRESHOLD = 0.8

    def is_duplicate(self, doc1: DocumentItem, doc2: DocumentItem, threshold: float = DEFAULT_THRESHOLD) -> bool:
        """
        Détermine si deux documents sont des doublons.

        Args:
            doc1: Premier document
            doc2: Second document
            threshold: Seuil de similarité à partir duquel il y a doublon

        Returns:
            True si la similarité atteint le seuil
        """
        return self.similarity(doc1, doc2) >= threshold

    def find_duplicates(
        self, documents: List[DocumentItem], threshold: float = DEFAULT_THRESHOLD
    ) -> List[Tuple[DocumentItem, DocumentItem]]:
        """
        Trouve toutes les paires de doublons dans une liste de documents.

        Args:
            documents: Documents à comparer entre eux
            threshold: Seuil de similarité à partir duquel il y a doublon

        Returns:
            Liste des paires de documents jugées dupliquées
        """
        duplicates: List[Tuple[DocumentItem, DocumentItem]] = []

        # Chaque paire n'est examinée qu'une fois : la similarité est symétrique
        for index, document in enumerate(documents):
            for other in documents[index + 1:]:
                if self.is_duplicate(document, other, threshold):
                    duplicates.append((document, other))

        return duplicates

    def similarity(self, doc1: DocumentItem, doc2: DocumentItem) -> float:
        """
        Calcule la similarité entre deux documents.

        Args:
            doc1: Premier document
            doc2: Second document

        Returns:
            Score de similarité entre 0.0 et 1.0
        """
        return jaccard_similarity(doc1.content, doc2.content)
