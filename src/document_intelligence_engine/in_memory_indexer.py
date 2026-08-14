"""
Indexeur de documents en mémoire pour le moteur d'intelligence documentaire GalSen IA.

## Ce que la phase 54.1 a corrigé, et pourquoi

**Le titre n'était pas indexé.** Un document intitulé « Rapport agricole 2024 »
dont le corps ne répétait pas ces mots était introuvable par son propre titre.
C'est le défaut le plus visible qu'un utilisateur puisse rencontrer : il tape ce
qu'il lit à l'écran, et rien ne sort.

**Les accents empêchaient de trouver.** « senegal » ne trouvait pas « Sénégal ».
Replier les accents est la correction évidente — et elle est **fausse telle
quelle pour le wolof**, où `ñ` et `n` distinguent des mots réels. Détruire cette
distinction dans l'index reviendrait à confondre deux mots pour faire plaisir à
une requête française.

La forme repliée est donc **ajoutée** au terme brut, jamais substituée :
l'expansion ajoute et ne retire jamais — la règle que la couche multilingue
(`corpus/languages/aliases.yaml`) tient déjà. Une requête avec `ñ` atteint le
terme brut ; une requête sans accent atteint la forme repliée. Aucune
distinction n'est perdue ; seule la portée d'une requête approximative s'élargit.

**Ce qui a fait correspondre n'était pas dit.** Le score sortait seul. Dans ce
dépôt, un score sans sa cause est le même défaut qu'une valeur sans provenance :
`matched_terms()` rend les termes qui ont réellement contribué.
"""

import re
import unicodedata
from typing import Dict, List
from .interfaces import DocumentIndexer
from .types import DocumentItem
from collections import defaultdict
import math

#: Poids du titre dans l'index. Trois : assez pour qu'un document se trouve par
#: son titre, pas assez pour qu'un titre bien choisi écrase un corps
#: réellement pertinent.
POIDS_DU_TITRE = 3


class InMemoryIndexer(DocumentIndexer):
    """Indexeur en mémoire simple basé sur un index inversé."""

    def __init__(self):
        """Initialise l'indexeur."""
        # Index inversé : terme -> dict document_id -> fréquence
        self._inverted_index: dict[str, dict[str, int]] = defaultdict(dict)
        # Stockage des documents pour récupérer le contenu
        self._documents: dict[str, DocumentItem] = {}
        # Les termes réellement indexés pour chaque document. Sans eux, la
        # suppression **recalculait** les termes depuis le contenu et espérait
        # tomber juste : elle ratait déjà tout ce qui ne venait pas du corps du
        # document. Se souvenir coûte un dictionnaire et supprime la classe de
        # bogue entière.
        self._document_terms: dict[str, set] = {}
        # Statistiques des documents pour le scoring BM25-like
        self._doc_lengths: dict[str, int] = {}
        self._avg_doc_length: float = 0.0
        self._total_terms: int = 0

    def _tokenize(self, text: str) -> List[str]:
        """Tokenise un texte en termes (mots en minuscules, sans ponctuation)."""
        # Convertir en minuscules et séparer par des non-mots
        words = re.findall(r'\b\w+\b', text.lower())
        return words

    @staticmethod
    def _replie(terme: str) -> str:
        """
        La forme sans accent d'un terme.

        Rendue **en plus** du terme brut, jamais à sa place : `ñ` et `n`
        distinguent des mots en wolof, et les confondre dans l'index
        reviendrait à effacer une distinction réelle pour faciliter une requête
        approximative.
        """
        decompose = unicodedata.normalize("NFKD", terme)
        return "".join(c for c in decompose if not unicodedata.combining(c))

    def _termes_indexables(self, document: DocumentItem) -> Dict[str, int]:
        """
        Les termes d'un document et leur fréquence, titre compris.

        Le titre pèse `POIDS_DU_TITRE` : un document doit se trouver par le nom
        qu'on lit à l'écran. Les formes repliées sont ajoutées avec la même
        fréquence que le terme dont elles viennent.

        Args:
            document: Le document.

        Returns:
            Terme → fréquence.
        """
        frequences: Dict[str, int] = {}
        sources = [(document.content or "", 1),
                   (getattr(document, "title", "") or "", POIDS_DU_TITRE)]

        for texte, poids in sources:
            for terme in self._tokenize(texte):
                frequences[terme] = frequences.get(terme, 0) + poids

        for terme, frequence in list(frequences.items()):
            replie = self._replie(terme)
            if replie != terme:
                frequences[replie] = frequences.get(replie, 0) + frequence
        return frequences

    def matched_terms(self, document_id: str, query: str) -> List[str]:
        """
        Les termes de la requête qui ont réellement fait correspondre ce document.

        Un score sans sa cause est, dans ce dépôt, le même défaut qu'une valeur
        sans provenance.

        Args:
            document_id: Le document.
            query: La requête.

        Returns:
            Les termes présents dans l'index pour ce document, dans l'ordre de
            la requête, sans doublon.
        """
        trouves: List[str] = []
        for terme in self._tokenize(query):
            for forme in (terme, self._replie(terme)):
                if document_id in self._inverted_index.get(forme, {}):
                    if terme not in trouves:
                        trouves.append(terme)
                    break
        return trouves

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

        # Tokeniser le contenu **et le titre** (54.1)
        term_freq = self._termes_indexables(document)

        # Mettre à jour l'index inversé et les statistiques
        doc_length = sum(term_freq.values())
        self._doc_lengths[document.document_id] = doc_length
        self._total_terms += doc_length

        # Recalculer la longueur moyenne du document
        self._avg_doc_length = self._total_terms / len(self._documents) if self._documents else 0.0

        # Mettre à jour l'index inversé
        self._document_terms[document.document_id] = set(term_freq)
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

    def explain(self, query: str, limit: int = 10) -> List[dict]:
        """
        Ce que la recherche a trouvé, **et pourquoi**.

        Args:
            query: La requête.
            limit: Nombre maximum de résultats.

        Returns:
            Un enregistrement par résultat : identifiant, score, termes ayant
            correspondu, et ceux de la requête qui n'ont rien touché.
        """
        demandes = self._tokenize(query)
        explications = []
        for document, score in self.search(query, limit):
            correspondants = self.matched_terms(document.document_id, query)
            explications.append({
                "document_id": document.document_id,
                "title": getattr(document, "title", ""),
                "score": round(score, 4),
                "matched_terms": correspondants,
                # Dits aussi : un terme qui n'a rien touché explique pourquoi un
                # résultat attendu manque.
                "unmatched_terms": [t for t in demandes if t not in correspondants],
                "method": "BM25 lexical",
                "note": (
                    "Comparaison de termes, pas de sens : ce score ne mesure "
                    "aucune similarité sémantique (ADR-015)."
                ),
            })
        return explications

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

        # Supprimer de l'index inversé, en relisant les termes **réellement
        # indexés**. Les recalculer depuis le contenu laissait derrière soi tout
        # ce qui ne venait pas du corps — un document réindexé restait trouvable
        # par son ancien titre.
        unique_terms = self._document_terms.pop(document_id, set())

        # Supprimer le document de l'index pour chaque terme
        for term in unique_terms:
            if document_id in self._inverted_index.get(term, {}):
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
        self._document_terms.clear()
        self._doc_lengths.clear()
        self._total_terms = 0
        self._avg_doc_length = 0.0