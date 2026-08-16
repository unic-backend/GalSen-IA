"""
Render success is not production success — made mechanical.

Directive §21 names the distinction and §20 lists what to check. The distinction
only survives if a check that could not run is impossible to confuse with a
check that passed, so this module has three outcomes and never two:

- `PASS` — the check ran and the file is fine.
- `FAIL` — the check ran and found something.
- `NOT_CHECKED` — the check could not run, with the reason and the capability
  that would let it.

Two outcomes would collapse the third into `PASS`, and that collapse is the
entire failure §21 is about. A pipeline reporting "12 checks passed" when four
of them never executed is more dangerous than one with no checks: it produces a
green report that a human then trusts instead of watching the video.

So the overall verdict is deliberately hard to reach. `PRODUCTION_SUCCESS`
requires every applicable check to pass **and** nothing important to be
unchecked. When audio cannot be decoded, the audio checks are `NOT_CHECKED`, and
the verdict is `INCOMPLETE` — not "passed, with notes". A production nobody
could fully inspect has not been fully inspected, and saying so is the only
honest output.

What is checkable here is real and worth having: the file exists and is not
empty, its format is what was asked for, its frame count matches the plan, its
subtitles fit their windows, its assets carry provenance, and the final
transcript matches the intended one (M06). What is not checkable — loudness,
clipping, black frames inside an undecodable container — says so by name.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

from ..core.capabilities import DISPONIBLE, probe

#: Les trois issues. Deux seulement feraient de `NOT_CHECKED` un `PASS`, et
#: c'est exactement l'effondrement que la directive §21 vise.
PASSE = "PASS"
ECHOUE = "FAIL"
NON_VERIFIE = "NOT_CHECKED"

#: Les verdicts d'ensemble.
PRODUCTION_REUSSIE = "PRODUCTION_SUCCESS"
PRODUCTION_INCOMPLETE = "INCOMPLETE"
PRODUCTION_ECHOUEE = "PRODUCTION_FAILED"

#: Les familles de contrôle demandées par la directive §20.
FAMILLES = ("video", "audio", "subtitles", "content")


class QualityControlRefused(ValueError):
    """Un contrôle qu'on ne peut pas conduire tel qu'il est demandé."""


def _resultat(
    nom: str, famille: str, issue: str, detail: str, **extra: Any,
) -> Dict[str, Any]:
    """Le résultat d'un contrôle."""
    return {
        "check": nom, "family": famille, "outcome": issue, "detail": detail,
        **extra,
    }


# ----------------------------------------------------------------------
# Vidéo
# ----------------------------------------------------------------------

def check_file(path: str, expected_format: str = "") -> List[Dict[str, Any]]:
    """
    Le fichier existe, n'est pas vide, et est ce qu'il prétend être.

    Args:
        path: Le fichier rendu.
        expected_format: Le format attendu, s'il a été demandé.

    Returns:
        Les contrôles de présence et de format. Un fichier de zéro octet
        s'encode « sans erreur » sur plus d'un encodeur : la taille est le
        premier contrôle, pas une formalité.
    """
    from ..ingestion.identify import IdentificationRefused, identify_file

    if not os.path.isfile(path):
        return [_resultat("file_exists", "video", ECHOUE,
                          f"Aucun fichier en « {path} ».")]

    taille = os.path.getsize(path)
    controles = [
        _resultat(
            "file_not_empty", "video", PASSE if taille > 0 else ECHOUE,
            f"{taille} octets."
            + ("" if taille else " Un fichier vide s'encode « sans erreur » "
                                 "sur plus d'un encodeur."),
            bytes=taille,
        ),
    ]
    if taille == 0:
        return controles

    try:
        identite = identify_file(path)
    except IdentificationRefused as erreur:
        controles.append(_resultat("format_identified", "video", ECHOUE,
                                   str(erreur)))
        return controles

    controles.append(_resultat(
        "format_identified", "video",
        PASSE if identite["identified"] else ECHOUE,
        f"Format détecté : {identite['format']}.",
        format=identite["format"],
    ))
    if expected_format:
        conforme = identite["format"] == expected_format
        controles.append(_resultat(
            "format_matches_request", "video", PASSE if conforme else ECHOUE,
            f"Attendu {expected_format}, obtenu {identite['format']}.",
        ))
    return controles


