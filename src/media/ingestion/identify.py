"""
What a file is — read from its bytes, never from its name.

Directive §3 lists the formats the engine must support, and the obvious way to
tell them apart is the extension. That is wrong for two independent reasons, and
both of them bite in production.

**It is wrong about correctness.** A `.mp4` produced by a phone, a screen
recorder and an editor are three different containers, and a file renamed once
by a well-meaning human is mislabelled forever after. Handing an AVI to an MP4
decoder produces an error message that blames the wrong thing.

**It is wrong about safety** (§30). The filename is external input. A pipeline
that routes work by extension routes it by something an attacker chooses; the
bytes are the only part of a supplied file that describes the file. So the
extension is recorded as a **claim**, the signature as **evidence**, and a
disagreement between them is reported rather than silently resolved in either
direction — an engine that trusts the name is exploitable, and one that silently
overrides it hides a real corruption.

Nothing here is guessed. A signature that matches nothing declared returns
`UNKNOWN_FORMAT`, which the caller must handle. There is no "probably a video"
branch, because the format decides which tool runs, and running the wrong tool
on an unknown file is how a media pipeline executes something it should not.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

#: Ce qu'un fichier peut être. Une famille décide de la chaîne de traitement,
#: donc une famille devinée fait tourner le mauvais outil.
FAMILLE_VIDEO = "video"
FAMILLE_AUDIO = "audio"
FAMILLE_IMAGE = "image"
FAMILLE_VECTEUR = "vector"

#: Le format d'un fichier qu'aucune signature déclarée ne reconnaît. C'est une
#: réponse à part entière : l'appelant doit la traiter, pas la contourner.
FORMAT_INCONNU = "UNKNOWN_FORMAT"

#: Les formats déclarés par la directive §3, avec leur famille et leurs
#: extensions habituelles. Les extensions servent à **comparer**, jamais à
#: décider.
FORMATS: Dict[str, Dict[str, Any]] = {
    "mp4": {"family": FAMILLE_VIDEO, "extensions": (".mp4", ".m4v")},
    "mov": {"family": FAMILLE_VIDEO, "extensions": (".mov", ".qt")},
    "matroska": {"family": FAMILLE_VIDEO, "extensions": (".mkv",)},
    "webm": {"family": FAMILLE_VIDEO, "extensions": (".webm",)},
    "avi": {"family": FAMILLE_VIDEO, "extensions": (".avi",)},
    "wav": {"family": FAMILLE_AUDIO, "extensions": (".wav",)},
    "mp3": {"family": FAMILLE_AUDIO, "extensions": (".mp3",)},
    "aac": {"family": FAMILLE_AUDIO, "extensions": (".aac", ".adts")},
    "flac": {"family": FAMILLE_AUDIO, "extensions": (".flac",)},
    "png": {"family": FAMILLE_IMAGE, "extensions": (".png",)},
    "jpeg": {"family": FAMILLE_IMAGE, "extensions": (".jpg", ".jpeg")},
    "webp": {"family": FAMILLE_IMAGE, "extensions": (".webp",)},
    "gif": {"family": FAMILLE_IMAGE, "extensions": (".gif",)},
    "svg": {"family": FAMILLE_VECTEUR, "extensions": (".svg",)},
}

#: Nombre d'octets lus pour identifier. Assez pour le type de document EBML,
#: qui n'est pas au tout début ; assez peu pour ne jamais charger un film.
OCTETS_LUS = 4096


class IdentificationRefused(ValueError):
    """Un fichier qui ne peut pas être identifié tel qu'il est présenté."""


def _est_riff(entete: bytes, marque: bytes) -> bool:
    """Vrai pour un conteneur RIFF portant cette marque en position 8."""
    return (len(entete) >= 12 and entete[:4] == b"RIFF"
            and entete[8:12] == marque)


def _marque_ftyp(entete: bytes) -> Optional[bytes]:
    """La marque d'un conteneur ISO-BMFF (`ftyp`), s'il y en a une."""
    if len(entete) >= 12 and entete[4:8] == b"ftyp":
        return entete[8:12]
    return None


