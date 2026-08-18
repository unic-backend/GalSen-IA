"""
Darra J — la couche d'intelligence éducative de GalSen IA.

Le curriculum officiel est une **source institutionnelle de vérité**. GalSen IA
ne le définit pas, le modèle non plus : la plateforme le reçoit, le versionne,
le retrouve et l'explique — sans jamais le réécrire.

Tant qu'aucune autorité n'a fourni de données : **ARCHITECTURE READY —
OFFICIAL CURRICULUM DATA PENDING**. Et `UNKNOWN` vaut mieux qu'une réponse
fausse.
"""

from .canonical import (
    ETATS_CANONIQUES,
    MARQUE_TEST,
    TRANSITIONS,
    CanonicalRefused,
    CurriculumStatus,
    CurriculumUnit,
    CurriculumVersion,
    EducationSystem,
    Grade,
    Period,
    Provenance,
    Subject,
    canonical_report,
    make_provenance,
    may_transition,
    fixture_provenance,
)

__all__ = [
    "CanonicalRefused",
    "CurriculumStatus",
    "CurriculumUnit",
    "CurriculumVersion",
    "ETATS_CANONIQUES",
    "EducationSystem",
    "Grade",
    "MARQUE_TEST",
    "Period",
    "Provenance",
    "Subject",
    "TRANSITIONS",
    "canonical_report",
    "make_provenance",
    "may_transition",
    "fixture_provenance",
]
