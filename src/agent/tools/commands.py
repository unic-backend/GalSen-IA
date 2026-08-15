"""
Running a command without handing over the machine.

The rule that shapes this module: **a command is a list, never a string.**
`subprocess.run("pytest " + cible, shell=True)` turns any value that reaches
`cible` into shell syntax — and in a self-healing engine, the values that reach
here come from tracebacks, which come from anywhere. Passing a list removes the
shell from the path entirely, so `; rm -rf /` is an argument nobody can execute.

Everything else is a bound. A repair that hangs is worse than a repair that
fails: the failure is reported, the hang is not. So every command carries a
timeout, an output ceiling, a working directory inside the repository, and an
environment it did not choose.

What this module deliberately does **not** do: decide whether a command is
allowed. It runs what it is given, safely. The allow-list lives with the
policies, because the answer depends on the repair, not on the mechanics.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .workspace import WorkspaceRefused, repo_root, resolve

#: Durée maximale d'une commande, en secondes. Au-delà, elle est tuée : une
#: réparation qui pend est pire qu'une réparation qui échoue, parce que l'échec
#: se rapporte et le blocage non.
SECONDES_MAXIMUM = 900

#: Sortie conservée, en caractères, pour chaque flux. Une suite de tests
#: bavarde produit des mégaoctets ; les garder en mémoire ferait tomber le
#: processus qui observe, pas celui qui parle.
SORTIE_MAXIMUM = 40_000

#: Exécutables que le harnais lance lui-même. Ce n'est pas une frontière de
#: sécurité — la frontière est l'absence de shell — mais un garde-fou contre
#: l'erreur de programmation qui passerait une commande inattendue.
EXECUTABLES_CONNUS = {"python", "python3", sys.executable, "git", "ruff", "pytest"}


class CommandRefused(ValueError):
    """Une commande qui ne peut pas être lancée telle qu'elle est écrite."""