def _type_ebml(entete: bytes) -> Optional[str]:
    """
    Le type d'un document EBML : `webm` ou `matroska`.

    Les deux partagent la même signature d'en-tête. Les confondre ferait
    annoncer un WebM là où un Matroska attend d'autres codecs — la distinction
    est dans le type de document, pas dans la signature.
    """
    if not entete.startswith(b"\x1a\x45\xdf\xa3"):
        return None
    tete = entete[:OCTETS_LUS]
    if b"webm" in tete:
        return "webm"
    if b"matroska" in tete:
        return "matroska"
    # Un EBML dont le type n'apparaît pas dans les premiers octets existe. Le
    # deviner reviendrait à choisir un codec pour l'appelant.
    return None


def _est_svg(entete: bytes) -> bool:
    """Vrai pour un document SVG, qui est du texte et n'a pas de signature."""
    try:
        debut = entete[:1024].decode("utf-8", errors="ignore").lstrip("﻿").lstrip()
    except Exception:
        return False
    return debut.startswith("<svg") or (
        debut.startswith("<?xml") and "<svg" in debut
    )


def detect_format(header: bytes) -> Optional[str]:
    """
    Le format d'un contenu, d'après ses octets seuls.

    Args:
        header: Les premiers octets du fichier.

    Returns:
        Le nom du format déclaré, ou `None` quand aucune signature ne
        correspond. `None` n'est pas « probablement une vidéo » : le format
        décide quel outil tourne, et lancer le mauvais outil sur un fichier
        inconnu est la façon dont une chaîne média exécute ce qu'elle ne devrait
        pas.
    """
    if not header:
        return None

    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if header.startswith(b"fLaC"):
        return "flac"

    if _est_riff(header, b"WEBP"):
        return "webp"
    if _est_riff(header, b"WAVE"):
        return "wav"
    if _est_riff(header, b"AVI "):
        return "avi"

    marque = _marque_ftyp(header)
    if marque is not None:
        # `qt  ` est QuickTime ; les autres marques ISO-BMFF sont du MP4. Les
        # deux se lisent différemment malgré un en-tête commun.
        return "mov" if marque.rstrip() == b"qt" else "mp4"

    document = _type_ebml(header)
    if document:
        return document

    if header.startswith(b"ID3"):
        return "mp3"
    if len(header) >= 2 and header[0] == 0xFF:
        # ADTS (AAC) et MPEG audio partagent le mot de synchronisation. Le
        # deuxième octet les sépare ; hors de ces valeurs, rien n'est affirmé.
        if header[1] in (0xF1, 0xF9):
            return "aac"
        if header[1] in (0xFB, 0xF3, 0xF2, 0xFA):
            return "mp3"

    if _est_svg(header):
        return "svg"
    return None


def claimed_format(filename: str) -> Optional[str]:
    """
    Le format que le **nom** prétend, sans aucune vérification.

    Args:
        filename: Le nom présenté.

    Returns:
        Le format correspondant à l'extension, ou `None`. C'est une
        déclaration de l'appelant, au même titre que n'importe quelle entrée
        externe : elle est enregistrée, jamais crue.
    """
    extension = os.path.splitext(str(filename or ""))[1].lower()
    if not extension:
        return None
    for nom, details in FORMATS.items():
        if extension in details["extensions"]:
            return nom
    return None


