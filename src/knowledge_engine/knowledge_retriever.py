"""
Récupérateur de connaissances pour le moteur de connaissances GalSen IA.
"""

from typing import List, Tuple, Optional
from .types import KnowledgeItem
from .interfaces import KnowledgeRetriever, KnowledgeIndexer


class KnowledgeRetrieverImpl(KnowledgeRetriever):
    """Implémentation du récupérateur de connaissances utilisant un indexeur."""

    def __init__(self, indexer: KnowledgeIndexer):
        """
        Initialise le récupérateur.

        Args:
            indexer: Indexeur de connaissances à utiliser pour la recherche
        """
        self._indexer = indexer

    def retrieve_relevant(self, query: str, knowledge_items: List[KnowledgeItem],
                          limit: int = 5) -> List[tuple[KnowledgeItem, float]]:
        """
        Récupère les connaissances les plus pertinentes pour une requête.
        Note: Le paramètre knowledge_items est ignoré car nous utilisons l'indexeur directement.
        Pour une utilisation avancée, on pourrait filtrer par les éléments fournis.

        Args:
            query: Requête de recherche
            knowledge_items: Liste de connaissances à considérer (non utilisée dans cette implémentation)
            limit: Nombre maximum de résultats

        Returns:
            Liste de tuples (connaissance, score de pertinence)
        """
        # Utiliser l'indexeur pour la recherche
        results = self._indexer.search(query, limit=limit)
        # L'indexeur retourne déjà des tuples (KnowledgeItem, float)
        return results

    def retrieve_by_ids(self, knowledge_ids: List[str],
                        store) -> List[KnowledgeItem]:
        """
        Récupère des connaissances par leurs IDs depuis un magasin.

        Args:
            knowledge_ids: Liste des IDs à récupérer
            store: Instance de KnowledgeStore pour récupérer les connaissances

        Returns:
            Liste des connaissances trouvées (dans l'ordre des IDs demandés)
        """
        results = []
        for kid in knowledge_ids:
            item = store.get(kid)
            if item:
                results.append(item)
        return results