"""
Aide à la résolution des chemins de fichiers SQLite (ADR-005).

Le répertoire de données est configurable via la variable d'environnement
GALSEN_DATA_DIR (défaut : "data").
"""

import os


def default_sqlite_path(filename: str) -> str:
    """
    Résout le chemin par défaut d'un fichier SQLite.

    Args:
        filename: Nom du fichier SQLite (exemple : "models.sqlite").

    Returns:
        Chemin complet dans le répertoire de données configuré.
    """
    return os.path.join(os.getenv("GALSEN_DATA_DIR", "data"), filename)