def check_frames(rendered: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Le nombre de trames envoyées correspond à ce que la scène décrivait.

    Args:
        rendered: Le rapport de `motion.render.render_video`.

    Returns:
        Le contrôle de complétude. Un encodage interrompu produit un fichier
        lisible et plus court — il passe tous les contrôles de format.
    """
    envoyees = rendered.get("frames_sent")
    attendues = rendered.get("expected_frames")
    if envoyees is None or attendues is None:
        return [_resultat(
            "frame_count", "video", NON_VERIFIE,
            "Le rapport de rendu ne porte pas de décompte de trames.",
        )]
    return [_resultat(
        "frame_count", "video", PASSE if envoyees == attendues else ECHOUE,
        f"{envoyees} trames envoyées sur {attendues} attendues."
        + ("" if envoyees == attendues else " Un encodage interrompu produit "
                                            "un fichier lisible et plus court."),
    )]


def check_black_frames(path: str) -> List[Dict[str, Any]]:
    """
    Les trames noires — non vérifiables sans décodage vidéo.

    Returns:
        `NOT_CHECKED` avec la capacité qui le permettrait. Déclarer « aucune
        trame noire » sans avoir regardé une seule trame serait le mensonge que
        cette famille de contrôles existe pour éviter.
    """
    sonde = probe("video_decode")
    if sonde["state"] != DISPONIBLE:
        return [_resultat(
            "black_frames", "video", NON_VERIFIE,
            f"`video_decode` est {sonde['state']} — {sonde['reason']} "
            "Déclarer « aucune trame noire » sans avoir regardé une seule "
            "trame serait le mensonge que ce contrôle existe pour éviter.",
            needs="video_decode",
        )]
    return [_resultat("black_frames", "video", NON_VERIFIE,
                      "Décodage disponible ; analyse non implémentée.",
                      needs="video_decode")]


# ----------------------------------------------------------------------
# Audio
# ----------------------------------------------------------------------

def check_audio(path: str) -> List[Dict[str, Any]]:
    """
    Écrêtage, silence et sonie — non vérifiables sans décodage audio.

    Returns:
        Trois `NOT_CHECKED` nommés. Les taire ferait un rapport qui semble
        complet, ce qui est pire que trois absences déclarées.
    """
    sonde = probe("audio_decode")
    raison = (
        f"`audio_decode` est {sonde['state']} — {sonde['reason']}"
        if sonde["state"] != DISPONIBLE else
        "Décodage disponible ; analyse non implémentée."
    )
    return [
        _resultat(nom, "audio", NON_VERIFIE, raison, needs="audio_decode")
        for nom in ("clipping", "silence", "loudness")
    ]


# ----------------------------------------------------------------------
# Sous-titres
# ----------------------------------------------------------------------

def check_subtitles(cues: Sequence[Any]) -> List[Dict[str, Any]]:
    """
    Débordement, durée, vitesse de lecture et chevauchement.

    Args:
        cues: Les sous-titres, tels que `subtitles.cues.build_cues` les rend.

    Returns:
        Un contrôle par défaut trouvé, et un `PASS` quand il n'y en a aucun.
        Le chevauchement est vérifié ici parce qu'il ne se voit pas dans une
        liste : deux sous-titres qui se recouvrent s'affichent l'un sur l'autre.
    """
    from ..subtitles.cues import check_cue

    if not cues:
        return [_resultat("subtitles_present", "subtitles", NON_VERIFIE,
                          "Aucun sous-titre fourni au contrôle.")]

    problemes: List[str] = []
    for cue in cues:
        verdict = check_cue(cue)
        problemes.extend(
            f"#{cue.index} {p['kind']}" for p in verdict["problems"]
        )

    ordonnes = sorted(cues, key=lambda c: c.start)
    chevauchements = [
        f"#{precedent.index}/#{suivant.index}"
        for precedent, suivant in zip(ordonnes, ordonnes[1:])
        if suivant.start < precedent.end
    ]

    return [
        _resultat(
            "subtitle_quality", "subtitles",
            PASSE if not problemes else ECHOUE,
            "Aucun défaut." if not problemes
            else f"{len(problemes)} défaut(s) : {', '.join(problemes[:5])}.",
        ),
        _resultat(
            "subtitle_overlap", "subtitles",
            PASSE if not chevauchements else ECHOUE,
            "Aucun chevauchement." if not chevauchements
            else f"{len(chevauchements)} paire(s) qui se recouvrent : "
                 f"{', '.join(chevauchements[:5])}. Elles s'afficheront l'une "
                 "sur l'autre.",
        ),
    ]


# ----------------------------------------------------------------------
# Contenu
# ----------------------------------------------------------------------

def check_content(
    intended_transcript: str = "",
    final_transcript: Optional[str] = None,
    assets: Sequence[Any] = (),
) -> List[Dict[str, Any]]:
    """
    Ce que la production **dit**, et ce qu'elle emploie.

    Args:
        intended_transcript: Le texte que le montage devait produire (M06).
        final_transcript: Le texte re-transcrit du rendu.
        assets: Les assets employés.

    Returns:
        La comparaison de transcription et la complétude de provenance. Le
        premier contrôle est celui qui attrape une coupe ayant enlevé le mot
        « pas ».
    """
    from ..timeline.verify import CONFORME, NON_VERIFIE as VERIF_ABSENTE, verify_render

    controles: List[Dict[str, Any]] = []

    if intended_transcript:
        verdict = verify_render(intended_transcript, final_transcript)
        if verdict["verdict"] == VERIF_ABSENTE:
            controles.append(_resultat(
                "transcript_matches_intent", "content", NON_VERIFIE,
                verdict["reason"], needs="transcription",
            ))
        else:
            controles.append(_resultat(
                "transcript_matches_intent", "content",
                PASSE if verdict["verdict"] == CONFORME else ECHOUE,
                verdict["reason"],
            ))
    else:
        controles.append(_resultat(
            "transcript_matches_intent", "content", NON_VERIFIE,
            "Aucun texte attendu fourni : il n'y a pas de référence à comparer.",
        ))

    incomplets = [
        getattr(asset, "asset_id", "?") for asset in assets
        if getattr(asset, "missing_fields", None)
        or not getattr(asset, "usable", True)
    ]
    controles.append(_resultat(
        "asset_provenance", "content",
        PASSE if not incomplets else ECHOUE,
        "Tous les assets portent une provenance complète."
        if not incomplets else
        f"{len(incomplets)} asset(s) sans provenance défendable : "
        f"{', '.join(incomplets[:5])}.",
    ))
    return controles


# ----------------------------------------------------------------------
# Verdict d'ensemble
# ----------------------------------------------------------------------

def verdict(checks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Le verdict d'ensemble, difficile à atteindre exprès.

    Args:
        checks: Tous les contrôles menés.

    Returns:
        `PRODUCTION_SUCCESS` seulement si **tout** ce qui était applicable est
        passé et que rien n'est resté non vérifié. Sinon `INCOMPLETE` — pas
        « passé, avec réserves ». Une production que personne n'a pu inspecter
        entièrement n'a pas été inspectée entièrement, et le dire est la seule
        sortie honnête.
    """
    if not checks:
        return {
            "verdict": PRODUCTION_INCOMPLETE,
            "reason": (
                "Aucun contrôle mené. Un rapport vide n'est pas une réussite : "
                "c'est l'absence de contrôle."
            ),
            "counts": {PASSE: 0, ECHOUE: 0, NON_VERIFIE: 0},
        }

    comptes = {
        issue: sum(1 for c in checks if c["outcome"] == issue)
        for issue in (PASSE, ECHOUE, NON_VERIFIE)
    }
    non_verifies = [c["check"] for c in checks if c["outcome"] == NON_VERIFIE]
    echecs = [c["check"] for c in checks if c["outcome"] == ECHOUE]

    if echecs:
        etat, raison = PRODUCTION_ECHOUEE, (
            f"{len(echecs)} contrôle(s) en échec : {', '.join(echecs[:5])}."
        )
    elif non_verifies:
        etat, raison = PRODUCTION_INCOMPLETE, (
            f"{len(non_verifies)} contrôle(s) **non vérifiés** : "
            f"{', '.join(non_verifies[:5])}. Une production que personne n'a pu "
            "inspecter entièrement n'a pas été inspectée entièrement."
        )
    else:
        etat, raison = PRODUCTION_REUSSIE, (
            "Tous les contrôles applicables sont passés, et aucun n'est resté "
            "non vérifié."
        )

    return {
        "verdict": etat,
        "counts": comptes,
        "failed": echecs,
        "not_checked": non_verifies,
        "by_family": {
            famille: [c["check"] for c in checks if c["family"] == famille]
            for famille in FAMILLES
        },
        "reason": raison,
        "note": (
            "Un rendu terminé n'est pas une production réussie. `NOT_CHECKED` "
            "n'est jamais compté comme `PASS` : « 12 contrôles passés » quand "
            "quatre n'ont jamais tourné produit un rapport vert qu'un humain "
            "croit au lieu de regarder la vidéo."
        ),
    }


def qc_report() -> Dict[str, Any]:
    """
    Ce que le contrôle qualité garantit, et ce qu'il refuse.

    Returns:
        Les issues, les familles, et les règles tenues.
    """
    return {
        "outcomes": [PASSE, ECHOUE, NON_VERIFIE],
        "verdicts": [PRODUCTION_REUSSIE, PRODUCTION_INCOMPLETE, PRODUCTION_ECHOUEE],
        "families": list(FAMILLES),
        "rules": [
            "Trois issues, jamais deux : deux feraient de `NOT_CHECKED` un "
            "`PASS`, et c'est l'effondrement que la directive §21 vise.",
            "`PRODUCTION_SUCCESS` exige que **tout** soit passé et que rien ne "
            "soit resté non vérifié. Sinon `INCOMPLETE`, pas « passé avec "
            "réserves ».",
            "Un contrôle non vérifiable nomme la **capacité** qui le "
            "permettrait — « aucune trame noire » sans avoir regardé une trame "
            "serait le mensonge que ce contrôle existe pour éviter.",
            "Un rapport vide n'est pas une réussite : c'est l'absence de "
            "contrôle.",
            "La taille du fichier est le premier contrôle : un fichier de zéro "
            "octet s'encode « sans erreur » sur plus d'un encodeur.",
        ],
        "does_not": [
            "Compter un contrôle non vérifié comme réussi.",
            "Déclarer une production réussie sans avoir tout inspecté.",
            "Affirmer l'absence d'un défaut qu'aucun outil n'a cherché.",
            "Rendre un verdict sur zéro contrôle.",
        ],
    }
