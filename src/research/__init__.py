"""
La couche d'orchestration de recherche (directive Research Orchestration).

Agent-Reach et web-search-mcp sont des **fournisseurs**. GalSen IA garde
l'intention, la planification, le choix des sources, le routage, la validation,
la provenance, la confiance, l'intégration à la connaissance, la sécurité, les
permissions, la mémoire et le raisonnement final.

| Module | Ce qu'il porte |
|---|---|
| `providers.py` | la déclaration d'un fournisseur de recherche, et sa santé |

Ce qui n'est **pas** ici, parce que cela existe déjà : la provenance
(`acquisition/`, `creative/jobs.py`), l'échelle de statut de connaissance
(`OBSERVED → CANDIDATE → CORROBORATED`), la frontière de confiance
(`security/trust.py`), les caches, les citations, la fraîcheur, les
contradictions, l'authentification, le RBAC et la limitation de débit.
"""
