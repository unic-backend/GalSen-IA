"""
Types de données pour le moteur de connaissances GalSen IA.
"""

from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import datetime
import hashlib


from .scope import KnowledgeSubject  # noqa: E402  (axes du VOLET 35)

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
    """Langues qu'un document peut déclarer.

    « Supportée » veut dire **étiquetable, stockable, filtrable et retrouvable
    lexicalement** dans cette langue — pas comprise. Ce que la plateforme sait
    réellement faire par langue est mesuré par `language_support()`
    (`src/knowledge_engine/languages.py`), capacité par capacité.

    `WO` (wolof) et `FF` (pulaar) sont des codes ISO 639-1 ; le sérère n'en a
    pas, `SRR` est son code ISO 639-3.
    """
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
    # Langues nationales du Sénégal (VOLET 36, ch. B). Sans elles, un document
    # wolof ne pouvait entrer qu'étiqueté dans une langue qui n'est pas la sienne.
    WO = "wo"
    FF = "ff"
    SRR = "srr"


class KnowledgeDomain(Enum):
    """Domaines de connaissance définis par le VOLET 05 (chapitres 01 et 02).

    Le chapitre 02 exige que la connaissance soit organisée avant d'être
    consommée : le domaine est le premier niveau de cette organisation, au-dessus
    des catégories libres. Il est fermé volontairement — un domaine que personne
    ne peut nommer ne peut pas non plus recevoir un propriétaire ni un cycle de
    revue (chapitre 06).

    UNSPECIFIED est la valeur par défaut : elle dit « pas encore classé », et ne
    doit jamais être confondue avec un classement réel.
    """
    BUSINESS = "business"
    TECHNICAL = "technical"
    OPERATIONAL = "operational"
    LEGAL = "legal"
    AI = "ai"
    USER_DOCUMENTATION = "user_documentation"
    PROJECT_DOCUMENTATION = "project_documentation"
    UNSPECIFIED = "unspecified"


class KnowledgeSensitivity(Enum):
    """Sensibilité d'une connaissance (VOLET 05, chapitre 02 — classification).

    Répond à « qu'est-ce qui doit être protégé », pas à « qui y a droit » : la
    correspondance entre sensibilité et rôles appartient au chapitre 07.
    PUBLIC est la valeur par défaut — une connaissance dont personne n'a déclaré
    la sensibilité ne doit pas être traitée comme protégée par accident.
    """
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class KnowledgeStatus(Enum):
    """Statut d'une connaissance dans son cycle de vie (VOLET 05, chapitres 02 et 04).

    Un seul axe pour les deux chapitres, qui nomment la même progression avec des
    mots différents : le chapitre 02 liste Draft, Reviewed, Approved, Archived ;
    le chapitre 04 liste Draft, Under Review, Verified, Approved, Deprecated.
    REVIEWED porte ce que le chapitre 04 appelle « Verified ». Deux énumérations
    pour une même progression seraient la duplication que le chapitre 02 interdit.

    ARCHIVED et DEPRECATED ne sont pas synonymes : une connaissance archivée est
    retirée de l'usage courant mais reste vraie, une connaissance dépréciée ne
    doit plus être utilisée comme référence.
    """
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


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
    domain: KnowledgeDomain = KnowledgeDomain.UNSPECIFIED
    # Les deux axes du VOLET 35, indépendants de `domain` : celui-ci classe la
    # documentation **de la plateforme**, ceux-là classent la connaissance **du
    # monde**. `scope` dit d'où elle vaut, `subject` de quoi elle parle.
    # Le défaut est « mondial, non classé » : une connaissance sans portée
    # déclarée n'est pas sénégalaise par accident.
    scope: str = "global"
    subject: KnowledgeSubject = KnowledgeSubject.UNSPECIFIED
    sensitivity: KnowledgeSensitivity = KnowledgeSensitivity.PUBLIC
    status: KnowledgeStatus = KnowledgeStatus.DRAFT
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
            domain=self.domain,
            scope=self.scope,
            subject=self.subject,
            sensitivity=self.sensitivity,
            # Un contenu réécrit n'est plus celui qui avait été revu : il repart en
            # brouillon et devra repasser par le cycle du chapitre 03.
            status=KnowledgeStatus.DRAFT,
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