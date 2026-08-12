"""
Indexeur de documents en mémoire pour le moteur d'intelligence documentaire GalSen IA.
"""

import re
from typing import List
from .interfaces import DocumentIndexer
from .types import DocumentItem
from collections import defaultdict
import math


class InMemoryIndexer(DocumentIndexer):
    """Indexeur en mémoire simple basé sur un index inversé."""

    def __init__(self):
        """Initialise l'indexeur."""
        # Index inversé : terme -> dict document_id -> fréquence
        self._inverted_index: dict[str, dict[str, int]] = defaultdict(dict)
        # Stockage des documents pour récupérer le contenu
        self._documents: dict[str, DocumentItem] = {}
        # Statistiques des documents pour le scoring BM25-like
        self._doc_lengths: dict[str, int] = {}
        self._avg_doc_length: float = 0.0
        self._total_terms: int = 0

    def _tokenize(self, text: str) -> List[str]:
        """Tokenise un texte en termes (mots en minuscules, sans ponctuation)."""
        # Convertir en minuscules et séparer par des non-mots
        words = re.findall(r'\b\w+\b', text.lower())
        return words

    def index(self, document: DocumentItem) -> None:
        """
        Indexe un document pour la recherche.

        Args:
            document: Document à indexer
        """
        # Supprimer l'index existant si le document était déjà indexé
        if document.document_id in self._documents:
            self.delete(document.document_id)

        # Stocker le document
        self._documents[document.document_id] = document

        # Tokeniser le contenu
        tokens = self._tokenize(document.content)
        term_freq = {}
        for token in tokens:
            term_freq[token] = term_freq.get(token, 0) + 1

        # Mettre à jour l'index inversé et les statistiques
        doc_length = len(tokens)
        self._doc_lengths[document.document_id] = doc_length
        self._total_terms += doc_length

        # Recalculer la longueur moyenne du document
        self._avg_doc_length = self._total_terms / len(self._documents) if self._documents else 0.0

        # Mettre à jour l'index inversé
        for term, freq in term_freq.items():
            self._inverted_index[term][document.document_id] = freq

    def search(self, query: str, limit: int = 10) -> List[tuple[DocumentItem, float]]:
        """
        Recherche des documents correspondant à la requête.

        Args:
            query: Chaîne de recherche
            limit: Nombre maximum de résultats à retourner

        Returns:
            Liste de tuples (document, score) triée par score décroissant
        """
        if not query.strip() or not self._documents:
            return []

        # Tokeniser la requête
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # Calculer les scores pour chaque document
        scores = self._compute_scores(query_terms)

        # Trier par score décroissant et prendre les top 'limit'
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

        # Construire la liste de résultats
        results = []
        for doc_id, score in sorted_results:
            if doc_id in self._documents:
                results.append((self._documents[doc_id], score))

        return results

    def _compute_scores(self, query_terms: List[str]) -> dict[str, float]:
        """
        Calcule les scores de pertinence pour les documents donnés les termes de la requête.

        Utilise une variante de BM25 simplifiée.

        Args:
            query_terms: Liste des termes de la requête

        Returns:
            Dictionnaire document_id -> score
        """
        scores = {}
        k1 = 1.2  # Paramètre de saturation de fréquence de terme
        b = 0.75  # Paramètre de normalisation de longueur

        for term in query_terms:
            if term not in self._inverted_index:
                continue

            # Fréquence documentaire inversée (IDF)
            n_i = len(self._inverted_index[term])  # Nombre de documents contenant le terme
            N = len(self._documents)  # Nombre total de documents
            # Éviter la division par zéro
            if n_i == 0:
                continue
            idf = math.log((N - n_i + 0.5) / (n_i + 0.5) + 1.0)  # BM25 IDF

            # Pour chaque document contenant le terme
            for doc_id, tf in self._inverted_index[term].items():
                doc_len = self._doc_lengths.get(doc_id, 0)
                if doc_len == 0:
                    continue

                # Calcul du facteur de fréquence de terme (TF)
                denom = tf + k1 * (1 - b + b * (doc_len / self._avg_doc_length))
                if denom == 0:
                    continue
                tf_factor = ((k1 + 1) * tf) / denom

                # Accumuler le score
                score_contribution = idf * tf_factor
                scores[doc_id] = scores.get(doc_id, 0.0) + score_contribution

        return scores

    def delete(self, document_id: str) -> bool:
        """
        Supprime l'index d'un document.

        Args:
            document_id: ID du document à supprimer de l'index

        Returns:
            True si le document était dans l'index et a été supprimé, False sinon
        """
        if document_id not in self._documents:
            return False

        # Supprimer de l'index inversé
        # Pour cela, nous devons savoir quels termes étaient dans ce document
        # Nous n'avons pas stocké cela directement, donc nous devons le recalculer
        document = self._documents[document_id]
        tokens = self._tokenize(document.content)
        unique_terms = set(tokens)

        # Supprimer le document de l'index pour chaque terme
        for term in unique_terms:
            if document_id in self._inverted_index[term]:
                del self._inverted_index[term][document_id]
                # Supprimer l'entrée du terme si elle est vide
                if not self._inverted_index[term]:
                    del self._inverted_index[term]

        # Mettre à jour les statistiques
        doc_len = self._doc_lengths.get(document_id, 0)
        if doc_len > 0:
            self._total_terms -= doc_len
            del self._doc_lengths[document_id]

        # Supprimer le document
        del self._documents[document_id]

        # Recalculer la longueur moyenne du document
        self._avg_doc_length = self._total_terms / len(self._documents) if self._documents else 0.0

        return True

    def clear(self) -> None:
        """Vide l'index complet."""
        self._inverted_index.clear()
        self._documents.clear()
        self._doc_lengths.clear()
        self._total_terms = 0
        self._avg_doc_length = 0.0