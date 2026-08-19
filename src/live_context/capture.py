"""
La surface d'entrée, et le rapport honnête de son absence
(L05.2, ADR-033, §7 de la directive Live Context).

## Le travail de ce module aujourd'hui est de dire « non »

§7 énumère huit entrées. Sur cette machine, **quatre ne peuvent pas exister** :
il n'y a ni `/dev/snd`, ni `/dev/video*`, `DISPLAY` est vide et `ffmpeg` n'est
pas sur le `PATH`. Un module de capture qui prétendrait le contraire serait la
plus grosse fabrication que ce dépôt ait produite.

Il rend donc, entrée par entrée, ce qu'il a **constaté** — et pour chaque
absence, **comment** elle a été constatée : un chemin cherché, une variable
vide, un module introuvable. « Absent » sans constat est une supposition, et
`state.absent()` le refuse.

## Une capacité se mesure en interrogeant l'environnement

C'est la règle du moteur média, et elle a déjà payé : l'`ffmpeg` de cette
machine est compilé `--disable-everything` et répond `-version` exactement comme
un complet. Vérifier qu'un binaire existe n'est pas mesurer une capacité.

Ici, chaque sonde regarde la chose elle-même — un nœud de périphérique, une
variable d'environnement, un module importable — jamais un drapeau qu'un
appelant aurait posé.

## Ce que ce module ne fait pas

**Il ne capture rien.** Il déclare ce qui serait capturable et rapporte ce qui
ne l'est pas. La capture appartient à un `LiveCaptureProvider` qu'ADR-033 laisse
à un volet ultérieur, et qui reste `BLOCKED` tant qu'aucun périphérique
n'existe.

**Il ne contourne rien.** ADR-018 refuse **inconditionnellement** qu'une capture
d'écran quitte la machine. Ce module se contente de dire si un écran existe ;
ce qu'on aurait le droit d'en faire est déjà tranché ailleurs.
"""

from __future__ import annotations

import glob
import importlib.util
import os
import shutil
from typing import Any, Dict, List, Tuple

from .state import Observation, absent

#: Les huit entrées de §7, dans l'ordre du texte.
ENTREES: Tuple[str, ...] = (
    "microphone",
    "system_audio",
    "camera",
    "screen",
    "uploaded_audio",
    "existing_media",
    "text",
    "external_events",
)

#: L'état d'une entrée. `ABSENT` vient de `state.py` — un seul vocabulaire.
DISPONIBLE = "AVAILABLE"

#: La modalité de chaque entrée, pour que l'observation porte la bonne.
_MODALITE: Dict[str, str] = {
    "microphone": "audio",
    "system_audio": "audio",
    "camera": "video",
    "screen": "screen",
    "uploaded_audio": "audio",
    "existing_media": "video",
    "text": "text",
    "external_events": "event",
}


class CaptureRefused(ValueError):
    """Une entrée non déclarée."""


def _module_present(nom: str) -> bool:
    """Dit si un module de la plateforme est importable."""
    try:
        return importlib.util.find_spec(nom) is not None
    except (ImportError, ValueError):
        return False


def _sonde_microphone() -> Tuple[bool, str]:
    """Cherche un périphérique audio."""
    if os.path.isdir("/dev/snd"):
        return True, "/dev/snd présent"
    return False, "/dev/snd cherché, absent — aucun périphérique audio"


def _sonde_camera() -> Tuple[bool, str]:
    """Cherche un périphérique vidéo."""
    trouves = glob.glob("/dev/video*")
    if trouves:
        return True, f"{len(trouves)} périphérique(s) vidéo"
    return False, "/dev/video* cherché, aucun résultat"


def _sonde_ecran() -> Tuple[bool, str]:
    """Cherche un affichage."""
    affichage = os.environ.get("DISPLAY", "").strip()
    wayland = os.environ.get("WAYLAND_DISPLAY", "").strip()
    if affichage or wayland:
        return True, f"DISPLAY={affichage or '(vide)'} WAYLAND={wayland or '(vide)'}"
    return False, "DISPLAY et WAYLAND_DISPLAY vides — aucun affichage"


