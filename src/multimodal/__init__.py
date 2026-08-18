"""
Entrées non textuelles de GalSen IA — parole et image (VOLET 32).

La plateforme lit des documents depuis longtemps. Elle n'entend rien : aucun
chemin audio n'existe dans `src/`, et le moteur de vision — 1 845 lignes,
OpenCV et Pillow — n'est relié à aucune ingestion. Une photo de parcelle ou un
message vocal en wolof ne peut donc entrer nulle part, alors que ce sont deux
des façons les plus naturelles de s'adresser à cette plateforme dans son pays.

La forme suit celle des embeddings (ADR-015), et pour les mêmes raisons :

- **une interface**, des fournisseurs, un registre ;
- **local uniquement** (ADR-014) : envoyer la voix d'un utilisateur chez un
  tiers serait un export bien plus intime qu'une invite de texte ;
- **une capacité absente rapporte son état**, elle ne rend jamais un résultat
  plausible — une transcription inventée serait mise dans la bouche de
  quelqu'un.
"""

from .interfaces import (
    TranscriptionProvider,
    TranscriptionProviderInfo,
    TranscriptionResult,
    TranscriptionUnavailable,
)
from .registry import active_transcriber, reset_transcriber, set_transcriber, transcription_status

__all__ = [
    "TranscriptionProvider",
    "TranscriptionProviderInfo",
    "TranscriptionResult",
    "TranscriptionUnavailable",
    "active_transcriber",
    "reset_transcriber",
    "set_transcriber",
    "transcription_status",
]
