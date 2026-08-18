"""
Stockage des fichiers sur le disque local (ADR-016).

Backend `filesystem` du service de fichiers : les métadonnées dans l'index JSON
tenu par `IndexedFileStore`, les octets dans `<data_dir>/files/<id>`.

Il vient du service `cloud`, où il servait `CloudFileItem`. ADR-016 fait du
service de fichiers le seul chemin d'écriture de la plateforme ; ce backend le
suit, avec ses défauts corrigés (index atomique, index illisible signalé plutôt
qu'ignoré, identifiants validés — voir `store_indexed.py`).

Le choix se fait par configuration, comme pour tout magasin :

```
GALSEN_FILE_BACKEND=filesystem
GALSEN_DATA_DIR=/var/lib/galsen
```
"""

import logging
import os
from typing import Optional

from src.storage.paths import data_dir

from .store_indexed import IndexedFileStore

logger = logging.getLogger(__name__)

SOUS_REPERTOIRE = "files"


class FileSystemFileStore(IndexedFileStore):
    """Magasin de fichiers dont les octets sont des fichiers du disque local."""

    def __init__(self, data_directory: Optional[str] = None) -> None:
        """
        Args:
            data_directory: Répertoire de stockage ; `GALSEN_DATA_DIR/files`
                par défaut, comme les bases SQLite du projet (ADR-005).
        """
        racine = data_directory or os.path.join(data_dir(), SOUS_REPERTOIRE)
        self._files_dir = os.path.join(racine, "blobs")
        os.makedirs(self._files_dir, exist_ok=True)
        super().__init__(racine)

    def _chemin(self, file_id: str) -> str:
        """Retourne le chemin des octets d'un fichier."""
        return os.path.join(self._files_dir, self._verifier_identifiant(file_id))

    def _write_blob(self, file_id: str, data: bytes, content_type: str) -> None:
        """
        Écrit les octets, de façon atomique.

        Un fichier écrit à moitié serait rendu tel quel par `get` : le contenu
        est écrit à côté puis renommé, donc il est complet ou absent.
        """
        cible = self._chemin(file_id)
        temporaire = f"{cible}.tmp"
        try:
            with open(temporaire, "wb") as fichier:
                fichier.write(data)
                fichier.flush()
                os.fsync(fichier.fileno())
            os.replace(temporaire, cible)
        except OSError as erreur:
            if os.path.exists(temporaire):
                try:
                    os.remove(temporaire)
                except OSError:
                    pass
            raise IOError(f"Impossible d'écrire {cible} : {erreur}") from erreur

    def _read_blob(self, file_id: str) -> Optional[bytes]:
        """Lit les octets d'un fichier, ou None s'ils sont introuvables."""
        try:
            with open(self._chemin(file_id), "rb") as fichier:
                return fichier.read()
        except (OSError, ValueError):
            return None

    def _delete_blob(self, file_id: str) -> None:
        """Supprime les octets d'un fichier ; une absence n'est pas une erreur."""
        try:
            os.remove(self._chemin(file_id))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as erreur:
            logger.warning("Impossible de supprimer les octets de %s : %s", file_id, erreur)
