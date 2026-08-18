"""
Adaptateurs vers les moteurs d'ingénierie logicielle externes (ADR-028).

Un adaptateur par moteur, et rien d'autre : la traduction entre le contrat
`CodingEngineAdapter` de GalSen IA et la façon dont un programme extérieur veut
être appelé. Aucun code de ces projets n'est recopié ici ; les licences et la
position de chacun sont dans `third_party/`.
"""

from src.coding_engine.adapters.aider_adapter import AiderAdapter
from src.coding_engine.adapters.openhands_adapter import OpenHandsAdapter
from src.coding_engine.adapters.swe_agent_adapter import SweAgentAdapter

__all__ = ["AiderAdapter", "OpenHandsAdapter", "SweAgentAdapter"]
