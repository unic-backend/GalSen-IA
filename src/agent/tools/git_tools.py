"""
Git for an autonomous repair: isolation first, history never rewritten.

The working tree a person is using is not a scratch pad. Everything an
autonomous repair does happens in a **separate git worktree** under
`.worktrees/auto-patch/<incident>`, which shares the object database but has its
own checkout and its own branch. The user's tree keeps its uncommitted changes,
its branch, and its index, whatever the repair does or fails to do.

That choice decides the rest of the module:

- **Rollback is deletion, not `git reset`.** A failed repair removes its
  worktree and its branch. Nothing in this file ever runs `reset --hard` against
  a tree it did not create — that command destroys work nobody can recover, and
  the tree it would destroy belongs to someone else.
- **No force, ever.** No `push --force`, no rebase of existing history, no
  amend. A repair adds commits on its own branch or it adds nothing.
- **Commits carry the incident.** A commit whose message does not say which
  repair produced it is a commit nobody can trace back to its diagnosis.

Every git call goes through `run_command`, so it inherits the no-shell rule, the
timeout and the audit-friendly result shape.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .commands import CommandRefused, run_command
from .workspace import WorkspaceRefused, repo_root

#: Où vivent les espaces isolés. Sous le dépôt pour rester dans le cadre
#: autorisé, et dans un répertoire que la recherche et les listings ignorent.
RACINE_ESPACES = ".worktrees"

#: Préfixe des branches de réparation. Une branche qui ne le porte pas ne sera
#: jamais supprimée par ce module : effacer la branche de quelqu'un d'autre
#: parce qu'un nom se ressemblait est le genre d'erreur qu'on ne répare pas.
PREFIXE_BRANCHE = "auto-patch/"

#: Ce qu'un identifiant d'incident a le droit d'être. Il finit dans un nom de
#: branche et dans un chemin ; tout le reste est refusé plutôt qu'échappé.
INCIDENT_VALIDE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


class GitRefused(RuntimeError):
    """Une opération git refusée par le harnais, avec sa raison."""


def _git(arguments: List[str], cwd: Optional[str] = None, timeout: int = 120) -> Any:
    """Lance git dans le dépôt, sans shell."""
    return run_command(["git", *arguments], timeout=timeout, cwd=cwd, root=cwd)


def git_status(cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    L'état du dépôt : branche, propreté, fichiers modifiés.

    Args:
        cwd: Le dépôt ou l'espace isolé observé.

    Returns:
        La branche, la liste des fichiers modifiés et la propreté.
    """
    branche = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    etat = _git(["status", "--porcelain"], cwd=cwd)
    lignes = [ligne for ligne in etat.stdout.splitlines() if ligne.strip()]
    return {
        "branch": branche.stdout.strip(),
        "clean": not lignes,
        "changed_files": [ligne[3:].strip() for ligne in lignes],
        "raw": lignes[:200],
    }


def get_changed_files(cwd: Optional[str] = None) -> List[str]:
    """Les fichiers modifiés, suivis ou non."""
    return git_status(cwd)["changed_files"]


def get_diff(cwd: Optional[str] = None, staged: bool = False) -> str:
    """
    Le diff courant, tel que git le produit.

    Args:
        cwd: Le dépôt observé.
        staged: Le diff de l'index plutôt que celui du répertoire de travail.

    Returns:
        Le diff unifié. Vide s'il n'y a rien à montrer — jamais fabriqué.
    """
    arguments = ["diff"] + (["--cached"] if staged else [])
    return _git(arguments, cwd=cwd).stdout


