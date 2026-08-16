"""
Music whose rights are known, or music that does not get used.

Directive §14 asks for BPM, energy, mood, structure, duration, vocal presence
and genre, then ends on the sentence that outranks all of them: *respect
licensing metadata and never claim unknown copyright status.*

That sentence is the one with consequences outside the software. Every other
field here being wrong produces a video that feels off. This one being wrong
produces a takedown, an invoice, or a client who cannot broadcast the thing they
paid for. So `UNKNOWN` licensing **blocks use** rather than being carried as a
warning: a track whose terms nobody read is not "probably fine", and the moment
a pipeline treats it as usable is the moment nobody looks again.

The analysis fields follow the discipline the rest of the engine uses. On this
machine `audio_decode` is UNAVAILABLE — there is no audio codec at all — so BPM,
energy and vocal presence cannot be measured. They are `None` with a reason, and
`None` is never 120 BPM. A sync computed from a default tempo puts every cut a
little off the beat, which is precisely the failure a music-sync feature exists
to avoid.

Synchronisation itself is computable without decoding anything, because it does
not need the audio: it needs the **scene boundaries**, which VOLET M04 measured
from frames. Aligning a cut to a beat requires a measured BPM; aligning music
*sections* to scene changes requires only the scene changes. The first is
refused here, the second works.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from ..core.capabilities import DISPONIBLE, probe

#: L'état des droits d'un morceau. `UNKNOWN` n'est pas une nuance de
#: « probablement libre » : c'est un blocage.
DROITS_CONNUS = "CLEARED"
DROITS_INCONNUS = "UNKNOWN"
DROITS_REFUSES = "RESTRICTED"

#: Les champs d'analyse demandés par la directive §14.
CHAMPS_ANALYSE = ("bpm", "energy", "mood", "duration_s", "vocal_presence", "genre")


class MusicRefused(ValueError):
    """Un morceau qui ne peut pas être employé tel qu'il est déclaré."""


