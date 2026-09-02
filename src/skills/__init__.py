"""
La bibliothèque de compétences : ce qui a servi, rangé pour resservir.

Idée reprise du dépôt Odyssey (`zju-vipa/Odyssey`, MIT, © 2023 MineDojo Team),
bâti sur Voyager. **Aucune ligne n'en est copiée** — son implémentation repose
sur `langchain`, `Chroma` et les embeddings d'OpenAI, que trois ADR de cette
plateforme écartent. Le substrat utilisé ici est celui du dépôt.

Détail et raisons → `src/skills/library.py`.
"""

from .library import (
    COLLECTION,
    BibliothequeCompetences,
    Competence,
    CompetenceRefusee,
)

__all__ = [
    "COLLECTION",
    "BibliothequeCompetences",
    "Competence",
    "CompetenceRefusee",
]
