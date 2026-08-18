"""
Observabilité de bout en bout : suivre un travail à travers ce qu'il a traversé.

Chaque sous-système consignait déjà ce qu'il faisait ; aucun ne savait répondre
à la question posée à trois heures du matin — *qu'est-il arrivé à ce travail-là ?*
"""

from .trail import (
    ILLISIBLE,
    RIEN,
    TROUVE,
    audit_fragment,
    checkpoint_fragment,
    observability_report,
    routine_fragment,
    trail,
)

__all__ = [
    "ILLISIBLE",
    "RIEN",
    "TROUVE",
    "audit_fragment",
    "checkpoint_fragment",
    "observability_report",
    "routine_fragment",
    "trail",
]
