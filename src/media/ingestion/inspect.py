"""
What a file contains — measured, or explicitly not known.

Directive §3 asks for duration, FPS, resolution, codec, bitrate, audio tracks,
channels, keyframes, waveform and loudness. On this machine most of those need
`ffprobe`, which is absent. The tempting shape is a record full of defaults:
`duration = 0.0`, `fps = 25`, `channels = 2`. Every one of those numbers is a
lie that reads exactly like a measurement, and the edit planner downstream
cannot tell the difference — it would place a cut at second 12 of a file whose
duration nobody ever read.

So a field here is in one of two states and never in between:

- **measured**, with the tool that measured it named; or
- **unknown**, with the reason and the capability that would supply it.

`MediaInfo.unknown_fields` lists the second kind, so a caller can refuse the
work instead of computing on absences. `require_for_editing()` does exactly that
refusal, because a cut placed on an unmeasured duration is the failure this
whole engine exists to prevent.

What *is* measurable here is real and not a consolation prize: image dimensions
come from Pillow, and format and family come from the file's own bytes
(`identify.py`). Those are exact.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..core.capabilities import DELAI_SONDE, has_ffprobe, probe
from .identify import FORMAT_INCONNU, FAMILLE_IMAGE, identify_file

#: Les champs que la directive §3 demande. Déclarés une fois : un champ qu'un
#: module invente au moment de s'en servir n'apparaît dans aucun rapport
#: d'absence, donc personne ne sait qu'il manque.
CHAMPS = (
    "duration", "fps", "width", "height", "video_codec", "bitrate",
    "audio_tracks", "audio_channels", "sample_rate",
)

#: Ce qui fournirait un champ manquant. Dire « inconnu » sans dire par quoi
#: laisse l'exploitant chercher au hasard.
FOURNISSEUR = {
    "duration": "media_probe", "fps": "media_probe", "bitrate": "media_probe",
    "video_codec": "media_probe", "audio_tracks": "media_probe",
    "audio_channels": "media_probe", "sample_rate": "media_probe",
    "width": "image_analysis", "height": "image_analysis",
}


class InspectionRefused(RuntimeError):
    """Un travail demandé sur des mesures qui n'existent pas."""


@dataclass
class MediaInfo:
    """
    Ce qu'on sait d'un fichier, et ce qu'on ne sait pas.

    Attributes:
        path: Le fichier.
        format: Son format, lu dans ses octets.
        family: `video`, `audio`, `image` ou `vector`.
        bytes: Sa taille.
        mismatch: Vrai quand le nom annonce autre chose que le contenu.
        measured: Les champs mesurés, avec leur valeur.
        measured_by: Par quel outil chaque champ a été mesuré.
        unknown: Les champs non mesurés, avec la raison.
    """

    path: str
    format: str = FORMAT_INCONNU
    family: Optional[str] = None
    bytes: int = 0
    mismatch: bool = False
    measured: Dict[str, Any] = field(default_factory=dict)
    measured_by: Dict[str, str] = field(default_factory=dict)
    unknown: Dict[str, str] = field(default_factory=dict)

    def get(self, champ: str) -> Optional[Any]:
        """
        La valeur d'un champ, ou `None` s'il n'a pas été mesuré.

        `None` veut dire **non mesuré**, jamais zéro. Un appelant qui traite les
        deux pareillement calculerait sur une absence.
        """
        return self.measured.get(champ)

    @property
    def unknown_fields(self) -> Tuple[str, ...]:
        """Les champs que personne n'a mesurés, triés."""
        return tuple(sorted(self.unknown))

    @property
    def is_complete(self) -> bool:
        """Vrai quand tous les champs attendus pour cette famille sont mesurés."""
        return not self.unknown

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences comprises."""
        return {
            "path": self.path, "format": self.format, "family": self.family,
            "bytes": self.bytes, "mismatch": self.mismatch,
            "measured": dict(self.measured),
            "measured_by": dict(self.measured_by),
            "unknown": dict(self.unknown),
            "unknown_fields": list(self.unknown_fields),
            "complete": self.is_complete,
            "note": (
                "Un champ est mesuré ou inconnu, jamais entre les deux. Une "
                "valeur par défaut se lirait comme une mesure, et un point de "
                "coupe placé sur une durée que personne n'a lue est exactement "
                "ce que ce moteur existe pour empêcher."
            ),
        }


def _attendus(famille: Optional[str]) -> Tuple[str, ...]:
    """Les champs qui ont un sens pour cette famille."""
    if famille == FAMILLE_IMAGE:
        return ("width", "height")
    if famille == "vector":
        return ()
    if famille == "audio":
        return ("duration", "bitrate", "audio_tracks", "audio_channels",
                "sample_rate")
    return CHAMPS


def _mesurer_image(chemin: str, info: MediaInfo) -> None:
    """Dimensions réelles d'une image, par Pillow."""
    try:
        from PIL import Image
    except ImportError as erreur:
        info.unknown["width"] = f"Pillow indisponible : {erreur}"
        info.unknown["height"] = f"Pillow indisponible : {erreur}"
        return
    try:
        with Image.open(chemin) as image:
            largeur, hauteur = image.size
    except Exception as erreur:
        # Un fichier identifié mais illisible est un fait, pas une dimension
        # par défaut : `(0, 0)` ferait diviser par zéro plus loin.
        raison = f"Image illisible ({type(erreur).__name__})."
        info.unknown["width"] = raison
        info.unknown["height"] = raison
        return
    info.measured["width"] = largeur
    info.measured["height"] = hauteur
    info.measured_by["width"] = "pillow"
    info.measured_by["height"] = "pillow"


