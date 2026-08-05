"""
Synthétiseur extractif pour le moteur d'intelligence documentaire GalSen IA.
"""

from typing import Dict, List

from .interfaces import DocumentSummarizer
from .text_utils import STOP_WORDS, split_sentences, tokenize
from .types import DocumentChunk, DocumentItem


class ExtractiveSummarizer(DocumentSummarizer):
    """
    Synthétiseur extractif : il sélectionne les phrases les plus représentatives
    du texte d'origine au lieu d'en générer de nouvelles.

    Le score d'une phrase est la moyenne des fréquences de ses mots significatifs.
    Une phrase composée de mots récurrents dans le document est jugée centrale.
    """

    def __init__(self, default_sentences: int = 3):
        """
        Initialise le synthétiseur.

        Args:
            default_sentences: Nombre de phrases retenues quand l'appelant
                n'en précise pas.
        """
        if default_sentences < 1:
            raise ValueError("Le nombre de phrases du résumé doit être au moins 1")
        self.default_sentences = default_sentences

    def summarize(self, document: DocumentItem, **kwargs) -> str:
        """
        Génère un résumé du document.

        Args:
            document: Document à résumer
            **kwargs: `sentences` pour choisir le nombre de phrases retenues

        Returns:
            Résumé sous forme de texte, phrases dans leur ordre d'origine
        """
        max_sentences = kwargs.get('sentences', self.default_sentences)
        return self._summarize_text(document.content, max_sentences)

    def summarize_chunk(self, chunk: DocumentChunk, **kwargs) -> str:
        """
        Génère un résumé d'un chunk de document.

        Args:
            chunk: Chunk à résumer
            **kwargs: `sentences` pour choisir le nombre de phrases retenues

        Returns:
            Résumé sous forme de texte
        """
        # Un chunk est court : une phrase suffit par défaut
        max_sentences = kwargs.get('sentences', 1)
        return self._summarize_text(chunk.content, max_sentences)

    def _summarize_text(self, text: str, max_sentences: int) -> str:
        """Sélectionne les phrases les mieux notées d'un texte."""
        sentences = split_sentences(text)
        if not sentences:
            return ""
        if len(sentences) <= max_sentences:
            return ' '.join(sentences)

        frequencies = self._word_frequencies(text)

        # On note chaque phrase en gardant sa position pour restituer l'ordre du texte
        scored = [
            (position, sentence, self._score_sentence(sentence, frequencies))
            for position, sentence in enumerate(sentences)
        ]

        # Tri stable : à score égal, la phrase la plus haute dans le texte gagne
        best = sorted(scored, key=lambda item: item[2], reverse=True)[:max_sentences]
        best.sort(key=lambda item: item[0])

        return ' '.join(sentence for _, sentence, _ in best)

    def _word_frequencies(self, text: str) -> Dict[str, int]:
        """Compte les occurrences des mots significatifs du texte."""
        frequencies: Dict[str, int] = {}
        for word in tokenize(text):
            if word not in STOP_WORDS:
                frequencies[word] = frequencies.get(word, 0) + 1
        return frequencies

    def _score_sentence(self, sentence: str, frequencies: Dict[str, int]) -> float:
        """Note une phrase par la fréquence moyenne de ses mots significatifs."""
        words: List[str] = [word for word in tokenize(sentence) if word not in STOP_WORDS]
        if not words:
            return 0.0
        # La moyenne évite d'avantager mécaniquement les phrases les plus longues
        return sum(frequencies.get(word, 0) for word in words) / len(words)
