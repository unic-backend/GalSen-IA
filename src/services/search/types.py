"""
Modèles de données du service de recherche unifiée.

Définit les types partagés : requête de recherche, résultat, source
de provenance et générateur d'identifiants.

Ce module n'a aucune dépendance externe.
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def generate_search_id() -> str:
    """Génère un identifiant unique de recherche (préfixe ``search_``)."""
    return f"search_{uuid.uuid4().hex[:12]}"


class SearchSource(str, Enum):
    """Source d'un résultat de recherche."""

    KNOWLEDGE = "knowledge"
    MEMORY = "memory"
    DOCUMENT = "document"
    VISION = "vision"


class SearchSort(str, Enum):
    """Mode de tri des résultats de recherche."""

    RELEVANCE = "relevance"
    DATE_DESC = "date_desc"
    DATE_ASC = "date_asc"


@dataclass
class SearchQuery:
    """
    Requête de recherche unifiée.

    Peut cibler une ou plusieurs sources et être filtrée par type,
    priorité minimale et intervalle de dates.
    """

    query: str
    sources: List[SearchSource] = field(default_factory=lambda: list(SearchSource))
    limit: int = 10
    offset: int = 0
    sort: SearchSort = SearchSort.RELEVANCE
    min_score: Optional[float] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    # Rôle de l'appelant, porté jusqu'aux fournisseurs : chercher n'autorise pas
    # à lire. Sans rôle, un fournisseur ne rend que ce qui est public
    # (VOLET 05 ch. 07, VOLET 14 ch. 07).
    role: Optional[str] = None


@dataclass
class SearchResultItem:
    """
    Résultat individuel d'une recherche.

    Chaque résultat provient d'une source spécifique et contient le contenu,
    le score de pertinence et les métadonnées de l'élément trouvé.
    """

    id: str
    source: SearchSource
    content: Any
    score: float
    title: Optional[str] = None
    summary: Optional[str] = None
    source_detail: Optional[str] = None
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat en dictionnaire."""
        result: Dict[str, Any] = {
            "id": self.id,
            "source": self.source.value,
            "content": self.content,
            "score": self.score,
        }
        optional_fields = {
            "title": self.title,
            "summary": self.summary,
            "source_detail": self.source_detail,
        }
        for key, value in optional_fields.items():
            if value is not None:
                result[key] = value
        if self.created_at is not None:
            created_iso = datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat()
            result["created_at"] = created_iso
        if self.updated_at is not None:
            updated_iso = datetime.fromtimestamp(self.updated_at, tz=timezone.utc).isoformat()
            result["updated_at"] = updated_iso
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class SearchResponse:
    """
    Réponse complète d'une recherche.

    Contient les résultats, le nombre total (avant pagination) et
    des métadonnées sur la recherche elle-même.
    """

    results: List[SearchResultItem]
    total: int
    query: str
    search_id: str = field(default_factory=generate_search_id)
    execution_time_ms: float = 0.0
    sources_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la réponse complète en dictionnaire."""
        return {
            "results": [r.to_dict() for r in self.results],
            "total": self.total,
            "query": self.query,
            "search_id": self.search_id,
            "execution_time_ms": self.execution_time_ms,
            "sources_used": self.sources_used,
        }