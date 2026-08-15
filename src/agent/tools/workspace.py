"""
Where an autonomous agent is allowed to look, and where it is not.

Every file primitive in this package resolves its path through `resolve()`, and
`resolve()` is the only place that decides. One decision point rather than one
per tool: a guard duplicated in eight functions is a guard that will disagree
with itself the day one copy is fixed.

The rules it enforces, and why each exists:

- **Everything is relative to a declared root.** An absolute path pointing
  outside it is refused, not silently reinterpreted.
- **`..` is resolved before judging, never rejected by spelling.** Checking for
  the two characters would miss `a/b/../../../etc/passwd` written as
  `a/%2e%2e`, and would refuse a legitimate `docs/../src`. What matters is where
  the path lands.
- **Symlinks are followed before judging.** A link inside the repository
  pointing at `/etc` is exactly the escape a naive prefix check misses, which is
  why `os.path.realpath` runs first and the comparison happens after.
- **Some files are out of reach whatever the caller intends** — `.env`, keys,
  databases, `.git` internals. `src/agent/guarded_editor.py` already held that
  list; it is imported from there rather than copied, so the two cannot drift.

This module reads and writes; it decides nothing about *whether* a repair should
happen. That belongs to the policies and the self-healer.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import re
from typing import Any, Dict, List, Optional

from ..guarded_editor import CHEMINS_INTERDITS

#: Taille maximale d'un fichier lu ou écrit par un outil, en octets. Un fichier
#: de code qui dépasse cela n'est plus une correction ciblée ; le lire entier
#: remplirait le contexte d'un agent sans rien lui apprendre.
OCTETS_MAXIMUM = 1_000_000

#: Répertoires que la recherche ne traverse jamais : ils contiennent des
#: artefacts, pas du code, et les parcourir coûte plus que tout le reste.
REPERTOIRES_IGNORES = {
    ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules",
    ".venv", "venv", ".mypy_cache", "htmlcov", ".worktrees",
}


class WorkspaceRefused(PermissionError):
    """Un accès hors du cadre autorisé. Levée, jamais rendue en valeur."""


def repo_root() -> str:
    """La racine du dépôt, déduite de l'emplacement de ce fichier."""
    ici = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(ici))))


def resolve(chemin: str, root: Optional[str] = None) -> str:
    """
    Résout un chemin et refuse tout ce qui sort du cadre.

    Args:
        chemin: Le chemin demandé, relatif à la racine ou absolu.
        root: La racine autorisée. Celle du dépôt par défaut ; un espace de
            travail isolé passe la sienne.

    Returns:
        Le chemin absolu, réel — liens symboliques résolus.

    Raises:
        WorkspaceRefused: Si le chemin sort de la racine ou vise un fichier
            hors de portée. Le message nomme la cause : un refus muet fait
            chercher au mauvais endroit.
    """
    racine = os.path.realpath(root or repo_root())
    demande = str(chemin or "").strip()
    if not demande:
        raise WorkspaceRefused("Aucun chemin demandé.")

    # `realpath` d'abord : c'est lui qui déplie `..` **et** les liens
    # symboliques. Juger la chaîne avant de la résoudre laisserait passer un
    # lien interne pointant au-dehors.
    absolu = os.path.realpath(
        demande if os.path.isabs(demande) else os.path.join(racine, demande)
    )

    if not (absolu == racine or absolu.startswith(racine + os.sep)):
        raise WorkspaceRefused(
            f"« {chemin} » sort de l'espace autorisé ({racine}). Rien, dans une "
            "réparation automatique, ne justifie d'écrire au-dehors."
        )

    minuscule = absolu.lower()
    for interdit in CHEMINS_INTERDITS:
        if interdit in minuscule:
            raise WorkspaceRefused(
                f"« {chemin} » touche un fichier hors de portée ({interdit}). "
                "Aucune approbation ne donne accès à ces fichiers."
            )
    return absolu


def relative(absolu: str, root: Optional[str] = None) -> str:
    """Le chemin d'un fichier relativement à la racine, pour un rapport."""
    return os.path.relpath(absolu, os.path.realpath(root or repo_root()))


def read_file(path: str, root: Optional[str] = None) -> str:
    """
    Lit un fichier du dépôt.

    Args:
        path: Le fichier.
        root: La racine autorisée.

    Returns:
        Son contenu, en UTF-8.

    Raises:
        WorkspaceRefused: Chemin hors cadre, fichier absent, ou trop gros.
    """
    absolu = resolve(path, root)
    if not os.path.isfile(absolu):
        raise WorkspaceRefused(f"« {path} » n'est pas un fichier.")
    taille = os.path.getsize(absolu)
    if taille > OCTETS_MAXIMUM:
        raise WorkspaceRefused(
            f"« {path} » fait {taille} octets, au-delà de {OCTETS_MAXIMUM}. "
            "Le lire entier remplirait le contexte sans rien apprendre."
        )
    with open(absolu, "r", encoding="utf-8", errors="replace") as fichier:
        return fichier.read()


