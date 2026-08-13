"""
Acquisition de documents : services, pas moteur (ADR-021).

Ce paquet contient les quelques services qui manquaient entre le registre des
sources et l'ingestion. Il n'ajoute ni agent, ni orchestrateur, ni moteur : la
décision de collecte existe déjà (`knowledge_engine/collection.py`), la barrière
de confiance existe déjà (`security/trust.py`), l'ingestion existe déjà. Ce qui
manquait est la moitié avant — découvrir, récupérer, et **tenir l'état** d'un
document candidat qui n'est encore rien.

Conception complète : `docs/architecture/senegal-knowledge-acquisition.md`.
"""

from .discovery import DiscoveryRefused, discover, discovery_report
from .fetcher import FetchRefused, FetchResult, fetch, fetch_robots, fetcher_report
from .language import detect_language, detection_report, reconcile
from .metadata import extract as extract_metadata
from .metadata import metadata_report
from .gate import (
    CollectionBatch,
    GateRefused,
    acquire,
    gate_report,
    plan_batch,
    submit_batch,
)
from .dedup import compare, dedup_report, find_duplicates, similarity
from .quality import evaluate, quality_report
from .parsing import boundary_report, cross_boundary, extract_text
from .record import (
    STATUTS_TERMINAUX,
    TRANSITIONS,
    AcquiredDocument,
    AcquisitionRefused,
    AcquisitionStatus,
    acquisition_report,
)

__all__ = [
    "AcquiredDocument",
    "CollectionBatch",
    "DiscoveryRefused",
    "discover",
    "discovery_report",
    "detect_language",
    "detection_report",
    "reconcile",
    "extract_metadata",
    "metadata_report",
    "boundary_report",
    "cross_boundary",
    "extract_text",
    "compare",
    "dedup_report",
    "find_duplicates",
    "similarity",
    "evaluate",
    "quality_report",
    "FetchRefused",
    "FetchResult",
    "GateRefused",
    "acquire",
    "fetch",
    "fetch_robots",
    "fetcher_report",
    "gate_report",
    "plan_batch",
    "submit_batch",
    "AcquisitionRefused",
    "AcquisitionStatus",
    "STATUTS_TERMINAUX",
    "TRANSITIONS",
    "acquisition_report",
]
