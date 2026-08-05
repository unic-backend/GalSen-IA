"""
Gestionnaire principal du moteur d'intelligence documentaire GalSen IA.

Ce module assemble les composants du moteur (stockage, chargement, découpage,
indexation, recherche, résumé, questions-réponses, comparaison, métadonnées,
versionnement, cache, validation) derrière une API unique. Chaque composant est
injectable, ce qui permet de remplacer une implémentation sans toucher aux
autres ni au code appelant.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from .basic_document_validator import DocumentValidatorImpl
from .composite_metadata_extractor import CompositeMetadataExtractor
from .document_loader_factory import DocumentLoaderFactory
from .embedded_image_extractor import ImageExtractorImpl
from .extractive_summarizer import ExtractiveSummarizer
from .in_memory_document_store import InMemoryDocumentStore
from .in_memory_indexer import InMemoryIndexer
from .in_memory_versioner import SimpleVersioner
from .interfaces import (
    DocumentCache, DocumentChunker, DocumentComparator, DocumentDuplicateDetector,
    DocumentImageExtractor, DocumentIndexer, DocumentManager, DocumentMetadataExtractor,
    DocumentQA, DocumentRetriever, DocumentStore, DocumentSummarizer,
    DocumentTableExtractor, DocumentValidator, DocumentVersioner
)
from .keyword_qa_engine import SimpleQAEngine
from .lru_document_cache import LRUDocumentCache
from .similarity_duplicate_detector import SimpleDuplicateDetector
from .simple_chunker import SimpleChunker
from .simple_retriever import SimpleRetriever
from .text_document_comparator import DocumentComparatorImpl
from .text_table_extractor import TableExtractorImpl
from .types import DocumentChunk, DocumentItem, DocumentMetadata

__all__ = [
    "DocumentManagerImpl",
    # Ré-exportés pour que les imports existants continuent de fonctionner
    "ExtractiveSummarizer",
    "SimpleQAEngine",
    "DocumentComparatorImpl",
    "SimpleDuplicateDetector",
    "CompositeMetadataExtractor",
    "TableExtractorImpl",
    "ImageExtractorImpl",
    "SimpleVersioner",
    "LRUDocumentCache",
    "DocumentValidatorImpl",
]


class DocumentManagerImpl(DocumentManager):
    """
    Implémentation concrète du gestionnaire de documents qui coordonne
    tous les composants du moteur d'intelligence documentaire.
    """

    def __init__(
        self,
        store: Optional[DocumentStore] = None,
        loader_factory: Optional[DocumentLoaderFactory] = None,
        chunker: Optional[DocumentChunker] = None,
        indexer: Optional[DocumentIndexer] = None,
        retriever: Optional[DocumentRetriever] = None,
        summarizer: Optional[DocumentSummarizer] = None,
        qa_engine: Optional[DocumentQA] = None,
        comparator: Optional[DocumentComparator] = None,
        duplicate_detector: Optional[DocumentDuplicateDetector] = None,
        metadata_extractor: Optional[DocumentMetadataExtractor] = None,
        table_extractor: Optional[DocumentTableExtractor] = None,
        image_extractor: Optional[DocumentImageExtractor] = None,
        versioner: Optional[DocumentVersioner] = None,
        cache: Optional[DocumentCache] = None,
        validator: Optional[DocumentValidator] = None,
    ):
        """
        Initialise le gestionnaire de documents.

        Tous les composants ont une implémentation par défaut : le gestionnaire
        s'utilise sans argument. Chacun peut être remplacé pour brancher un autre
        stockage, un autre index ou un autre modèle sans modifier le reste.

        Args:
            store: Stockage des documents
            loader_factory: Usine fournissant le chargeur adapté à chaque format
            chunker: Découpeur de documents en morceaux
            indexer: Index de recherche plein texte
            retriever: Récupérateur de passages pertinents
            summarizer: Générateur de résumés
            qa_engine: Moteur de questions-réponses
            comparator: Comparateur de documents
            duplicate_detector: Détecteur de doublons
            metadata_extractor: Extracteur de métadonnées
            table_extractor: Extracteur de tableaux
            image_extractor: Extracteur d'images
            versioner: Gestionnaire de versions
            cache: Cache des documents chargés
            validator: Validateur de documents
        """
        self._store = store or InMemoryDocumentStore()
        self._loader_factory = loader_factory or DocumentLoaderFactory()
        self._chunker = chunker or SimpleChunker()
        self._indexer = indexer or InMemoryIndexer()
        self._retriever = retriever or SimpleRetriever(self._indexer)
        self._summarizer = summarizer or ExtractiveSummarizer()
        # Le moteur de questions-réponses et le versionneur lisent le stockage
        self._qa_engine = qa_engine or SimpleQAEngine(self._store)
        self._comparator = comparator or DocumentComparatorImpl()
        self._duplicate_detector = duplicate_detector or SimpleDuplicateDetector()
        self._metadata_extractor = metadata_extractor or CompositeMetadataExtractor()
        self._table_extractor = table_extractor or TableExtractorImpl()
        self._image_extractor = image_extractor or ImageExtractorImpl()
        self._versioner = versioner or SimpleVersioner(self._store)
        self._cache = cache or LRUDocumentCache()
        self._validator = validator or DocumentValidatorImpl()

        self._logger = logging.getLogger(__name__)
        self._logger.info("Gestionnaire de documents initialisé")

    # Méthodes de gestion du stockage des documents
    def register_document(self, document: DocumentItem) -> str:
        """Enregistre un nouveau document."""
        return self._store.save(document)

    def get_document(self, document_id: str) -> Optional[DocumentItem]:
        """Récupère un document enregistré."""
        return self._store.get(document_id)

    def update_document(self, document: DocumentItem) -> bool:
        """Met à jour un document enregistré."""
        return self._store.update(document)

    def unregister_document(self, document_id: str) -> bool:
        """Désenregistre un document et retire sa trace de l'index."""
        self._indexer.delete(document_id)
        return self._store.delete(document_id)

    def list_documents(self, **filters) -> List[DocumentItem]:
        """Liste tous les documents enregistrés."""
        return self._store.list_items(**filters)

    # Méthodes de traitement de documents
    def load_document(self, source: str, **kwargs) -> DocumentItem:
        """
        Charge un document depuis une source et l'enregistre.

        Args:
            source: Chemin du fichier à charger
            **kwargs: Options transmises au chargeur (encoding, delimiter, etc.)

        Returns:
            Document chargé et enregistré

        Raises:
            ValueError: Si aucun chargeur ne prend en charge ce format
        """
        cache_key = self._cache_key(source, kwargs)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        loader = self._loader_factory.get_loader_for_file(source)
        if loader is None:
            raise ValueError(f"Aucun chargeur trouvé pour le fichier: {source}")

        # Les chargeurs retournent directement un DocumentItem
        document = loader.load(source, **kwargs)
        self.register_document(document)
        self._cache.set(cache_key, document)

        return document

    def chunk_document(self, document_id: str, **kwargs) -> List[DocumentChunk]:
        """Découpe un document en morceaux et les attache au document."""
        document = self._require_document(document_id)

        chunks = self._chunker.chunk(document, **kwargs)
        document.chunks = chunks
        self.update_document(document)
        return chunks

    def index_document(self, document_id: str) -> None:
        """Indexe un document pour la recherche."""
        self._indexer.index(self._require_document(document_id))

    def search_documents(self, query: str, limit: int = 10) -> List[Tuple[DocumentItem, float]]:
        """Recherche des documents correspondant à la requête."""
        return self._indexer.search(query, limit=limit)

    def retrieve_relevant_chunks(
        self, query: str, document_id: Optional[str] = None, limit: int = 5
    ) -> List[DocumentChunk]:
        """Récupère les chunks les plus pertinents pour une requête."""
        return self._retriever.retrieve(query, document_id, limit)

    def summarize_document(self, document_id: str, **kwargs) -> str:
        """Génère un résumé d'un document."""
        return self._summarizer.summarize(self._require_document(document_id), **kwargs)

    def answer_question(self, question: str, document_id: Optional[str] = None, **kwargs) -> str:
        """Répond à une question basée sur le contenu des documents."""
        return self._qa_engine.answer_question(question, document_id, **kwargs)

    def answer_question_with_sources(
        self, question: str, document_id: Optional[str] = None, **kwargs
    ) -> Tuple[str, List[DocumentChunk]]:
        """Répond à une question en retournant aussi les passages sources."""
        return self._qa_engine.answer_question_with_sources(question, document_id, **kwargs)

    def compare_documents(self, document_id1: str, document_id2: str, **kwargs) -> Dict[str, Any]:
        """Compare deux documents."""
        doc1 = self._require_document(document_id1)
        doc2 = self._require_document(document_id2)
        return self._comparator.compare(doc1, doc2, **kwargs)

    def detect_duplicates(self, threshold: float = 0.8) -> List[Tuple[DocumentItem, DocumentItem]]:
        """Détecte les doublons parmi tous les documents."""
        return self._duplicate_detector.find_duplicates(self.list_documents(), threshold)

    def extract_metadata(self, document_id: str) -> DocumentMetadata:
        """Extrait les métadonnées d'un document."""
        return self._metadata_extractor.extract_metadata(self._require_document(document_id))

    def extract_tables(self, document_id: str) -> List[Dict[str, Any]]:
        """Extrait les tableaux d'un document."""
        return self._table_extractor.extract_tables(self._require_document(document_id))

    def extract_images(self, document_id: str, **kwargs) -> List[Dict[str, Any]]:
        """Extrait les images d'un document."""
        return self._image_extractor.extract_images(self._require_document(document_id), **kwargs)

    def create_version(self, document_id: str, changes: Dict[str, Any]) -> DocumentItem:
        """
        Crée une nouvelle version d'un document et l'enregistre.

        Args:
            document_id: Document servant de base à la nouvelle version
            changes: Champs modifiés (`content`, `title`, `status`, `comment`)

        Returns:
            Nouvelle version enregistrée, avec son propre identifiant
        """
        document = self._require_document(document_id)

        new_version = self._versioner.create_version(document, changes)
        # La version est un document à part entière : elle est stockée comme tel
        self.register_document(new_version)
        return new_version

    def get_version_history(self, document_id: str) -> List[DocumentItem]:
        """Récupère l'historique des versions d'un document, de la plus ancienne à la plus récente."""
        return self._versioner.get_version_history(document_id)

    def validate_document(self, document_id: str) -> Tuple[bool, List[str]]:
        """Valide un document."""
        return self._validator.validate(self._require_document(document_id))

    # Méthodes utilitaires supplémentaires
    def get_document_info(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations détaillées d'un document."""
        document = self.get_document(document_id)
        if document is None:
            return None

        return {
            "document_id": document.document_id,
            "document_type": document.document_type.value,
            "title": document.title,
            "content_length": len(document.content),
            "chunk_count": len(document.chunks),
            "version": document.version,
            "parent_id": document.parent_id,
            "status": document.status.value,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
            "metadata": document.metadata
        }

    def get_stats(self) -> Dict[str, Any]:
        """Retourne un état synthétique du moteur."""
        documents = self.list_documents()
        by_type: Dict[str, int] = {}
        for document in documents:
            type_name = document.document_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1

        return {
            "document_count": len(documents),
            "documents_by_type": by_type,
            "total_characters": sum(len(document.content) for document in documents),
        }

    def cleanup(self) -> None:
        """Nettoie les ressources."""
        self._store.cleanup_expired()
        self._indexer.clear()
        self._cache.clear()
        self._logger.info("Gestionnaire de documents nettoyé")

    def _require_document(self, document_id: str) -> DocumentItem:
        """
        Récupère un document ou signale son absence.

        Raises:
            ValueError: Si aucun document ne porte cet identifiant
        """
        document = self.get_document(document_id)
        if document is None:
            raise ValueError(f"Document non trouvé: {document_id}")
        return document

    def _cache_key(self, source: str, options: Dict[str, Any]) -> str:
        """Construit la clé de cache d'un chargement, options comprises."""
        normalized_options = sorted((str(key), str(value)) for key, value in options.items())
        return f"load:{source}:{normalized_options}"
