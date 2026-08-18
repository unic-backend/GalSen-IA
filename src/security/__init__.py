"""
Le modèle de sécurité, mesuré et rassemblé (VOLET 34, ch. 13).

Les protections existent depuis longtemps — RBAC, propriété par sujet,
portillon, audit, racines déclarées, bac à sable, liste blanche MCP — mais elles
vivaient dans six modules et cinq ADR. Ce paquet ne les réimplémente pas : il
les **lit**, et rend ce qu'elles garantissent réellement, failles comprises.

- `posture()` — ce que la plateforme peut faire à cette machine, maintenant.
- `list_checkpoints()` — ce qu'on peut encore défaire, et ce qu'on ne peut pas.
"""

# `list_checkpoints` plutôt que `checkpoints` : réexporter une fonction sous le
# nom de son module masque le module lui-même, et `import
# src.security.checkpoints` rendait alors la fonction.
from .checkpoints import list_checkpoints, undo
from .posture import posture, summary

__all__ = ["list_checkpoints", "posture", "summary", "undo"]
