"""
Magasin de fichiers à index JSON séparé des octets (ADR-016).

Deux backends du service `cloud` — disque local et S3 — partagent la même
structure : un **index JSON de métadonnées** et un **dépôt d'octets** à côté.
Seul le second diffère. Les porter sous le service de fichiers en deux classes
complètes aurait écrit une troisième et une quatrième fois la logique d'index,
ce qu'ADR-016 reproche justement à l'existant.

Cette classe tient donc l'index, et laisse trois opérations aux sous-classes :
écrire, lire et supprimer un bloc d'octets.

Trois défauts de l'implémentation d'origine sont corrigés ici, parce qu'un port
qui recopie ses défauts n'est pas un port :

1. **Un index tronqué faisait disparaître tous les fichiers, en silence.**
   `_load_index` attrapait `JSONDecodeError` et repartait sur un index vide :
   le magasin rapportait « 0 fichier » alors que les octets étaient toujours sur
   le disque. Mesuré sur `FileSystemCloudStore`. Un index illisible **arrête**
   désormais l'ouverture, et le fichier fautif est conservé — c'est la seule
   trace de ce qui a été stocké.
2. **L'index était réécrit en place**, donc une écriture interrompue produisait
   exactement le fichier tronqué du point 1. Il est écrit dans un fichier
   temporaire puis renommé : `os.replace` est atomique, l'ancien index reste
   valide jusqu'au dernier instant.
3. **Un identifiant servait de nom de fichier sans contrôle.** Un `id` contenant
   `../` écrivait hors du répertoire de données. Les identifiants sont validés.
"""

import json
import logging
import os
import re
import threading
import time
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from .interfaces import FileStore
from .types import FileCategory, FileItem, FileSummary

logger = logging.getLogger(__name__)

# Un identifiant sert de nom de fichier ou de clé d'objet : il ne contient que
# ce qui est sûr dans les deux cas.
IDENTIFIANT_VALIDE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class IndexCorrompu(RuntimeError):
    """L'index des métadonnées est illisible ; les octets, eux, sont peut-être là."""


