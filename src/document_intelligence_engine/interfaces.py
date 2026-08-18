"""
Interfaces pour le moteur d'intelligence documentaire GalSen IA.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .types import DocumentItem, DocumentChunk, DocumentMetadata


class DocumentStore(ABC):
    """Interface pour le stockage des documents."""

    @abstractmethod
    def save(self, document: DocumentItem) -> str:
        """Sauvegarde un document et retourne son ID."""
        pass

    @abstractmethod
    def get(self, document_id: str) -> Optional[DocumentItem]:
        """Récupère un document par son ID."""
        pass

    @abstractmethod
    def update(self, document: DocumentItem) -> bool:
        """Met à jour un document existant."""
        pass

    @abstractmethod
    def delete(self, document_id: str) -> bool:
        """Supprime un document."""
        pass

    @abstractmethod
    def list_items(self, limit: int = 100, **filters) -> List[DocumentItem]:
        """Liste les documents avec des filtres optionnels."""
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """Nettoie les documents expirés et retourne le nombre supprimé."""
        pass


class DocumentLoader(ABC):
    """Interface pour le chargement des documents depuis diverses sources."""

    @abstractmethod
    def load(self, source: str, **kwargs) -> DocumentItem:
        """Charge un document à partir d'une source (chemin, URL, etc.) et retourne un DocumentItem."""
        pass

    @abstractmethod
    def supports_type(self, document_type: str) -> bool:
        """Vérifie si le chargeur supporte un type de document donné."""
        pass


class DocumentChunker(ABC):
    """Interface pour la découpe de documents en morceaux."""

    @abstractmethod
    def chunk(self, document: DocumentItem, **kwargs) -> List[DocumentChunk]:
        """Découpe un document en morceaux et retourne la liste des chunks."""
        pass


class DocumentIndexer(ABC):
    """Interface pour l'indexation du contenu des documents."""

    @abstractmethod
    def index(self, document: DocumentItem) -> None:
        """Indexe un document pour la recherche."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[tuple[DocumentItem, float]]:
        """Recherche des documents correspondant à la requête et retourne une liste de (document, score)."""
        pass

    @abstractmethod
    def delete(self, document_id: str) -> bool:
        """Supprime l'index d'un document."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Vide l'index complet."""
        pass


class DocumentRetriever(ABC):
    """Interface pour la récupération de contenus pertinents depuis les documents."""

    @abstractmethod
    def retrieve(self, query: str, document_id: Optional[str] = None, limit: int = 5) -> List[DocumentChunk]:
        """Récupère les chunks les plus pertinents pour une requête, éventuellement limités à un document."""
        pass


class DocumentSummarizer(ABC):
    """Interface pour la synthèse de documents."""

    @abstractmethod
    def summarize(self, document: DocumentItem, **kwargs) -> str:
        """Génère un résumé du document."""
        pass

    @abstractmethod
    def summarize_chunk(self, chunk: DocumentChunk, **kwargs) -> str:
        """Génère un résumé d'un chunk de document."""
        pass


class DocumentQA(ABC):
    """Interface pour la réponse à des questions sur des documents."""

    @abstractmethod
    def answer_question(self, question: str, document_id: Optional[str] = None, **kwargs) -> str:
        """Répond à une question basée sur le contenu d'un document ou de tous les documents."""
        pass

    @abstractmethod
    def answer_question_with_sources(
        self,
        question: str,
        document_id: Optional[str] = None,
        **kwargs,
    ) -> tuple[str, List[DocumentChunk]]:
        """Répond à une question en retournant la réponse et les chunks sources."""
        pass


class DocumentComparator(ABC):
    """Interface pour la comparaison de documents."""

    @abstractmethod
    def compare(self, doc1: DocumentItem, doc2: DocumentItem, **kwargs) -> Dict[str, Any]:
        """Compare deux documents et retourne les différences et similarités."""
        pass


class DocumentDuplicateDetector(ABC):
    """Interface pour la détection de doublons entre documents."""

    @abstractmethod
    def is_duplicate(self, doc1: DocumentItem, doc2: DocumentItem, threshold: float = 0.8) -> bool:
        """Détermine si deux documents sont des doublons au-delà d'un seuil de similarité."""
        pass

    @abstractmethod
    def find_duplicates(
        self,
        documents: List[DocumentItem],
        threshold: float = 0.8,
    ) -> List[tuple[DocumentItem, DocumentItem]]:
        """Trouve toutes les paires de doublons dans une liste de documents."""
        pass


class DocumentMetadataExtractor(ABC):
    """Interface pour l'extraction de métadonnées des documents."""

    @abstractmethod
    def extract_metadata(self, document: DocumentItem) -> DocumentMetadata:
        """Extrait les métadonnées d'un document."""
        pass


