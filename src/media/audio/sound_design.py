"""
A sound sits on an event, or it does not exist.

Directive §13 describes a semantic sound system — EVENT → TIMING → SOUND →
VOLUME → MIX — and §12 adds the sentence that decides the whole design:
*sound effects must be placed according to actual timeline events. Do not
randomly place sounds.*

"Randomly" is generous. What actually happens is worse and looks better: a
system places a riser "at the reveal" by asking a model when the reveal is, gets
a confident 4.2 seconds, and drops a sound there. It lands half a second before
the cut, every time, and the edit feels vaguely wrong in a way nobody can name
in a review. So a placement here carries `derived_from`: the event that caused
it and where that event's time came from. An event with no measured time
produces **no sound**, reported by name.

Ducking follows the same rule and is the one part of a mix that is genuinely
computable without decoding audio: if a music bed overlaps a region where
someone is speaking, the music comes down for exactly that region. The speech
regions come from the word timings of M05 — measured, never interpolated — so a
duck window is as trustworthy as the words that produced it.

What this module cannot do here is stated rather than skipped. `audio_decode` is
UNAVAILABLE on this machine: no codec at all. So loudness, energy and true peak
are not measured, and nothing invents them — a normalisation target computed
from an unmeasured loudness would push a mix in a direction nobody chose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.capabilities import DISPONIBLE, probe

#: Les événements de timeline auxquels un son peut se rattacher. Un son demandé
#: pour un événement absent de cette table n'est pas « à peu près » un autre :
#: il n'a pas de moment, donc il n'a pas de place.
EVENEMENTS = (
    "scene_start",
    "scene_end",
    "cut",
    "reveal",
    "highlight",
    "section_transition",
    "emphasis",
)

#: Les familles de son, et les événements qu'elles servent (§13). Déclarées :
#: un rapprochement implicite entre un événement et un son est une décision de
#: montage prise par l'auteur du cadre.
FAMILLES = {
    "riser": {"serves": ("reveal", "section_transition"),
              "default_gain_db": -8.0,
              "lead_in_s": 1.2},
    "impact": {"serves": ("reveal", "cut"),
               "default_gain_db": -6.0,
               "lead_in_s": 0.0},
    "marker": {"serves": ("highlight", "emphasis"),
               "default_gain_db": -14.0,
               "lead_in_s": 0.0},
    "transition": {"serves": ("section_transition", "scene_start", "scene_end"),
                   "default_gain_db": -10.0,
                   "lead_in_s": 0.15},
}

#: Atténuation appliquée à un lit musical sous une voix. Déclarée, donc
#: discutable : trop faible, la voix se bat avec la musique ; trop forte,
#: le morceau disparaît et revient en pompant.
ATTENUATION_VOIX_DB = -12.0

#: Marge ajoutée de part et d'autre d'une région parlée avant d'atténuer. Sans
#: elle, l'atténuation démarre pile sur la première syllabe et s'entend.
MARGE_DUCKING_S = 0.25


class SoundRefused(ValueError):
    """Un son demandé qui ne peut être posé nulle part de défendable."""


@dataclass(frozen=True)
class TimelineEvent:
    """
    Un moment de la timeline auquel un son peut se rattacher.

    Attributes:
        kind: Un événement de `EVENEMENTS`.
        at: L'instant, en secondes.
        source: D'où vient cet instant — `scene_boundary`, `word_timing`,
            `edit_plan`. Un instant sans source est un instant que personne ne
            peut vérifier.
        label: De quoi il s'agit, pour la relecture.
    """

    kind: str
    at: float
    source: str
    label: str = ""

    def __post_init__(self) -> None:
        if self.kind not in EVENEMENTS:
            raise SoundRefused(
                f"Événement « {self.kind} » non déclaré. Déclarés : "
                f"{list(EVENEMENTS)}. Un son demandé pour un événement inconnu "
                "n'a pas de moment, donc pas de place."
            )
        if not str(self.source or "").strip():
            raise SoundRefused(
                f"Événement « {self.kind} » à {self.at} s sans source. Un "
                "instant que personne ne peut vérifier est un instant inventé, "
                "et le son posé dessus tombe à côté de la coupe."
            )
        if self.at < 0:
            raise SoundRefused(f"Instant négatif : {self.at} s.")


@dataclass(frozen=True)
class SoundCue:
    """
    Un son posé, et la raison pour laquelle il est là.

    Attributes:
        family: La famille employée.
        at: L'instant où le son démarre.
        event_kind: L'événement qui l'a causé.
        event_at: L'instant de cet événement.
        gain_db: Le niveau.
        derived_from: La source de l'instant de l'événement.
    """

    family: str
    at: float
    event_kind: str
    event_at: float
    gain_db: float
    derived_from: str

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "family": self.family, "at": self.at,
            "event_kind": self.event_kind, "event_at": self.event_at,
            "gain_db": self.gain_db, "derived_from": self.derived_from,
        }


def families_for(event_kind: str) -> List[str]:
    """
    Les familles de son déclarées pour un événement.

    Args:
        event_kind: L'événement.

    Returns:
        Les familles qui le servent, triées. Vide quand aucune ne le sert —
        et une famille voisine n'est pas proposée : rapprocher un « impact »
        d'un « marker » est une décision de montage.
    """
    return sorted(
        nom for nom, details in FAMILLES.items()
        if event_kind in details["serves"]
    )


def place_sounds(
    events: Sequence[TimelineEvent],
    choices: Optional[Dict[str, str]] = None,
    gains: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Pose un son par événement, chacun rattaché à ce qui l'a causé.

    Args:
        events: Les événements de la timeline, avec leurs instants **mesurés**.
        choices: La famille voulue par événement, quand plusieurs conviennent.
        gains: Les niveaux voulus par famille.

    Returns:
        Les sons posés, et les événements laissés **sans son avec leur raison**.
        Un son est toujours attaché à un événement : sans événement, il n'y a
        pas de moment, et un moment demandé à un modèle tombe une demi-seconde
        avant la coupe — à chaque fois, et sans que personne sache le nommer en
        relecture.
    """
    voulues = choices or {}
    niveaux = gains or {}

    poses: List[SoundCue] = []
    sans_son: List[Dict[str, Any]] = []

    for evenement in events:
        candidates = families_for(evenement.kind)
        if not candidates:
            sans_son.append({
                "event_kind": evenement.kind, "at": evenement.at,
                "reason": (
                    f"Aucune famille déclarée ne sert « {evenement.kind} ». "
                    "En proposer une voisine serait une décision de montage."
                ),
            })
            continue

        famille = voulues.get(evenement.kind, candidates[0])
        if famille not in FAMILLES:
            sans_son.append({
                "event_kind": evenement.kind, "at": evenement.at,
                "reason": f"Famille « {famille} » non déclarée.",
            })
            continue
        if evenement.kind not in FAMILLES[famille]["serves"]:
            sans_son.append({
                "event_kind": evenement.kind, "at": evenement.at,
                "reason": (
                    f"« {famille} » ne sert pas « {evenement.kind} » "
                    f"(sert : {list(FAMILLES[famille]['serves'])})."
                ),
            })
            continue

        # Un riser doit **commencer avant** son événement pour y arriver : son
        # amorce est déclarée par la famille, pas devinée au cas par cas.
        amorce = FAMILLES[famille]["lead_in_s"]
        poses.append(SoundCue(
            family=famille,
            at=round(max(evenement.at - amorce, 0.0), 4),
            event_kind=evenement.kind,
            event_at=evenement.at,
            gain_db=niveaux.get(famille, FAMILLES[famille]["default_gain_db"]),
            derived_from=evenement.source,
        ))

    return {
        "cues": [cue.as_dict() for cue in sorted(poses, key=lambda c: c.at)],
        "objects": sorted(poses, key=lambda c: c.at),
        "events_without_sound": sans_son,
        "placed": len(poses),
        "note": (
            "Chaque son porte l'événement qui l'a causé et la source de "
            "l'instant de cet événement. Un son sans événement n'a pas de "
            "moment défendable."
        ),
    }


