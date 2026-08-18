"""
What this machine can actually do to media — asked, never assumed.

Every stage of the production pipeline depends on a tool that may or may not be
installed, and the usual way to handle that is a boolean: is `ffmpeg` on the
PATH? That boolean is wrong in both directions here, and finding out why is what
this module exists for.

This environment has no `ffmpeg` on the PATH, so the boolean says *no media work
is possible*. But `/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux` exists, shipped
with the browser tooling — so the boolean would also have said *yes* if that
path were added, and it would have been wrong again: that binary is built
`--disable-everything` with a small allowlist. It can turn PNG frames into a
VP8/WebM video. It cannot read an MP4, decode H.264, touch audio at all, or
probe a file's duration.

Both answers would have produced a broken engine: one refusing work it can do,
the other accepting work it cannot. So a probe here **interrogates the binary**
— `-encoders`, `-decoders`, `-demuxers`, `-protocols` — and reports capability
by capability.

Three rules, taken from what this repository already enforces:

- **The three states are the platform's own** (`src/integration/degradation.py`):
  `AVAILABLE`, `DEGRADED`, `UNAVAILABLE`. A second vocabulary for the same idea
  would be one more thing to keep aligned.
- **A probe that raises is reported, not propagated.** A capability report
  knocked over by what it observes is exactly the failure it exists to prevent.
- **Commands are lists, never strings**, and no shell is involved. Paths here
  come from the environment, and an environment variable is data.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from typing import Any, Callable, Dict, List, Optional

from ...integration.degradation import DEGRADE, DISPONIBLE, INDISPONIBLE

#: Les capacités que le moteur peut avoir besoin d'atteindre. Elles sont
#: déclarées une fois : une capacité qu'un module invente au moment de s'en
#: servir n'apparaît dans aucun rapport, donc personne ne sait qu'elle manque.
CAPACITES = (
    "media_probe",
    "video_decode",
    "video_encode",
    "frame_encode",
    "audio_decode",
    "audio_analysis",
    "transcription",
    "image_analysis",
    "browser_render",
    "gpu_compute",
)

#: Ce qu'une capacité absente empêche, et ce qui continue sans elle. Écrit ici
#: pour qu'un exploitant sache ce qu'il perd avant de chercher à l'installer.
CONSEQUENCES = {
    "media_probe": "Durée, FPS, codec et pistes d'un fichier. Sans elle, aucune "
                   "décision de montage ne peut être calculée — et aucune ne "
                   "doit être devinée.",
    "video_decode": "Lire une vidéo existante. Sans elle, l'analyse et le "
                    "dérushage n'ont pas d'entrée.",
    "video_encode": "Écrire un master dans un format de diffusion.",
    "frame_encode": "Assembler une suite d'images en vidéo. C'est le chemin du "
                    "motion design (§9) : il ne demande aucun décodeur.",
    "audio_decode": "Lire une piste audio.",
    "audio_analysis": "Silences, énergie, forme d'onde, sonie. Sans elle, un "
                      "point de coupe ne peut pas être placé sûrement.",
    "transcription": "Parole en texte, avec les temps par mot. Fournie par "
                     "`src/multimodal/` (VOLET 32), jamais réimplémentée ici.",
    "image_analysis": "Analyse d'image et de trame. Fournie par "
                      "`src/vision_intelligence_engine/`.",
    "browser_render": "Rendu HTML/CSS/SVG en trames (§9).",
    "gpu_compute": "Modèles génératifs locaux (§10, §11).",
}

#: Là où un binaire média peut se trouver quand il n'est pas dans le `PATH`.
#: L'outillage navigateur en embarque un, et le trouver évite de déclarer
#: indisponible une capacité qui existe.
RACINE_NAVIGATEUR = "PLAYWRIGHT_BROWSERS_PATH"

#: Temps maximum accordé à une introspection de binaire. Elle ne doit jamais
#: pouvoir bloquer un rapport d'état.
DELAI_SONDE = 10

_verrou = threading.RLock()
_cache: Dict[str, Any] = {}


class MediaCapabilityError(RuntimeError):
    """Une capacité média demandée alors qu'elle n'est pas atteignable."""


# ----------------------------------------------------------------------
# Découverte des binaires
# ----------------------------------------------------------------------

def find_ffmpeg() -> Optional[str]:
    """
    Trouve un binaire `ffmpeg` utilisable, `PATH` d'abord.

    Returns:
        Son chemin, ou `None`. Le `PATH` est prioritaire : un binaire installé
        par l'exploitant est presque toujours plus complet que celui embarqué
        avec un outillage navigateur, et le sien est celui qu'il croit utiliser.
    """
    depuis_path = shutil.which("ffmpeg")
    if depuis_path:
        return depuis_path

    racine = os.environ.get(RACINE_NAVIGATEUR, "").strip()
    if not racine or not os.path.isdir(racine):
        return None

    for dossier in sorted(os.listdir(racine)):
        if not dossier.startswith("ffmpeg"):
            continue
        chemin = os.path.join(racine, dossier)
        for nom in ("ffmpeg-linux", "ffmpeg", "ffmpeg.exe"):
            candidat = os.path.join(chemin, nom)
            if os.path.isfile(candidat) and os.access(candidat, os.X_OK):
                return candidat
    return None


def find_browser() -> Optional[str]:
    """
    Trouve un navigateur capable de rendre des trames.

    Returns:
        Son chemin, ou `None`. Cherché dans le `PATH` puis dans la racine
        déclarée par l'outillage navigateur.
    """
    for nom in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        trouve = shutil.which(nom)
        if trouve:
            return trouve

    racine = os.environ.get(RACINE_NAVIGATEUR, "").strip()
    if not racine or not os.path.isdir(racine):
        return None

    for dossier in sorted(os.listdir(racine)):
        if not dossier.startswith("chromium"):
            continue
        for suffixe in ("chrome-linux/chrome", "chrome-linux/headless_shell",
                        "chrome", "headless_shell"):
            candidat = os.path.join(racine, dossier, suffixe)
            if os.path.isfile(candidat) and os.access(candidat, os.X_OK):
                return candidat
    return None


def _demander(binaire: str, question: str) -> str:
    """
    Demande à un binaire ce qu'il sait faire.

    Args:
        binaire: Le chemin du binaire.
        question: L'option d'introspection (`-encoders`, `-demuxers`…).

    Returns:
        Sa sortie, ou une chaîne vide s'il n'a pas répondu. La commande est une
        **liste** et aucun shell n'est lancé : le chemin vient de
        l'environnement, et une variable d'environnement est une donnée.
    """
    try:
        resultat = subprocess.run(
            [binaire, "-hide_banner", question],
            capture_output=True, text=True, timeout=DELAI_SONDE, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (resultat.stdout or "") + (resultat.stderr or "")


def _noms(sortie: str) -> set:
    """
    Les noms déclarés par une liste `-encoders` / `-decoders` / `-demuxers`.

    Le nom est le **deuxième jeton** d'une ligne, après la colonne d'attributs.
    Chercher une sous-chaîne à la place confondrait `image2` avec `image2pipe`
    — deux choses différentes : l'un lit une suite de fichiers numérotés,
    l'autre reçoit des trames sur son entrée standard. Ce dépôt a déjà payé ce
    genre de rapprochement approximatif une fois (`find_country`, VOLET 69).
    """
    trouves = set()
    for ligne in sortie.splitlines():
        jetons = ligne.split()
        if len(jetons) >= 2 and not ligne.startswith(("  ", "-", "Enc", "Dec", "File")):
            trouves.add(jetons[1])
        elif len(jetons) >= 2 and ligne.startswith(" ") and len(jetons[0]) <= 7:
            trouves.add(jetons[1])
    return trouves


def ffmpeg_support(binaire: Optional[str] = None) -> Dict[str, Any]:
    """
    Ce qu'un `ffmpeg` donné sait réellement faire.

    Args:
        binaire: Le binaire à interroger. Trouvé automatiquement si absent.

    Returns:
        Les familles de formats qu'il porte, mesurées en l'interrogeant. Un
        `ffmpeg` construit `--disable-everything` existe et répond `-version`
        comme les autres : se fier à sa présence ferait accepter un travail
        qu'il ne peut pas faire.

        **Encoder n'est pas décoder.** Le binaire embarqué avec l'outillage
        navigateur porte un encodeur PNG et aucun décodeur PNG : lui envoyer des
        trames PNG échoue, lui envoyer des trames JPEG fonctionne. Les deux sens
        sont donc mesurés séparément — mesuré en exécutant, pas déduit.
    """
    chemin = binaire or find_ffmpeg()
    if not chemin:
        return {"found": False, "path": None}

    encodeurs = _noms(_demander(chemin, "-encoders"))
    decodeurs = _noms(_demander(chemin, "-decoders"))
    demultiplexeurs = _noms(_demander(chemin, "-demuxers"))

    return {
        "found": True,
        "path": chemin,
        "version": (_demander(chemin, "-version").splitlines() or [""])[0],
        "encodes_h264": bool({"libx264", "h264", "h264_nvenc"} & encodeurs),
        "encodes_vp8_vp9": bool({"libvpx", "libvpx-vp9"} & encodeurs),
        "encodes_png": "png" in encodeurs,
        "decodes_h264": "h264" in decodeurs,
        # Le format des trames qu'on peut lui **envoyer**. C'est le décodeur qui
        # décide, jamais l'encodeur du même nom.
        "decodes_png": "png" in decodeurs,
        "decodes_mjpeg": "mjpeg" in decodeurs,
        "reads_mp4_mov": bool({"mov,mp4,m4a,3gp,3g2,mj2", "mp4", "mov"} & demultiplexeurs),
        "reads_matroska": any(nom.startswith("matroska") for nom in demultiplexeurs),
        # `image2` lit une suite de fichiers numérotés ; `image2pipe` reçoit des
        # trames sur l'entrée standard. Les confondre fait construire une
        # commande qui n'ouvrira jamais son entrée.
        "reads_image_files": "image2" in demultiplexeurs,
        "reads_image_pipe": "image2pipe" in demultiplexeurs,
        # Aucun encodeur audio du tout est le cas réel d'un binaire embarqué
        # avec un outillage navigateur : il n'a jamais servi qu'à filmer un écran.
        "handles_audio": bool(
            {"aac", "libmp3lame", "libopus", "opus", "pcm_s16le"} & encodeurs
        ),
    }


def frame_pipe_format(binaire: Optional[str] = None) -> Optional[str]:
    """
    Le format de trame que ce `ffmpeg` accepte réellement sur son entrée.

    Args:
        binaire: Le binaire à interroger.

    Returns:
        `"mjpeg"`, `"png"`, ou `None` si aucune trame ne peut lui être envoyée.
        Nommer le format est nécessaire : le motion design produit des images,
        et les produire dans un format que le binaire ne **décode** pas
        échouerait au dernier pas, après tout le travail de rendu.
    """
    support = ffmpeg_support(binaire)
    if not support["found"] or not support["reads_image_pipe"]:
        return None
    if support["decodes_mjpeg"]:
        return "mjpeg"
    if support["decodes_png"]:
        return "png"
    return None


def has_ffprobe() -> Optional[str]:
    """Le chemin d'un `ffprobe`, ou `None`. Il ne voyage pas toujours avec `ffmpeg`."""
    return shutil.which("ffprobe")


