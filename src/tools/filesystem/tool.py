"""
File system tool for GalSen IA.

Gives agents read and write access to files, confined to an explicit root
directory. Every path is resolved and checked against that root before any
operation, so an agent cannot reach the rest of the machine — neither through
`..` segments, nor through absolute paths, nor through symbolic links.

Writing is disabled by default: an agent that only needs to read never gets the
ability to modify anything.
"""

import fnmatch
import logging
import os
import shutil
from collections import deque
from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

logger = logging.getLogger(__name__)


class FileSystemTool(BaseTool):
    """
    Outil d'accès au système de fichiers, confiné à un répertoire racine.

    Opérations disponibles : `read`, `write`, `append`, `list`, `tree`, `exists`,
    `stat`, `search`, `grep`, `mkdir`, `delete`, `copy`, `move`.

    Exemple:
        tool.execute("read", "docs/memory/vision.md")
        tool.execute("search", "*.py", directory="src")
    """

    # Opérations qui modifient le système de fichiers
    WRITE_OPERATIONS = frozenset({"write", "append", "mkdir", "delete", "copy", "move"})

    # Répertoires ignorés lors des parcours récursifs : ils sont volumineux et sans intérêt
    DEFAULT_EXCLUDED_DIRECTORIES = frozenset({
        ".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".mypy_cache",
    })

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil.

        Args:
            config: Configuration avec les clés optionnelles :
                - `root`: répertoire racine autorisé (par défaut la racine du projet)
                - `allow_write`: autorise les opérations d'écriture (par défaut False)
                - `max_read_bytes`: taille maximale lue en une fois (par défaut 5 Mo)
                - `max_results`: nombre maximum d'entrées retournées (par défaut 500)
                - `encoding`: encodage de lecture et d'écriture (par défaut utf-8)
                - `excluded_directories`: répertoires ignorés lors des parcours
        """
        super().__init__(config)

        self.root = os.path.realpath(self.config.get("root") or self._detect_project_root())
        self.allow_write = bool(self.config.get("allow_write", False))
        self.max_read_bytes = int(self.config.get("max_read_bytes", 5 * 1024 * 1024))
        self.max_results = int(self.config.get("max_results", 500))
        self.encoding = self.config.get("encoding", "utf-8")
        self.excluded_directories = frozenset(
            self.config.get("excluded_directories", self.DEFAULT_EXCLUDED_DIRECTORIES)
        )

        if not os.path.isdir(self.root):
            raise ValueError(f"Racine du système de fichiers introuvable: {self.root}")

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur le système de fichiers.

        Args:
            *args: L'opération, puis son chemin cible éventuel
            **kwargs: Options propres à l'opération

        Returns:
            Résultat de l'opération, dont la forme dépend de celle-ci

        Raises:
            ValueError: Opération inconnue, écriture interdite, ou chemin hors racine
        """
        if not args:
            raise ValueError("Une opération est requise (read, write, list, search, ...)")

        operation = str(args[0]).lower()
        operation_args = args[1:]

        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. "
                f"Opérations disponibles: {', '.join(self.available_operations())}"
            )

        if operation in self.WRITE_OPERATIONS and not self.allow_write:
            raise ValueError(
                f"L'opération '{operation}' modifie le système de fichiers et l'écriture "
                "est désactivée. Activez 'allow_write' dans la configuration de l'outil."
            )

        return handler(*operation_args, **kwargs)

    def available_operations(self) -> List[str]:
        """Retourne la liste des opérations prises en charge."""
        return sorted(
            name[len("_op_"):] for name in dir(self)
            if name.startswith("_op_") and callable(getattr(self, name))
        )

    # ------------------------------------------------------------------
    # Opérations de lecture
    # ------------------------------------------------------------------
    def _op_read(self, path: str, **kwargs) -> Dict[str, Any]:
        """Lit un fichier texte et retourne son contenu."""
        target = self._resolve(path)
        if not os.path.isfile(target):
            raise FileNotFoundError(f"Fichier introuvable: {path}")

        size = os.path.getsize(target)
        if size > self.max_read_bytes:
            raise ValueError(
                f"Fichier trop volumineux ({size} octets, maximum {self.max_read_bytes})"
            )

        encoding = kwargs.get("encoding", self.encoding)
        with open(target, "r", encoding=encoding, errors="replace") as handle:
            content = handle.read()

        from src.security.trust import TrustLevel, envelope_fields

        resultat = {
            "path": self._relative(target),
            "content": content,
            "size": size,
            "line_count": len(content.splitlines()),
        }
        # Un fichier lu sur le disque n'est pas forcément écrit par la personne
        # qui pose la question : un dépôt cloné, une pièce jointe enregistrée,
        # un fichier téléchargé (VOLET 36, ch. A.3). `content` reste brut — cet
        # outil sert d'abord à lire du code et des données.
        resultat.update(envelope_fields(
            content, TrustLevel.DOCUMENT, origin=self._relative(target),
        ))
        return resultat

    def _op_tail(self, path: str, **kwargs) -> Dict[str, Any]:
        """
        Lit les dernières lignes d'un fichier.

        Contrairement à `read`, cette opération n'a pas de limite de taille :
        elle ne charge que la fin du fichier. C'est le seul moyen d'inspecter un
        journal qui grossit sans borne.

        Args:
            path: Chemin du fichier
            **kwargs: `lines` pour le nombre de lignes retournées (500 par défaut)

        Returns:
            Les dernières lignes et la taille totale du fichier
        """
        target = self._resolve(path)
        if not os.path.isfile(target):
            raise FileNotFoundError(f"Fichier introuvable: {path}")

        line_count = int(kwargs.get("lines", 500))
        if line_count < 1:
            raise ValueError("Le nombre de lignes doit être au moins 1")

        encoding = kwargs.get("encoding", self.encoding)
        tail = deque(maxlen=line_count)

        # Le fichier est parcouru par flux : sa taille n'entre jamais en mémoire
        with open(target, "r", encoding=encoding, errors="replace") as handle:
            for line in handle:
                tail.append(line.rstrip("\n"))

        return {
            "path": self._relative(target),
            "lines": list(tail),
            "line_count": len(tail),
            "file_size": os.path.getsize(target),
        }

    def _op_exists(self, path: str, **kwargs) -> bool:
        """Indique si un chemin existe."""
        return os.path.exists(self._resolve(path))

    def _op_stat(self, path: str, **kwargs) -> Dict[str, Any]:
        """Retourne les informations d'un fichier ou répertoire."""
        target = self._resolve(path)
        if not os.path.exists(target):
            raise FileNotFoundError(f"Chemin introuvable: {path}")

        info = os.stat(target)
        return {
            "path": self._relative(target),
            "is_file": os.path.isfile(target),
            "is_directory": os.path.isdir(target),
            "size": info.st_size,
            "modified": info.st_mtime,
            "created": info.st_ctime,
        }

    def _op_list(self, path: str = ".", **kwargs) -> List[Dict[str, Any]]:
        """Liste le contenu direct d'un répertoire."""
        target = self._resolve(path)
        if not os.path.isdir(target):
            raise NotADirectoryError(f"Répertoire introuvable: {path}")

        entries: List[Dict[str, Any]] = []
        for name in sorted(os.listdir(target)):
            if name in self.excluded_directories:
                continue

            full_path = os.path.join(target, name)
            entries.append({
                "name": name,
                "path": self._relative(full_path),
                "is_directory": os.path.isdir(full_path),
                "size": os.path.getsize(full_path) if os.path.isfile(full_path) else 0,
            })
            if len(entries) >= self.max_results:
                break

        return entries

    def _op_tree(self, path: str = ".", **kwargs) -> List[str]:
        """Liste récursivement les fichiers d'un répertoire."""
        target = self._resolve(path)
        if not os.path.isdir(target):
            raise NotADirectoryError(f"Répertoire introuvable: {path}")

        max_depth = int(kwargs.get("max_depth", 10))
        files: List[str] = []

        for current_dir, subdirs, filenames in os.walk(target):
            # Élaguer les répertoires exclus avant de les parcourir
            subdirs[:] = [d for d in subdirs if d not in self.excluded_directories]

            depth = self._relative(current_dir).count(os.sep)
            if depth >= max_depth:
                subdirs.clear()

            for filename in sorted(filenames):
                files.append(self._relative(os.path.join(current_dir, filename)))
                if len(files) >= self.max_results:
                    return files

        return files

    def _op_search(self, pattern: str, **kwargs) -> List[str]:
        """Recherche les fichiers dont le nom correspond à un motif glob."""
        directory = kwargs.get("directory", ".")
        matches: List[str] = []

        for relative_path in self._op_tree(directory, max_depth=kwargs.get("max_depth", 10)):
            if fnmatch.fnmatch(os.path.basename(relative_path), pattern):
                matches.append(relative_path)
                if len(matches) >= self.max_results:
                    break

        return matches

    def _op_grep(self, text: str, **kwargs) -> List[Dict[str, Any]]:
        """Recherche un texte dans les fichiers d'un répertoire."""
        directory = kwargs.get("directory", ".")
        file_pattern = kwargs.get("file_pattern", "*")
        case_sensitive = bool(kwargs.get("case_sensitive", False))
        needle = text if case_sensitive else text.lower()

        matches: List[Dict[str, Any]] = []
        for relative_path in self._op_search(file_pattern, directory=directory):
            full_path = self._resolve(relative_path)
            try:
                if os.path.getsize(full_path) > self.max_read_bytes:
                    continue
                with open(full_path, "r", encoding=self.encoding, errors="replace") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        haystack = line if case_sensitive else line.lower()
                        if needle in haystack:
                            matches.append({
                                "path": relative_path,
                                "line": line_number,
                                "content": line.rstrip("\n"),
                            })
                            if len(matches) >= self.max_results:
                                return matches
            except OSError as error:
                # Un fichier illisible ne doit pas interrompre la recherche entière
                logger.debug(f"Fichier ignoré pendant la recherche ({relative_path}): {error}")

        return matches

    # ------------------------------------------------------------------
    # Opérations d'écriture
    # ------------------------------------------------------------------
    def _op_write(self, path: str, content: str = "", **kwargs) -> Dict[str, Any]:
        """Écrit un fichier, en écrasant son contenu existant."""
        return self._write_file(path, content, mode="w", **kwargs)

    def _op_append(self, path: str, content: str = "", **kwargs) -> Dict[str, Any]:
        """Ajoute du contenu à la fin d'un fichier."""
        return self._write_file(path, content, mode="a", **kwargs)

    def _op_mkdir(self, path: str, **kwargs) -> Dict[str, Any]:
        """Crée un répertoire, y compris ses parents."""
        target = self._resolve(path)
        os.makedirs(target, exist_ok=True)
        return {"path": self._relative(target), "created": True}

    def _op_delete(self, path: str, **kwargs) -> Dict[str, Any]:
        """Supprime un fichier, ou un répertoire si `recursive` est vrai."""
        target = self._resolve(path)
        if not os.path.exists(target):
            raise FileNotFoundError(f"Chemin introuvable: {path}")

        # La racine elle-même ne peut jamais être supprimée
        if target == self.root:
            raise ValueError("La racine du système de fichiers ne peut pas être supprimée")

        if os.path.isdir(target):
            if not kwargs.get("recursive", False):
                raise IsADirectoryError(
                    f"'{path}' est un répertoire. Passez recursive=True pour le supprimer."
                )
            shutil.rmtree(target)
        else:
            os.remove(target)

        return {"path": self._relative(target), "deleted": True}

    def _op_copy(self, source: str, destination: str, **kwargs) -> Dict[str, Any]:
        """Copie un fichier ou un répertoire."""
        source_path = self._resolve(source)
        destination_path = self._resolve(destination)

        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source introuvable: {source}")

        if os.path.isdir(source_path):
            shutil.copytree(source_path, destination_path, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            shutil.copy2(source_path, destination_path)

        return {
            "source": self._relative(source_path),
            "destination": self._relative(destination_path),
            "copied": True,
        }

    def _op_move(self, source: str, destination: str, **kwargs) -> Dict[str, Any]:
        """Déplace ou renomme un fichier ou un répertoire."""
        source_path = self._resolve(source)
        destination_path = self._resolve(destination)

        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source introuvable: {source}")

        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        shutil.move(source_path, destination_path)

        return {
            "source": self._relative(source_path),
            "destination": self._relative(destination_path),
            "moved": True,
        }

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _write_file(self, path: str, content: str, mode: str, **kwargs) -> Dict[str, Any]:
        """Écrit un contenu dans un fichier, en créant les répertoires manquants."""
        target = self._resolve(path)
        encoding = kwargs.get("encoding", self.encoding)

        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(target, mode, encoding=encoding) as handle:
            handle.write(content)

        return {
            "path": self._relative(target),
            "bytes_written": len(content.encode(encoding)),
            "mode": "append" if mode == "a" else "overwrite",
        }

    def _resolve(self, path: str) -> str:
        """
        Résout un chemin et vérifie qu'il reste sous la racine autorisée.

        Args:
            path: Chemin relatif à la racine, ou absolu

        Returns:
            Le chemin absolu réel

        Raises:
            ValueError: Si le chemin sort de la racine autorisée
        """
        if not isinstance(path, str) or not path.strip():
            raise ValueError("Le chemin doit être une chaîne non vide")

        candidate = path if os.path.isabs(path) else os.path.join(self.root, path)
        # realpath résout les liens symboliques : sans cela, un lien pourrait
        # pointer hors de la racine tout en semblant s'y trouver
        resolved = os.path.realpath(candidate)

        if resolved != self.root and not resolved.startswith(self.root + os.sep):
            raise ValueError(
                f"Accès refusé: '{path}' est hors du répertoire autorisé ({self.root})"
            )

        return resolved

    def _relative(self, absolute_path: str) -> str:
        """Retourne un chemin exprimé relativement à la racine."""
        return os.path.relpath(absolute_path, self.root).replace(os.sep, "/")

    @staticmethod
    def _detect_project_root() -> str:
        """Déduit la racine du projet depuis l'emplacement de ce fichier."""
        # Ce fichier est dans <racine>/src/tools/filesystem/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