class DocumentTableExtractor(ABC):
    """Interface pour l'extraction de tableaux des documents."""

    @abstractmethod
    def extract_tables(self, document: DocumentItem) -> List[Dict[str, Any]]:
        """Extrait tous les tableaux d'un document et retourne une liste de représentations de tableaux."""
        pass


class DocumentImageExtractor(ABC):
    """Interface pour l'extraction d'images des documents."""

    @abstractmethod
    def extract_images(self, document: DocumentItem, **kwargs) -> List[Dict[str, Any]]:
        """Extrait toutes les images d'un document et retourne une liste de représentations d'images."""
        pass


class DocumentVersioner(ABC):
    """Interface pour la gestion des versions de documents."""

    @abstractmethod
    def create_version(self, document: DocumentItem, changes: Dict[str, Any]) -> DocumentItem:
        """Crée une nouvelle version d'un document basée sur les changements."""
        pass

    @abstractmethod
    def get_version_history(self, document_id: str) -> List[DocumentItem]:
        """Récupère l'historique des versions d'un document."""
        pass


class DocumentCache(ABC):
    """Interface pour la mise en cache des résultats de traitement de documents."""

    @abstractmethod
    def get(self, key: str) -> Any:
        """Récupère une valeur du cache."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Stocke une valeur dans le cache avec une durée de vie optionnelle."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Supprime une valeur du cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Vide le cache."""
        pass


class DocumentValidator(ABC):
    """Interface pour la validation des documents."""

    @abstractmethod
    def validate(self, document: DocumentItem) -> tuple[bool, List[str]]:
        """Valide un document et retourne un tuple (est_valide, liste_des_erreurs)."""
        pass


class DocumentManager(ABC):
    """Interface principale du gestionnaire de documents qui coordonne tous les composants."""

    # Méthodes de gestion du stockage des documents
    @abstractmethod
    def register_document(self, document: DocumentItem) -> str:
        """Enregistre un nouveau document."""
        pass

    @abstractmethod
    def get_document(self, document_id: str) -> Optional[DocumentItem]:
        """Récupère un document enregistré."""
        pass

    @abstractmethod
    def update_document(self, document: DocumentItem) -> bool:
        """Met à jour un document enregistré."""
        pass

    @abstractmethod
    def unregister_document(self, document_id: str) -> bool:
        """Désenregistre un document."""
        pass

    @abstractmethod
    def list_documents(self, **filters) -> List[DocumentItem]:
        """Liste tous les documents enregistrés."""
        pass

    # Méthodes de traitement de documents
    @abstractmethod
    def load_document(self, source: str, **kwargs) -> DocumentItem:
        """Charge un document depuis une source et l'enregistre."""
        pass

    @abstractmethod
    def chunk_document(self, document_id: str, **kwargs) -> List[DocumentChunk]:
        """Découpe un document en morceaux."""
        pass

    @abstractmethod
    def index_document(self, document_id: str) -> None:
        """Indexe un document pour la recherche."""
        pass

    @abstractmethod
    def search_documents(self, query: str, limit: int = 10) -> List[tuple[DocumentItem, float]]:
        """Recherche des documents correspondant à la requête."""
        pass

    @abstractmethod
    def retrieve_relevant_chunks(
        self,
        query: str,
        document_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[DocumentChunk]:
        """Récupère les chunks les plus pertinents pour une requête."""
        pass

    @abstractmethod
    def summarize_document(self, document_id: str, **kwargs) -> str:
        """Génère un résumé d'un document."""
        pass

    @abstractmethod
    def answer_question(self, question: str, document_id: Optional[str] = None, **kwargs) -> str:
        """Répond à une question basée sur le contenu d'un document ou de tous les documents."""
        pass

    @abstractmethod
    def compare_documents(self, document_id1: str, document_id2: str, **kwargs) -> Dict[str, Any]:
        """Compare deux documents."""
        pass

    @abstractmethod
    def detect_duplicates(self, threshold: float = 0.8) -> List[tuple[DocumentItem, DocumentItem]]:
        """Détecte les doublons parmi tous les documents."""
        pass

    @abstractmethod
    def extract_metadata(self, document_id: str) -> DocumentMetadata:
        """Extrait les métadonnées d'un document."""
        pass

    @abstractmethod
    def extract_tables(self, document_id: str) -> List[Dict[str, Any]]:
        """Extrait les tableaux d'un document."""
        pass

    @abstractmethod
    def extract_images(self, document_id: str) -> List[Dict[str, Any]]:
        """Extrait les images d'un document."""
        pass

    @abstractmethod
    def create_version(self, document_id: str, changes: Dict[str, Any]) -> DocumentItem:
        """Crée une nouvelle version d'un document."""
        pass

    @abstractmethod
    def validate_document(self, document_id: str) -> tuple[bool, List[str]]:
        """Valide un document."""
        pass

    # Méthodes utilitaires supplémentaires
    @abstractmethod
    def get_document_info(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations détaillées d'un document."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Nettoie les ressources."""
        pass