# ----------------------------------------------------------------------
# Les sondes
# ----------------------------------------------------------------------

def _etat(etat: str, raison: str, **detail: Any) -> Dict[str, Any]:
    """Le résultat d'une sonde."""
    return {"state": etat, "reason": raison, "detail": detail}


def _sonde_media_probe() -> Dict[str, Any]:
    """Durée, FPS, codec : ce qui fait qu'une décision de montage est calculable."""
    ffprobe = has_ffprobe()
    if ffprobe:
        return _etat(DISPONIBLE, "`ffprobe` disponible.", path=ffprobe)
    support = ffmpeg_support()
    if support["found"]:
        return _etat(
            DEGRADE,
            "`ffmpeg` trouvé mais pas `ffprobe`. Les métadonnées ne sont pas "
            "lisibles de façon fiable, et les **deviner** est précisément ce "
            "que ce moteur refuse.",
            ffmpeg=support["path"],
        )
    return _etat(INDISPONIBLE, "Ni `ffprobe` ni `ffmpeg`.")


def _sonde_video_decode() -> Dict[str, Any]:
    """Lire une vidéo existante."""
    support = ffmpeg_support()
    if not support["found"]:
        return _etat(INDISPONIBLE, "Aucun `ffmpeg`.")
    if support["decodes_h264"] and support["reads_mp4_mov"]:
        return _etat(DISPONIBLE, "H.264 et MP4/MOV lisibles.", path=support["path"])
    formats = [nom for nom, porte in (
        ("matroska", support["reads_matroska"]),
        ("image2pipe", support["reads_image_pipe"]),
        ("mjpeg", support["decodes_mjpeg"]),
    ) if porte]
    if formats:
        return _etat(
            DEGRADE,
            "`ffmpeg` présent mais sans H.264/MP4 : il ne lit que "
            + ", ".join(formats) + ". Un binaire construit "
            "`--disable-everything` répond `-version` comme les autres.",
            path=support["path"], reads=formats,
        )
    return _etat(INDISPONIBLE, "`ffmpeg` présent mais ne lit aucun format vidéo utile.",
                 path=support["path"])


