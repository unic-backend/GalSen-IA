"""
Extracteur de métadonnées pour le moteur d'intelligence documentaire GalSen IA.
"""

from typing import Optional

from .interfaces import DocumentMetadataExtractor
from .text_utils import split_sentences, tokenize
from .types import DocumentItem, DocumentMetadata


class CompositeMetadataExtractor(DocumentMetadataExtractor):
    """
    Extracteur combinant les métadonnées déclarées par le chargeur et celles
    calculées à partir du contenu textuel.

    Les métadonnées du chargeur (auteur, dates, titre issus du fichier source)
    font autorité ; les statistiques de texte sont calculées uniquement quand
    elles manquent.
    """

    # Métadonnées du chargeur reprises telles quelles dans DocumentMetadata
    _LOADER_FIELDS = (
        "author", "creator", "producer", "creation_date", "modification_date",
        "title", "subject", "keywords", "language", "page_count",
    )

    # Marqueurs propres à chaque langue, utilisés pour la détection
    _FRENCH_MARKERS = frozenset({
        "le", "la", "les", "des", "une", "est", "sont", "dans", "pour", "avec",
        "que", "qui", "sur", "pas", "plus", "cette", "nous", "vous",
    })
    _ENGLISH_MARKERS = frozenset({
        "the", "of", "and", "is", "are", "in", "for", "with", "that", "which",
        "on", "not", "more", "this", "we", "you",
    })

    def extract_metadata(self, document: DocumentItem) -> DocumentMetadata:
        """
        Extrait les métadonnées d'un document.

        Args:
            document: Document à analyser

        Returns:
            Métadonnées consolidées du document
        """
        metadata = DocumentMetadata()

        self._copy_loader_fields(document, metadata)
        self._compute_text_statistics(document, metadata)

        if metadata.title is None:
            metadata.title = document.title
        if metadata.language is None:
            metadata.language = self._detect_language(document.content)

        return metadata

    def _copy_loader_fields(self, document: DocumentItem, metadata: DocumentMetadata) -> None:
        """Reprend les métadonnées fournies par le chargeur du document."""
        for field in self._LOADER_FIELDS:
            value = document.metadata.get(field)
            if value is not None:
                setattr(metadata, field, value)

        # Le chargeur peut déjà connaître les compteurs (fichiers texte)
        if document.metadata.get("line_count") is not None:
            metadata.line_count = document.metadata["line_count"]
        if document.metadata.get("char_count") is not None:
            metadata.character_count = document.metadata["char_count"]

    def _compute_text_statistics(self, document: DocumentItem, metadata: DocumentMetadata) -> None:
        """Calcule les statistiques manquantes à partir du contenu."""
        content = document.content
        words = tokenize(content)

        if metadata.word_count is None:
            metadata.word_count = len(words)
        if metadata.character_count is None:
            metadata.character_count = len(content)
        if metadata.line_count is None:
            metadata.line_count = len(content.splitlines())

        metadata.table_count = document.metadata.get("table_count", metadata.table_count)
        metadata.image_count = document.metadata.get("image_count", metadata.image_count)

        # Indicateurs de lisibilité rangés dans `custom` : ils sont dérivés du
        # texte et n'ont pas de sens pour les métadonnées d'un fichier binaire
        sentences = split_sentences(content)
        metadata.custom["sentence_count"] = len(sentences)
        metadata.custom["average_sentence_length"] = (
            round(len(words) / len(sentences), 2) if sentences else 0.0
        )
        metadata.custom["lexical_diversity"] = (
            round(len(set(words)) / len(words), 4) if words else 0.0
        )

    def _detect_language(self, content: str) -> Optional[str]:
        """
        Devine la langue dominante du texte.

        La détection compare le nombre de mots outils français et anglais. Elle
        reste volontairement simple et retourne None quand le texte est trop
        court ou trop ambigu pour trancher.
        """
        words = set(tokenize(content))
        if not words:
            return None

        french_hits = len(words & self._FRENCH_MARKERS)
        english_hits = len(words & self._ENGLISH_MARKERS)

        if french_hits == english_hits:
            return None
        return "fr" if french_hits > english_hits else "en"