class IndexedFileStore(FileStore):
    """
    Magasin de fichiers dont les métadonnées vivent dans un index JSON.

    Les sous-classes fournissent le dépôt d'octets (`_write_blob`, `_read_blob`,
    `_delete_blob`). Tout le reste — index, filtres, statistiques, verrou — est
    ici et n'est écrit qu'une fois.
    """

    def __init__(self, data_dir: str) -> None:
        """
        Args:
            data_dir: Répertoire portant l'index (et, selon le backend, les octets).
        """
        self._data_dir = data_dir
        self._index_path = os.path.join(data_dir, "index.json")
        self._lock = threading.RLock()
        self._items: Dict[str, FileSummary] = {}
        self._order: List[str] = []

        os.makedirs(data_dir, exist_ok=True)
        self._load_index()

    # ------------------------------------------------------------------
    # Dépôt d'octets — fourni par la sous-classe
    # ------------------------------------------------------------------

    @abstractmethod
    def _write_blob(self, file_id: str, data: bytes, content_type: str) -> None:
        """Écrit les octets d'un fichier."""

    @abstractmethod
    def _read_blob(self, file_id: str) -> Optional[bytes]:
        """Lit les octets d'un fichier, ou None s'ils sont introuvables."""

    @abstractmethod
    def _delete_blob(self, file_id: str) -> None:
        """Supprime les octets d'un fichier. Une absence n'est pas une erreur."""

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        """
        Charge l'index, ou refuse d'ouvrir le magasin.

        Repartir d'un index vide serait la pire réponse possible : le magasin
        rapporterait « aucun fichier » alors que les octets sont là, un appelant
        les téléverserait de nouveau, et la réparation deviendrait impossible.
        """
        if not os.path.exists(self._index_path):
            return

        try:
            with open(self._index_path, "r", encoding="utf-8") as fichier:
                donnees = json.load(fichier)
        except json.JSONDecodeError as erreur:
            raise IndexCorrompu(
                f"Index illisible ({self._index_path}) : {erreur}. "
                "Les octets des fichiers sont probablement intacts ; l'index est "
                "conservé tel quel pour permettre une réparation."
            ) from erreur
        except OSError as erreur:
            raise IndexCorrompu(
                f"Index inaccessible ({self._index_path}) : {erreur}"
            ) from erreur

        self._order = list(donnees.get("order", []))
        for element in donnees.get("items", []):
            resume = self._resume_depuis_dict(element)
            self._items[resume.id] = resume

        # Un identifiant listé sans métadonnées correspondantes fausserait
        # `count()` et lèverait au premier listage.
        self._order = [
            identifiant for identifiant in self._order if identifiant in self._items
        ]
        logger.info("Index chargé : %d fichiers depuis %s",
                    len(self._items), os.path.abspath(self._index_path))

    @staticmethod
    def _resume_depuis_dict(element: Dict[str, Any]) -> FileSummary:
        """Reconstruit un résumé depuis une entrée de l'index."""
        categorie = element.get("category", FileCategory.OTHER.value)
        try:
            categorie = FileCategory(categorie)
        except ValueError:
            categorie = FileCategory.OTHER
        return FileSummary(
            id=element["id"],
            name=element["name"],
            content_type=element["content_type"],
            size=element["size"],
            category=categorie,
            description=element.get("description"),
            tags=element.get("tags", {}),
            uploaded_by=element.get("uploaded_by"),
            source=element.get("source"),
            metadata=element.get("metadata", {}),
            created_at=element["created_at"],
            updated_at=element["updated_at"],
        )

    @staticmethod
    def _resume_en_dict(resume: FileSummary) -> Dict[str, Any]:
        """Sérialise un résumé pour l'index, horodatages bruts compris."""
        return {
            "id": resume.id,
            "name": resume.name,
            "content_type": resume.content_type,
            "size": resume.size,
            "category": resume.category.value,
            "description": resume.description,
            "tags": resume.tags,
            "uploaded_by": resume.uploaded_by,
            "source": resume.source,
            "metadata": resume.metadata,
            # Les secondes, pas l'ISO : c'est ce que relit `_resume_depuis_dict`,
            # et une conversion aller-retour perdrait la précision.
            "created_at": resume.created_at,
            "updated_at": resume.updated_at,
        }

    def _save_index(self) -> None:
        """
        Écrit l'index de façon atomique.

        Écrire en place laissait une fenêtre — une coupure, un disque plein —
        où l'index était tronqué. `os.replace` est atomique : l'ancien index
        reste entièrement valide jusqu'au renommage.
        """
        contenu = {
            "order": self._order,
            "items": [self._resume_en_dict(resume) for resume in self._items.values()],
        }
        temporaire = f"{self._index_path}.tmp"
        try:
            with open(temporaire, "w", encoding="utf-8") as fichier:
                json.dump(contenu, fichier, ensure_ascii=False)
                fichier.flush()
                os.fsync(fichier.fileno())
            os.replace(temporaire, self._index_path)
        except OSError as erreur:
            logger.error("Impossible d'écrire l'index (%s) : %s", self._index_path, erreur)
            if os.path.exists(temporaire):
                try:
                    os.remove(temporaire)
                except OSError:
                    pass
            raise

    @staticmethod
    def _verifier_identifiant(file_id: str) -> str:
        """Refuse un identifiant qui ne peut pas servir de nom de fichier."""
        if not IDENTIFIANT_VALIDE.match(file_id or ""):
            raise ValueError(
                f"Identifiant de fichier refusé : « {file_id} ». "
                "Il sert de nom de fichier et de clé d'objet."
            )
        return file_id

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    def save(self, file: FileItem) -> str:
        """
        Enregistre un fichier : les octets d'abord, l'index ensuite.

        Cet ordre est délibéré. Si l'écriture des octets échoue, rien n'entre
        dans l'index et le fichier n'a jamais existé. L'ordre inverse
        produirait une entrée d'index pointant vers rien — un fichier que la
        plateforme listerait et ne pourrait pas rendre.
        """
        self._verifier_identifiant(file.id)
        with self._lock:
            if file.id in self._items:
                raise ValueError(f"Le fichier {file.id} existe déjà.")

            self._write_blob(file.id, file.data, file.content_type)
            self._items[file.id] = file.summary()
            self._order.append(file.id)
            try:
                self._save_index()
            except OSError:
                # L'index n'a pas pu être écrit : l'état mémoire ne doit pas
                # prétendre le contraire.
                self._items.pop(file.id, None)
                self._order = [i for i in self._order if i != file.id]
                self._delete_blob(file.id)
                raise
            return file.id

    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier ; retourne False si absent."""
        with self._lock:
            resume = self._items.get(file_id)
            if resume is None:
                return False
            resume.metadata.update(metadata)
            resume.updated_at = time.time()
            self._save_index()
            return True

    def delete(self, file_id: str) -> bool:
        """Supprime un fichier, octets compris ; retourne False si absent."""
        with self._lock:
            if file_id not in self._items:
                return False
            self._delete_blob(file_id)
            del self._items[file_id]
            self._order = [identifiant for identifiant in self._order
                           if identifiant != file_id]
            self._save_index()
            return True

    def clear(self) -> int:
        """
        Supprime tous les fichiers, **octets compris**, et retourne le compte.

        Le magasin S3 d'origine ne vidait que son index local : il rapportait
        N fichiers supprimés pendant que N objets restaient dans le seau,
        facturés et lisibles. « Supprimé » doit vouloir dire supprimé.
        """
        with self._lock:
            compte = len(self._order)
            for identifiant in list(self._order):
                self._delete_blob(identifiant)
            self._items.clear()
            self._order.clear()
            self._save_index()
            return compte

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def get(self, file_id: str) -> Optional[FileItem]:
        """Retourne un fichier avec son contenu, ou None si absent."""
        with self._lock:
            resume = self._items.get(file_id)
            if resume is None:
                return None
            octets = self._read_blob(file_id)
            if octets is None:
                # L'index connaît le fichier, le dépôt ne l'a plus. Rendre un
                # fichier vide serait rendre un mensonge plausible.
                logger.error(
                    "Octets introuvables pour %s : l'index et le dépôt divergent.",
                    file_id,
                )
                return None
            return self._fichier_complet(resume, octets)

    def get_by_name(self, name: str) -> Optional[FileItem]:
        """Retourne le fichier le plus récent portant ce nom exact."""
        with self._lock:
            for identifiant in reversed(self._order):
                if self._items[identifiant].name == name:
                    return self.get(identifiant)
            return None

    @staticmethod
    def _fichier_complet(resume: FileSummary, octets: bytes) -> FileItem:
        """Recompose un `FileItem` depuis son résumé et ses octets."""
        return FileItem(
            id=resume.id,
            name=resume.name,
            content_type=resume.content_type,
            size=resume.size,
            data=octets,
            category=resume.category,
            description=resume.description,
            tags=dict(resume.tags),
            uploaded_by=resume.uploaded_by,
            source=resume.source,
            metadata=dict(resume.metadata),
            created_at=resume.created_at,
            updated_at=resume.updated_at,
        )

    @staticmethod
    def _correspond(
        resume: FileSummary,
        category: Optional[str],
        content_type: Optional[str],
        uploaded_by: Optional[str],
        tags: Optional[Dict[str, str]],
    ) -> bool:
        """Applique les mêmes filtres que les autres magasins de fichiers."""
        if category is not None and resume.category.value != category:
            return False
        if content_type is not None and resume.content_type != content_type:
            return False
        if uploaded_by is not None and resume.uploaded_by != uploaded_by:
            return False
        if tags:
            return all(resume.tags.get(cle) == valeur for cle, valeur in tags.items())
        return True

    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        content_type: Optional[str] = None,
        uploaded_by: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> List[FileSummary]:
        """
        Retourne les fichiers filtrés, du plus récent au plus ancien, sans leur
        contenu (ADR-016).

        Ce magasin n'a jamais eu le défaut que le stockage SQLite avait : les
        octets vivent hors de l'index, donc lister ne les touche pas.
        """
        with self._lock:
            retenus = [
                self._items[identifiant] for identifiant in reversed(self._order)
                if self._correspond(self._items[identifiant], category,
                                    content_type, uploaded_by, tags)
            ]
            return retenus[offset:offset + limit]

    def count(self) -> int:
        """Retourne le nombre total de fichiers."""
        with self._lock:
            return len(self._order)

    def total_size(self) -> int:
        """Retourne la taille totale des fichiers stockés."""
        with self._lock:
            return sum(resume.size for resume in self._items.values())

    def stats(self) -> Dict[str, Any]:
        """Retourne les mêmes statistiques que les autres magasins de fichiers."""
        with self._lock:
            taille = sum(resume.size for resume in self._items.values())
            par_categorie: Dict[str, int] = {}
            par_type: Dict[str, int] = {}
            for resume in self._items.values():
                categorie = resume.category.value
                par_categorie[categorie] = par_categorie.get(categorie, 0) + 1
                par_type[resume.content_type] = par_type.get(resume.content_type, 0) + 1
            return {
                "total": len(self._order),
                "total_size": taille,
                "total_size_mb": round(taille / (1024 * 1024), 2),
                "by_category": par_categorie,
                "by_content_type": par_type,
            }
