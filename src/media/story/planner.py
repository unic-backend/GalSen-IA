"""
A scene plan whose durations are honest and whose captions are not echoes.

Directive §7 asks for a scene converted into slots — purpose, duration, voice,
visual, camera, motion, typography, sound, music, transition — and adds two
demands that most planners quietly drop.

**"Visual design should communicate ideas instead of simply repeating spoken
words. Avoid generic giant text overlays."** This is not a style preference; it
is checkable. A typography slot whose text is the spoken line with the
punctuation removed carries no information at all — the viewer already has those
words, in the voice, and the screen spends its only channel repeating them.
`check_redundancy()` measures the overlap and reports it, because that failure
is invisible in a plan and obvious in a finished video.

**Duration.** A planner assigns "8 s" to a scene and nothing distinguishes that
number from a measurement. Two fields exist here and never merge: a
`target_duration` is what someone asked for, a `measured_duration` comes from
the material actually selected. When both exist and disagree, the disagreement
is reported — a scene planned at 8 s holding 14 s of speech will either run long
or cut someone off mid-sentence, and finding out at render time costs a render.

A slot nobody filled stays empty and is named. Filling it with a plausible
default is how a plan comes to describe a video that was never discussed.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: Les emplacements d'une scène (directive §7). Déclarés une fois : un
#: emplacement qu'un module invente en s'en servant n'apparaît dans aucun
#: rapport de plan, donc personne ne voit qu'il manque.
EMPLACEMENTS = (
    "voice", "visual", "camera", "motion", "typography", "sound", "music",
    "transition",
)

#: Part de mots communs au-delà de laquelle une incrustation ne fait que
#: répéter la voix. Déclarée, donc discutable : trop bas, un mot-clé repris à
#: l'écran serait signalé ; trop haut, une paraphrase passerait.
SEUIL_REDONDANCE = 0.7

#: Écart relatif toléré entre durée visée et durée mesurée avant de le dire.
ECART_DUREE_TOLERE = 0.15


class PlanRefused(ValueError):
    """Une scène qui ne peut pas être planifiée telle qu'elle est décrite."""


def _mots(texte: str) -> List[str]:
    """Découpe un texte en mots comparables, sans casse ni accent ni ponctuation."""
    decompose = unicodedata.normalize("NFKD", str(texte or ""))
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    nettoye = "".join(
        c if c.isalnum() or c.isspace() else " " for c in sans_accent.casefold()
    )
    return nettoye.split()


