"""
Indexeur de connaissances pour recherche plein texte rapide.
"""

import logging
import re
from typing import Dict, Set, List
from src.text_normalization import (
    LANGUE_PAR_DEFAUT,
    normalize_token,
    token_variants,
    tokenize,
)
from .types import KnowledgeItem
from .interfaces import KnowledgeIndexer, KnowledgeStore
import threading


# Mots d'une requête, avant normalisation. Même découpage que
# `text_normalization`, appliqué ici pour produire les deux formes.
_MOT_REQUETE = re.compile(r"\w+", re.UNICODE)


class InMemoryKnowledgeIndexer(KnowledgeIndexer):
    """Indexeur en mémoire utilisant un index inversé simple."""

    # Nombre maximal de documents lus lors d'une reconstruction complète.
    # La limite existait déjà, dispersée et muette : au-delà, les documents
    # excédentaires n'étaient jamais indexés et devenaient introuvables sans
    # qu'aucun signal ne l'indique. Elle est désormais nommée, partagée avec la
    # vérification d'intégrité, et son atteinte est rapportée.
    MAX_INDEXABLE_DOCUMENTS = 100000

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

    # Mots vides écartés de l'index. Écrits avec leurs accents : ils sont
    # normalisés comme le reste, donc « où » et « ou » se rejoignent.
    STOP_WORDS = frozenset({
        'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'à', 'a',
        'ce', 'cet', 'cette', 'ces', 'en', 'au', 'aux', 'avec', 'sans', 'sur',
        'sous', 'pour', 'par', 'pas', 'mais', 'où', 'qui', 'que',
        'quoi', 'dont', 'lorsque', 'quand', 'comment', 'pourquoi',
    })

    def _tokenize(self, text: str, language: str = LANGUE_PAR_DEFAUT) -> List[str]:
        """
        Découpe un texte en mots comparables, selon la langue du document.

        La normalisation s'applique **des deux côtés** — indexation et requête —
        et c'est ce qui la rend sûre : « pluviometrie » retrouve
        « pluviométrie », « arachide » retrouve « arachides ».

        Depuis L3 (VOLET 36, ch. B), la règle du pluriel `-s` ne s'applique
        qu'aux langues qui la connaissent : un texte wolof n'est plus amputé.
        La symétrie est tenue par `_query_terms`, qui interroge l'index avec les
        deux formes — sans quoi une requête française manquerait un terme wolof
        indexé entier.
        """
        return tokenize(text, self.STOP_WORDS, language=language)

    @staticmethod
    def _langue_de(knowledge: KnowledgeItem) -> str:
        """Retourne le code de langue déclaré d'une connaissance."""
        langue = getattr(knowledge, "language", None)
        return str(getattr(langue, "value", langue) or LANGUE_PAR_DEFAUT)

    def _query_terms(self, query: str) -> List[List[str]]:
        """
        Rend, pour chaque mot de la requête, ses formes possibles.

        Une requête n'a pas de langue déclarée et rien ne sait l'inférer
        (VOLET 36, ch. B) : chercher les deux formes ajoute des correspondances
        et n'en retire aucune.
        """
        vides = {normalize_token(mot) for mot in self.STOP_WORDS}
        groupes = []
        for mot in _MOT_REQUETE.findall(query):
            formes = [forme for forme in token_variants(mot)
                      if forme not in vides and len(forme) > 1]
            if formes:
                groupes.append(formes)
        return groupes

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
            documents = self._store.list_items(limit=self.MAX_INDEXABLE_DOCUMENTS)
            for knowledge in documents:
                text = knowledge.content
                terms = self._tokenize(text, self._langue_de(knowledge))
                self._add_to_index(knowledge.id, terms)
            if len(documents) >= self.MAX_INDEXABLE_DOCUMENTS:
                # Au-delà, la recherche est incomplète : le taire reviendrait à
                # rendre « aucun résultat » pour des documents bien présents.
                logging.getLogger(__name__).warning(
                    "Index tronqué à %d documents : le magasin en contient davantage, "
                    "les suivants sont introuvables par la recherche.",
                    self.MAX_INDEXABLE_DOCUMENTS,
                )

    def add(self, knowledge: KnowledgeItem) -> None:
        """Ajoute une connaissance à l'index."""
        with self._lock:
            doc_id = knowledge.id
            # Si déjà présent, retirer d'abord
            if doc_id in self._doc_terms:
                self._remove_from_index(doc_id)
            terms = self._tokenize(knowledge.content, self._langue_de(knowledge))
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
            query_groups = self._query_terms(query)
            if not query_groups:
                return []
            query_terms = [formes[0] for formes in query_groups]

            # Pour chaque terme, obtenir l'ensemble des documents contenant ce terme
            result_sets: List[set] = []
            for formes in query_groups:
                trouves = {doc for forme in formes for doc in self._index.get(forme, set())}
                if trouves:
                    result_sets.append(trouves)
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
                common = len([formes for formes in query_groups
                              if any(forme in doc_terms for forme in formes)])
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
            documents = {k.id: k for k in self._store.list_items(limit=self.MAX_INDEXABLE_DOCUMENTS)}
            tronque = self._store.count() > self.MAX_INDEXABLE_DOCUMENTS
            indexes = set(self._doc_terms)

            manquants = sorted(set(documents) - indexes)
            orphelins = sorted(indexes - set(documents))

            perimes = []
            for doc_id in sorted(indexes & set(documents)):
                attendu = set(self._tokenize(documents[doc_id].content,
                                             self._langue_de(documents[doc_id])))
                if attendu != self._doc_terms.get(doc_id, set()):
                    perimes.append(doc_id)

            return {
                "consistent": not (manquants or orphelins or perimes or tronque),
                "truncated": tronque,
                "indexed_documents": len(indexes),
                "stored_documents": self._store.count(),
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