def git_create_branch(branch_name: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    Crée une branche et s'y place.

    Args:
        branch_name: Son nom.
        cwd: Le dépôt.

    Returns:
        La branche créée.

    Raises:
        GitRefused: Si la création échoue — le message de git est transmis tel
            quel, pas résumé.
    """
    resultat = _git(["checkout", "-b", branch_name], cwd=cwd)
    if not resultat.ok:
        raise GitRefused(f"Création de « {branch_name} » refusée : {resultat.stderr.strip()}")
    return {"branch": branch_name}


def git_commit_changes(
    message: str, cwd: Optional[str] = None, paths: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Valide les modifications d'un espace de travail.

    Args:
        message: Le message. Il doit nommer l'incident : un commit dont on ne
            peut pas retrouver le diagnostic est un commit orphelin.
        cwd: L'espace concerné.
        paths: Les chemins à ajouter. Tout ce qui a changé sinon.

    Returns:
        L'empreinte du commit et les fichiers validés.

    Raises:
        GitRefused: Si rien n'a changé, ou si git refuse.
    """
    if not str(message or "").strip():
        raise GitRefused("Un commit sans message ne se relit pas.")

    ajout = _git(["add", "--"] + (paths if paths else ["."]), cwd=cwd)
    if not ajout.ok:
        raise GitRefused(f"`git add` a échoué : {ajout.stderr.strip()}")

    prevu = _git(["diff", "--cached", "--name-only"], cwd=cwd).stdout.split()
    if not prevu:
        raise GitRefused("Rien à valider : aucun fichier n'a changé.")

    # `-m` et jamais `--amend` : une réparation ajoute un commit, elle ne
    # réécrit pas ce qui existait avant elle.
    commit = _git(["commit", "-m", message], cwd=cwd, timeout=180)
    if not commit.ok:
        raise GitRefused(f"`git commit` a échoué : {commit.stderr.strip()}")

    empreinte = _git(["rev-parse", "HEAD"], cwd=cwd).stdout.strip()
    return {"commit": empreinte, "files": prevu, "message": message}


@dataclass
class IsolatedWorkspace:
    """
    Un espace de travail isolé, avec sa branche.

    Attributes:
        incident_id: L'incident qui l'a fait naître.
        path: Le répertoire de la copie de travail.
        branch: La branche créée pour la réparation.
        base_commit: Le commit d'où elle part.
    """

    incident_id: str
    path: str
    branch: str
    base_commit: str

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "incident_id": self.incident_id,
            "path": self.path,
            "branch": self.branch,
            "base_commit": self.base_commit,
        }


def create_isolated_workspace(
    incident_id: str, root: Optional[str] = None
) -> IsolatedWorkspace:
    """
    Ouvre un espace de travail isolé pour une réparation.

    L'arbre de travail de l'utilisateur n'est **pas** touché : `git worktree`
    crée une seconde copie, avec sa propre branche, partageant la base d'objets.
    Ses modifications non validées, sa branche et son index restent ce qu'ils
    étaient, quoi que la réparation fasse ou rate.

    Args:
        incident_id: L'identifiant de l'incident. Il finit dans un nom de
            branche et dans un chemin, donc il est **validé**, pas échappé.
        root: Le dépôt d'origine.

    Returns:
        L'espace ouvert.

    Raises:
        GitRefused: Identifiant invalide, espace déjà ouvert, ou refus de git.
    """
    if not INCIDENT_VALIDE.match(str(incident_id or "")):
        raise GitRefused(
            f"Identifiant d'incident « {incident_id} » invalide. Il devient un "
            "nom de branche et un chemin : ce qui n'est pas alphanumérique, "
            "point, tiret ou souligné est refusé plutôt qu'échappé."
        )

    depot = os.path.realpath(root or repo_root())
    destination = os.path.join(depot, RACINE_ESPACES, incident_id)
    branche = f"{PREFIXE_BRANCHE}{incident_id}"

    if os.path.exists(destination):
        raise GitRefused(
            f"Un espace existe déjà pour « {incident_id} » ({destination}). "
            "Le réutiliser mêlerait deux réparations dans un même arbre."
        )

    base = _git(["rev-parse", "HEAD"], cwd=depot)
    if not base.ok:
        raise GitRefused(f"Dépôt illisible : {base.stderr.strip()}")

    os.makedirs(os.path.dirname(destination), exist_ok=True)
    ouverture = _git(
        ["worktree", "add", "-b", branche, destination, "HEAD"], cwd=depot, timeout=300,
    )
    if not ouverture.ok:
        raise GitRefused(
            f"Espace isolé impossible pour « {incident_id} » : {ouverture.stderr.strip()}"
        )

    return IsolatedWorkspace(
        incident_id=str(incident_id), path=destination, branch=branche,
        base_commit=base.stdout.strip(),
    )