@dataclass(frozen=True)
class MusicTrack:
    """
    Un morceau, ses droits, et ce qu'on a réellement mesuré de lui.

    Attributes:
        track_id: Son identité.
        title: Son titre.
        rights: `CLEARED`, `UNKNOWN` ou `RESTRICTED`.
        licence: La licence, quand elle a été lue.
        source: D'où il vient.
        attribution_required: Si la licence exige une mention.
        measured: Les champs réellement mesurés.
        unknown_reason: Pourquoi les autres ne le sont pas.
    """

    track_id: str
    title: str = ""
    rights: str = DROITS_INCONNUS
    licence: str = ""
    source: str = ""
    attribution_required: bool = False
    measured: Dict[str, Any] = None  # type: ignore[assignment]
    unknown_reason: str = ""

    def __post_init__(self) -> None:
        if self.rights not in (DROITS_CONNUS, DROITS_INCONNUS, DROITS_REFUSES):
            raise MusicRefused(
                f"État de droits « {self.rights} » inconnu. Déclarés : "
                f"{[DROITS_CONNUS, DROITS_INCONNUS, DROITS_REFUSES]}."
            )
        if self.measured is None:
            object.__setattr__(self, "measured", {})
        if self.rights == DROITS_CONNUS and not str(self.licence or "").strip():
            raise MusicRefused(
                f"« {self.track_id} » est déclaré libéré sans licence nommée. "
                "Un morceau « libéré » sans licence est un morceau dont "
                "personne n'a lu les termes, et l'écrire ainsi fait que "
                "personne ne regardera plus."
            )

    @property
    def usable(self) -> bool:
        """Vrai seulement pour des droits **connus et accordés**."""
        return self.rights == DROITS_CONNUS

    def get(self, champ: str) -> Optional[Any]:
        """La valeur mesurée d'un champ, ou `None` s'il ne l'a pas été."""
        return self.measured.get(champ)

    @property
    def unmeasured_fields(self) -> List[str]:
        """Les champs d'analyse que personne n'a mesurés."""
        return [champ for champ in CHAMPS_ANALYSE if champ not in self.measured]

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences comprises."""
        return {
            "track_id": self.track_id, "title": self.title,
            "rights": self.rights, "licence": self.licence,
            "source": self.source,
            "attribution_required": self.attribution_required,
            "usable": self.usable,
            "measured": dict(self.measured),
            "unmeasured_fields": self.unmeasured_fields,
            "unknown_reason": self.unknown_reason,
        }


def require_rights(track: MusicTrack) -> None:
    """
    Exige des droits connus avant tout emploi.

    Args:
        track: Le morceau.

    Raises:
        MusicRefused: Pour des droits inconnus ou refusés. `UNKNOWN` bloque :
            un morceau dont personne n'a lu les termes n'est pas « probablement
            libre », et le traiter comme utilisable est le moment où plus
            personne ne regarde. Les conséquences sortent du logiciel — un
            retrait, une facture, ou un client qui ne peut pas diffuser ce
            qu'il a payé.
    """
    if track.rights == DROITS_CONNUS:
        return
    raise MusicRefused(
        f"« {track.track_id} » : droits {track.rights}. "
        + (
            "Un morceau dont personne n'a lu les termes n'est pas "
            "« probablement libre ». Les conséquences sortent du logiciel : un "
            "retrait, une facture, ou un client qui ne peut pas diffuser ce "
            "qu'il a payé."
            if track.rights == DROITS_INCONNUS else
            "La licence lue refuse cet usage."
        )
    )


def analyse_status(track: MusicTrack) -> Dict[str, Any]:
    """
    Ce qui est mesurable de ce morceau sur cette machine.

    Args:
        track: Le morceau.

    Returns:
        L'état de `audio_decode`, les champs mesurés et ceux qui ne le sont pas.
        Rien n'est estimé : un BPM par défaut met chaque coupe légèrement à
        côté du temps, ce qui est exactement le défaut qu'une synchronisation
        musicale existe pour éviter.
    """
    sonde = probe("audio_decode")
    return {
        "track_id": track.track_id,
        "capability_state": sonde["state"],
        "measurable": sonde["state"] == DISPONIBLE,
        "measured": dict(track.measured),
        "unmeasured": track.unmeasured_fields,
        "reason": (
            "Analyse audio possible."
            if sonde["state"] == DISPONIBLE else
            f"`audio_decode` est {sonde['state']}. BPM, énergie et présence "
            "vocale ne sont pas mesurés et ne sont pas estimés : un BPM par "
            "défaut met chaque coupe légèrement à côté du temps."
        ),
    }


def sync_to_scenes(
    track: MusicTrack,
    scene_times: Sequence[float],
    music_start: float = 0.0,
) -> Dict[str, Any]:
    """
    Aligne des changements de section musicale sur des changements de scène.

    Args:
        track: Le morceau — ses droits sont exigés avant tout emploi.
        scene_times: Les instants de changement de scène, **mesurés** (VOLET
            M04 les calcule sur les trames, avec une cadence mesurée).
        music_start: L'instant où le morceau démarre dans la timeline.

    Returns:
        Les points de synchronisation, et ce qui n'a pas pu être aligné. Aligner
        sur des scènes ne demande **pas** de décoder l'audio : c'est l'alignement
        sur le tempo qui l'exige, et il est refusé ici faute de BPM mesuré.

    Raises:
        MusicRefused: Droits inconnus ou refusés, ou aucun instant de scène.
    """
    require_rights(track)
    if not scene_times:
        raise MusicRefused(
            "Aucun instant de scène : il n'y a rien sur quoi aligner. Poser des "
            "points réguliers à la place fabriquerait un rythme que la vidéo "
            "n'a pas."
        )

    points = [
        {"at": round(instant, 4), "offset_in_track": round(instant - music_start, 4),
         "derived_from": "scene_boundary"}
        for instant in sorted(scene_times) if instant >= music_start
    ]

    bpm = track.get("bpm")
    return {
        "track_id": track.track_id,
        "sync_points": points,
        "beat_aligned": False,
        "bpm": bpm,
        "beat_alignment_reason": (
            "Alignement sur le tempo possible : un BPM a été mesuré."
            if bpm is not None else
            "Aucun BPM mesuré : l'alignement sur le temps n'est pas tenté. "
            "Un tempo supposé met chaque coupe légèrement à côté, ce qui "
            "s'entend sans qu'on sache le nommer."
        ),
        "ignored_before_start": len(scene_times) - len(points),
        "note": (
            "Aligner des sections sur des scènes ne demande pas de décoder "
            "l'audio — seulement des instants de scène mesurés. C'est "
            "l'alignement sur le tempo qui exige un BPM."
        ),
    }


def credits_for(tracks: Sequence[MusicTrack]) -> Dict[str, Any]:
    """
    Les mentions à porter au générique.

    Args:
        tracks: Les morceaux employés.

    Returns:
        Les mentions exigées par les licences, et les morceaux dont les droits
        ne permettent pas l'emploi. Oublier une mention exigée est une
        violation de licence aussi sûrement qu'un emploi sans droits.
    """
    mentions = [
        {"track_id": piste.track_id, "title": piste.title,
         "licence": piste.licence, "source": piste.source}
        for piste in tracks
        if piste.usable and piste.attribution_required
    ]
    bloques = [
        {"track_id": piste.track_id, "rights": piste.rights}
        for piste in tracks if not piste.usable
    ]
    return {
        "credits": mentions,
        "blocked_tracks": bloques,
        "complete": not bloques,
        "note": (
            "Oublier une mention exigée est une violation de licence aussi "
            "sûrement qu'un emploi sans droits."
        ),
    }


def music_report() -> Dict[str, Any]:
    """
    Ce que la couche musicale garantit, et ce qu'elle refuse.

    Returns:
        Les états de droits, les champs d'analyse, et les règles tenues.
    """
    return {
        "rights_states": [DROITS_CONNUS, DROITS_INCONNUS, DROITS_REFUSES],
        "analysis_fields": list(CHAMPS_ANALYSE),
        "rules": [
            "`UNKNOWN` **bloque l'emploi**. Un morceau dont personne n'a lu les "
            "termes n'est pas « probablement libre », et le traiter comme "
            "utilisable est le moment où plus personne ne regarde.",
            "Les conséquences d'une erreur ici sortent du logiciel : un "
            "retrait, une facture, ou un client qui ne peut pas diffuser ce "
            "qu'il a payé.",
            "« Libéré » sans licence nommée est refusé : l'écrire ainsi fait "
            "que personne ne regardera plus.",
            "Aucun champ d'analyse n'est estimé. `None` n'est jamais 120 BPM — "
            "un tempo supposé met chaque coupe légèrement à côté du temps.",
            "Aligner des sections sur des scènes ne demande pas de décoder "
            "l'audio ; aligner sur le tempo l'exige, et est refusé sans BPM "
            "mesuré.",
            "Une mention exigée oubliée est une violation, au même titre qu'un "
            "emploi sans droits.",
        ],
        "does_not": [
            "Employer un morceau dont les droits sont inconnus.",
            "Estimer un BPM, une énergie ou une présence vocale.",
            "Aligner sur un tempo supposé.",
            "Poser des points de synchronisation réguliers faute de scènes.",
        ],
    }
