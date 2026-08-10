"""
Indexeur de connaissances pour recherche plein texte rapide.
"""

import re
from typing import Dict, Set, List, Optional
from .types import KnowledgeItem
from .interfaces import KnowledgeIndexer, KnowledgeStore
import threading


class InMemoryKnowledgeIndexer(KnowledgeIndexer):
    """Indexeur en mémoire utilisant un index inversé simple."""

    def __init__(self, store: KnowledgeStore):
        """
        Initialise l'indexeur.

        Args:
            store: Le stockage de connaissances à indexer (en mémoire ou SQLite)
        """
        self._store = store
        # index: terme -> ensemble d'IDs de documents contenant le terme
        self._index: Dict[str, Set[str]] = {}
        # mapping document ID -> ensemble de termes (pour mise à jour efficace)
        self._doc_terms: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()

        # Tokenizer: séquences de lettres et chiffres (y compris accentués?)
        self._word_re = re.compile(r'\w+', re.UNICODE)

        # Construire l'index initial à partir du store existant
        self._rebuild_index()

    def add_to_index(self, knowledge: KnowledgeItem) -> None:
        """Ajoute une connaissance à l'index."""
        self.add(knowledge)

    def remove_from_index(self, knowledge_id: str) -> None:
        """Retire une connaissance de l'index."""
        self.delete(knowledge_id)

    def update_index(self, knowledge: KnowledgeItem) -> None:
        """Met à jour l'index pour une connaissance modifiée."""
        self.update(knowledge)

    def _tokenize(self, text: str) -> List[str]:
        """Tokenise un texte en mots en minuscules."""
        words = self._word_re.findall(text.lower())
        # Filtrer les mots très courants (stop words simples) - optionnel
        stop_words = {'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'à', 'a',
                      'ce', 'cet', 'cette', 'ces', 'en', 'au', 'aux', 'avec', 'sans', 'sur',
                      'sous', 'pour', 'par', 'pas', 'mais', 'ou', 'où', 'qui', 'que',
                      'quoi', 'dont', 'où', 'lorsque', 'quand', 'comment', 'pourquoi'}
        return [w for w in words if w not in stop_words and len(w) > 1]

    def _add_to_index(self, doc_id: str, terms: List[str]) -> None:
        """Ajoute un document à l'index pour les termes donnés."""
        term_set = set(terms)
        self._doc_terms[doc_id] = term_set
        for term in term_set:
            if term not in self._index:
                self._index[term] = set()
            self._index[term].add(doc_id)

    def _remove_from_index(self, doc_id: str) -> None:
        """Supprime un document de l'index."""
        if doc_id in self._doc_terms:
            for term in self._doc_terms[doc_id]:
                if term in self._index:
                    self._index[term].discard(doc_id)
                    if not self._index[term]:
                        del self._index[term]
            del self._doc_terms[doc_id]

    def _rebuild_index(self) -> None:
        """Reconstruit entièrement l'index à partir du stockage."""
        with self._lock:
            self._index.clear()
            self._doc_terms.clear()
            # Utilise l'interface publique du stockage pour fonctionner aussi
            # avec un stockage SQLite (ADR-005), pas seulement en mémoire.
            for knowledge in self._store.list_items(limit=10000):
                text = knowledge.content
                terms = self._tokenize(text)
                self._add_to_index(knowledge.id, terms)

    def add(self, knowledge: KnowledgeItem) -> None:
        """Ajoute une connaissance à l'index."""
        with self._lock:
            doc_id = knowledge.id
            # Si déjà présent, retirer d'abord
            if doc_id in self._doc_terms:
                self._remove_from_index(doc_id)
            terms = self._tokenize(knowledge.content)
            self._add_to_index(doc_id, terms)

    def update(self, knowledge: KnowledgeItem) -> None:
        """Met à jour une connaissance dans l'index (équivaut à supprimer puis ajouter)."""
        self.add(knowledge)  # notre add gère déjà la mise à jour

    def delete(self, knowledge_id: str) -> None:
        """Supprime une connaissance de l'index."""
        with self._lock:
            self._remove_from_index(knowledge_id)

    def search(self, query: str, limit: int = 10) -> List[tuple[KnowledgeItem, float]]:
        """
        Recherche des documents correspondant à la requête.
        Retourne une liste de tuples (connaissance, score de pertinence) triée par score décroissant.
        Le score est la proportion de termes de la requête présents dans le document.
        """
        with self._lock:
            query_terms = self._tokenize(query)
            if not query_terms:
                return []

            # Pour chaque terme, obtenir l'ensemble des documents contenant ce terme
            result_sets: List[set] = []
            for term in query_terms:
                if term in self._index:
                    result_sets.append(self._index[term])
                else:
                    # Si un terme n'est pas trouvé, aucun document ne peut contenir tous les termes (AND)
                    # Nous pouvons changer pour OR, mais pour la pertinence nous faisons AND puis scoring
                    # Ici, nous ferons une recherche OR et scorerons par nombre de termes correspondants
                    pass

            # Recherche OR: union des ensembles
            if not result_sets:
                return []
            # Pour une recherche ET (AND), nous intersecrions; pour OR, nous unissons.
            # Nous ferons un scoring basé sur le nombre de termes correspondants.
            # Approche simple: récupérer tous les documents qui contiennent au moins un terme
            candidate_ids: set = set()
            for s in result_sets:
                candidate_ids.update(s)

            # Scorer chaque document par le nombre de termes de la requête présents
            scores: dict[str, int] = {}
            for doc_id in candidate_ids:
                doc_terms = self._doc_terms.get(doc_id, set())
                common = len([t for t in query_terms if t in doc_terms])
                if common > 0:
                    scores[doc_id] = common

            # Normaliser le score par le nombre de termes de la requête pour obtenir une valeur entre 0 et 1
            max_score = len(query_terms)
            if max_score == 0:
                return []
            # Trier par score décroissant
            sorted_items = []
            for doc_id in sorted(scores.keys(), key=lambda x: scores[x], reverse=True):
                knowledge = self._store.get(doc_id)
                if knowledge is not None:
                    normalized_score = scores[doc_id] / max_score
                    sorted_items.append((knowledge, float(normalized_score)))
                if len(sorted_items) >= limit:
                    break
            return sorted_items

    def clear(self) -> None:
        """Efface complètement l'index."""
        with self._lock:
            self._index.clear()
            self._doc_terms.clear()

    def check_integrity(self) -> dict:
        """
        Compare l'index au magasin qu'il indexe (VOLET 14, chapitre 05).

        Le chapitre exige de « vérifier l'intégrité de l'index ». Un index qui
        diverge du magasin ne se voit pas : la recherche rend simplement moins,
        ou pointe vers des documents disparus.

        Returns:
            Un dictionnaire portant `consistent` (booléen), les identifiants
            présents dans le magasin mais absents de l'index (`missing`), ceux
            présents dans l'index sans exister dans le magasin (`orphaned`), et
            les documents dont les termes ne correspondent plus à leur contenu
            (`stale`). Les listes sont bornées : au-delà de 50 identifiants, le
            compte suffit à décider d'une reconstruction.
        """
        with self._lock:
            documents = {k.id: k for k in self._store.list_items(limit=100000)}
            indexes = set(self._doc_terms)

            manquants = sorted(set(documents) - indexes)
            orphelins = sorted(indexes - set(documents))

            perimes = []
            for doc_id in sorted(indexes & set(documents)):
                attendu = set(self._tokenize(documents[doc_id].content))
                if attendu != self._doc_terms.get(doc_id, set()):
                    perimes.append(doc_id)

            return {
                "consistent": not (manquants or orphelins or perimes),
                "indexed_documents": len(indexes),
                "stored_documents": len(documents),
                "missing": manquants[:50],
                "missing_count": len(manquants),
                "orphaned": orphelins[:50],
                "orphaned_count": len(orphelins),
                "stale": perimes[:50],
                "stale_count": len(perimes),
            }

    def get_stats(self) -> dict:
        """Retourne des statistiques sur l'index."""
        with self._lock:
            total_terms = len(self._index)
            total_docs = len(self._doc_terms)
            postings = sum(len(posting) for posting in self._index.values())
            return {
                "unique_terms": total_terms,
                "indexed_documents": total_docs,
                "total_postings": postings,
                "average_postings_per_term": postings / max(1, total_terms)
            }