def identify_bytes(header: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Identifie un contenu et compare ce qu'il est à ce qu'il prétend être.

    Args:
        header: Les premiers octets.
        filename: Le nom présenté, s'il y en a un.

    Returns:
        Le format détecté, le format revendiqué, et `mismatch` quand ils
        diffèrent. Le désaccord est **rapporté**, jamais tranché en silence :
        faire confiance au nom rend la chaîne exploitable, et écraser le nom
        sans le dire cache une corruption réelle.
    """
    detecte = detect_format(header)
    revendique = claimed_format(filename)
    famille = FORMATS[detecte]["family"] if detecte else None

    desaccord = bool(detecte and revendique and detecte != revendique)
    return {
        "format": detecte or FORMAT_INCONNU,
        "family": famille,
        "claimed_format": revendique,
        "filename": filename,
        "mismatch": desaccord,
        "identified": detecte is not None,
        "reason": (
            f"Signature reconnue : {detecte}." if detecte and not desaccord else
            f"Le contenu est un {detecte}, le nom annonce un {revendique}. "
            "Le désaccord est rapporté et non tranché : croire le nom rend la "
            "chaîne exploitable, l'écraser en silence cache une corruption."
            if desaccord else
            "Aucune signature déclarée ne correspond. Ce n'est pas « sans "
            "doute une vidéo » : le format décide quel outil tourne."
        ),
    }


def identify_file(path: str) -> Dict[str, Any]:
    """
    Identifie un fichier sur disque.

    Args:
        path: Le chemin, **déjà résolu** par `src/storage/roots.py`. Ce module
            n'ouvre pas de second garde-fou de chemin : il en existe un, et deux
            finiraient par diverger.

    Returns:
        Le résultat de `identify_bytes`, avec la taille du fichier.

    Raises:
        IdentificationRefused: Si le fichier est absent, illisible, ou vide. Un
            fichier vide identifié comme quoi que ce soit ferait démarrer une
            production sur rien.
    """
    if not os.path.isfile(path):
        raise IdentificationRefused(f"Fichier introuvable : « {path} ».")
    try:
        taille = os.path.getsize(path)
        with open(path, "rb") as fichier:
            entete = fichier.read(OCTETS_LUS)
    except OSError as erreur:
        raise IdentificationRefused(f"Fichier illisible : {erreur}") from erreur

    if taille == 0:
        raise IdentificationRefused(
            f"Fichier vide : « {path} ». L'identifier comme quoi que ce soit "
            "ferait démarrer une production sur rien."
        )

    resultat = identify_bytes(entete, os.path.basename(path))
    resultat["path"] = path
    resultat["bytes"] = taille
    return resultat


def supported_formats() -> Dict[str, List[str]]:
    """
    Les formats déclarés, par famille.

    Returns:
        Chaque famille et les formats qu'elle contient. Un format absent de
        cette table est inconnu du moteur, quelle que soit sa popularité.
    """
    par_famille: Dict[str, List[str]] = {}
    for nom, details in FORMATS.items():
        par_famille.setdefault(details["family"], []).append(nom)
    return {famille: sorted(noms) for famille, noms in sorted(par_famille.items())}


def identification_report() -> Dict[str, Any]:
    """
    Ce que l'identification garantit, et ce qu'elle refuse.

    Returns:
        Les formats, les familles, et les règles tenues.
    """
    return {
        "formats": sorted(FORMATS),
        "families": supported_formats(),
        "unknown": FORMAT_INCONNU,
        "header_bytes": OCTETS_LUS,
        "rules": [
            "L'extension est une **déclaration**, la signature est la preuve. "
            "Un nom de fichier est une entrée externe.",
            "Un désaccord entre les deux est **rapporté**, jamais tranché en "
            "silence : croire le nom rend la chaîne exploitable, l'écraser "
            "cache une corruption.",
            "`webm` et `matroska` partagent une signature : la distinction "
            "vient du type de document, pas de l'en-tête.",
            "Une signature inconnue rend `UNKNOWN_FORMAT` — pas « sans doute "
            "une vidéo ». Le format décide quel outil tourne.",
            "Le chemin est résolu par `src/storage/roots.py` en amont : ce "
            "module n'ouvre pas un second garde-fou.",
        ],
        "does_not": [
            "Deviner un format depuis son extension.",
            "Choisir entre le nom et le contenu sans le dire.",
            "Identifier un fichier vide.",
            "Exécuter quoi que ce soit sur un contenu non identifié.",
        ],
    }