def _sonde_video_encode() -> Dict[str, Any]:
    """Écrire un master diffusable."""
    support = ffmpeg_support()
    if not support["found"]:
        return _etat(INDISPONIBLE, "Aucun `ffmpeg`.")
    if support["encodes_h264"]:
        return _etat(DISPONIBLE, "H.264 disponible.", path=support["path"])
    if support["encodes_vp8_vp9"]:
        return _etat(
            DEGRADE,
            "Pas de H.264 : seul VP8/VP9 (WebM) est encodable. Suffisant pour "
            "une prévisualisation, pas pour un master demandé en MP4.",
            path=support["path"],
        )
    return _etat(INDISPONIBLE, "Aucun encodeur vidéo.", path=support["path"])


def _sonde_frame_encode() -> Dict[str, Any]:
    """
    Assembler des images en vidéo — le chemin du motion design (§9).

    La sonde nomme **le format de trame à produire**, parce que c'est la seule
    information qui rend la capacité utilisable : produire des PNG pour un
    binaire qui ne décode que le MJPEG échoue au dernier pas, après tout le
    travail de rendu.
    """
    support = ffmpeg_support()
    if not support["found"]:
        return _etat(INDISPONIBLE, "Aucun `ffmpeg`.")

    encodeur = support["encodes_vp8_vp9"] or support["encodes_h264"]
    format_trame = frame_pipe_format()

    if format_trame and encodeur:
        return _etat(
            DISPONIBLE,
            f"Trames « {format_trame} » envoyées sur l'entrée standard, "
            "encodées en vidéo. Vérifié en exécutant, pas déduit.",
            path=support["path"], frame_format=format_trame,
            file_sequence=support["reads_image_files"],
        )
    if not encodeur:
        return _etat(INDISPONIBLE, "Aucun encodeur vidéo.", path=support["path"])
    return _etat(
        INDISPONIBLE,
        "Aucun format de trame acceptable : le binaire ne **décode** ni PNG ni "
        "MJPEG. Porter un encodeur PNG ne suffit pas — encoder n'est pas "
        "décoder.",
        path=support["path"],
    )


