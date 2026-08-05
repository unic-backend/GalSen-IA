"""
Moteur de questions-réponses par mots-clés pour le moteur d'intelligence
documentaire GalSen IA.
"""

import logging
from typing import List, Optional, Tuple

from .interfaces import DocumentQA, DocumentStore
from .text_utils import significant_words, split_sentences
from .types import DocumentChunk, DocumentItem


class SimpleQAEngine(DocumentQA):
    """
    Moteur de questions-réponses extractif basé sur le recouvrement de mots-clés.

    La réponse est constituée des phrases des documents qui partagent le plus de
    mots significatifs avec la question. Aucune génération de texte n'est faite :
    le moteur ne peut donc pas inventer d'information absente des documents.
    """

    # Message renvoyé quand aucune phrase du corpus ne recoupe la question
    NO_ANSWER_MESSAGE = "Aucune information pertinente n'a été trouvée dans les documents."

    def __init__(self, store: DocumentStore, max_sentences: int = 3):
        """
        Initialise le moteur de questions-réponses.

        Args:
            store: Stockage dans lequel chercher les documents
            max_sentences: Nombre maximum de phrases assemblées dans la réponse
        """
        if max_sentences < 1:
            raise ValueError("Le nombre de phrases de la réponse doit être au moins 1")
        self._store = store
        self._max_sentences = max_sentences
        self._logger = logging.getLogger(__name__)

    def answer_question(self, question: str, document_id: Optional[str] = None, **kwargs) -> str:
        """
        Répond à une question à partir du contenu des documents.

        Args:
            question: Question posée
            document_id: Restreint la recherche à ce document si fourni
            **kwargs: `max_sentences` pour ajuster la longueur de la réponse

        Returns:
            Réponse extraite des documents, ou un message explicite si le corpus
            ne contient rien de pertinent
        """
        answer, _ = self.answer_question_with_sources(question, document_id, **kwargs)
        return answer

    def answer_question_with_sources(
        self, question: str, document_id: Optional[str] = None, **kwargs
    ) -> Tuple[str, List[DocumentChunk]]:
        """
        Répond à une question en retournant aussi les passages sources.

        Args:
            question: Question posée
            document_id: Restreint la recherche à ce document si fourni
            **kwargs: `max_sentences` pour ajuster la longueur de la réponse

        Returns:
            Tuple (réponse, chunks sources). La liste est vide si aucune phrase
            pertinente n'a été trouvée.
        """
        max_sentences = kwargs.get('max_sentences', self._max_sentences)
        question_words = significant_words(question)
        if not question_words:
            return self.NO_ANSWER_MESSAGE, []

        documents = self._documents_to_search(document_id)
        matches = self._find_matching_sentences(documents, question_words)
        if not matches:
            return self.NO_ANSWER_MESSAGE, []

        # Les meilleures correspondances d'abord, puis on tronque
        matches.sort(key=lambda match: match[2], reverse=True)
        selected = matches[:max_sentences]

        answer = ' '.join(sentence for _, sentence, _ in selected)
        sources = [
            self._build_source_chunk(document, sentence, score)
            for document, sentence, score in selected
        ]
        return answer, sources

    def _documents_to_search(self, document_id: Optional[str]) -> List[DocumentItem]:
        """Retourne les documents à parcourir pour répondre."""
        if document_id is None:
            return self._store.list_items()

        document = self._store.get(document_id)
        if document is None:
            self._logger.warning(f"Document non trouvé pour la question: {document_id}")
            return []
        return [document]

    def _find_matching_sentences(
        self, documents: List[DocumentItem], question_words: set
    ) -> List[Tuple[DocumentItem, str, float]]:
        """Note chaque phrase des documents selon son recouvrement avec la question."""
        matches: List[Tuple[DocumentItem, str, float]] = []

        for document in documents:
            for sentence in split_sentences(document.content):
                sentence_words = significant_words(sentence)
                if not sentence_words:
                    continue

                overlap = question_words & sentence_words
                if not overlap:
                    continue

                # Proportion de la question couverte par la phrase
                score = len(overlap) / len(question_words)
                matches.append((document, sentence, score))

        return matches

    def _build_source_chunk(self, document: DocumentItem, sentence: str, score: float) -> DocumentChunk:
        """Construit le chunk source correspondant à une phrase retenue."""
        start_index = document.content.find(sentence)
        if start_index < 0:
            start_index = 0

        return DocumentChunk(
            chunk_id=f"{document.document_id}_qa_{start_index}",
            document_id=document.document_id,
            content=sentence,
            start_index=start_index,
            end_index=start_index + len(sentence),
            metadata={
                "answer_score": score,
                "source": "question_answering"
            }
        )
