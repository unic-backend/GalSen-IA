"""
Les primitives d'un agent d'ingénierie : lire, chercher, lancer, versionner.

Chacune est sûre par construction — un chemin passe par `resolve()`, une
commande est une **liste** et jamais une chaîne — et aucune ne décide si une
réparation est permise. Cette décision appartient aux politiques.
"""

from .commands import (
    EXECUTABLES_CONNUS,
    SECONDES_MAXIMUM,
    SORTIE_MAXIMUM,
    CommandRefused,
    CommandResult,
    parse_pytest_counts,
    run_command,
    run_ruff,
    run_test_suite,
)
from .workspace import (
    OCTETS_MAXIMUM,
    WorkspaceRefused,
    file_hash,
    hash_many,
    list_directory,
    read_file,
    relative,
    repo_root,
    resolve,
    search_code,
    write_file,
)

__all__ = [
    "CommandRefused",
    "CommandResult",
    "EXECUTABLES_CONNUS",
    "OCTETS_MAXIMUM",
    "SECONDES_MAXIMUM",
    "SORTIE_MAXIMUM",
    "WorkspaceRefused",
    "file_hash",
    "hash_many",
    "list_directory",
    "parse_pytest_counts",
    "read_file",
    "relative",
    "repo_root",
    "resolve",
    "run_command",
    "run_ruff",
    "run_test_suite",
    "search_code",
    "write_file",
]