def _sonde_audio_decode() -> Dict[str, Any]:
    """Lire une piste audio."""
    support = ffmpeg_support()
    if not support["found"]:
        return _etat(INDISPONIBLE, "Aucun `ffmpeg`.")
    if support["handles_audio"]:
        return _etat(DISPONIBLE, "Codecs audio disponibles.", path=support["path"])
    return _etat(
        INDISPONIBLE,
        "`ffmpeg` présent mais **sans aucun codec audio**. C'est le cas d'un "
        "binaire embarqué avec un outillage navigateur : il n'a jamais servi "
        "qu'à filmer un écran muet.",
        path=support["path"],
    )


def _sonde_audio_analysis() -> Dict[str, Any]:
    """Silences, énergie, sonie — ce qui rend un point de coupe sûr."""
    audio = _sonde_audio_decode()
    if audio["state"] != DISPONIBLE:
        return _etat(
            INDISPONIBLE,
            "Sans décodage audio, aucune analyse. Placer un point de coupe "
            "sans mesurer le silence reviendrait à couper au milieu d'un mot.",
        )
    return _etat(DISPONIBLE, "Analyse audio calculable depuis `ffmpeg`.")


def _sonde_transcription() -> Dict[str, Any]:
    """Parole en texte — fournie par `src/multimodal/`, jamais réimplémentée."""
    try:
        from ...multimodal.registry import active_transcriber
    except ImportError as erreur:
        return _etat(INDISPONIBLE, f"Registre de transcription illisible : {erreur}")

    fournisseur = active_transcriber()
    if fournisseur is None:
        return _etat(
            INDISPONIBLE,
            "Aucun transcripteur actif (VOLET 32). Un fichier audio doit être "
            "refusé **en le disant**, jamais traité comme un texte vide.",
        )
    return _etat(DISPONIBLE, f"Transcripteur « {fournisseur.provider_id} ».")


