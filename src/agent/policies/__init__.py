"""
Ce qu'une réparation automatique n'a pas le droit de faire.

Deux politiques, et elles ne se recouvrent pas : l'**immuabilité** dit quels
fichiers restent hors de portée, l'**intégrité** dit ce qu'un correctif n'a pas
le droit d'avoir fait aux tests. La première se juge avant, la seconde après.
"""

from .immutability import (
    FRONTIERE,
    HARNAIS,
    MAINTENANCE_SECURITE,
    REPARATION_ORDINAIRE,
    SECRETS,
    TESTS_PROTEGES,
    ImmutabilityRefused,
    check_patch_scope,
    classify,
    may_modify,
    protected_paths,
)
from .integrity import (
    compare_inventories,
    compare_protected_hashes,
    protected_test_hashes,
    inventory,
)

__all__ = [
    "FRONTIERE",
    "HARNAIS",
    "ImmutabilityRefused",
    "MAINTENANCE_SECURITE",
    "REPARATION_ORDINAIRE",
    "SECRETS",
    "TESTS_PROTEGES",
    "check_patch_scope",
    "classify",
    "compare_inventories",
    "compare_protected_hashes",
    "may_modify",
    "protected_paths",
    "protected_test_hashes",
    "inventory",
]
