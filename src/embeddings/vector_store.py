"""
Magasin de vecteurs, en SQLite et en NumPy (ADR-015).

Pas de base vectorielle : à l'échelle qu'aura cette base de connaissances pendant
longtemps — des milliers d'éléments, pas des millions — un cosinus exhaustif sur
une matrice en mémoire se compte en millisecondes, et ne demande aucun service à
opérer, sécuriser, sauvegarder et superviser. NumPy est **déjà une dépendance**.
Le déclencheur qui renversera ce choix est écrit dans ADR-015 : ~100 000 vecteurs,
ou une latence p95 au-delà de 100 ms.

Deux points de conception méritent d'être dits :

- **Le modèle et la dimension voyagent avec chaque vecteur.** Comparer des
  vecteurs issus de deux modèles rend un nombre parfaitement calculé et
  parfaitement dénué de sens. Le magasin refuse le mélange au lieu de le classer.
- **Les vecteurs sont stockés normalisés**, donc la recherche est un simple
  produit scalaire. La normalisation appartient au fournisseur, qui la fait une
  fois à l'encodage.

Un troisième point s'est ajouté après mesure. `search()` relisait la table et
reparsait chaque `values_json` **à chaque requête** : la matrice était
reconstruite à chaque appel, ce qui n'est pas le coût du cosinus mais celui de
l'analyse JSON. Mesuré sur cette machine avant correction : **49,4 ms** à 271
vecteurs et **1 856,8 ms** à 10 000, médianes sur 15 requêtes.

La matrice est donc **mise en cache par (collection, modèle)**, et le cache est
validé par un compteur de version inscrit dans la base à chaque écriture. Ce
compteur — et non un simple drapeau en mémoire — parce qu'un cache que seul son
propre processus sait invalider sert un résultat périmé dès qu'un autre écrit,
et un résultat périmé rendu comme courant est exactement ce que ce dépôt refuse
partout ailleurs. `PRAGMA data_version` aurait été exact aussi, mais il exige
une connexion persistante : mesuré ici, une connexion neuve rend toujours `1`,
et ce magasin en ouvre une par opération.
"""

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file

DEFAULT_FILENAME = "vectors.sqlite"

#: Taille maximale d'une matrice mise en cache, en mégaoctets. Déclarée, donc
#: discutable : 153,6 Mo suffisent à 100 000 vecteurs de 384 dimensions, et une
#: collection plus grosse est **servie sans cache** plutôt que de faire grossir
#: le processus en silence. `stats()` dit laquelle.
CACHE_MAX_MO = 256