def duck_windows(
    speech_regions: Sequence[Tuple[float, float]],
    music_start: float,
    music_end: float,
    attenuation_db: float = ATTENUATION_VOIX_DB,
    margin: float = MARGE_DUCKING_S,
) -> Dict[str, Any]:
    """
    Les fenêtres où le lit musical doit descendre sous la voix.

    Args:
        speech_regions: Les régions parlées, en secondes, telles que les temps
            de mot **mesurés** les donnent (VOLET M05).
        music_start: Début du lit musical.
        music_end: Fin du lit musical.
        attenuation_db: L'atténuation appliquée.
        margin: Marge de part et d'autre. Sans elle, l'atténuation démarre pile
            sur la première syllabe et s'entend.

    Returns:
        Les fenêtres fusionnées, l'atténuation, et la part de musique atténuée.
        C'est la seule partie du mixage réellement calculable sans décoder
        d'audio : une fenêtre vaut exactement ce que valent les mots qui l'ont
        produite.

    Raises:
        SoundRefused: Si le lit musical est vide ou inversé.
    """
    if music_end <= music_start:
        raise SoundRefused(
            f"Lit musical vide ou inversé ({music_start} → {music_end})."
        )

    brutes: List[Tuple[float, float]] = []
    for debut, fin in speech_regions:
        if fin <= debut:
            continue
        depart = max(debut - margin, music_start)
        arrivee = min(fin + margin, music_end)
        if arrivee > depart:
            brutes.append((round(depart, 4), round(arrivee, 4)))

    # Deux régions parlées proches produisent deux atténuations qui se touchent.
    # Les laisser séparées ferait remonter la musique entre deux mots, ce qui
    # s'entend comme un pompage.
    fusionnees: List[List[float]] = []
    for depart, arrivee in sorted(brutes):
        if fusionnees and depart <= fusionnees[-1][1]:
            fusionnees[-1][1] = max(fusionnees[-1][1], arrivee)
        else:
            fusionnees.append([depart, arrivee])

    couverte = sum(fin - debut for debut, fin in fusionnees)
    return {
        "windows": [
            {"start": debut, "end": fin, "gain_db": attenuation_db}
            for debut, fin in fusionnees
        ],
        "attenuation_db": attenuation_db,
        "margin": margin,
        "ducked_ratio": round(couverte / (music_end - music_start), 4),
        "merged_from": len(brutes),
        "note": (
            "Les fenêtres qui se touchent sont fusionnées : les laisser "
            "séparées ferait remonter la musique entre deux mots, ce qui "
            "s'entend comme un pompage."
        ),
    }


