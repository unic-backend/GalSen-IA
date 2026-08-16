"""
Where an HTTP caller's media paths are judged, and why the engine is not a
second gate.

Directive §30 lists six things to prevent — prompt injection, malicious
filenames, path traversal, command injection, unsafe codec execution,
unauthorised filesystem access — and ends on the instruction that decides the
design: *reuse the existing GalSen AI security boundary.* So the traversal and
symlink decision is **not rewritten here**. `src/agent/tools/workspace.py`
already resolves before judging (a path is `realpath`-ed first, because
`a/b/../../../etc/passwd` is not detectable by spelling and a symlink inside the
root pointing at `/etc` is exactly what a prefix check misses). This module
gives it the media root and adds the three things that are media-specific.

**A filename beginning with `-` is not a filename to a codec, it is an
option.** `ffmpeg … -y out.webm` writes a file; `ffmpeg … -y -i /etc/passwd`
reads one. No shell is involved anywhere in this engine — every invocation
passes an argument list — so `;` and backticks are inert, and pretending
otherwise by escaping them would suggest a protection that is not what is
actually holding. What holds is that the codec and container are **fixed in the
code**, never taken from a caller: nothing a user sends reaches a `-c:v`.

**The boundary is at the entry, not in the primitive.** `render_video()` takes
the path it is told to use, because a caller inside this process has already
been through here. Putting a second gate in the primitive would mean two rules
about the same thing, and this repository has watched two copies of one rule
disagree the day one of them was fixed. What arrives over HTTP is judged once,
here, before the engine sees it.

**A rejected path is named in the refusal, never silently rewritten.** Turning
`../../etc/passwd` into `etc/passwd` and carrying on hands the caller a
different file than the one they asked for and tells nobody.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional, Tuple

from ...agent.tools.workspace import WorkspaceRefused, resolve
from ...storage.paths import data_dir

#: Le sous-répertoire média du répertoire de données (ADR-005). Les médias sont
#: des fichiers d'utilisateurs : ils vivent avec les autres données de la
#: plateforme, pas dans le dépôt.
SOUS_REPERTOIRE = "media"

#: Les extensions acceptées à l'entrée. Une liste blanche plutôt qu'une liste
#: noire : personne ne sait énumérer tout ce qui est dangereux, et le premier
#: format oublié est celui qui passe.
EXTENSIONS_AUTORISEES: Tuple[str, ...] = (
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".srt", ".vtt", ".ass",
)

#: Caractères qui n'ont rien à faire dans un nom de fichier et qui, eux, font
#: quelque chose ailleurs : un octet nul tronque un chemin dans une couche C,
#: un saut de ligne coupe une ligne de journal en deux.
CARACTERES_INTERDITS = re.compile(r"[\x00-\x1f\x7f]")

#: Un débit acceptable pour un encodeur. Validé bien qu'aucun shell ne soit
#: employé : ce qui est refusé ici est une valeur que l'encodeur rejetterait
#: plus tard, après tout le travail de rendu.
DEBIT_VALIDE = re.compile(r"^\d{1,6}[kKmM]?$")


class MediaPathRefused(PermissionError):
    """Un chemin média hors du cadre autorisé. Levée, jamais rendue en valeur."""


def media_root() -> str:
    """
    La racine sous laquelle tout média est lu et écrit.

    Returns:
        `<GALSEN_DATA_DIR>/media`, résolu. Le répertoire est créé au besoin :
        une racine inexistante ferait échouer la résolution et ce refus-là
        n'apprendrait rien à personne.
    """
    racine = os.path.join(data_dir(), SOUS_REPERTOIRE)
    os.makedirs(racine, exist_ok=True)
    return os.path.realpath(racine)


def safe_media_path(
    path: str, root: Optional[str] = None, must_exist: bool = False,
    allow_extensions: Optional[Tuple[str, ...]] = None,
) -> str:
    """
    Résout un chemin média reçu de l'extérieur, ou refuse en disant pourquoi.

    Args:
        path: Le chemin demandé, relatif à la racine média.
        root: Une autre racine, pour un espace de travail isolé.
        must_exist: Exige que le fichier existe déjà.
        allow_extensions: Les extensions acceptées. `EXTENSIONS_AUTORISEES` par
            défaut.

    Returns:
        Le chemin absolu et réel, liens symboliques résolus.

    Raises:
        MediaPathRefused: Chemin vide, caractère de contrôle, nom commençant par
            `-` (un codec y lirait une option, pas un fichier), extension hors
            liste, sortie de la racine, ou fichier absent quand il est exigé.
            Le refus **nomme** ce qui a été demandé : réécrire silencieusement
            `../../etc/passwd` en `etc/passwd` rendrait un autre fichier que
            celui demandé sans le dire à personne.
    """
    demande = str(path or "").strip()
    if not demande:
        raise MediaPathRefused(
            "Aucun chemin média. Choisir un fichier par défaut ferait traiter "
            "un média que personne n'a désigné."
        )

    if CARACTERES_INTERDITS.search(demande):
        raise MediaPathRefused(
            f"« {demande!r} » contient un caractère de contrôle. Un octet nul "
            "tronque un chemin dans une couche C, et un saut de ligne coupe une "
            "ligne de journal en deux."
        )

    nom = os.path.basename(demande)
    if nom.startswith("-"):
        raise MediaPathRefused(
            f"« {nom} » commence par « - » : un codec y lit une **option**, pas "
            "un fichier. `-i /etc/passwd` est un nom de fichier parfaitement "
            "valide pour un système de fichiers."
        )

    extensions = allow_extensions or EXTENSIONS_AUTORISEES
    if os.path.splitext(nom)[1].lower() not in extensions:
        raise MediaPathRefused(
            f"Extension de « {nom} » hors de la liste acceptée. La liste est "
            "**blanche** : personne ne sait énumérer tout ce qui est dangereux, "
            "et le premier format oublié est celui qui passe."
        )

    try:
        # La décision de traversée et de lien symbolique appartient à
        # `workspace.resolve` : une deuxième copie finirait par diverger de
        # celle-ci le jour où l'une des deux serait corrigée.
        absolu = resolve(demande, root=root or media_root())
    except WorkspaceRefused as refus:
        raise MediaPathRefused(str(refus)) from refus

    if must_exist and not os.path.isfile(absolu):
        raise MediaPathRefused(
            f"« {demande} » n'existe pas sous la racine média. Un fichier "
            "absent n'est pas un fichier vide : le traiter comme tel produirait "
            "une durée de zéro que rien en aval ne distinguerait d'une mesure."
        )
    return absolu


def safe_output_name(name: str, extension: str = ".webm") -> str:
    """
    Un nom de sortie sûr, construit **à partir** de ce qui a été demandé.

    Args:
        name: Le nom souhaité.
        extension: L'extension imposée par l'encodeur.

    Returns:
        Un nom composé de lettres, chiffres, tirets et points, avec l'extension
        imposée. Le nom est repris quand il est déjà sûr ; il n'est pas remplacé
        par un identifiant tiré au sort, qui ferait perdre à l'utilisateur le
        seul repère qu'il avait sur son fichier.

    Raises:
        MediaPathRefused: Quand il ne reste rien après nettoyage — auquel cas le
            nom n'apportait aucune information et en inventer un le ferait
            passer pour choisi.
    """
    base = os.path.basename(str(name or "")).strip()
    base = os.path.splitext(base)[0]
    propre = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-.")
    if not propre:
        raise MediaPathRefused(
            f"« {name} » ne laisse aucun nom exploitable. En tirer un au sort "
            "le ferait passer pour un nom choisi."
        )
    return f"{propre[:120]}{extension}"


def safe_bitrate(value: str) -> str:
    """
    Un débit accepté par l'encodeur, ou un refus **avant** le rendu.

    Args:
        value: Le débit demandé, par exemple `800k`.

    Returns:
        Le débit, inchangé.

    Raises:
        MediaPathRefused: Sur une valeur que l'encodeur rejetterait — après tout
            le travail de rendu, ce qui est le pire moment pour l'apprendre.
    """
    debit = str(value or "").strip()
    if not DEBIT_VALIDE.match(debit):
        raise MediaPathRefused(
            f"Débit « {debit} » invalide. Attendu : un nombre suivi de `k` ou "
            "`M`. Le refuser ici évite de l'apprendre après tout le rendu."
        )
    return debit


def boundary_report() -> Dict[str, Any]:
    """
    Ce que la frontière média tient, et ce qu'elle ne prétend pas tenir.

    Returns:
        Les règles, ce qui est réutilisé, et les protections qui n'en sont pas.
    """
    return {
        "root": media_root(),
        "allowed_extensions": list(EXTENSIONS_AUTORISEES),
        "reuses": {
            "traversal_and_symlinks": "src/agent/tools/workspace.py — resolve()",
            "external_text": "src/security/trust.py — inspect() / wrap()",
            "data_directory": "src/storage/paths.py — data_dir() (ADR-005)",
        },
        "rules": [
            "Le chemin est **résolu avant d'être jugé** : `..` et les liens "
            "symboliques ne se détectent pas à l'orthographe.",
            "Un nom commençant par « - » est refusé : un codec y lit une "
            "option, pas un fichier.",
            "La liste d'extensions est **blanche** : le premier format oublié "
            "d'une liste noire est celui qui passe.",
            "Un chemin refusé est **nommé**, jamais réécrit en silence.",
            "La frontière est à l'entrée. La primitive de rendu n'en est pas "
            "une seconde : deux règles sur le même sujet finissent par ne plus "
            "dire la même chose.",
        ],
        "does_not": [
            "Réécrire un chemin hors cadre en un chemin dedans.",
            "Échapper des métacaractères de shell : aucun shell n'est employé, "
            "et le prétendre désignerait la mauvaise protection.",
            "Empêcher un autre processus d'écrire dans la racine média.",
        ],
        "codec_note": (
            "Le conteneur et le codec sont **fixés dans le code** "
            "(`src/media/motion/render.py`) : aucune chaîne d'appelant "
            "n'atteint un argument `-c:v`. C'est ce qui tient contre "
            "l'exécution de codec arbitraire, pas un échappement."
        ),
    }
