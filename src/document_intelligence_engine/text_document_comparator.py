"""
Comparateur de documents pour le moteur d'intelligence documentaire GalSen IA.
"""

import difflib
from typing import Any, Dict, List

from .interfaces import DocumentComparator
from .text_utils import tokenize
from .types import DocumentItem


class DocumentComparatorImpl(DocumentComparator):
    """
    Comparateur textuel de documents.

    Il fournit un score de similarité global (Jaccard sur les mots), les mots
    caractéristiques de chaque document, et un diff ligne à ligne exploitable
    pour visualiser les changements.
    """

    # Nombre de mots retournés dans chaque liste, pour garder une sortie lisible
    DEFAULT_WORD_SAMPLE = 10

    def compare(self, doc1: DocumentItem, doc2: DocumentItem, **kwargs) -> Dict[str, Any]:
        """
        Compare deux documents.

        Args:
            doc1: Premier document
            doc2: Second document
            **kwargs: `word_sample` pour le nombre de mots listés,
                `include_diff` (True par défaut) pour joindre le diff ligne à ligne

        Returns:
            Dictionnaire contenant la similarité, les mots communs, les mots
            propres à chaque document et, optionnellement, le diff
        """
        word_sample = kwargs.get('word_sample', self.DEFAULT_WORD_SAMPLE)
        include_diff = kwargs.get('include_diff', True)

        words1 = set(tokenize(doc1.content))
        words2 = set(tokenize(doc2.content))

        common = words1 & words2
        union = words1 | words2

        # Deux documents vides sont considérés identiques
        if not union:
            similarity = 1.0
        else:
            similarity = len(common) / len(union)

        result: Dict[str, Any] = {
            "similarity": similarity,
            "identical": doc1.content == doc2.content,
            "common_words": sorted(common)[:word_sample],
            "unique_to_doc1": sorted(words1 - words2)[:word_sample],
            "unique_to_doc2": sorted(words2 - words1)[:word_sample],
        }

        if include_diff:
            result["diff"] = self._build_diff(doc1, doc2)

        return result

    def _build_diff(self, doc1: DocumentItem, doc2: DocumentItem) -> List[str]:
        """Construit le diff unifié ligne à ligne entre deux documents."""
        return list(difflib.unified_diff(
            doc1.content.splitlines(),
            doc2.content.splitlines(),
            fromfile=doc1.title or doc1.document_id,
            tofile=doc2.title or doc2.document_id,
            lineterm=""
        ))
