"""
Outil de base de données pour GalSen IA.

Fournit une interface simple à une base de données SQLite.
"""

import sqlite3
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.tool.base import BaseTool


class DatabaseTool(BaseTool):
    """
    Outil d'accès à une base de données SQLite.

    Opérations disponibles : `run` (exécuter une requête SQL), `tables` (lister les tables),
    `schema` (obtenir le schéma d'une table).

    Exemple:
        tool.execute("run", "CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, name TEXT)")
        tool.execute("run", "INSERT INTO test (name) VALUES (?)", ("Alice",))
        tool.execute("run", "SELECT * FROM test")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil.

        Args:
            config: Configuration avec les clés optionnelles :
                - `database_path`: chemin vers le fichier de base de données SQLite
                  (par défaut, un fichier `data.db` à la racine du projet).
        """
        super().__init__(config)
        # Determine the database file path
        db_path = self.config.get("database_path")
        if db_path is None:
            # Default to data.db in the project root
            db_path = os.path.join(self._detect_project_root(), "data.db")
        self.database_path: str = db_path
        self._connection: Optional[sqlite3.Connection] = None
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.database_path)), exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """
        Retourne la connexion SQLite, en la créant si nécessaire.

        Returns:
            Une instance de sqlite3.Connection.
        """
        if self._connection is None:
            # Use autocommit mode (isolation_level=None) so each statement is committed automatically
            self._connection = sqlite3.connect(
                self.database_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                isolation_level=None,
            )
            # Ensure foreign keys are enforced (optional)
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    def close(self) -> None:
        """Ferme la connexion à la base de données."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur la base de données.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération, dépendant de celle-ci.

        Raises:
            ValueError: Opération inconnue.
        """
        if not args:
            raise ValueError("Une operation est requise (run, tables, schema, ...)")
        operation = str(args[0]).lower()
        operation_args = args[1:]

        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Operation '{operation}' inconnue. "
                f"Operations disponibles: {', '.join(self.available_operations())}"
            )

        return handler(*operation_args, **kwargs)

    def available_operations(self) -> List[str]:
        """Retourne la liste des operations prises en charge."""
        return sorted(
            name[len("_op_"):]
            for name in dir(self)
            if name.startswith("_op_") and callable(getattr(self, name))
        )

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------
    def _op_run(
        self,
        sql: str,
        parameters: Optional[Sequence[Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Exécute une requête SQL unique.

        Args:
            sql: La requête SQL à exécuter.
            parameters: Paramètres optionnels pour la requête (sequence ou mapping).
            **kwargs: Options supplementaires ( aucune actuellement ).

        Returns:
            Dictionnaire contenant :
                - "rows": liste de tuples de resultats (vide pour les requetes non SELECT)
                - "rowcount": nombre de lignes affectees ou retournees
                - "lastrowid": rowid de la derniere ligne inseree (None si non applicable)
        """
        if not isinstance(sql, str) or not sql.strip():
            raise ValueError("La requete SQL doit être une chaîne non vide")

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            if parameters:
                cursor.execute(sql, parameters)
            else:
                cursor.execute(sql)

            # Determine if the query is a SELECT-like statement
            is_select = cursor.description is not None
            rows: List[Tuple[Any, ...]] = []
            if is_select:
                rows = cursor.fetchall()
                rowcount = len(rows)
            else:
                rowcount = cursor.rowcount

            result = {
                "rows": rows,
                "rowcount": rowcount,
                "lastrowid": cursor.lastrowid,
            }
            return result
        finally:
            cursor.close()

    def _op_tables(self, **kwargs) -> List[str]:
        """
        Liste les tables de la base de données.

        Returns:
            Liste des noms de tables.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        finally:
            cursor.close()

    def _op_schema(self, table_name: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Retourne le schéma d'une table donnée.

        Args:
            table_name: Nom de la table a inspecter.

        Returns:
            Liste de dictionnaires décrivant chaque colonne (cid, name, type, notnull, dflt_value, pk).
        """
        if not isinstance(table_name, str) or not table_name.strip():
            raise ValueError("Le nom de la table doit être une chaîne non vide")

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Use PRAGMA table_info to get schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = []
            for row in cursor.fetchall():
                columns.append(
                    {
                        "cid": row[0],
                        "name": row[1],
                        "type": row[2],
                        "notnull": bool(row[3]),
                        "dflt_value": row[4],
                        "pk": bool(row[5]),
                    }
                )
            return columns
        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    @staticmethod
    def _detect_project_root() -> str:
        """
        Déduit la racine du projet depuis l'emplacement de ce fichier.

        Returns:
            Chemin absolu vers la racine du projet.
        """
        # Ce fichier est dans <racine>/src/tools/database/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))