def destroy_isolated_workspace(
    espace: IsolatedWorkspace, root: Optional[str] = None, delete_branch: bool = True
) -> Dict[str, Any]:
    """
    Détruit un espace isolé, et sa branche si elle est bien une branche de
    réparation.

    C'est **tout** ce que veut dire « annuler » ici : rien n'est réinitialisé
    dans l'arbre de l'utilisateur, parce que rien n'y a jamais été écrit.

    Args:
        espace: L'espace à détruire.
        root: Le dépôt d'origine.
        delete_branch: Supprimer aussi la branche.

    Returns:
        Ce qui a été détruit, et ce qui ne l'a pas été.
    """
    depot = os.path.realpath(root or repo_root())
    retire = _git(["worktree", "remove", "--force", espace.path], cwd=depot, timeout=300)

    # `git worktree remove` peut échouer si le répertoire a déjà disparu ; dans
    # ce cas seul le registre reste à nettoyer, et le dire vaut mieux que de
    # laisser une entrée fantôme.
    if not retire.ok and os.path.exists(espace.path):
        shutil.rmtree(espace.path, ignore_errors=True)
    _git(["worktree", "prune"], cwd=depot)

    branche_supprimee = False
    if delete_branch and espace.branch.startswith(PREFIXE_BRANCHE):
        # Le préfixe est vérifié : supprimer la branche de quelqu'un d'autre
        # parce qu'un nom se ressemblait est une erreur qu'on ne répare pas.
        branche_supprimee = _git(["branch", "-D", espace.branch], cwd=depot).ok

    return {
        "incident_id": espace.incident_id,
        "worktree_removed": not os.path.exists(espace.path),
        "branch_deleted": branche_supprimee,
        "detail": retire.stderr.strip()[:300],
    }


def list_repair_workspaces(root: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Les espaces de réparation ouverts, y compris ceux que personne n'a fermés.

    Un espace orphelin est une trace de réparation interrompue : le nommer est
    la seule façon qu'il soit nettoyé un jour.
    """
    depot = os.path.realpath(root or repo_root())
    liste = _git(["worktree", "list", "--porcelain"], cwd=depot)

    espaces: List[Dict[str, Any]] = []
    courant: Dict[str, Any] = {}
    for ligne in liste.stdout.splitlines():
        if ligne.startswith("worktree "):
            courant = {"path": ligne.split(" ", 1)[1]}
        elif ligne.startswith("branch "):
            courant["branch"] = ligne.split(" ", 1)[1].replace("refs/heads/", "")
            if RACINE_ESPACES in courant["path"]:
                espaces.append(courant)
        elif not ligne.strip() and courant:
            courant = {}
    return espaces


def restore_file_from_snapshot(
    path: str, snapshot: Optional[str], cwd: Optional[str] = None
) -> Dict[str, Any]:
    """
    Remet un fichier dans l'état où un instantané l'avait trouvé.

    Args:
        path: Le fichier.
        snapshot: Son contenu d'origine, ou `None` s'il n'existait pas — auquel
            cas il est supprimé, ce qui est la seule restauration correcte.
        cwd: L'espace concerné.

    Returns:
        Ce qui a été fait.

    Raises:
        WorkspaceRefused: Chemin hors cadre.
    """
    from .workspace import resolve, write_file

    absolu = resolve(path, cwd)
    if snapshot is None:
        if os.path.exists(absolu):
            os.remove(absolu)
        return {"path": path, "restored": "deleted"}
    write_file(path, snapshot, root=cwd)
    return {"path": path, "restored": "content"}


__all__ = [
    "GitRefused",
    "INCIDENT_VALIDE",
    "IsolatedWorkspace",
    "PREFIXE_BRANCHE",
    "RACINE_ESPACES",
    "create_isolated_workspace",
    "destroy_isolated_workspace",
    "get_changed_files",
    "get_diff",
    "git_commit_changes",
    "git_create_branch",
    "git_status",
    "list_repair_workspaces",
    "restore_file_from_snapshot",
]

# `CommandRefused` et `WorkspaceRefused` remontent telles quelles : les
# renommer ici ferait croire à deux familles d'erreurs là où il n'y en a qu'une.
_ERREURS_TRANSMISES = (CommandRefused, WorkspaceRefused)
