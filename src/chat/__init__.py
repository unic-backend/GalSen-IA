"""
La couche de réponse finale de la conversation.

Elle se tient entre l'orchestrateur, qui produit des résultats structurés, et
`ChatResponse`, que lit un être humain. Rien d'autre dans la plateforme ne fait
cette transformation — mesuré le 2026-08-23, aucun des 17 agents ne rédige.

Contrat complet → `docs/architecture/chat-final-response.md`.
"""

from .response import (
    ContexteReponse,
    RedacteurConversation,
    ReponseFinale,
    composer_sans_modele,
    construire_invite,
)

__all__ = [
    "ContexteReponse",
    "RedacteurConversation",
    "ReponseFinale",
    "composer_sans_modele",
    "construire_invite",
]
