"""
Le journal des actions autonomes.

Une réparation que personne ne peut reconstituer après coup est une réparation
en laquelle personne ne peut avoir confiance.
"""

from .journal import (
    ACTIONS,
    ENTREES_CONSERVEES,
    AuditEntry,
    AuditJournal,
)

__all__ = ["ACTIONS", "ENTREES_CONSERVEES", "AuditEntry", "AuditJournal"]
