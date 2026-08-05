"""
Types de données pour le moteur de connaissances GalSen IA.
"""

from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import datetime
import hashlib


class KnowledgeType(Enum):
    """Types de connaissances."""
    FACT = "fact"
    PROCEDURE = "procedure"
    RULE = "rule"
    PRINCIPLE = "principle"
    EXAMPLE = "example"
    REFERENCE = "reference"


class ContentType(Enum):
    """Types de contenu."""
    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    DOCX = "docx"


class Language(Enum):
    """Langues supportées."""
    FR = "fr"
    EN = "en"
    ES = "es"
    DE = "de"
    AR = "ar"
    SW = "sw"
    HA = "ha"
    YO = "yo"
    ZU = "zu"
    AF = "af"
    AM = "am"


class ConfidenceLevel(Enum):
    """Niveaux de confiance."""
    VERY_LOW = 0.0
    LOW = 0.25
    MEDIUM = 0.5
    HIGH = 0.75
    VERY_HIGH = 1.0


class SourceCategory(Enum):
    """Catégories de sources définissant la hiérarchie de connaissance.

    Conformément au chapitre 04 de la Constitution GalSen IA, la fiabilité
    d'une connaissance dépend de la catégorie de sa source :
    - P1 : lois officielles, publications gouvernementales, normes officielles,
      documentation officielle.
    - P2 : recherche évaluée par les pairs, documentation technique de confiance,
      institutions réputées.
    - P3 : références industrielles fiables, consensus d'experts.
    - P4 : estimations ou opinions clairement étiquetées.
    """
    OFFICIAL = "official"
    GOVERNMENT = "government"
    STANDARD = "standard"
    OFFICIAL_DOCUMENTATION = "official_documentation"
    PEER_REVIEWED = "peer_reviewed"
    TRUSTED_DOCUMENTATION = "trusted_documentation"
    INSTITUTIONAL = "institutional"
    INDUSTRY = "industry"
    EXPERT_CONSENSUS = "expert_consensus"
    ESTIMATE = "estimate"
    OPINION = "opinion"
    UNKNOWN = "unknown"


class KnowledgePriority(IntEnum):
    """Priorité de fiabilité d'une connaissance (valeur basse = plus fiable).

    P1 correspond aux sources officielles (niveau le plus fiable),
    P4 aux estimations et opinions (le moins fiable).
    """
    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4

    @classmethod
    def from_source_category(cls, source_category: Optional['SourceCategory']) -> 'KnowledgePriority':
        """Déduit la priorité par défaut à partir de la catégorie de source."""
        if source_category is None:
            return cls.P3
        if source_category in (SourceCategory.OFFICIAL, SourceCategory.GOVERNMENT,
                               SourceCategory.STANDARD, SourceCategory.OFFICIAL_DOCUMENTATION):
            return cls.P1
        if source_category in (SourceCategory.PEER_REVIEWED, SourceCategory.TRUSTED_DOCUMENTATION,
                               SourceCategory.INSTITUTIONAL):
            return cls.P2
        if source_category in (SourceCategory.ESTIMATE, SourceCategory.OPINION):
            return cls.P4
        return cls.P3


@dataclass
class KnowledgeSource:
    """Source d'une connaissance."""
    id: str
    type: str  # e.g., 'file', 'url', 'api', 'database'
    location: str  # path, URL, connection string
    accessed_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    hash: Optional[str] = None  # hash of the content at retrieval
    source_category: Optional[SourceCategory] = None  # catégorie de source (P1-P4)
    title: Optional[str] = None  # titre du document source
    author: Optional[str] = None  # auteur ou institution de la source
    url: Optional[str] = None  # URL de la source si applicable
    citation: Optional[str] = None  # citation complète de la source
    retrieved_at: Optional[datetime.datetime] = None  # date de récupération


@dataclass
class KnowledgeItem:
    """Un élément de connaissance dans la base."""
    content: str
    summary: Optional[str] = None
    knowledge_type: KnowledgeType = KnowledgeType.FACT
    content_type: ContentType = ContentType.TEXT
    language: Language = Language.FR
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    source: KnowledgeSource = field(default_factory=lambda: KnowledgeSource(id="unknown", type="unknown", location="unknown"))
    confidence: float = 0.5  # 0.0 to 1.0
    version: int = 1
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    relations: List[str] = field(default_factory=list)  # IDs of related knowledge items
    id: Optional[str] = None
    priority: KnowledgePriority = KnowledgePriority.P3

    def __post_init__(self):
        """Generate ID if not provided."""
        if self.id is None:
            # Create a deterministic ID based on content hash
            content_hash = hashlib.sha256(self.content.encode('utf-8')).hexdigest()[:12]
            self.id = f"kn{content_hash}"

    def compute_content_hash(self) -> str:
        """Calcule le hash du contenu."""
        return hashlib.sha256(self.content.encode('utf-8')).hexdigest()

    def is_outdated(self, other: 'KnowledgeItem') -> bool:
        """Vérifie si cet élément est plus ancien que l'autre."""
        return self.updated_at < other.updated_at

    def update_content(self, new_content: str, source: Optional[KnowledgeSource] = None) -> 'KnowledgeItem':
        """Crée une nouvelle version de l'élément avec du contenu mis à jour."""
        new_item = KnowledgeItem(
            id=self.id,  # même ID pour la même logique de connaissance
            content=new_content,
            summary=None,  # à regénérer
            knowledge_type=self.knowledge_type,
            content_type=self.content_type,
            language=self.language,
            tags=self.tags.copy(),
            categories=self.categories.copy(),
            source=source or self.source,
            confidence=self.confidence,
            version=self.version + 1,
            created_at=self.created_at,
            updated_at=datetime.datetime.now(datetime.timezone.utc),
            metadata=self.metadata.copy(),
            relations=self.relations.copy(),
            priority=self.priority
        )
        return new_item