@dataclass(frozen=True)
class PlannedScene:
    """
    Une scène planifiée, emplacement par emplacement.

    Attributes:
        scene_id: Son identité.
        purpose: Le rôle narratif qu'elle occupe.
        slots: Ce qui remplit chaque emplacement.
        target_duration: La durée **demandée**, si quelqu'un en a demandé une.
        measured_duration: La durée **de la matière** retenue, si elle existe.
        material_quote: La citation dont la scène est faite.
    """

    scene_id: str
    purpose: str
    slots: Dict[str, str] = field(default_factory=dict)
    target_duration: Optional[float] = None
    measured_duration: Optional[float] = None
    material_quote: str = ""

    def __post_init__(self) -> None:
        if not str(self.purpose or "").strip():
            raise PlanRefused(
                f"Scène « {self.scene_id} » sans rôle narratif. Une scène qui "
                "ne sert à rien de nommable ne se défend pas devant un "
                "réalisateur, et elle finit coupée sans qu'on sache pourquoi "
                "elle était là."
            )
        inconnus = sorted(set(self.slots) - set(EMPLACEMENTS))
        if inconnus:
            raise PlanRefused(
                f"Emplacements inconnus : {inconnus}. Les accepter en silence "
                f"ferait croire qu'ils seront rendus. Déclarés : "
                f"{list(EMPLACEMENTS)}."
            )

    @property
    def empty_slots(self) -> Tuple[str, ...]:
        """
        Les emplacements que personne n'a remplis.

        Nommés, jamais comblés : un défaut plausible fait décrire au plan une
        vidéo dont personne n'a parlé.
        """
        return tuple(
            nom for nom in EMPLACEMENTS if not str(self.slots.get(nom, "")).strip()
        )

    @property
    def duration_conflict(self) -> Optional[Dict[str, Any]]:
        """
        L'écart entre la durée visée et celle de la matière, s'il compte.

        `None` quand l'une des deux manque : comparer une mesure à une absence
        produirait un écart imaginaire.
        """
        if self.target_duration is None or self.measured_duration is None:
            return None
        ecart = self.measured_duration - self.target_duration
        if abs(ecart) <= self.target_duration * ECART_DUREE_TOLERE:
            return None
        return {
            "target": self.target_duration,
            "measured": self.measured_duration,
            "delta": round(ecart, 4),
            "reason": (
                "La matière retenue ne tient pas dans la durée visée. Elle "
                "débordera ou coupera quelqu'un au milieu d'une phrase, et "
                "s'en apercevoir au rendu coûte un rendu."
                if ecart > 0 else
                "La matière retenue est bien plus courte que la durée visée : "
                "la scène tiendra, mais l'écart vient d'un plan ou d'une "
                "sélection que personne n'a revu."
            ),
        }

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences comprises."""
        return {
            "scene_id": self.scene_id, "purpose": self.purpose,
            "slots": dict(self.slots),
            "empty_slots": list(self.empty_slots),
            "target_duration": self.target_duration,
            "measured_duration": self.measured_duration,
            "duration_conflict": self.duration_conflict,
            "material_quote": self.material_quote,
        }


def check_redundancy(
    scene: PlannedScene, threshold: float = SEUIL_REDONDANCE,
) -> Dict[str, Any]:
    """
    Mesure si l'incrustation ne fait que répéter la voix.

    Args:
        scene: La scène planifiée.
        threshold: Part de mots communs au-delà de laquelle c'est un écho.

    Returns:
        Le taux de recouvrement et le verdict. Une incrustation qui reprend la
        phrase dite n'apporte rien : le spectateur a déjà ces mots, dans la
        voix, et l'écran dépense son seul canal à les répéter. C'est invisible
        dans un plan et évident dans la vidéo finie.
    """
    voix = _mots(scene.slots.get("voice", ""))
    ecran = _mots(scene.slots.get("typography", ""))

    if not voix or not ecran:
        return {
            "redundant": False, "overlap": None,
            "reason": (
                "Rien à comparer : la voix ou l'incrustation est vide. Un "
                "recouvrement calculé ici serait un chiffre sans mesure."
            ),
        }

    communs = sum(1 for mot in set(ecran) if mot in set(voix))
    recouvrement = communs / len(set(ecran))
    redondant = recouvrement >= threshold

    return {
        "redundant": redondant,
        "overlap": round(recouvrement, 4),
        "threshold": threshold,
        "reason": (
            f"{round(recouvrement * 100)} % des mots de l'incrustation sont "
            "déjà dits à voix haute. L'écran répète au lieu de montrer — c'est "
            "le « grand texte générique » que la directive §7 demande d'éviter."
            if redondant else
            f"{round(recouvrement * 100)} % de recouvrement : l'incrustation "
            "apporte autre chose que la voix."
        ),
    }


def plan_scenes(
    assignment: Dict[str, Any],
    slots_by_role: Optional[Dict[str, Dict[str, str]]] = None,
    targets: Optional[Dict[str, float]] = None,
    measured: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Construit un plan de scènes à partir de rôles narratifs remplis.

    Args:
        assignment: Le résultat de `structures.assign_roles`.
        slots_by_role: Les emplacements proposés, par rôle.
        targets: Les durées visées, par rôle.
        measured: Les durées de la matière, par rôle.

    Returns:
        Une scène par rôle **rempli**, les rôles vides rappelés, et les
        problèmes détectés — emplacements vides, conflits de durée,
        incrustations redondantes.

    Raises:
        PlanRefused: Si aucun rôle n'est rempli. Planifier sur rien produirait
            un plan qui décrit une vidéo qui n'existe pas.
    """
    remplis = assignment.get("filled") or {}
    if not remplis:
        raise PlanRefused(
            "Aucun rôle narratif rempli : il n'y a rien à planifier. Un plan "
            "construit ici décrirait une vidéo qui n'existe pas."
        )

    emplacements = slots_by_role or {}
    visees = targets or {}
    mesurees = measured or {}

    scenes: List[PlannedScene] = []
    for rang, role in enumerate(assignment["roles"], start=1):
        entrees = remplis.get(role)
        if not entrees:
            continue
        scenes.append(PlannedScene(
            scene_id=f"scene-{rang:02d}",
            purpose=role,
            slots=dict(emplacements.get(role, {})),
            target_duration=visees.get(role),
            measured_duration=mesurees.get(role),
            material_quote=" ".join(
                str(entree.get("quote", "")) for entree in entrees
            ).strip(),
        ))

    redondances = [
        {"scene_id": scene.scene_id, **check_redundancy(scene)}
        for scene in scenes
        if check_redundancy(scene)["redundant"]
    ]
    conflits = [
        {"scene_id": scene.scene_id, **scene.duration_conflict}
        for scene in scenes if scene.duration_conflict
    ]

    return {
        "domain": assignment.get("domain"),
        "scenes": [scene.as_dict() for scene in scenes],
        "objects": scenes,
        "empty_roles": list(assignment.get("empty_roles", [])),
        "redundant_typography": redondances,
        "duration_conflicts": conflits,
        "total_target": round(
            sum(s.target_duration for s in scenes if s.target_duration), 4,
        ) or None,
        "total_measured": round(
            sum(s.measured_duration for s in scenes if s.measured_duration), 4,
        ) or None,
        "note": (
            "Une durée visée et une durée mesurée ne se confondent jamais : "
            "l'une est une demande, l'autre un fait. Les fondre ferait passer "
            "un souhait pour une mesure."
        ),
    }


def planner_report() -> Dict[str, Any]:
    """
    Ce que le planificateur garantit, et ce qu'il refuse.

    Returns:
        Les emplacements, les seuils déclarés, et les règles tenues.
    """
    return {
        "slots": list(EMPLACEMENTS),
        "redundancy_threshold": SEUIL_REDONDANCE,
        "duration_tolerance": ECART_DUREE_TOLERE,
        "rules": [
            "Une durée **visée** et une durée **mesurée** sont deux champs "
            "distincts : l'une est une demande, l'autre un fait.",
            "Leur écart est rapporté avant le rendu — une scène planifiée à 8 s "
            "qui contient 14 s de parole débordera ou coupera quelqu'un au "
            "milieu d'une phrase, et le voir au rendu coûte un rendu.",
            "Une incrustation qui répète la phrase dite n'apporte rien : le "
            "spectateur a déjà ces mots, dans la voix. C'est mesurable, et "
            "c'est le « grand texte générique » que la directive §7 refuse.",
            "Un emplacement vide est **nommé** : un défaut plausible ferait "
            "décrire au plan une vidéo dont personne n'a parlé.",
            "Une scène sans rôle narratif est refusée — elle finit coupée sans "
            "que personne sache pourquoi elle était là.",
        ],
        "does_not": [
            "Confondre une durée demandée avec une durée mesurée.",
            "Remplir un emplacement vide avec un défaut plausible.",
            "Accepter un emplacement non déclaré.",
            "Planifier sur zéro rôle rempli.",
        ],
    }