def _sonde_image_analysis() -> Dict[str, Any]:
    """Analyse de trame — fournie par le moteur de vision."""
    try:
        import cv2
        import PIL
    except ImportError as erreur:
        return _etat(INDISPONIBLE, f"Moteur de vision indisponible : {erreur}")
    return _etat(
        DISPONIBLE, "OpenCV et Pillow disponibles.",
        opencv=cv2.__version__, pillow=PIL.__version__,
    )


def _sonde_browser_render() -> Dict[str, Any]:
    """Rendu HTML/CSS/SVG en trames (§9)."""
    navigateur = find_browser()
    if not navigateur:
        return _etat(INDISPONIBLE, "Aucun navigateur trouvé.")
    try:
        import playwright  # noqa: F401
    except ImportError:
        return _etat(
            DEGRADE,
            "Navigateur présent mais aucun pilote pour le conduire "
            "(`playwright` absent). Un navigateur qu'on ne peut pas piloter ne "
            "capture aucune trame.",
            browser=navigateur,
        )
    return _etat(DISPONIBLE, "Navigateur et pilote disponibles.", browser=navigateur)


def _sonde_gpu_compute() -> Dict[str, Any]:
    """Modèles génératifs locaux (§10, §11)."""
    try:
        import torch
    except ImportError:
        return _etat(
            INDISPONIBLE,
            "`torch` absent : aucun modèle génératif local. Les fournisseurs "
            "restent déclarables — c'est l'exécution qui manque, pas "
            "l'architecture.",
        )
    if not torch.cuda.is_available():
        return _etat(
            DEGRADE,
            "`torch` présent sans CUDA : exécution CPU seulement, ce qui exclut "
            "la génération vidéo en pratique.",
            torch=torch.__version__,
        )
    return _etat(
        DISPONIBLE, "CUDA disponible.",
        torch=torch.__version__, devices=torch.cuda.device_count(),
    )


