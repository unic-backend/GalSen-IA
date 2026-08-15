"""
Système de greffons : ce qu'un tiers déclare, et ce qui le borne.

Un greffon est du code que ce dépôt n'a pas écrit. Toute l'architecture découle
de ce fait : il **déclare** ce qu'il demande (`manifest.py`), il est inscrit
**désactivé** et activé par une décision humaine tracée (`registry.py`), et il
s'exécute dans le bac à sable existant du VOLET 34 — jamais dans un second écrit
pour l'occasion, que personne n'aurait essayé de franchir (`execution.py`).
"""

from .execution import (
    POLITIQUE_GREFFON,
    PluginExecutionRefused,
    execution_report,
    may_run,
    run_plugin,
)
from .manifest import (
    ManifestRefused,
    PluginManifest,
    forbidden_combination,
    manifest_report,
    read_manifest,
)
from .registry import PluginRefused, PluginRegistry

__all__ = [
    "POLITIQUE_GREFFON",
    "ManifestRefused",
    "PluginExecutionRefused",
    "PluginManifest",
    "PluginRefused",
    "PluginRegistry",
    "execution_report",
    "forbidden_combination",
    "manifest_report",
    "may_run",
    "read_manifest",
    "run_plugin",
]
