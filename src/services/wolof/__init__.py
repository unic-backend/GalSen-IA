"""
Le corpus wolof, servi au RAG existant.

Ce paquet est l'adaptateur entre le corpus traité
(`data/processed_wolof/official_wolof_corpus.json`) et la chaîne de récupération
déjà en place. Il ne contient ni index, ni base vectorielle, ni seconde
architecture de RAG : uniquement la lecture, le découpage et la provenance.

`system_prompt.txt` y vit aussi : c'est le contrat orthographique que la
génération doit tenir en wolof.

**Emplacement** : la directive nommait `services/` à la racine. Le dépôt a déjà
`src/services/`, et un test d'architecture (`test_import_convention.py`) interdit
qu'un paquet `services` résolve en import nu — deux chemins vers un même nom
cassent `isinstance`. Le module vit donc ici, sous le paquet existant.
"""

from .rag_loader import (
    CORPUS,
    CorpusUnavailable,
    chunk_text,
    corpus_report,
    get_metadata,
    iterate_chunks,
    iterate_documents,
    load_corpus,
)

__all__ = [
    "CORPUS",
    "CorpusUnavailable",
    "chunk_text",
    "corpus_report",
    "get_metadata",
    "iterate_chunks",
    "iterate_documents",
    "load_corpus",
]
