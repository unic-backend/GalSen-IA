"""
Système de greffons : ce qu'un tiers déclare, et ce qui le borne.

Un greffon est du code que ce dépôt n'a pas écrit. Toute l'architecture découle
de ce fait : il **déclare** ce qu'il demande (`manifest.py`), il est inscrit
**désactivé** et activé par une décision humaine tracée (`registry.py`), et il
s'exécute dans le bac à sable existant du VOLET 34 — jamais dans un second écrit
pour l'occasion, que personne n'aurait essayé de franchir (`execution.py`).
"""

from .contract import (
    VERSION_DU_CONTRAT,
    plugin_contract,
    refusal_rules,
)
from .execution import (
    POLITIQUE_GREFFON,
    PluginExecutionRefused,
    execution_report,
    may_run,
    run_installed,
    run_plugin,
)
from .manifest import (
    ManifestRefused,
    PluginManifest,
    forbidden_combination,
    manifest_report,
    read_manifest,
)
from .registry import (
    PluginRefused,
    PluginRegistry,
    discover,
    install_from_directory,
    read_plugin_directory,
)

__all__ = [
    "POLITIQUE_GREFFON",
    "VERSION_DU_CONTRAT",
    "ManifestRefused",
    "PluginExecutionRefused",
    "PluginManifest",
    "PluginRefused",
    "PluginRegistry",
    "execution_report",
    "forbidden_combination",
    "manifest_report",
    "plugin_contract",
    "refusal_rules",
    "may_run",
    "discover",
    "install_from_directory",
    "read_manifest",
    "read_plugin_directory",
    "run_installed",
    "run_plugin",
]
