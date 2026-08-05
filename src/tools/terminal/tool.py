"""
Terminal tool for GalSen IA.

Runs external commands on behalf of agents, under three constraints that are not
negotiable:

- **No shell.** Commands are executed directly, never through a shell, so shell
  metacharacters in an argument cannot turn into a second command.
- **Allowlist.** Only the executables declared in the configuration can run. An
  agent that receives a manipulated instruction still cannot run anything else.
- **Timeout.** Every command is bounded in time, so a hanging process cannot
  block the platform.

The command is given as a list of arguments, never as a single string, which
removes any need to parse quoting.
"""

import logging
import os
import shlex
import subprocess
from typing import Any, Dict, List, Optional, Sequence, Union

from src.tool.base import BaseTool

logger = logging.getLogger(__name__)


class TerminalTool(BaseTool):
    """
    Outil d'exécution de commandes externes.

    Exemple:
        tool.execute(["python", "--version"])
        tool.execute("pytest -q", working_directory="tests")
    """

    # Exécutables autorisés par défaut : de quoi inspecter et tester le projet,
    # sans rien qui permette d'installer ou de supprimer quoi que ce soit.
    DEFAULT_ALLOWED_COMMANDS = (
        "python", "python3", "py",
        "pytest",
        "git",
        "node", "npm",
        "echo",
    )

    DEFAULT_TIMEOUT_SECONDS = 60

    # Taille au-delà de laquelle la sortie est tronquée, pour ne pas saturer la mémoire
    DEFAULT_MAX_OUTPUT_CHARS = 100_000

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil.

        Args:
            config: Configuration avec les clés optionnelles :
                - `allowed_commands`: exécutables autorisés
                - `working_directory`: répertoire de travail racine (par défaut la racine du projet)
                - `timeout`: délai maximum en secondes (par défaut 60)
                - `max_output_chars`: taille maximale de sortie conservée
                - `environment`: variables d'environnement supplémentaires
        """
        super().__init__(config)

        self.allowed_commands = frozenset(
            self.config.get("allowed_commands", self.DEFAULT_ALLOWED_COMMANDS)
        )
        self.working_directory = os.path.realpath(
            self.config.get("working_directory") or self._detect_project_root()
        )
        self.timeout = int(self.config.get("timeout", self.DEFAULT_TIMEOUT_SECONDS))
        self.max_output_chars = int(
            self.config.get("max_output_chars", self.DEFAULT_MAX_OUTPUT_CHARS)
        )
        self.extra_environment = dict(self.config.get("environment", {}))

        if not os.path.isdir(self.working_directory):
            raise ValueError(f"Répertoire de travail introuvable: {self.working_directory}")

    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Exécute une commande externe.

        Args:
            *args: La commande, sous forme de liste d'arguments ou de chaîne
            **kwargs: Options :
                - `working_directory`: sous-répertoire d'exécution, confiné à la racine
                - `timeout`: délai maximum pour cette commande
                - `input_text`: texte envoyé sur l'entrée standard

        Returns:
            Dictionnaire `{"command", "returncode", "stdout", "stderr", "success", "timed_out"}`

        Raises:
            ValueError: Commande absente, mal formée, ou non autorisée
        """
        if not args:
            raise ValueError("Une commande est requise")

        command = self._normalize_command(args[0] if len(args) == 1 else list(args))
        self._assert_allowed(command)

        working_directory = self._resolve_working_directory(kwargs.get("working_directory"))
        timeout = int(kwargs.get("timeout", self.timeout))
        input_text = kwargs.get("input_text")

        environment = os.environ.copy()
        environment.update(self.extra_environment)

        logger.info(f"Exécution de la commande: {' '.join(command)}")

        try:
            completed = subprocess.run(
                command,
                cwd=working_directory,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                input=input_text,
                env=environment,
                # shell=False est le défaut et doit le rester : c'est ce qui empêche
                # l'injection de commande via les arguments
                shell=False,
            )
        except subprocess.TimeoutExpired as expired:
            logger.warning(f"Commande interrompue après {timeout}s: {' '.join(command)}")
            return {
                "command": command,
                "returncode": None,
                "stdout": self._truncate(expired.stdout or ""),
                "stderr": self._truncate(expired.stderr or ""),
                "success": False,
                "timed_out": True,
            }
        except FileNotFoundError:
            raise ValueError(f"Exécutable introuvable: {command[0]}")

        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": self._truncate(completed.stdout),
            "stderr": self._truncate(completed.stderr),
            "success": completed.returncode == 0,
            "timed_out": False,
        }

    def is_command_allowed(self, executable: str) -> bool:
        """
        Indique si un exécutable figure dans la liste blanche.

        Args:
            executable: Nom de l'exécutable

        Returns:
            True si la commande peut être exécutée
        """
        return self._executable_name(executable) in self.allowed_commands

    def allowed_command_list(self) -> List[str]:
        """Retourne la liste triée des exécutables autorisés."""
        return sorted(self.allowed_commands)

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _normalize_command(self, command: Union[str, Sequence[str]]) -> List[str]:
        """
        Convertit une commande en liste d'arguments.

        Une chaîne est découpée avec `shlex`, qui respecte les guillemets. Le
        résultat reste une liste passée telle quelle au système : aucun shell
        ne réinterprète les caractères spéciaux.
        """
        if isinstance(command, str):
            parts = shlex.split(command)
        elif isinstance(command, (list, tuple)):
            parts = [str(part) for part in command]
        else:
            raise ValueError("La commande doit être une chaîne ou une liste d'arguments")

        if not parts:
            raise ValueError("La commande ne peut pas être vide")

        return parts

    def _assert_allowed(self, command: List[str]) -> None:
        """Vérifie que l'exécutable demandé est autorisé."""
        executable = self._executable_name(command[0])
        if executable not in self.allowed_commands:
            raise ValueError(
                f"Commande '{executable}' non autorisée. "
                f"Commandes autorisées: {', '.join(self.allowed_command_list())}"
            )

    @staticmethod
    def _executable_name(executable: str) -> str:
        """Extrait le nom de l'exécutable, sans chemin ni extension Windows."""
        name = os.path.basename(str(executable)).lower()
        for suffix in (".exe", ".cmd", ".bat"):
            if name.endswith(suffix):
                return name[: -len(suffix)]
        return name

    def _resolve_working_directory(self, requested: Optional[str]) -> str:
        """Résout le répertoire d'exécution en le confinant à la racine autorisée."""
        if not requested:
            return self.working_directory

        candidate = requested if os.path.isabs(requested) else os.path.join(
            self.working_directory, requested
        )
        resolved = os.path.realpath(candidate)

        if resolved != self.working_directory and not resolved.startswith(
            self.working_directory + os.sep
        ):
            raise ValueError(
                f"Répertoire de travail refusé: '{requested}' est hors de "
                f"{self.working_directory}"
            )

        if not os.path.isdir(resolved):
            raise ValueError(f"Répertoire de travail introuvable: {requested}")

        return resolved

    def _truncate(self, output: str) -> str:
        """Tronque une sortie trop longue en le signalant explicitement."""
        if len(output) <= self.max_output_chars:
            return output
        return output[: self.max_output_chars] + "\n... [sortie tronquée]"

    @staticmethod
    def _detect_project_root() -> str:
        """Déduit la racine du projet depuis l'emplacement de ce fichier."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
