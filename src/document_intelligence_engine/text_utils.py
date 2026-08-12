"""
Utilitaires de traitement de texte partagés par les composants du moteur
d'intelligence documentaire GalSen IA.

Ce module centralise la tokenisation, le découpage en phrases et la liste des
mots vides afin que le résumé, les questions-réponses, la comparaison et la
détection de doublons se basent tous sur la même définition d'un « mot ».
"""

import re
from typing import List, Set

# Mots vides français et anglais : ils sont trop fréquents pour porter du sens
# et fausseraient les scores de pertinence.
STOP_WORDS: Set[str] = frozenset({
    # Français
    "au", "aux", "avec", "ce", "ces", "dans", "de", "des", "du", "elle", "en",
    "et", "eux", "il", "ils", "je", "la", "le", "les", "leur", "lui", "ma",
    "mais", "me", "meme", "mes", "moi", "mon", "ne", "nos", "notre", "nous",
    "on", "ou", "par", "pas", "pour", "qu", "que", "qui", "sa", "se", "ses",
    "son", "sur", "ta", "te", "tes", "toi", "ton", "tu", "un", "une", "vos",
    "votre", "vous", "est", "sont", "etre", "avoir", "cette", "plus", "comme",
    # Anglais
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "has", "have", "he", "her", "his", "i", "in", "is", "it", "its",
    "of", "or", "she", "that", "the", "their", "them", "there", "these",
    "they", "this", "to", "was", "were", "will", "with", "you", "your",
})

# Une phrase se termine par une ponctuation forte suivie d'un espace
_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?])\s+')

# Un mot est une suite de caractères alphanumériques (accents compris)
_WORD_PATTERN = re.compile(r'\b\w+\b', re.UNICODE)


def tokenize(text: str) -> List[str]:
    """
    Découpe un texte en mots normalisés en minuscules.

    Args:
        text: Texte à découper

    Returns:
        Liste des mots trouvés, dans l'ordre d'apparition
    """
    return _WORD_PATTERN.findall(text.lower())


def significant_words(text: str) -> Set[str]:
    """
    Retourne l'ensemble des mots porteurs de sens d'un texte (mots vides exclus).

    Args:
        text: Texte à analyser

    Returns:
        Ensemble des mots significatifs en minuscules
    """
    return {word for word in tokenize(text) if word not in STOP_WORDS}


def split_sentences(text: str) -> List[str]:
    """
    Découpe un texte en phrases.

    Args:
        text: Texte à découper

    Returns:
        Liste des phrases non vides, dans l'ordre d'apparition
    """
    return [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(text) if sentence.strip()]


def jaccard_similarity(text1: str, text2: str) -> float:
    """
    Calcule la similarité de Jaccard entre deux textes, basée sur leurs mots.

    Args:
        text1: Premier texte
        text2: Second texte

    Returns:
        Score entre 0.0 (aucun mot commun) et 1.0 (mêmes mots).
        Deux textes vides sont considérés identiques.
    """
    words1 = set(tokenize(text1))
    words2 = set(tokenize(text2))

    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0

    union = words1 | words2
    return len(words1 & words2) / len(union)
