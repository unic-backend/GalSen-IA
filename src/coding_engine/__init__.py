"""
Coding Engine : la capacité d'ingénierie logicielle de GalSen IA (ADR-028).

Trois moteurs externes travaillent derrière une interface qui appartient à la
plateforme :

| Moteur     | Licence    | Forme de l'intégration | Ce qu'il fait le mieux |
|------------|------------|------------------------|------------------------|
| Aider      | Apache-2.0 | sous-processus (CLI)   | modification ciblée    |
| SWE-agent  | MIT        | sous-processus (CLI)   | résolution de problème |
| OpenHands  | MIT        | HTTP (serveur d'agent) | implémentation complète|

Aucun code de ces projets n'est recopié dans ce dépôt, et aucun n'est une
dépendance : GalSen IA fonctionne sans eux, un moteur absent est rapporté avec
son motif, et les autres continuent.

Claude, Anthropic et Claude Code **ne font pas partie** de ce moteur ni d'aucun
autre. Le modèle vient du Model Engine, quel que soit le fournisseur configuré.
"""

from src.coding_engine.interfaces import CodingEngineAdapter
from src.coding_engine.manager import CodingEngineManager
from src.coding_engine.router import CodingRouter, RoutingDecision, infer_capabilities
from src.coding_engine.types import (
    CodingCapability,
    CodingStatus,
    CodingTask,
    CodingTaskResult,
    EngineAvailability,
    FileChange,
    ModelSpec,
    TestReport,
    UnavailabilityReason,
)

__all__ = [
    "CodingCapability",
    "CodingEngineAdapter",
    "CodingEngineManager",
    "CodingRouter",
    "CodingStatus",
    "CodingTask",
    "CodingTaskResult",
    "EngineAvailability",
    "FileChange",
    "ModelSpec",
    "RoutingDecision",
    "TestReport",
    "UnavailabilityReason",
    "infer_capabilities",
]
