"""
Bac à sable d'exécution (VOLET 34, ch. 08).

ADR-017 §5 : aucune capacité d'exécution ne livre sans son test d'évasion. Ce que
ce bac à sable garantit et ce qu'il ne garantit pas est déclaré dans
`policy.NON_GARANTI` et rapporté par `describe()`.
"""

from .policy import ENVIRONNEMENT_TRANSMIS, NON_GARANTI, SandboxPolicy, SandboxResult
from .runner import SandboxUnavailable, describe, run, run_python, unavailable_reason

__all__ = [
    "ENVIRONNEMENT_TRANSMIS",
    "NON_GARANTI",
    "SandboxPolicy",
    "SandboxResult",
    "SandboxUnavailable",
    "describe",
    "run",
    "run_python",
    "unavailable_reason",
]
