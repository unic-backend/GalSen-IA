"""
Modèle de données pour le moteur d'intelligence documentaire GalSen IA.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import time


class DocumentType(Enum):
    """Types de documents pris en charge."""
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    TXT = "txt"
    MARKDOWN = "markdown"
    CSV = "csv"
    HTML = "html"
    # OCR will be handled as a special case or via specific loaders


class DocumentStatus(Enum):
    """Statuts des documents."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    PROCESSING = "processing"
    ERROR = "error"


@dataclass
class DocumentItem:
    """Représente un document enregistré dans le moteur."""
    document_id: str
    document_type: DocumentType
    title: str
    content: str  # Contenu texte extrait (pour les documents textuels) ou référence
    raw_data: Optional[bytes] = None  # Données brutes du fichier (optionnel)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: DocumentStatus = DocumentStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: int = 1
    parent_id: Optional[str] = None  # Pour le versionnement
    chunks: List['DocumentChunk'] = field(default_factory=list)  # Liste des chunks associés

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'élément en dictionnaire."""
        return {
            "document_id": self.document_id,
            "document_type": self.document_type.value,
            "title": self.title,
            "content": self.content,
            "raw_data": self.raw_data.hex() if self.raw_data else None,
            "metadata": self.metadata,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "parent_id": self.parent_id,
            "chunks": [chunk.to_dict() for chunk in self.chunks]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentItem':
        """Crée un élément à partir d'un dictionnaire."""
        # Conversion des champs spéciaux
        raw_data = bytes.fromhex(data["raw_data"]) if data.get("raw_data") else None
        chunks = [DocumentChunk.from_dict(c) for c in data.get("chunks", [])]
        return cls(
            document_id=data["document_id"],
            document_type=DocumentType(data["document_type"]),
            title=data["title"],
            content=data["content"],
            raw_data=raw_data,
            metadata=data.get("metadata", {}),
            status=DocumentStatus(data.get("status", DocumentStatus.ACTIVE.value)),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            version=data.get("version", 1),
            parent_id=data.get("parent_id"),
            chunks=chunks
        )


@dataclass
class DocumentChunk:
    """Représente un morceau de texte extrait d'un document."""
    chunk_id: str
    document_id: str
    content: str
    start_index: int  # Position de début dans le texte original
    end_index: int    # Position de fin dans le texte original
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le chunk en dictionnaire."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentChunk':
        """Crée un chunk à partir d'un dictionnaire."""
        return cls(
            chunk_id=data["chunk_id"],
            document_id=data["document_id"],
            content=data["content"],
            start_index=data["start_index"],
            end_index=data["end_index"],
            metadata=data.get("metadata", {})
        )


@dataclass
class DocumentMetadata:
    """Métadonnées extraites d'un document."""
    author: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    title: Optional[str] = None
    subject: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    language: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None
    line_count: Optional[int] = None
    # Pour les tableaux et images
    table_count: int = 0
    image_count: int = 0
    # Métadonnées personnalisées
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit les métadonnées en dictionnaire."""
        return {
            "author": self.author,
            "creator": self.creator,
            "producer": self.producer,
            "creation_date": self.creation_date,
            "modification_date": self.modification_date,
            "title": self.title,
            "subject": self.subject,
            "keywords": self.keywords,
            "language": self.language,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "character_count": self.character_count,
            "line_count": self.line_count,
            "table_count": self.table_count,
            "image_count": self.image_count,
            "custom": self.custom
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentMetadata':
        """Crée des métadonnées à partir d'un dictionnaire."""
        return cls(
            author=data.get("author"),
            creator=data.get("creator"),
            producer=data.get("producer"),
            creation_date=data.get("creation_date"),
            modification_date=data.get("modification_date"),
            title=data.get("title"),
            subject=data.get("subject"),
            keywords=data.get("keywords", []),
            language=data.get("language"),
            page_count=data.get("page_count"),
            word_count=data.get("word_count"),
            character_count=data.get("character_count"),
            line_count=data.get("line_count"),
            table_count=data.get("table_count", 0),
            image_count=data.get("image_count", 0),
            custom=data.get("custom", {})
        )