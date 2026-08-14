"""
Le wolof : autorité orthographique et outils de traitement.

Ce paquet porte le standard orthographique du wolof — l'alphabet de 27 lettres
arrêté par le décret n° 2005-992 et porté par le CLAD (Université Cheikh Anta
Diop) — et la normalisation déterministe qui s'y conforme.

Il ne duplique aucune architecture existante : la normalisation d'indexation
reste dans `src/text_normalization.py`, la détection de langue dans
`src/acquisition/language.py`, la récupération dans le moteur de connaissances.
Ce qui vit ici est ce qu'aucun de ces modules ne pouvait porter — **comment le
wolof s'écrit**, et le refus d'y appliquer des règles françaises.

Le corpus de travail (UD_Wolof-WTB) est une ressource distincte du standard :
`scripts/ingest_wolof.py` l'acquiert, `services/wolof_rag_loader.py` le sert.
"""

from .clad import (
    ALPHABET,
    LETTRES_PROPRES,
    STANDARD,
    VERSION,
    alphabet_report,
    is_in_alphabet,
    letters_outside_alphabet,
    normalize,
    normalize_text,
    suspected_miscodings,
)

__all__ = [
    "ALPHABET",
    "LETTRES_PROPRES",
    "STANDARD",
    "VERSION",
    "alphabet_report",
    "is_in_alphabet",
    "letters_outside_alphabet",
    "normalize",
    "normalize_text",
    "suspected_miscodings",
]
