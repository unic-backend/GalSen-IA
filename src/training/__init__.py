"""
Ce qu'il faut avoir avant d'entraîner SamP et ToP (VOLET 33 — ADR-014).

Conception complète → `docs/architecture/training-infrastructure.md`.

Le brief demandait de l'entraînement distribué, DeepSpeed, du RLHF. La mesure a
renversé l'ordre : en QLoRA, un modèle de 7 à 8 milliards de paramètres tient sur
un seul GPU de 24 Go, et n'a besoin d'**aucune** distribution. Les vrais
obstacles, dans l'ordre, sont :

1. **il n'y a pas de données** ;
2. **il n'y a aucun moyen de dire si un entraînement a aidé** ;
3. **le signal n'est pas capturé** — et c'est le seul des trois dont le coût
   augmente chaque jour qui passe, parce qu'une correction d'utilisateur non
   enregistrée est perdue pour toujours.

Ce paquet traite ces trois-là. La recette d'entraînement, elle, vit dans
`scripts/training/` : c'est du code qui a besoin d'un GPU, et il n'a pas sa place
dans une image de production.
"""

from .feedback import (
    Feedback,
    FeedbackKind,
    FeedbackStore,
    SQLiteFeedbackStore,
    shared_feedback_store,
)

__all__ = [
    "Feedback",
    "FeedbackKind",
    "FeedbackStore",
    "SQLiteFeedbackStore",
    "shared_feedback_store",
]