def loudness_status() -> Dict[str, Any]:
    """
    Ce que la sonie peut être ici — c'est-à-dire rien.

    Returns:
        L'état mesuré de `audio_decode` et ce que son absence empêche. Une cible
        de normalisation calculée sur une sonie non mesurée pousserait un mixage
        dans une direction que personne n'a choisie.
    """
    sonde = probe("audio_decode")
    mesurable = sonde["state"] == DISPONIBLE
    return {
        "measurable": mesurable,
        "capability_state": sonde["state"],
        "integrated_loudness_lufs": None,
        "true_peak_dbfs": None,
        "reason": (
            "Sonie mesurable : l'analyse peut être lancée."
            if mesurable else
            f"`audio_decode` est {sonde['state']} — {sonde['reason']} Aucune "
            "sonie n'est estimée : une cible de normalisation calculée sur une "
            "valeur non mesurée pousserait le mixage dans une direction que "
            "personne n'a choisie."
        ),
    }


def sound_design_report() -> Dict[str, Any]:
    """
    Ce que le sound design garantit, et ce qu'il refuse.

    Returns:
        Les événements, les familles, et les règles tenues.
    """
    return {
        "events": list(EVENEMENTS),
        "families": {
            nom: {"serves": list(details["serves"]),
                  "default_gain_db": details["default_gain_db"],
                  "lead_in_s": details["lead_in_s"]}
            for nom, details in sorted(FAMILLES.items())
        },
        "duck_attenuation_db": ATTENUATION_VOIX_DB,
        "loudness": loudness_status(),
        "rules": [
            "Un son est **posé sur un événement**, et porte l'événement qui l'a "
            "causé ainsi que la source de son instant.",
            "Un instant demandé à un modèle tombe une demi-seconde avant la "
            "coupe — à chaque fois, et personne ne sait le nommer en relecture.",
            "Un événement qu'aucune famille ne sert reste **sans son** : "
            "proposer une famille voisine serait une décision de montage.",
            "L'amorce d'un riser est déclarée par sa famille : un son qui doit "
            "arriver **sur** l'événement commence avant lui.",
            "Les fenêtres d'atténuation qui se touchent sont fusionnées, sinon "
            "la musique remonte entre deux mots et cela s'entend.",
            "Aucune sonie n'est estimée quand elle n'est pas mesurable.",
        ],
        "does_not": [
            "Placer un son sans événement de timeline.",
            "Demander un instant à un modèle.",
            "Substituer une famille de son à une autre.",
            "Estimer une sonie, un pic ou une énergie non mesurés.",
        ],
    }
