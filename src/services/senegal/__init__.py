"""
La connaissance sénégalaise, servie au RAG existant.

Ce paquet est l'adaptateur entre la connaissance construite
(`data/processed_senegal/senegal_master_knowledge.json`) et la chaîne de
récupération déjà en place. Il ne contient ni index, ni base vectorielle, ni
seconde architecture : lecture, requêtes déterministes, provenance.

`system_prompt_senegal.txt` y vit aussi : c'est le contrat que la génération
doit tenir sur un pays réel — citer, distinguer le fait de l'interprétation, et
rendre `UNKNOWN` plutôt que combler.

**Emplacement** : la directive nommait `services/` à la racine. Le dépôt a déjà
`src/services/`, et un test d'architecture interdit qu'un paquet `services`
résolve en import nu. Le module vit donc sous le paquet existant, comme le
wolof avant lui.
"""

from .discrepancy import compare_department_count, compare_regions, discrepancy_report
from .master_rag import (
    KnowledgeUnavailable,
    get_wolof_corpus,
    iterate_chunks,
    knowledge_report,
    load_all_knowledge,
    load_domain_knowledge,
    query_by_region,
    query_by_sector,
    retrieve_context,
)

__all__ = [
    "KnowledgeUnavailable",
    "compare_department_count",
    "compare_regions",
    "discrepancy_report",
    "load_domain_knowledge",
    "get_wolof_corpus",
    "iterate_chunks",
    "knowledge_report",
    "load_all_knowledge",
    "query_by_region",
    "query_by_sector",
    "retrieve_context",
]