def _sonde_media() -> Tuple[bool, str]:
    """
    Cherche de quoi lire un média existant.

    Le module d'ingestion suffit à *décrire* un média ; le décoder demande
    `ffmpeg`, et son absence est rapportée séparément plutôt que fondue dans un
    seul verdict.
    """
    module = _module_present("src.media.ingestion.identify")
    ffmpeg = shutil.which("ffmpeg") is not None
    if module and ffmpeg:
        return True, "src.media.ingestion présent, ffmpeg sur le PATH"
    if module:
        return True, ("src.media.ingestion présent ; **ffmpeg absent du PATH**, "
                      "donc l'identification est possible et le décodage non")
    return False, "src.media.ingestion introuvable"


def probe(entree: str) -> Observation:
    """
    Interroge l'environnement pour une entrée, et rend ce qui a été constaté.

    Args:
        entree: Une entrée de `ENTREES`.

    Returns:
        Une `Observation` — `MEASURED` avec `AVAILABLE` quand l'entrée existe,
        `ABSENT` avec le constat sinon.

    Raises:
        CaptureRefused: Si l'entrée n'est pas déclarée.
    """
    if entree not in ENTREES:
        raise CaptureRefused(
            f"Entrée « {entree} » non déclarée. Déclarées : {list(ENTREES)}."
        )
    modalite = _MODALITE[entree]

    if entree in ("microphone", "system_audio"):
        present, constat = _sonde_microphone()
    elif entree == "camera":
        present, constat = _sonde_camera()
    elif entree == "screen":
        present, constat = _sonde_ecran()
    elif entree == "uploaded_audio":
        present = _module_present("src.services.file")
        constat = ("src.services.file présent" if present
                   else "src.services.file introuvable")
    elif entree == "existing_media":
        present, constat = _sonde_media()
    elif entree == "text":
        present, constat = True, "une entrée texte ne demande aucun périphérique"
    else:  # external_events
        present = _module_present("src.routines") or _module_present("src.proactive")
        constat = ("src.routines / src.proactive présents" if present
                   else "ni src.routines ni src.proactive")

    if not present:
        return absent(subject=entree, modality=modalite, detail=constat)
    return Observation(subject=entree, status="MEASURED", modality=modalite,
                       value=DISPONIBLE, detail=constat)


def capture_surface() -> Dict[str, Any]:
    """
    L'état des huit entrées, mesuré maintenant.

    Returns:
        Une observation par entrée, les comptes, et la liste de ce qui manque
        avec son constat. **Aucun booléen global** : « la capture n'est pas
        disponible » n'apprend pas à un opérateur ce qui manque.
    """
    observations = [probe(e) for e in ENTREES]
    disponibles = [o.subject for o in observations if o.is_known]
    absentes = [{"input": o.subject, "reason": o.detail}
                for o in observations if not o.is_known]
    return {
        "inputs": [o.as_dict() for o in observations],
        "available": disponibles,
        "absent": absentes,
        "available_count": len(disponibles),
        "absent_count": len(absentes),
        "score": None,
        "note": ("Chaque absence porte son constat. Aucun score et aucun "
                 "booléen global : ce qui aide un opérateur, c'est de savoir "
                 "quelle entrée manque et pourquoi."),
    }


def available_modalities() -> List[str]:
    """
    Les modalités réellement disponibles, sans doublon.

    Returns:
        Les modalités triées. C'est ce que §7 demande de déterminer
        dynamiquement, et c'est testable ici **parce que** la moitié des
        entrées manque.
    """
    return sorted({o.modality for o in (probe(e) for e in ENTREES)
                   if o.is_known})


def capture_report() -> Dict[str, Any]:
    """
    Ce que la couche de capture déclare, et ce qu'elle refuse.

    Returns:
        Le vocabulaire, l'état mesuré, et les règles tenues.
    """
    surface = capture_surface()
    return {
        "declared_inputs": list(ENTREES),
        "surface": surface,
        "modalities_available": available_modalities(),
        "captures_anything": False,
        "rules": [
            "Une capacité se mesure en interrogeant l'environnement, jamais en "
            "croyant un drapeau.",
            "Une absence porte son constat : un chemin cherché, une variable "
            "vide, un module introuvable.",
            "Aucun booléen global et aucun score : l'opérateur a besoin de "
            "savoir quelle entrée manque.",
            "Ce module ne capture rien ; il dit ce qui serait capturable.",
            "ADR-018 refuse inconditionnellement qu'une capture d'écran quitte "
            "la machine — ce module dit seulement si un écran existe.",
        ],
    }