def _mesurer_avec_ffprobe(chemin: str, info: MediaInfo) -> bool:
    """
    Interroge `ffprobe`, quand il existe.

    Returns:
        Vrai si la mesure a abouti. La commande est une **liste** et aucun shell
        n'est lancé : le chemin vient d'un fichier fourni de l'extérieur.
    """
    binaire = has_ffprobe()
    if not binaire:
        return False
    try:
        resultat = subprocess.run(
            [binaire, "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", chemin],
            capture_output=True, text=True, timeout=DELAI_SONDE, check=False,
        )
        donnees = json.loads(resultat.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return False

    conteneur = donnees.get("format") or {}
    flux = donnees.get("streams") or []
    video = next((f for f in flux if f.get("codec_type") == "video"), None)
    audios = [f for f in flux if f.get("codec_type") == "audio"]

    def _poser(champ: str, valeur: Any) -> None:
        if valeur is not None:
            info.measured[champ] = valeur
            info.measured_by[champ] = "ffprobe"

    _poser("duration", float(conteneur["duration"]) if conteneur.get("duration") else None)
    _poser("bitrate", int(conteneur["bit_rate"]) if conteneur.get("bit_rate") else None)
    _poser("audio_tracks", len(audios) if flux else None)

    if video:
        _poser("width", video.get("width"))
        _poser("height", video.get("height"))
        _poser("video_codec", video.get("codec_name"))
        cadence = video.get("avg_frame_rate") or ""
        if "/" in cadence:
            numerateur, denominateur = cadence.split("/", 1)
            if denominateur not in ("0", ""):
                _poser("fps", round(float(numerateur) / float(denominateur), 4))
    if audios:
        _poser("audio_channels", audios[0].get("channels"))
        _poser("sample_rate",
               int(audios[0]["sample_rate"]) if audios[0].get("sample_rate") else None)
    return True


def inspect_media(path: str) -> MediaInfo:
    """
    Inspecte un fichier : ce qu'il est, puis ce qu'on peut mesurer de lui.

    Args:
        path: Le chemin, **déjà résolu** par `src/storage/roots.py`.

    Returns:
        Un `MediaInfo` dont chaque champ attendu est soit mesuré, soit listé
        dans `unknown` avec sa raison et la capacité qui le fournirait. Aucune
        valeur par défaut n'est posée.

    Raises:
        IdentificationRefused: Fichier absent, vide ou illisible.
    """
    identite = identify_file(path)
    info = MediaInfo(
        path=path,
        format=identite["format"],
        family=identite["family"],
        bytes=identite["bytes"],
        mismatch=identite["mismatch"],
    )

    if info.family == FAMILLE_IMAGE:
        _mesurer_image(path, info)
    else:
        _mesurer_avec_ffprobe(path, info)

    sonde = probe("media_probe")
    for champ in _attendus(info.family):
        if champ in info.measured or champ in info.unknown:
            # Une raison **déjà posée** est plus précise que celle-ci : « image
            # illisible » dit que le fichier est cassé, alors que le repli dirait
            # qu'une capacité manque — ce qui est faux et envoie chercher au
            # mauvais endroit. Le repli comble, il n'écrase pas.
            continue
        capacite = FOURNISSEUR[champ]
        info.unknown[champ] = (
            f"Non mesuré. Fourni par la capacité « {capacite} », "
            f"actuellement {sonde['state']} : {sonde['reason']}"
            if capacite == "media_probe" else
            f"Non mesuré. Fourni par la capacité « {capacite} »."
        )
    return info


def require_for_editing(info: MediaInfo, fields: Optional[List[str]] = None) -> None:
    """
    Exige que les champs nécessaires à un montage soient mesurés.

    Args:
        info: L'inspection.
        fields: Les champs requis. `duration` et `fps` par défaut — ce sont les
            deux dont dépend le placement d'un point de coupe.

    Raises:
        InspectionRefused: Dès qu'un champ requis manque. C'est le point où un
            moteur ordinaire prendrait `0.0` et placerait une coupe dans un
            fichier dont personne n'a lu la durée.
    """
    requis = list(fields or ["duration", "fps"])
    manquants = [champ for champ in requis if champ not in info.measured]
    if not manquants:
        return
    raisons = "; ".join(f"{champ} : {info.unknown.get(champ, 'non mesuré')}"
                        for champ in manquants)
    raise InspectionRefused(
        f"Montage impossible sur « {os.path.basename(info.path)} » : "
        f"{', '.join(manquants)} non mesuré(s). {raisons} "
        "Prendre une valeur par défaut placerait une coupe dans un fichier "
        "dont personne n'a lu la durée."
    )


def inspection_report() -> Dict[str, Any]:
    """
    Ce que l'inspection garantit, et ce qu'elle refuse.

    Returns:
        Les champs, leurs fournisseurs, et les règles tenues.
    """
    return {
        "fields": list(CHAMPS),
        "provided_by": dict(FOURNISSEUR),
        "rules": [
            "Un champ est **mesuré ou inconnu**, jamais entre les deux : une "
            "valeur par défaut se lit exactement comme une mesure.",
            "Un champ inconnu nomme **la capacité qui le fournirait** — dire "
            "« inconnu » sans dire par quoi laisse chercher au hasard.",
            "`get()` rend `None` pour un champ non mesuré, jamais zéro.",
            "`require_for_editing()` refuse plutôt que de calculer sur une "
            "absence : une coupe placée sur une durée jamais lue est l'échec "
            "que ce moteur existe pour empêcher.",
            "Les commandes sont des **listes**, sans shell : le chemin vient "
            "d'un fichier fourni de l'extérieur.",
        ],
        "does_not": [
            "Poser une durée, une cadence ou un nombre de pistes par défaut.",
            "Traiter une image illisible comme une image de taille nulle.",
            "Mesurer ce qu'aucun outil disponible ne sait mesurer.",
        ],
    }