def write_file(path: str, content: str, root: Optional[str] = None) -> Dict[str, Any]:
    """
    Écrit un fichier, dans le cadre autorisé.

    N'est **pas** un portillon : l'autorisation d'écrire est décidée plus haut,
    par les politiques et la validation de correctif. Cette fonction garantit
    seulement *où* l'écriture peut atterrir.

    Args:
        path: Le fichier.
        content: Le contenu complet.
        root: La racine autorisée.

    Returns:
        Le chemin relatif, la taille et l'empreinte du résultat.

    Raises:
        WorkspaceRefused: Chemin hors cadre ou contenu trop gros.
    """
    absolu = resolve(path, root)
    donnees = str(content)
    if len(donnees.encode("utf-8")) > OCTETS_MAXIMUM:
        raise WorkspaceRefused(
            f"Contenu de {len(donnees)} caractères pour « {path} » : au-delà de "
            f"{OCTETS_MAXIMUM} octets, ce n'est plus une correction ciblée."
        )

    os.makedirs(os.path.dirname(absolu), exist_ok=True)
    with open(absolu, "w", encoding="utf-8") as fichier:
        fichier.write(donnees)
    return {
        "path": relative(absolu, root),
        "bytes": len(donnees.encode("utf-8")),
        "sha256": file_hash(path, root),
    }


def list_directory(
    path: str = ".", recursive: bool = False, root: Optional[str] = None
) -> List[str]:
    """
    Liste un répertoire du dépôt.

    Args:
        path: Le répertoire.
        recursive: Descendre dans les sous-répertoires.
        root: La racine autorisée.

    Returns:
        Les chemins relatifs, triés. Les répertoires d'artefacts sont écartés.

    Raises:
        WorkspaceRefused: Chemin hors cadre ou répertoire absent.
    """
    absolu = resolve(path, root)
    if not os.path.isdir(absolu):
        raise WorkspaceRefused(f"« {path} » n'est pas un répertoire.")

    trouves: List[str] = []
    if not recursive:
        for nom in sorted(os.listdir(absolu)):
            if nom in REPERTOIRES_IGNORES:
                continue
            trouves.append(relative(os.path.join(absolu, nom), root))
        return trouves

    for dossier, sous_dossiers, fichiers in os.walk(absolu):
        sous_dossiers[:] = [d for d in sorted(sous_dossiers) if d not in REPERTOIRES_IGNORES]
        for nom in sorted(fichiers):
            trouves.append(relative(os.path.join(dossier, nom), root))
    return trouves


def search_code(
    pattern: str,
    file_extension: str = ".py",
    root: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """
    Cherche une expression dans le code du dépôt.

    Args:
        pattern: L'expression régulière cherchée.
        file_extension: L'extension des fichiers parcourus, ou `*` pour tous.
        root: La racine autorisée.
        limit: Nombre maximal de correspondances rendues.

    Returns:
        Les correspondances : fichier, ligne, texte. Bornées, parce qu'une
        recherche qui rend dix mille lignes n'est pas une recherche.

    Raises:
        WorkspaceRefused: Si l'expression est vide ou invalide.
    """
    if not str(pattern or "").strip():
        raise WorkspaceRefused("Aucune expression cherchée.")
    try:
        expression = re.compile(pattern)
    except re.error as erreur:
        raise WorkspaceRefused(f"Expression invalide : {erreur}") from erreur

    racine = os.path.realpath(root or repo_root())
    resultats: List[Dict[str, Any]] = []
    for dossier, sous_dossiers, fichiers in os.walk(racine):
        sous_dossiers[:] = [d for d in sous_dossiers if d not in REPERTOIRES_IGNORES]
        for nom in sorted(fichiers):
            if file_extension not in ("*", "") and not fnmatch.fnmatch(
                nom, f"*{file_extension}"
            ):
                continue
            absolu = os.path.join(dossier, nom)
            try:
                with open(absolu, "r", encoding="utf-8", errors="replace") as fichier:
                    for numero, ligne in enumerate(fichier, start=1):
                        if expression.search(ligne):
                            resultats.append({
                                "path": os.path.relpath(absolu, racine),
                                "line": numero,
                                "text": ligne.rstrip()[:300],
                            })
                            if len(resultats) >= limit:
                                return resultats
            except OSError:
                # Un fichier illisible est sauté, pas deviné : l'absence de
                # correspondance n'est pas la preuve qu'il n'y en a pas.
                continue
    return resultats


def file_hash(path: str, root: Optional[str] = None) -> str:
    """
    L'empreinte SHA-256 d'un fichier.

    C'est ce qui permet de dire, après coup, qu'un fichier **n'a pas** changé —
    une affirmation qu'aucune date de modification ne peut porter.

    Args:
        path: Le fichier.
        root: La racine autorisée.

    Returns:
        L'empreinte hexadécimale.

    Raises:
        WorkspaceRefused: Chemin hors cadre ou fichier absent.
    """
    absolu = resolve(path, root)
    if not os.path.isfile(absolu):
        raise WorkspaceRefused(f"« {path} » n'est pas un fichier.")
    empreinte = hashlib.sha256()
    with open(absolu, "rb") as fichier:
        for bloc in iter(lambda: fichier.read(65_536), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


def hash_many(paths: List[str], root: Optional[str] = None) -> Dict[str, str]:
    """
    Les empreintes d'un ensemble de fichiers.

    Un fichier absent rend `MISSING` plutôt que d'être omis : disparaître et ne
    jamais avoir existé sont deux événements différents, et c'est précisément la
    différence qu'un contrôle d'intégrité cherche.
    """
    empreintes: Dict[str, str] = {}
    for chemin in paths:
        try:
            empreintes[chemin] = file_hash(chemin, root)
        except WorkspaceRefused:
            empreintes[chemin] = "MISSING"
    return empreintes