@dataclass
class CommandResult:
    """
    Ce qu'une commande a produit.

    Attributes:
        command: La commande, telle que lancée.
        returncode: Son code de sortie ; `None` si elle a été tuée.
        stdout: Sortie standard, tronquée à `SORTIE_MAXIMUM`.
        stderr: Sortie d'erreur, tronquée de même.
        elapsed_ms: Durée mesurée.
        timed_out: Vrai si le délai a été atteint.
        truncated: Les flux dont la sortie a été tronquée — dit, jamais tu.
    """

    command: List[str]
    returncode: Optional[int]
    stdout: str = ""
    stderr: str = ""
    elapsed_ms: float = 0.0
    timed_out: bool = False
    truncated: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Vrai pour un succès franc : code 0 et pas de délai atteint."""
        return self.returncode == 0 and not self.timed_out

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "command": list(self.command),
            "returncode": self.returncode,
            "ok": self.ok,
            "timed_out": self.timed_out,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "truncated": list(self.truncated),
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def _tronquer(texte: str) -> tuple:
    """Tronque un flux en disant qu'il l'a été."""
    if len(texte) <= SORTIE_MAXIMUM:
        return texte, False
    garde = texte[:SORTIE_MAXIMUM]
    return (
        garde + f"\n[… tronqué : {len(texte) - SORTIE_MAXIMUM} caractères de plus]",
        True,
    )


def run_command(
    cmd: Sequence[str],
    timeout: int = 60,
    cwd: Optional[str] = None,
    root: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> CommandResult:
    """
    Lance une commande, sans shell, dans le dépôt.

    Args:
        cmd: La commande, **en liste**. Une chaîne est refusée : c'est elle qui
            transformerait un message d'erreur en syntaxe shell.
        timeout: Délai en secondes, plafonné à `SECONDES_MAXIMUM`.
        cwd: Répertoire de travail, dans le cadre autorisé.
        root: La racine autorisée.
        env: Variables ajoutées à un environnement minimal.

    Returns:
        Le résultat, y compris en cas d'échec ou de délai atteint.

    Raises:
        CommandRefused: Commande vide, passée en chaîne, ou exécutable inconnu.
        WorkspaceRefused: Répertoire de travail hors cadre.
    """
    if isinstance(cmd, (str, bytes)):
        raise CommandRefused(
            "Une commande se passe en **liste**, jamais en chaîne. Une chaîne "
            "serait interprétée par un shell, et les valeurs qui arrivent ici "
            "viennent de traces d'exécution — c'est-à-dire de n'importe où."
        )
    arguments = [str(a) for a in cmd]
    if not arguments:
        raise CommandRefused("Commande vide.")

    executable = os.path.basename(arguments[0])
    if executable not in {os.path.basename(e) for e in EXECUTABLES_CONNUS}:
        raise CommandRefused(
            f"Exécutable « {executable} » hors de la liste du harnais. Le "
            "harnais lance ses propres outils ; il n'est pas un interpréteur "
            "de commandes."
        )

    repertoire = resolve(cwd, root) if cwd else os.path.realpath(root or repo_root())
    if not os.path.isdir(repertoire):
        raise WorkspaceRefused(f"« {cwd} » n'est pas un répertoire.")

    delai = max(1, min(int(timeout), SECONDES_MAXIMUM))

    # Un environnement choisi, pas hérité : les secrets présents dans le
    # processus parent n'ont aucune raison d'atteindre un sous-processus lancé
    # par une réparation automatique.
    environnement = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", repertoire),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "PYTHONPATH": repertoire,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if env:
        environnement.update({str(c): str(v) for c, v in env.items()})

    depart = time.monotonic()
    try:
        acheve = subprocess.run(  # noqa: S603 - liste, jamais de shell
            arguments, cwd=repertoire, env=environnement, timeout=delai,
            capture_output=True, text=True, check=False,
        )
    except subprocess.TimeoutExpired as expire:
        sortie, coupee = _tronquer(expire.stdout or "" if isinstance(expire.stdout, str) else "")
        return CommandResult(
            command=arguments, returncode=None, stdout=sortie,
            stderr=f"Délai de {delai} s atteint : la commande a été tuée.",
            elapsed_ms=(time.monotonic() - depart) * 1000,
            timed_out=True, truncated=["stdout"] if coupee else [],
        )

    sortie, sortie_coupee = _tronquer(acheve.stdout or "")
    erreur, erreur_coupee = _tronquer(acheve.stderr or "")
    return CommandResult(
        command=arguments, returncode=acheve.returncode,
        stdout=sortie, stderr=erreur,
        elapsed_ms=(time.monotonic() - depart) * 1000,
        truncated=([f for f, c in (("stdout", sortie_coupee), ("stderr", erreur_coupee)) if c]),
    )


def run_test_suite(
    target: Optional[str] = None,
    timeout: int = SECONDES_MAXIMUM,
    cwd: Optional[str] = None,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Lance la suite de tests, ou une partie.

    Args:
        target: Le fichier ou le motif à passer à pytest. Tout le dépôt sinon.
        timeout: Délai.
        cwd: Où lancer — l'espace isolé d'une réparation, par exemple.
        root: La racine autorisée.

    Returns:
        Le résultat, plus les compteurs **relus dans la sortie** : un code de
        sortie nul ne dit pas si des tests ont été exécutés, et une suite qui
        n'en collecte aucun sort à zéro.
    """
    commande = [sys.executable, "-m", "pytest", "-q"]
    if target:
        # La cible est résolue comme un chemin : elle vient parfois d'un
        # diagnostic, donc d'une trace, donc de nulle part de sûr.
        commande.append(resolve(target, root or cwd))

    resultat = run_command(commande, timeout=timeout, cwd=cwd, root=root or cwd)
    compteurs = parse_pytest_counts(resultat.stdout + "\n" + resultat.stderr)
    return {
        **resultat.as_dict(),
        **compteurs,
        # Un code 0 sans test collecté n'est pas un succès : c'est une suite qui
        # n'a rien vérifié, et c'est exactement ce qu'une réparation ratée
        # produit quand elle casse la collecte.
        "meaningful": resultat.ok and compteurs["passed"] > 0,
    }


def parse_pytest_counts(sortie: str) -> Dict[str, int]:
    """
    Relit les compteurs dans la sortie de pytest.

    Returns:
        `passed`, `failed`, `errors`, `skipped`. Zéro quand la ligne de résumé
        est absente — et `meaningful` s'appuie dessus pour ne pas prendre une
        collecte vide pour une réussite.
    """
    import re

    compteurs = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for nom in list(compteurs):
        trouve = re.findall(rf"(\d+) {nom[:-1] if nom == 'errors' else nom}\b", sortie)
        if trouve:
            compteurs[nom] = int(trouve[-1])
    return compteurs


def run_ruff(
    target: str = ".", timeout: int = 300, cwd: Optional[str] = None,
    root: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Lance `ruff check`, sans jamais l'affaiblir.

    Aucune option n'est ajoutée ici : `--fix`, `--no-cache` ou une exclusion
    passée par le harnais changerait ce que la porte mesure, et une porte dont
    on choisit la sévérité au moment de la franchir n'est pas une porte.
    """
    resultat = run_command(
        ["ruff", "check", target], timeout=timeout, cwd=cwd, root=root or cwd,
    )
    return {**resultat.as_dict(), "clean": resultat.ok}
