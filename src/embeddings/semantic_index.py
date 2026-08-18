"""
Classement sémantique d'éléments textuels (ADR-015).

Ce module fait le lien entre un encodeur, un magasin de vecteurs et un appelant
qui possède des éléments à classer. Il existe pour que **mémoire, connaissances
et recherche partagent un seul chemin vectoriel** : trois implémentations de la
même idée finiraient par diverger, et la plateforme a déjà trouvé trois fois deux
implémentations d'une même interface en désaccord.

**L'indexation est paresseuse, et c'est un choix.** Un élément est encodé la
première fois qu'une recherche le rencontre sans le trouver dans le magasin.
L'alternative — encoder à l'écriture — imposerait de modifier chaque chemin
d'écriture de la plateforme, donc d'en créer plusieurs, donc de risquer qu'un
seul soit oublié et qu'une partie du corpus reste invisible sans que rien ne le
signale. Le prix payé est la première requête d'un corpus neuf ; il est borné, il
est visible, et il ne se paie qu'une fois.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .interfaces import EmbeddingProvider
from .vector_store import SQLiteVectorStore, Vector, VectorMatch

logger = logging.getLogger(__name__)

# Méthodes de classement rapportées à l'appelant. Une réponse doit toujours dire
# laquelle a servi : présenter un résultat lexical comme sémantique ferait
# construire sur une similarité comprise là où il n'y a que des jetons partagés.
METHOD_SEMANTIC = "semantic"
METHOD_LEXICAL = "lexical"


class SemanticIndex:
    """
    Classe des éléments textuels par proximité de sens.

    Exemple:
        index = SemanticIndex(embedder, store, collection="memory")
        classes = index.rank("maladie du mil", [("m1", "Le sorgho est atteint")])
    """

    def __init__(
        self,
        embedder: EmbeddingProvider,
        store: Optional[SQLiteVectorStore] = None,
        collection: str = "default",
    ):
        """
        Args:
            embedder: Encodeur à utiliser ; il détermine l'espace vectoriel.
            store: Magasin de vecteurs ; celui par défaut sinon.
            collection: Espace de noms des vecteurs — « memory », « knowledge »…
        """
        self._embedder = embedder
        self._store = store or SQLiteVectorStore()
        self._collection = collection

    @property
    def collection(self) -> str:
        """Collection interrogée par cet index."""
        return self._collection

    def index(self, elements: Sequence[Tuple[str, str]]) -> int:
        """
        Encode et stocke des éléments.

        Args:
            elements: Paires `(identifiant, texte)`.

        Returns:
            Le nombre d'éléments encodés.
        """
        elements = [(item_id, texte) for item_id, texte in elements if texte and texte.strip()]
        if not elements:
            return 0

        vecteurs = self._embedder.embed([texte for _, texte in elements])
        return self._store.upsert([
            Vector(
                item_id=item_id,
                collection=self._collection,
                values=valeurs,
                model_name=self._embedder.model_name,
            )
            for (item_id, _), valeurs in zip(elements, vecteurs)
        ])

    def rank(
        self,
        requete: str,
        elements: Sequence[Tuple[str, str]],
        limit: int = 10,
        min_score: float = 0.0,
    ) -> List[VectorMatch]:
        """
        Classe des éléments par proximité de sens avec la requête.

        Les éléments absents du magasin sont encodés au passage — c'est
        l'indexation paresseuse décrite en tête de module.

        Args:
            requete: Texte de la requête.
            elements: Paires `(identifiant, texte)` candidates.
            limit: Nombre maximal de résultats.
            min_score: Score minimal ; sous ce seuil, ce n'est pas un résultat.

        Returns:
            Les correspondances, de la plus proche à la plus lointaine, restreintes
            aux identifiants fournis.
        """
        if not requete.strip() or not elements:
            return []

        self._indexer_les_manquants(elements)

        vecteur_requete = self._embedder.embed([requete])[0]
        candidats = {item_id for item_id, _ in elements}
        # On demande plus large que `limit` : le magasin peut contenir des
        # éléments hors de cette liste (un autre sujet, une autre session), et
        # les écarter après coup viderait un résultat déjà tronqué.
        correspondances = self._store.search(
            self._collection,
            vecteur_requete,
            self._embedder.model_name,
            limit=max(limit * 4, limit + len(candidats)),
            min_score=min_score,
        )
        return [c for c in correspondances if c.item_id in candidats][:limit]

    def _indexer_les_manquants(self, elements: Sequence[Tuple[str, str]]) -> None:
        """Encode les éléments que le magasin ne connaît pas encore."""
        connus = self._identifiants_connus()
        manquants = [(item_id, texte) for item_id, texte in elements if item_id not in connus]
        if manquants:
            logger.debug(
                "Indexation paresseuse : %d élément(s) encodé(s) dans « %s ».",
                len(manquants), self._collection,
            )
            self.index(manquants)

    def _identifiants_connus(self) -> set:
        """Retourne les identifiants déjà encodés dans la collection."""
        return self._store.item_ids(self._collection, self._embedder.model_name)


def rank_or_fallback(
    requete: str,
    elements: Sequence[Tuple[str, str]],
    repli: Callable[[], List[Tuple[str, float]]],
    embedder: Optional[EmbeddingProvider],
    collection: str,
    limit: int = 10,
    min_score: float = 0.0,
    store: Optional[SQLiteVectorStore] = None,
) -> Tuple[List[Tuple[str, float]], Dict[str, Any]]:
    """
    Classe par le sens si c'est possible, par les mots sinon — et le dit.

    C'est la fonction que les appelants utilisent : elle garantit qu'un résultat
    lexical ne sera jamais présenté comme sémantique.

    Args:
        requete: Texte de la requête.
        elements: Paires `(identifiant, texte)` candidates.
        repli: Fonction rendant le classement lexical, appelée seulement si besoin.
        embedder: Encodeur, ou None s'il n'y en a pas.
        collection: Collection de vecteurs à utiliser.
        limit: Nombre maximal de résultats.
        min_score: Score minimal.
        store: Magasin de vecteurs ; celui par défaut sinon.

    Returns:
        Le classement `(identifiant, score)` et un rapport disant quelle méthode
        a servi, et pourquoi si ce n'est pas la sémantique.
    """
    if embedder is None:
        return repli(), {
            "method": METHOD_LEXICAL,
            "reason": "Aucun encodeur disponible : classement par termes communs (ADR-015).",
        }

    try:
        correspondances = SemanticIndex(embedder, store, collection).rank(
            requete, elements, limit=limit, min_score=min_score
        )
    except Exception as erreur:
        # Un encodeur qui tombe ne doit pas emporter la recherche — mais le repli
        # doit être annoncé, sinon la panne devient invisible.
        logger.warning("Classement sémantique impossible (%s) : repli lexical.", erreur)
        return repli(), {
            "method": METHOD_LEXICAL,
            "reason": f"Encodage impossible ({erreur}) : classement par termes communs.",
        }

    return (
        [(c.item_id, c.score) for c in correspondances],
        {"method": METHOD_SEMANTIC, "model": embedder.model_name},
    )