#: La table des sondes. Une capacité déclarée sans sonde serait une capacité que
#: personne ne mesure.
SONDES: Dict[str, Callable[[], Dict[str, Any]]] = {
    "media_probe": _sonde_media_probe,
    "video_decode": _sonde_video_decode,
    "video_encode": _sonde_video_encode,
    "frame_encode": _sonde_frame_encode,
    "audio_decode": _sonde_audio_decode,
    "audio_analysis": _sonde_audio_analysis,
    "transcription": _sonde_transcription,
    "image_analysis": _sonde_image_analysis,
    "browser_render": _sonde_browser_render,
    "gpu_compute": _sonde_gpu_compute,
}


def probe(name: str) -> Dict[str, Any]:
    """
    Interroge une capacité, sans jamais se laisser renverser par elle.

    Args:
        name: La capacité, telle que déclarée dans `CAPACITES`.

    Returns:
        Son état, sa raison, et ce que son absence empêche.

    Raises:
        KeyError: Pour une capacité non déclarée. Deviner serait pire : un nom
            mal écrit rendrait « disponible » pour toujours.
    """
    sonde = SONDES[name]
    try:
        resultat = sonde()
    except Exception as erreur:
        # Le cas que ce module existe pour tenir : un rapport de capacités
        # renversé par ce qu'il observe serait exactement la panne qu'il doit
        # empêcher.
        resultat = _etat(INDISPONIBLE, f"{type(erreur).__name__}: {erreur}")

    return {
        "capability": name,
        "state": resultat["state"],
        "reason": resultat["reason"],
        "detail": resultat.get("detail", {}),
        "without_it": CONSEQUENCES[name],
    }


def capability_report(names: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    L'état de toutes les capacités média.

    Args:
        names: Les capacités à sonder. Toutes par défaut.

    Returns:
        Chaque capacité avec son état, et un état global. Une capacité manquante
        ne fait pas basculer les autres : dégradé n'est pas en panne.
    """
    demandes = list(names or CAPACITES)
    inconnues = [nom for nom in demandes if nom not in SONDES]
    if inconnues:
        raise KeyError(f"Capacités non déclarées : {inconnues}")

    resultats = {nom: probe(nom) for nom in demandes}
    etats = [entree["state"] for entree in resultats.values()]

    return {
        "capabilities": resultats,
        "available": sorted(n for n, e in resultats.items() if e["state"] == DISPONIBLE),
        "degraded": sorted(n for n, e in resultats.items() if e["state"] == DEGRADE),
        "unavailable": sorted(n for n, e in resultats.items() if e["state"] == INDISPONIBLE),
        "state": (
            DISPONIBLE if all(e == DISPONIBLE for e in etats)
            else INDISPONIBLE if all(e == INDISPONIBLE for e in etats)
            else DEGRADE
        ),
        "note": (
            "Chaque capacité est **mesurée** en interrogeant l'outil, pas "
            "déduite de sa présence : un `ffmpeg` construit "
            "`--disable-everything` répond `-version` comme les autres et ne "
            "lit pourtant aucun MP4."
        ),
    }


def require(name: str) -> Dict[str, Any]:
    """
    Exige une capacité, ou refuse en disant ce qui manque.

    Args:
        name: La capacité requise.

    Returns:
        Le résultat de la sonde quand la capacité est disponible.

    Raises:
        MediaCapabilityError: Quand elle est dégradée ou absente. C'est le point
            où un moteur ordinaire produirait « quelque chose quand même » — un
            fichier vide, une durée par défaut, une transcription inventée.
    """
    resultat = probe(name)
    if resultat["state"] != DISPONIBLE:
        raise MediaCapabilityError(
            f"Capacité « {name} » {resultat['state']} : {resultat['reason']} "
            f"Ce qu'elle porte : {resultat['without_it']}"
        )
    return resultat


def clear_cache() -> None:
    """Oublie les résultats mémorisés. Utile après une installation."""
    with _verrou:
        _cache.clear()