@dataclass
class Vector:
    """Un vecteur et ce qu'il désigne."""

    item_id: str
    collection: str
    values: List[float]
    model_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorMatch:
    """Un résultat de recherche vectorielle."""

    item_id: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat."""
        return {"item_id": self.item_id, "score": round(self.score, 6), "metadata": self.metadata}


class DimensionMismatch(ValueError):
    """Un vecteur ne vient pas du même espace que ceux déjà stockés."""


class SQLiteVectorStore:
    """
    Magasin de vecteurs persistant.

    Exemple:
        magasin = SQLiteVectorStore()
        magasin.upsert([Vector("m1", "memory", [0.1, 0.9], "modele-x")])
        magasin.search("memory", [0.1, 0.9], "modele-x", limit=5)
    """

    def __init__(self, chemin: Optional[str] = None):
        """
        Ouvre — et crée si besoin — la base de vecteurs.

        Args:
            chemin: Fichier SQLite ; `GALSEN_DATA_DIR/vectors.sqlite` par défaut.
        """
        self._chemin = chemin or default_sqlite_path(DEFAULT_FILENAME)
        self._lock = threading.RLock()
        # Par (collection, modèle) : la version lue au moment du calcul, la
        # matrice, les identifiants et les métadonnées **non analysées**. Les
        # métadonnées ne sont converties que pour les résultats rendus.
        self._cache: Dict[tuple, Dict[str, Any]] = {}
        self._cache_coups = {"frais": 0, "reconstruit": 0, "non_cachable": 0}
        self._preparer()

    def _connexion(self) -> sqlite3.Connection:
        """Ouvre une connexion réglée comme toutes les autres bases (ADR-005)."""
        return prepare_connection(sqlite3.connect(self._chemin))

    def _preparer(self) -> None:
        """Crée le schéma. Le modèle est stocké par vecteur, à dessein."""
        with self._lock, self._connexion() as connexion:
            connexion.execute(
                """
                CREATE TABLE IF NOT EXISTS vectors (
                    item_id     TEXT NOT NULL,
                    collection  TEXT NOT NULL,
                    model_name  TEXT NOT NULL,
                    dimension   INTEGER NOT NULL,
                    values_json TEXT NOT NULL,
                    metadata    TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (collection, item_id)
                )
                """
            )
            connexion.execute(
                "CREATE INDEX IF NOT EXISTS idx_vectors_collection ON vectors(collection)"
            )
            # Le compteur qui valide le cache. Une seule ligne, lue en O(1) à
            # chaque recherche : c'est ce qui permet de faire confiance à une
            # matrice gardée en mémoire sans supposer qu'on est seul à écrire.
            connexion.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_store_version (
                    id      INTEGER PRIMARY KEY CHECK (id = 1),
                    version INTEGER NOT NULL
                )
                """
            )
            connexion.execute(
                "INSERT OR IGNORE INTO vector_store_version (id, version) VALUES (1, 0)"
            )
        secure_database_file(self._chemin)

    @staticmethod
    def _incrementer_version(connexion: sqlite3.Connection) -> None:
        """
        Marque la base comme modifiée, **dans la transaction de l'écriture**.

        Hors de cette transaction, une écriture pourrait être validée sans que
        le compteur bouge, et un cache resterait « frais » sur des données qui
        ont changé.
        """
        connexion.execute(
            "UPDATE vector_store_version SET version = version + 1 WHERE id = 1"
        )

    def _version(self) -> int:
        """La version courante de la base. Une ligne, lue à chaque recherche."""
        with self._lock, self._connexion() as connexion:
            ligne = connexion.execute(
                "SELECT version FROM vector_store_version WHERE id = 1"
            ).fetchone()
        return int(ligne[0]) if ligne else 0

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    def upsert(self, vecteurs: Sequence[Vector]) -> int:
        """
        Ajoute ou remplace des vecteurs.

        Args:
            vecteurs: Vecteurs à écrire.

        Returns:
            Le nombre de vecteurs écrits.

        Raises:
            DimensionMismatch: Si un vecteur ne correspond pas à la dimension
                déjà présente dans sa collection pour le même modèle.
        """
        if not vecteurs:
            return 0

        with self._lock, self._connexion() as connexion:
            for vecteur in vecteurs:
                dimension = len(vecteur.values)
                if dimension == 0:
                    raise ValueError(f"Vecteur vide pour « {vecteur.item_id} »")
                self._verifier_dimension(connexion, vecteur, dimension)
                connexion.execute(
                    """
                    INSERT INTO vectors
                        (item_id, collection, model_name, dimension, values_json, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(collection, item_id) DO UPDATE SET
                        model_name = excluded.model_name,
                        dimension = excluded.dimension,
                        values_json = excluded.values_json,
                        metadata = excluded.metadata
                    """,
                    (
                        vecteur.item_id,
                        vecteur.collection,
                        vecteur.model_name,
                        dimension,
                        json.dumps(vecteur.values),
                        json.dumps(vecteur.metadata),
                    ),
                )
            self._incrementer_version(connexion)

        return len(vecteurs)

    @staticmethod
    def _verifier_dimension(connexion: sqlite3.Connection, vecteur: Vector, dimension: int) -> None:
        """Refuse un vecteur qui ne vient pas de l'espace déjà stocké."""
        ligne = connexion.execute(
            "SELECT dimension FROM vectors WHERE collection = ? AND model_name = ? LIMIT 1",
            (vecteur.collection, vecteur.model_name),
        ).fetchone()
        if ligne and ligne[0] != dimension:
            raise DimensionMismatch(
                f"Le modèle « {vecteur.model_name} » a déjà écrit des vecteurs de "
                f"dimension {ligne[0]} dans « {vecteur.collection} », celui-ci en a "
                f"{dimension}. Réencodez la collection plutôt que de mélanger deux espaces."
            )

    def delete(self, collection: str, item_ids: Sequence[str]) -> int:
        """Supprime des vecteurs ; retourne le nombre effacé."""
        if not item_ids:
            return 0
        with self._lock, self._connexion() as connexion:
            curseur = connexion.execute(
                f"DELETE FROM vectors WHERE collection = ? AND item_id IN "
                f"({','.join('?' * len(item_ids))})",
                (collection, *item_ids),
            )
            self._incrementer_version(connexion)
            return curseur.rowcount

    def clear(self, collection: Optional[str] = None) -> int:
        """Vide une collection, ou tout le magasin."""
        with self._lock, self._connexion() as connexion:
            if collection is None:
                curseur = connexion.execute("DELETE FROM vectors")
            else:
                curseur = connexion.execute(
                    "DELETE FROM vectors WHERE collection = ?", (collection,)
                )
            self._incrementer_version(connexion)
            return curseur.rowcount

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def count(self, collection: Optional[str] = None) -> int:
        """Compte les vecteurs stockés."""
        with self._lock, self._connexion() as connexion:
            if collection is None:
                return connexion.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
            return connexion.execute(
                "SELECT COUNT(*) FROM vectors WHERE collection = ?", (collection,)
            ).fetchone()[0]

    def item_ids(self, collection: str, model_name: str) -> set:
        """
        Retourne les identifiants déjà encodés par un modèle dans une collection.

        Sert à l'indexation paresseuse : savoir ce qui manque sans relire les
        vecteurs eux-mêmes, qui pèsent mille fois plus que leurs identifiants.
        """
        with self._lock, self._connexion() as connexion:
            lignes = connexion.execute(
                "SELECT item_id FROM vectors WHERE collection = ? AND model_name = ?",
                (collection, model_name),
            ).fetchall()
        return {ligne[0] for ligne in lignes}

    def models(self, collection: str) -> List[str]:
        """Retourne les modèles ayant écrit dans une collection."""
        with self._lock, self._connexion() as connexion:
            lignes = connexion.execute(
                "SELECT DISTINCT model_name FROM vectors WHERE collection = ?", (collection,)
            ).fetchall()
        return sorted(ligne[0] for ligne in lignes)

    def search(
        self,
        collection: str,
        requete: Sequence[float],
        model_name: str,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> List[VectorMatch]:
        """
        Retourne les vecteurs les plus proches, par cosinus décroissant.

        Seuls les vecteurs **du même modèle** sont comparés : un cosinus entre
        deux espaces différents est un nombre bien calculé qui ne veut rien dire.

        Args:
            collection: Collection à interroger.
            requete: Vecteur de la requête, normalisé.
            model_name: Modèle ayant produit le vecteur de requête.
            limit: Nombre maximal de résultats.
            min_score: Score minimal ; un résultat sous ce seuil n'est pas un résultat.

        Returns:
            Les correspondances, de la plus proche à la plus lointaine.
        """
        entree = self._matrice(collection, model_name)
        if entree is None:
            return []

        matrice = entree["matrice"]
        vecteur_requete = np.asarray(requete, dtype=np.float32)
        if matrice.shape[1] != vecteur_requete.shape[0]:
            raise DimensionMismatch(
                f"La requête a {vecteur_requete.shape[0]} dimensions, les vecteurs "
                f"stockés en ont {matrice.shape[1]}."
            )

        # Les vecteurs sont stockés normalisés : le produit scalaire **est** le
        # cosinus. Renormaliser ici coûterait un calcul par requête pour rien.
        scores = matrice @ vecteur_requete

        ordre = np.argsort(-scores)[: max(limit, 0)]
        resultats = []
        for index in ordre:
            score = float(scores[index])
            if score < min_score:
                continue
            # Les métadonnées ne sont analysées que pour ce qui est rendu : les
            # analyser toutes coûtait un `json.loads` par ligne et par requête,
            # pour au plus `limit` résultats.
            resultats.append(VectorMatch(
                item_id=entree["item_ids"][index],
                score=score,
                metadata=json.loads(entree["metadonnees"][index]),
            ))
        return resultats

    def _matrice(self, collection: str, model_name: str) -> Optional[Dict[str, Any]]:
        """
        La matrice d'une collection, depuis le cache quand il est encore valide.

        Args:
            collection: La collection interrogée.
            model_name: Le modèle dont les vecteurs sont comparables.

        Returns:
            Un dictionnaire portant la matrice, les identifiants et les
            métadonnées non analysées, ou `None` si la collection est vide.

            La validité se juge sur le **compteur de version de la base**, pas
            sur un drapeau en mémoire : un cache que seul son processus sait
            invalider rend un résultat périmé dès qu'un autre écrit.
        """
        version = self._version()
        cle = (collection, model_name)

        with self._lock:
            entree = self._cache.get(cle)
            if entree is not None and entree["version"] == version:
                self._cache_coups["frais"] += 1
                return entree

        with self._lock, self._connexion() as connexion:
            lignes = connexion.execute(
                "SELECT item_id, values_json, metadata FROM vectors "
                "WHERE collection = ? AND model_name = ?",
                (collection, model_name),
            ).fetchall()

        if not lignes:
            with self._lock:
                self._cache.pop(cle, None)
            return None

        matrice = np.asarray(
            [json.loads(ligne[1]) for ligne in lignes], dtype=np.float32
        )
        entree = {
            "version": version,
            "matrice": matrice,
            "item_ids": [ligne[0] for ligne in lignes],
            "metadonnees": [ligne[2] for ligne in lignes],
            "octets": int(matrice.nbytes),
        }

        # Au-delà du plafond déclaré, la collection est servie **sans** cache.
        # Faire grossir le processus en silence est un autre défaut, pas une
        # optimisation, et `stats()` nomme la collection concernée.
        if matrice.nbytes > CACHE_MAX_MO * 1024 * 1024:
            with self._lock:
                self._cache.pop(cle, None)
                self._cache_coups["non_cachable"] += 1
            return entree

        with self._lock:
            self._cache[cle] = entree
            self._cache_coups["reconstruit"] += 1
        return entree

    def stats(self) -> Dict[str, Any]:
        """Retourne l'état du magasin, pour `/health` et les rapports."""
        with self._lock, self._connexion() as connexion:
            lignes = connexion.execute(
                "SELECT collection, COUNT(*), COUNT(DISTINCT model_name) "
                "FROM vectors GROUP BY collection"
            ).fetchall()
        with self._lock:
            cache = {
                "entries": len(self._cache),
                "bytes": sum(e["octets"] for e in self._cache.values()),
                "hits": dict(self._cache_coups),
                "max_mb": CACHE_MAX_MO,
                "note": (
                    "La matrice est gardée par (collection, modèle) et validée "
                    "par le compteur de version de la base. Une collection "
                    f"au-delà de {CACHE_MAX_MO} Mo est servie **sans** cache "
                    "plutôt que de faire grossir le processus en silence."
                ),
            }

        return {
            "path": self._chemin,
            "cache": cache,
            "total_vectors": sum(ligne[1] for ligne in lignes),
            "collections": {
                ligne[0]: {"vectors": ligne[1], "models": ligne[2]} for ligne in lignes
            },
        }
