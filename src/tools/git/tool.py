"""
Git tool for GalSen IA.

Exposes the repository state to agents: branch, status, history, diff, remotes.
Read operations are always available; operations that change the repository
require `allow_write` to be enabled.

Two rules from `.claude/rules/git-workflow.md` are enforced in code rather than
left to discipline: pushing to a protected branch and force pushing are refused,
whatever the caller asks.
"""

import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

logger = logging.getLogger(__name__)


class GitNotAvailableError(RuntimeError):
    """Raised when git is missing or the directory is not a repository."""


class GitTool(BaseTool):
    """
    Outil d'accès à un dépôt Git.

    Opérations de lecture : `status`, `current_branch`, `branches`, `log`,
    `diff`, `show`, `remotes`, `is_repository`, `summary`.
    Opérations d'écriture : `add`, `commit`, `create_branch`, `checkout`, `push`.

    Exemple:
        tool.execute("status")
        tool.execute("log", limit=5)
    """

    WRITE_OPERATIONS = frozenset({"add", "commit", "create_branch", "checkout", "push"})

    # Branches sur lesquelles l'outil refuse de pousser
    DEFAULT_PROTECTED_BRANCHES = ("main", "master")

    DEFAULT_TIMEOUT_SECONDS = 30

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil.

        Args:
            config: Configuration avec les clés optionnelles :
                - `repository_path`: chemin du dépôt (par défaut la racine du projet)
                - `allow_write`: autorise les opérations modifiantes (par défaut False)
                - `protected_branches`: branches interdites au push
                - `timeout`: délai maximum d'une commande git
        """
        super().__init__(config)

        self.repository_path = os.path.realpath(
            self.config.get("repository_path") or self._detect_project_root()
        )
        self.allow_write = bool(self.config.get("allow_write", False))
        self.protected_branches = frozenset(
            self.config.get("protected_branches", self.DEFAULT_PROTECTED_BRANCHES)
        )
        self.timeout = int(self.config.get("timeout", self.DEFAULT_TIMEOUT_SECONDS))

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération Git.

        Args:
            *args: L'opération, puis ses arguments éventuels
            **kwargs: Options propres à l'opération

        Returns:
            Résultat de l'opération

        Raises:
            ValueError: Opération inconnue ou écriture interdite
            GitNotAvailableError: Git absent ou répertoire hors dépôt
        """
        if not args:
            raise ValueError("Une opération est requise (status, log, diff, ...)")

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
                f"L'opération '{operation}' modifie le dépôt et l'écriture est désactivée. "
                "Activez 'allow_write' dans la configuration de l'outil."
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
    def _op_is_repository(self, **kwargs) -> bool:
        """Indique si le chemin configuré est un dépôt Git exploitable."""
        try:
            result = self._run_git(["rev-parse", "--is-inside-work-tree"])
            return result["stdout"].strip() == "true"
        except GitNotAvailableError:
            return False

    def _op_current_branch(self, **kwargs) -> str:
        """Retourne le nom de la branche courante."""
        return self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=True)["stdout"].strip()

    def _op_status(self, **kwargs) -> Dict[str, Any]:
        """Retourne l'état du répertoire de travail."""
        # --porcelain garantit un format stable entre versions de git
        output = self._run_git(["status", "--porcelain"], check=True)["stdout"]

        staged: List[str] = []
        modified: List[str] = []
        untracked: List[str] = []

        for line in output.splitlines():
            if len(line) < 3:
                continue
            index_status, worktree_status, path = line[0], line[1], line[3:]

            if index_status == "?" and worktree_status == "?":
                untracked.append(path)
                continue
            if index_status != " ":
                staged.append(path)
            if worktree_status != " ":
                modified.append(path)

        return {
            "branch": self._op_current_branch(),
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
            "clean": not (staged or modified or untracked),
        }

    def _op_branches(self, **kwargs) -> List[str]:
        """Liste les branches locales."""
        output = self._run_git(
            ["for-each-ref", "--format=%(refname:short)", "refs/heads/"], check=True
        )["stdout"]
        return [line.strip() for line in output.splitlines() if line.strip()]

    def _op_log(self, **kwargs) -> List[Dict[str, str]]:
        """Retourne les derniers commits."""
        limit = int(kwargs.get("limit", 10))
        # Un séparateur improbable évite toute ambiguïté avec le contenu des messages
        separator = "\x1f"
        output = self._run_git([
            "log",
            f"-{limit}",
            f"--format=%H{separator}%an{separator}%at{separator}%s",
        ], check=True)["stdout"]

        commits: List[Dict[str, str]] = []
        for line in output.splitlines():
            parts = line.split(separator)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "timestamp": parts[2],
                    "subject": parts[3],
                })
        return commits

    def _op_diff(self, **kwargs) -> Dict[str, Any]:
        """Retourne le diff du répertoire de travail ou de l'index."""
        command = ["diff"]
        if kwargs.get("staged", False):
            command.append("--staged")
        if kwargs.get("stat", False):
            command.append("--stat")
        if kwargs.get("path"):
            command.extend(["--", str(kwargs["path"])])

        output = self._run_git(command, check=True)["stdout"]
        return {"diff": output, "has_changes": bool(output.strip())}

    def _op_show(self, revision: str = "HEAD", **kwargs) -> str:
        """Affiche un commit."""
        return self._run_git(["show", "--stat", str(revision)], check=True)["stdout"]

    def _op_remotes(self, **kwargs) -> Dict[str, str]:
        """Liste les dépôts distants configurés."""
        output = self._run_git(["remote", "-v"], check=True)["stdout"]

        remotes: Dict[str, str] = {}
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                remotes[parts[0]] = parts[1]
        return remotes

    def _op_summary(self, **kwargs) -> Dict[str, Any]:
        """
        Retourne une vue d'ensemble du dépôt.

        Cette opération ne lève pas d'exception quand le répertoire n'est pas un
        dépôt : elle le signale, pour qu'un agent puisse s'en accommoder.
        """
        if not self._op_is_repository():
            return {
                "is_repository": False,
                "reason": "Le répertoire n'est pas un dépôt Git ou git est absent",
                "path": self.repository_path,
            }

        status = self._op_status()
        return {
            "is_repository": True,
            "path": self.repository_path,
            "branch": status["branch"],
            "clean": status["clean"],
            "staged_count": len(status["staged"]),
            "modified_count": len(status["modified"]),
            "untracked_count": len(status["untracked"]),
            "remotes": self._op_remotes(),
            "recent_commits": self._op_log(limit=5),
        }

    # ------------------------------------------------------------------
    # Opérations d'écriture
    # ------------------------------------------------------------------
    def _op_add(self, *paths, **kwargs) -> Dict[str, Any]:
        """Ajoute des fichiers à l'index."""
        if not paths:
            raise ValueError("Au moins un chemin est requis")

        self._run_git(["add", "--", *[str(path) for path in paths]], check=True)
        return {"added": [str(path) for path in paths]}

    def _op_commit(self, message: str, **kwargs) -> Dict[str, Any]:
        """Crée un commit avec les fichiers déjà indexés."""
        if not message or not message.strip():
            raise ValueError("Le message de commit ne peut pas être vide")

        result = self._run_git(["commit", "-m", message], check=True)
        return {
            "committed": True,
            "message": message,
            "output": result["stdout"],
            "hash": self._run_git(["rev-parse", "HEAD"], check=True)["stdout"].strip(),
        }

    def _op_create_branch(self, name: str, **kwargs) -> Dict[str, Any]:
        """Crée une branche et bascule dessus."""
        if not name or not name.strip():
            raise ValueError("Le nom de branche ne peut pas être vide")

        self._run_git(["checkout", "-b", name], check=True)
        return {"branch": name, "created": True}

    def _op_checkout(self, name: str, **kwargs) -> Dict[str, Any]:
        """Bascule sur une branche existante."""
        self._run_git(["checkout", name], check=True)
        return {"branch": name, "checked_out": True}

    def _op_push(self, remote: str = "origin", branch: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Pousse une branche vers un dépôt distant.

        Le push vers une branche protégée et le push forcé sont refusés, quelle
        que soit la demande : ce sont des règles du projet, pas des options.
        """
        target_branch = branch or self._op_current_branch()

        if target_branch in self.protected_branches:
            raise ValueError(
                f"Push refusé: '{target_branch}' est une branche protégée. "
                "Le projet interdit de pousser directement sur cette branche."
            )

        if kwargs.get("force", False):
            raise ValueError("Push forcé refusé: le projet interdit le force push.")

        result = self._run_git(["push", remote, target_branch], check=True)
        return {"pushed": True, "remote": remote, "branch": target_branch, "output": result["stdout"]}

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _run_git(self, arguments: List[str], check: bool = False) -> Dict[str, Any]:
        """
        Exécute une commande git dans le dépôt configuré.

        Args:
            arguments: Arguments passés à git, sans le mot `git`
            check: Lève une exception si git retourne un code d'erreur

        Returns:
            Dictionnaire `{"returncode", "stdout", "stderr"}`

        Raises:
            GitNotAvailableError: Git absent, répertoire hors dépôt, ou erreur si `check`
        """
        try:
            completed = subprocess.run(
                ["git", *arguments],
                cwd=self.repository_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                shell=False,
            )
        except FileNotFoundError as error:
            raise GitNotAvailableError(
                "Git n'est pas installé ou n'est pas dans le PATH"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise GitNotAvailableError(
                f"La commande git a dépassé le délai de {self.timeout}s"
            ) from error

        if check and completed.returncode != 0:
            raise GitNotAvailableError(
                f"Commande git en échec ({' '.join(arguments)}): {completed.stderr.strip()}"
            )

        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    @staticmethod
    def _detect_project_root() -> str:
        """Déduit la racine du projet depuis l'emplacement de ce fichier."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
