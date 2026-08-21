"""
Espace de travail et limites d'exécution du Coding Engine (ADR-028).

Les trois moteurs intégrés écrivent des fichiers et lancent des commandes. Ce
module est la frontière qu'ils ne franchissent pas.

Il fait trois choses, et chacune répond à une façon précise dont une exécution
peut mal tourner :

1. **Confiner.** Un chemin est résolu — liens symboliques compris — et refusé
   s'il sort de l'espace confié. Sans cela, une instruction mal comprise ou mal
   intentionnée touche `~/.ssh`.
2. **Filtrer l'environnement.** Un sous-processus hérite de tout par défaut :
   `GALSEN_API_KEYS`, `GITHUB_TOKEN`, les clés du fournisseur. On part d'une
   liste blanche et on n'ajoute que ce que le moteur doit connaître.
3. **Constater les changements.** Ce que le moteur *dit* avoir fait et ce qu'il
   a fait sont deux choses ; seul le second est rapporté, mesuré sur le disque.

Ce que ce module **ne** fait pas, et il faut le savoir : il n'isole pas le
processus du reste de la machine. Un sous-processus lancé ici peut lire ce que
l'utilisateur qui lance GalSen IA peut lire. La seule isolation réelle est un
conteneur — d'où `GALSEN_CODING_REQUIRE_CONTAINER`, qui refuse toute exécution
hors conteneur quand l'exploitant l'exige. C'est écrit dans ADR-028, section
*Limites connues*.

## Le point 1 ne tenait pas ce qu'il promettait

Le confinement ci-dessus est **relatif** : il empêche de sortir de l'espace de
travail, jamais de choisir `~/.ssh` comme espace de travail. `resolve_workspace`
acceptait n'importe quel dossier existant de l'hôte, et le paragraphe qui
promettait de protéger `~/.ssh` décrivait donc une garantie que le module
n'avait pas.

D'où les **racines déclarées** : `GALSEN_CODING_WORKSPACE_ROOTS` énumère les
dossiers sous lesquels un espace de travail peut se trouver. Rien en dehors
n'est acceptable, et **une variable absente ne vaut pas « tout est permis »** :
elle vaut « personne n'a déclaré où ce moteur peut écrire », et un moteur qui
écrit là où personne ne l'a autorisé est le défaut qu'on corrige ici. Le refus
nomme la variable — une capacité inachevée rapporte son état, elle ne se replie
pas sur un défaut plausible.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.coding_engine.types import FileChange
from src.sandbox.policy import SandboxPolicy

# Variables transmises à un sous-processus. Tout le reste est retiré : un
# moteur de codage n'a aucune raison de voir les clés de la plateforme.
VARIABLES_AUTORISEES = frozenset({
    "PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "TMPDIR", "TEMP", "TMP",
    "USER", "LOGNAME", "SHELL", "PWD",
    # Windows : sans elles, la plupart des exécutables ne démarrent pas.
    "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "PATHEXT", "USERPROFILE", "APPDATA",
    "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMDATA", "WINDIR",
})

# Motifs refusés dans une instruction avant même de lancer un moteur. La liste
# est courte et volontairement grossière : elle attrape la catastrophe évidente,
# elle ne prétend pas être une analyse sémantique.
# Les motifs sont insensibles à la casse : `-R` et `-r` désignent le même
# geste, et un filtre qui ne verrait que l'un des deux serait une passoire.
MOTIFS_DESTRUCTEURS = (
    (re.compile(r"\brm\s+-[a-z]*[rf][a-z]*\s+/(?:\s|$)", re.I), "suppression de la racine"),
    (re.compile(r"\bmkfs(\.\w+)?\b", re.I), "formatage de système de fichiers"),
    (re.compile(r"\bdd\s+[^\n]*\bof=/dev/", re.I), "écriture directe sur un périphérique"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:"), "bombe à fourche"),
    (re.compile(r"\bchmod\s+-[a-z]*r[a-z]*\s+777\s+/(?:\s|$)", re.I), "ouverture des droits sur la racine"),
    (re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b", re.I), "arrêt de la machine"),
)

# Actions qui ne sont pas destructrices mais qui sortent de l'espace de travail :
# elles ne sont pas refusées, elles passent par l'approbation humaine.
MOTIFS_A_APPROUVER = (
    (re.compile(r"\bgit\s+push\b", re.I), "publication distante"),
    (re.compile(r"\bgit\s+remote\s+(add|set-url)\b", re.I), "changement de dépôt distant"),
    (re.compile(r"\b(npm|pip|poetry|cargo)\s+publish\b", re.I), "publication de paquet"),
    (re.compile(r"\bdocker\s+push\b", re.I), "publication d'image"),
    (re.compile(r"\.env\b|\bsecrets?\b|\bcredentials?\b|\bid_rsa\b", re.I), "accès à des secrets"),
    (re.compile(r"\bproduction\b|\bprod\b", re.I), "configuration de production"),
    (re.compile(r"\brm\s+-[a-z]*r", re.I), "suppression récursive"),
)

VARIABLE_CONTENEUR = "GALSEN_CODING_REQUIRE_CONTAINER"

#: Les dossiers sous lesquels un espace de travail peut se trouver, déclarés par
#: l'exploitant et séparés comme un `PATH` (`:` sous Unix, `;` sous Windows).
VARIABLE_RACINES = "GALSEN_CODING_WORKSPACE_ROOTS"


class WorkspaceError(ValueError):
    """Espace de travail inutilisable, ou chemin qui en sort."""


@dataclass(frozen=True)
class SafetyVerdict:
    """
    Ce que l'analyse d'une instruction a conclu.

    Attributes:
        allowed: Faux si l'instruction est refusée sans appel.
        needs_approval: Vrai si un humain doit se prononcer avant.
        reasons: Les motifs relevés, en clair.
    """

    allowed: bool
    needs_approval: bool
    reasons: List[str]


def declared_roots() -> Tuple[List[Path], List[str]]:
    """
    Lit les racines déclarées par l'exploitant.

    La lecture se fait à chaque appel, comme pour `container_required()` : une
    politique mise en cache à l'import ne se corrige plus sans redémarrage, et
    c'est celle-là qu'on oublie d'appliquer.

    Returns:
        Les racines utilisables, résolues, et les entrées écartées avec leur
        raison. Une entrée fautive n'est **pas** silencieusement ignorée : une
        faute de frappe qui rétrécit la politique sans le dire se paye à
        l'exécution suivante, sur un refus qu'on ne s'explique pas.
    """
    brut = os.environ.get(VARIABLE_RACINES, "")
    racines: List[Path] = []
    ecartees: List[str] = []
    for entree in brut.split(os.pathsep):
        entree = entree.strip()
        if not entree:
            continue
        chemin = Path(entree).expanduser().resolve()
        if not chemin.is_dir():
            ecartees.append(f"« {entree} » : ce n'est pas un dossier existant")
            continue
        racines.append(chemin)
    return racines, ecartees


def _hors_des_racines(resolu: Path) -> str:
    """
    Dit pourquoi un espace de travail n'est pas déclaré, ou `""` s'il l'est.

    Args:
        resolu: L'espace de travail, déjà résolu.

    Returns:
        Le motif du refus, en clair, ou une chaîne vide quand le chemin tombe
        sous une racine déclarée.
    """
    racines, ecartees = declared_roots()
    detail = (" Entrées écartées de la déclaration : "
              + " ; ".join(ecartees) + ".") if ecartees else ""

    if not racines:
        return (
            f"Aucune racine d'espace de travail n'est déclarée. Renseignez "
            f"« {VARIABLE_RACINES} » avec les dossiers où ce moteur a le droit "
            f"d'écrire, séparés par « {os.pathsep} ». Une variable absente ne "
            f"veut pas dire « tout l'hôte » : elle veut dire que personne n'a "
            f"dit où ce moteur peut travailler.{detail}"
        )

    if any(resolu == racine or racine in resolu.parents for racine in racines):
        return ""

    return (
        f"« {resolu} » ne se trouve sous aucune racine déclarée "
        f"({', '.join(str(racine) for racine in racines)}). Le confinement des "
        f"chemins empêche de sortir de l'espace de travail ; il n'empêche pas "
        f"d'en choisir un mauvais, et c'est ce que cette borne fait.{detail}"
    )


def resolve_workspace(path: Any) -> Path:
    """
    Vérifie qu'un espace de travail est utilisable et retourne son chemin résolu.

    Args:
        path: Le dossier confié.

    Returns:
        Le chemin absolu, liens symboliques résolus.

    Raises:
        WorkspaceError: Chemin vide, inexistant, qui n'est pas un dossier, ou
            qui ne tombe sous aucune racine déclarée par l'exploitant.

    Note:
        L'existence est contrôlée **avant** la déclaration, à dessein : le
        contrôle d'accès a déjà eu lieu plus haut (`authorization.py`), et
        « ce dossier n'existe pas » répare une faute de frappe là où « hors
        des racines » enverrait chercher un problème de configuration.
    """
    if not path:
        raise WorkspaceError("Aucun espace de travail fourni.")
    resolu = Path(path).expanduser().resolve()
    if not resolu.exists():
        raise WorkspaceError(f"« {resolu} » n'existe pas.")
    if not resolu.is_dir():
        raise WorkspaceError(f"« {resolu} » n'est pas un dossier.")
    refus = _hors_des_racines(resolu)
    if refus:
        raise WorkspaceError(refus)
    return resolu


def confine(workspace: Path, relative_path: str) -> Path:
    """
    Résout un chemin sous l'espace de travail et refuse tout ce qui en sort.

    Args:
        workspace: L'espace de travail, déjà résolu.
        relative_path: Chemin déclaré par l'appelant ou par un moteur.

    Returns:
        Le chemin absolu, garanti sous l'espace de travail.

    Raises:
        WorkspaceError: Chemin absolu, remontée par `..`, ou lien symbolique
            menant dehors.
    """
    if not relative_path:
        raise WorkspaceError("Chemin vide.")
    if os.path.isabs(relative_path) or relative_path.startswith("~"):
        raise WorkspaceError(f"« {relative_path} » : chemin absolu refusé.")
    resolu = (workspace / relative_path).resolve()
    if resolu != workspace and workspace not in resolu.parents:
        raise WorkspaceError(f"« {relative_path} » sort de l'espace de travail.")
    return resolu


def inspect_instruction(instruction: str, allow_push: bool = False) -> SafetyVerdict:
    """
    Examine une instruction avant de la confier à un moteur.

    L'analyse est textuelle et grossière : elle attrape la catastrophe évidente
    et les gestes qui sortent de l'espace de travail. Elle ne remplace pas le
    confinement, elle vient avant.

    Args:
        instruction: Ce qui est demandé.
        allow_push: Si vrai, une publication distante n'exige plus d'approbation
            — l'appelant l'a déjà déclarée voulue.

    Returns:
        Le verdict, avec les motifs relevés.
    """
    # La casse n'est plus retirée : les motifs sont eux-mêmes insensibles.
    texte = instruction or ""
    refus = [motif for regle, motif in MOTIFS_DESTRUCTEURS if regle.search(texte)]
    if refus:
        return SafetyVerdict(allowed=False, needs_approval=False, reasons=refus)

    a_approuver = [motif for regle, motif in MOTIFS_A_APPROUVER if regle.search(texte)]
    if allow_push:
        a_approuver = [m for m in a_approuver if m not in ("publication distante",)]
    return SafetyVerdict(
        allowed=True, needs_approval=bool(a_approuver), reasons=a_approuver
    )


def sanitized_environment(extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    """
    Construit l'environnement d'un sous-processus.

    La liste blanche est celle du bac à sable de la plateforme
    (`src/sandbox/policy.py`), pas une seconde écrite ici : deux listes pour une
    même règle divergent, et c'est celle qu'on oublie de mettre à jour qui
    laisse fuir la variable ajoutée demain.

    Args:
        extra: Variables à ajouter — typiquement l'adresse et la clé du modèle.

    Returns:
        L'environnement à passer au processus.
    """
    politique = SandboxPolicy(
        extra_environment=tuple(
            (nom, valeur) for nom, valeur in (extra or {}).items() if valeur is not None
        )
    )
    return politique.env()


def container_required() -> bool:
    """
    Indique si l'exploitant exige un conteneur pour toute exécution.

    Returns:
        Vrai quand `GALSEN_CODING_REQUIRE_CONTAINER` vaut `1`, `true` ou `yes`.
    """
    return os.environ.get(VARIABLE_CONTENEUR, "").strip().lower() in {"1", "true", "yes"}


def running_in_container() -> bool:
    """
    Détecte, au mieux, si le processus tourne dans un conteneur.

    La détection est indicative : `/.dockerenv` et le groupe de contrôle sont
    les deux marques usuelles. Elle sert à refuser une exécution quand
    l'exploitant a exigé un conteneur, jamais à en autoriser une de plus.

    Returns:
        Vrai si une marque de conteneur est trouvée.
    """
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/self/cgroup").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return any(marque in cgroup for marque in ("docker", "kubepods", "containerd", "lxc"))


# ----------------------------------------------------------------------
# Constat des changements
# ----------------------------------------------------------------------

def snapshot(workspace: Path) -> Dict[str, Tuple[float, int]]:
    """
    Relève l'état des fichiers de l'espace de travail.

    Sert au constat des changements quand le dossier n'est pas un dépôt Git.
    Les dossiers de service (`.git`, `__pycache__`, `.venv`, `node_modules`)
    sont ignorés : leur bruit noierait les vrais changements.

    Args:
        workspace: L'espace de travail.

    Returns:
        Chemin relatif → (date de modification, taille).
    """
    ignores = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}
    releve: Dict[str, Tuple[float, int]] = {}
    for racine, dossiers, fichiers in os.walk(workspace):
        dossiers[:] = [d for d in dossiers if d not in ignores]
        for nom in fichiers:
            chemin = Path(racine) / nom
            try:
                etat = chemin.stat()
            except OSError:
                continue
            releve[str(chemin.relative_to(workspace))] = (etat.st_mtime, etat.st_size)
    return releve


def diff_snapshots(
    avant: Mapping[str, Tuple[float, int]],
    apres: Mapping[str, Tuple[float, int]],
) -> List[FileChange]:
    """
    Compare deux relevés et en tire la liste des fichiers touchés.

    Args:
        avant: Relevé pris avant l'exécution.
        apres: Relevé pris après.

    Returns:
        Les changements constatés, triés par chemin.
    """
    changements = [
        FileChange(path=chemin, change_type="created")
        for chemin in apres if chemin not in avant
    ]
    changements += [
        FileChange(path=chemin, change_type="deleted")
        for chemin in avant if chemin not in apres
    ]
    changements += [
        FileChange(path=chemin, change_type="modified")
        for chemin, etat in apres.items()
        if chemin in avant and avant[chemin] != etat
    ]
    return sorted(changements, key=lambda c: c.path)


def git_changes(workspace: Path) -> Optional[List[FileChange]]:
    """
    Liste les fichiers modifiés d'après Git, quand l'espace est un dépôt.

    Git est plus juste qu'un relevé de dates : il ignore ce que `.gitignore`
    ignore et distingue création, modification et suppression sans ambiguïté.

    Args:
        workspace: L'espace de travail.

    Returns:
        Les changements, ou `None` si l'espace n'est pas un dépôt Git ou si
        Git est absent — l'appelant retombe alors sur le relevé de fichiers.
    """
    if not (workspace / ".git").exists() or not shutil.which("git"):
        return None
    try:
        sortie = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(workspace), capture_output=True, text=True, timeout=30,
            env=sanitized_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if sortie.returncode != 0:
        return None

    types = {"?": "created", "A": "created", "M": "modified", "D": "deleted", "R": "modified"}
    changements = []
    for ligne in sortie.stdout.splitlines():
        if len(ligne) < 4:
            continue
        code = ligne[:2].strip() or "?"
        chemin = ligne[3:].strip().strip('"')
        # Un renommage s'écrit « ancien -> nouveau » : on retient le nouveau.
        if " -> " in chemin:
            chemin = chemin.split(" -> ", 1)[1]
        changements.append(
            FileChange(path=chemin, change_type=types.get(code[0], "modified"))
        )
    return sorted(changements, key=lambda c: c.path)
