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
"""

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file

DEFAULT_FILENAME = "vectors.sqlite"


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
        secure_database_file(self._chemin)

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
        with self._lock, self._connexion() as connexion:
            lignes = connexion.execute(
                "SELECT item_id, values_json, metadata FROM vectors "
                "WHERE collection = ? AND model_name = ?",
                (collection, model_name),
            ).fetchall()

        if not lignes:
            return []

        vecteur_requete = np.asarray(requete, dtype=np.float32)
        matrice = np.asarray(
            [json.loads(ligne[1]) for ligne in lignes], dtype=np.float32
        )
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
            item_id, _, metadata = lignes[index]
            resultats.append(
                VectorMatch(item_id=item_id, score=score, metadata=json.loads(metadata))
            )
        return resultats

    def stats(self) -> Dict[str, Any]:
        """Retourne l'état du magasin, pour `/health` et les rapports."""
        with self._lock, self._connexion() as connexion:
            lignes = connexion.execute(
                "SELECT collection, COUNT(*), COUNT(DISTINCT model_name) "
                "FROM vectors GROUP BY collection"
            ).fetchall()
        return {
            "path": self._chemin,
            "total_vectors": sum(ligne[1] for ligne in lignes),
            "collections": {
                ligne[0]: {"vectors": ligne[1], "models": ligne[2]} for ligne in lignes
            },
        }
