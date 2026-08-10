"""
Moteur documentaire : lit un fichier et en extrait un contenu exploitable.

Responsabilités
    Charger un document selon son format, valider ce qui a été lu, en extraire
    le texte et les métadonnées. Le moteur n'interprète pas le contenu : il le
    rend disponible aux autres moteurs.

Interfaces publiques
    `DocumentManagerImpl` est le point d'entrée. Un chargeur par format
    (`pdf_loader`, `docx_loader`, `xlsx_loader`, `pptx_loader`, `ocr_loader`,
    `markdown_loader`, `text_loader`), sélectionné par fabrique.

Dépendances
    Optionnelles, une par format : PyPDF2, python-docx, openpyxl, python-pptx,
    pytesseract (`requirements-optional.txt`). Elles sont importées à l'usage —
    leur absence désactive un format, elle ne casse pas le moteur.

Configuration
    Aucune variable d'environnement propre.

Limites connues
    Les chargeurs sont couverts à 18-25 % par les tests, faute des dépendances
    optionnelles dans l'environnement de test. Un format dont la bibliothèque
    manque rapporte son indisponibilité plutôt qu'un contenu vide.
"""

from .basic_document_validator import DocumentValidatorImpl
from .composite_metadata_extractor import CompositeMetadataExtractor
from .document_loader_factory import BaseDocumentLoader, DocumentLoaderFactory, get_factory
from .document_manager import DocumentManagerImpl
from .embedded_image_extractor import ImageExtractorImpl
from .extractive_summarizer import ExtractiveSummarizer
from .in_memory_document_store import InMemoryDocumentStore
from .in_memory_indexer import InMemoryIndexer
from .in_memory_versioner import SimpleVersioner
from .interfaces import (
    DocumentCache,
    DocumentChunker,
    DocumentComparator,
    DocumentDuplicateDetector,
    DocumentImageExtractor,
    DocumentIndexer,
    DocumentLoader,
    DocumentManager,
    DocumentMetadataExtractor,
    DocumentQA,
    DocumentRetriever,
    DocumentStore,
    DocumentSummarizer,
    DocumentTableExtractor,
    DocumentValidator,
    DocumentVersioner,
)
from .keyword_qa_engine import SimpleQAEngine
from .lru_document_cache import LRUDocumentCache
from .similarity_duplicate_detector import SimpleDuplicateDetector
from .simple_chunker import SimpleChunker
from .simple_retriever import SimpleRetriever
from .text_document_comparator import DocumentComparatorImpl
from .text_table_extractor import TableExtractorImpl
from .types import (
    DocumentChunk,
    DocumentItem,
    DocumentMetadata,
    DocumentStatus,
    DocumentType,
)

__all__ = [
    # Point d'entrée principal
    "DocumentManagerImpl",
    # Contrats
    "DocumentCache",
    "DocumentChunker",
    "DocumentComparator",
    "DocumentDuplicateDetector",
    "DocumentImageExtractor",
    "DocumentIndexer",
    "DocumentLoader",
    "DocumentManager",
    "DocumentMetadataExtractor",
    "DocumentQA",
    "DocumentRetriever",
    "DocumentStore",
    "DocumentSummarizer",
    "DocumentTableExtractor",
    "DocumentValidator",
    "DocumentVersioner",
    # Chargement
    "BaseDocumentLoader",
    "DocumentLoaderFactory",
    "get_factory",
    # Implémentations par défaut
    "CompositeMetadataExtractor",
    "DocumentComparatorImpl",
    "DocumentValidatorImpl",
    "ExtractiveSummarizer",
    "ImageExtractorImpl",
    "InMemoryDocumentStore",
    "InMemoryIndexer",
    "LRUDocumentCache",
    "SimpleChunker",
    "SimpleDuplicateDetector",
    "SimpleQAEngine",
    "SimpleRetriever",
    "SimpleVersioner",
    "TableExtractorImpl",
    # Modèle de données
    "DocumentChunk",
    "DocumentItem",
    "DocumentMetadata",
    "DocumentStatus",
    "DocumentType",
]
