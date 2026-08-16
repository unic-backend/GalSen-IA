"""
Directing as structure, and shots that can be regenerated one at a time.

Directive §18 says what the DirectorEngine must not be, and it is worth quoting
because it names the exact failure: *do NOT simply append adjectives such as
"cinematic", "beautiful", "dramatic" to a prompt.* Those words survive into the
generated video as a general mood and decide nothing. Shot type, lens, camera
height, movement, depth of field, blocking, gaze — those decide something, and
each of them is a value from a declared vocabulary here rather than a phrase in
a sentence.

The practical test is whether a director's decision can be **changed**. "Make it
more cinematic" cannot be revised, because nobody can say what it asked for.
"Medium close-up, 50 mm, eye level, slow push-in" can: you change one field, and
the rest of the plan is unaffected.

§19 asks for shot-level regeneration, and that constrains the data more than it
looks. A shot must name everything it depends on — the world, the entities, the
references, the audio segments, the director's instructions — because otherwise
regenerating shot 7 means regenerating everything before it to reconstruct the
context it silently inherited.

Two fields stay separate throughout, for the reason the media engine already
learned: `target_duration` is what someone asked for and `measured_duration` is
what came back. Writing a target into a measured field creates a measurement
nobody took.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .world import FIDELITES, WorldState

#: Les échelles de plan déclarées. Une échelle inconnue est refusée pour être
#: **ajoutée ici** : elle décide du cadrage, donc elle ne se devine pas.
ECHELLES = (
    "extreme_wide", "wide", "medium_wide", "medium", "medium_close_up",
    "close_up", "extreme_close_up", "over_the_shoulder", "two_shot", "insert",
)

#: Les hauteurs de caméra.
HAUTEURS = ("eye_level", "low", "high", "overhead", "ground")

#: Les mouvements de caméra. `static` en est un : ne pas bouger est une
#: décision, pas une absence de décision.
MOUVEMENTS = ("static", "pan", "tilt", "dolly_in", "dolly_out", "track",
              "crane", "handheld", "zoom")

#: Les intentions de lumière. Ce sont des directions, pas des adjectifs : elles
#: se contestent et se remplacent une par une.
LUMIERES = ("natural", "soft_key", "hard_key", "backlit", "silhouette",
            "practical", "low_key", "high_key")

#: Les transitions déclarées.
TRANSITIONS = ("cut", "dissolve", "fade_in", "fade_out", "match_cut", "wipe")

#: L'état d'un plan dans la production.
PLANIFIE = "PLANNED"
GENERE = "GENERATED"
A_REFAIRE = "NEEDS_REGENERATION"
ETATS_DE_PLAN = (PLANIFIE, GENERE, A_REFAIRE)


class DirectionRefused(ValueError):
    """Une instruction de réalisation ou un plan impossible tel quel."""


@dataclass(frozen=True)
class DirectorSpec:
    """
    Les instructions de réalisation d'un plan — structurées, pas adjectivales.

    Attributes:
        shot_size: L'échelle, parmi `ECHELLES`.
        camera_height: La hauteur, parmi `HAUTEURS`.
        movement: Le mouvement, parmi `MOUVEMENTS`.
        lens_mm: La focale, en millimètres. `None` = non décidée.
        depth_of_field: `shallow`, `deep`, ou vide quand ce n'est pas décidé.
        lighting: L'intention lumineuse, parmi `LUMIERES`.
        blocking: Où se placent les entités, par identité.
        gaze: Où regarde chaque entité.
        transition_in: La transition d'entrée.
        intent: Ce que le plan doit accomplir, en une phrase.
    """

    shot_size: str
    camera_height: str = "eye_level"
    movement: str = "static"
    lens_mm: Optional[float] = None
    depth_of_field: str = ""
    lighting: str = "natural"
    blocking: Dict[str, str] = field(default_factory=dict)
    gaze: Dict[str, str] = field(default_factory=dict)
    transition_in: str = "cut"
    intent: str = ""

    def __post_init__(self) -> None:
        for valeur, declarees, nom in (
            (self.shot_size, ECHELLES, "échelle"),
            (self.camera_height, HAUTEURS, "hauteur"),
            (self.movement, MOUVEMENTS, "mouvement"),
            (self.lighting, LUMIERES, "lumière"),
            (self.transition_in, TRANSITIONS, "transition"),
        ):
            if valeur not in declarees:
                raise DirectionRefused(
                    f"{nom.capitalize()} « {valeur} » non déclarée. Déclarées : "
                    f"{list(declarees)}. Une valeur inventée ici se comporte "
                    "comme un adjectif : elle ne décide rien et ne se conteste "
                    "pas (§18)."
                )
        if self.lens_mm is not None and self.lens_mm <= 0:
            raise DirectionRefused(f"Focale {self.lens_mm} mm impossible.")
        if self.depth_of_field and self.depth_of_field not in ("shallow", "deep"):
            raise DirectionRefused(
                f"Profondeur de champ « {self.depth_of_field} » non déclarée. "
                "Déclarées : ['shallow', 'deep']."
            )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "shot_size": self.shot_size, "camera_height": self.camera_height,
            "movement": self.movement, "lens_mm": self.lens_mm,
            "depth_of_field": self.depth_of_field, "lighting": self.lighting,
            "blocking": dict(self.blocking), "gaze": dict(self.gaze),
            "transition_in": self.transition_in, "intent": self.intent,
        }


#: Les adjectifs qui décrivent une ambiance sans rien décider. Ils sont
#: **nommés** pour que le refus soit précis : ce ne sont pas de mauvais mots,
#: ce sont des mots qui n'appartiennent pas à une instruction de réalisation.
ADJECTIFS_SANS_DECISION = (
    "cinematic", "cinématographique", "beautiful", "beau", "belle",
    "dramatic", "dramatique", "epic", "épique", "stunning", "magnifique",
    "professional", "professionnel", "amazing", "incroyable", "artistic",
)


def check_intent(intent: str) -> Dict[str, Any]:
    """
    Relève les adjectifs d'ambiance dans une intention de plan.

    Args:
        intent: L'intention écrite pour le plan.

    Returns:
        Les adjectifs relevés et un avertissement. **Rien n'est retiré** : le
        texte reste tel qu'il a été écrit, et le relevé sert à dire qu'il ne
        décide encore rien. Supprimer les mots donnerait l'impression que la
        décision a été prise.
    """
    mots = "".join(c.lower() if c.isalpha() else " " for c in intent).split()
    releves = sorted({m for m in mots if m in ADJECTIFS_SANS_DECISION})
    return {
        "intent": intent,
        "mood_adjectives": releves,
        "decides_nothing": bool(releves),
        "note": (
            "Aucun adjectif d'ambiance : l'intention peut être discutée."
            if not releves else
            f"{len(releves)} adjectif(s) d'ambiance ({', '.join(releves)}). "
            "Ils survivent dans la vidéo comme une humeur générale et ne "
            "décident rien : ce sont les champs structurés du `DirectorSpec` "
            "qui se contestent et se remplacent (§18)."
        ),
    }


@dataclass
class Shot:
    """
    Un plan, et tout ce dont il dépend.

    Il nomme ses dépendances **explicitement** : sans cela, refaire le plan 7
    obligerait à refaire tout ce qui le précède pour reconstruire le contexte
    dont il hérite en silence (§19).

    Attributes:
        shot_id: Son identité.
        index: Sa place dans la production.
        world_id: Le monde auquel il appartient.
        entity_ids: Les entités présentes.
        reference_ids: Les références qui les conditionnent.
        audio_segment_ids: Les segments de parole qu'il porte.
        director: Les instructions de réalisation.
        target_duration: La durée **demandée**.
        measured_duration: La durée **constatée** après rendu. `None` tant que
            rien n'a été rendu.
        state: Son état, parmi `ETATS_DE_PLAN`.
        continuity_constraints: Ce qui doit tenir entre ce plan et les autres.
    """

    shot_id: str
    index: int
    world_id: str
    director: DirectorSpec
    entity_ids: Tuple[str, ...] = ()
    reference_ids: Tuple[str, ...] = ()
    audio_segment_ids: Tuple[str, ...] = ()
    target_duration: Optional[float] = None
    measured_duration: Optional[float] = None
    state: str = PLANIFIE
    continuity_constraints: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.state not in ETATS_DE_PLAN:
            raise DirectionRefused(
                f"État « {self.state} » non déclaré. Déclarés : "
                f"{list(ETATS_DE_PLAN)}."
            )
        if self.target_duration is not None and self.target_duration <= 0:
            raise DirectionRefused(
                f"Durée visée {self.target_duration} : un plan sans durée "
                "positive ne se rend pas."
            )
        if not str(self.world_id or "").strip():
            raise DirectionRefused(
                f"Plan « {self.shot_id} » sans monde. Un plan qui ne nomme pas "
                "son monde ne peut pas être refait seul : son contexte est "
                "hérité en silence (§19)."
            )

    @property
    def duration_gap(self) -> Optional[float]:
        """
        L'écart entre la durée demandée et la durée constatée.

        `None` tant que l'une des deux manque — et c'est le point : un écart
        calculé sur une durée absente serait un écart inventé.
        """
        if self.target_duration is None or self.measured_duration is None:
            return None
        return round(self.measured_duration - self.target_duration, 4)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences comprises."""
        return {
            "shot_id": self.shot_id, "index": self.index,
            "world_id": self.world_id,
            "entity_ids": list(self.entity_ids),
            "reference_ids": list(self.reference_ids),
            "audio_segment_ids": list(self.audio_segment_ids),
            "director": self.director.as_dict(),
            "target_duration": self.target_duration,
            "measured_duration": self.measured_duration,
            "duration_gap": self.duration_gap,
            "state": self.state,
            "continuity_constraints": list(self.continuity_constraints),
        }


class ShotPlanner:
    """
    La décomposition d'une production en plans refaisables un par un.
    """

    def __init__(self, world: WorldState) -> None:
        """
        Ouvre un plan de tournage sur un monde.

        Args:
            world: Le monde auquel les plans se réfèrent.
        """
        self._verrou = threading.RLock()
        self.world = world
        self._plans: List[Shot] = []

    def add(self, director: DirectorSpec, entity_ids: Sequence[str] = (),
            reference_ids: Sequence[str] = (),
            audio_segment_ids: Sequence[str] = (),
            target_duration: Optional[float] = None,
            constraints: Sequence[str] = ()) -> Shot:
        """
        Ajoute un plan.

        Raises:
            DirectionRefused: Si une entité citée n'est pas dans le monde. Un
                plan qui nomme une entité absente sera généré sur un monde qui
                ne la contient pas, et l'écart n'apparaîtra qu'à la
                vérification.
        """
        with self._verrou:
            manquantes = [i for i in entity_ids if self.world.entity(i) is None]
            if manquantes:
                raise DirectionRefused(
                    f"Entités absentes du monde « {self.world.world_id} » : "
                    f"{manquantes}. Les générer quand même produirait un plan "
                    "sur un monde qui ne les contient pas."
                )
            plan = Shot(
                shot_id=f"shot-{uuid.uuid4().hex[:8]}",
                index=len(self._plans) + 1,
                world_id=self.world.world_id,
                director=director,
                entity_ids=tuple(entity_ids),
                reference_ids=tuple(reference_ids),
                audio_segment_ids=tuple(audio_segment_ids),
                target_duration=target_duration,
                continuity_constraints=tuple(constraints),
            )
            self._plans.append(plan)
            return plan

    @property
    def shots(self) -> Tuple[Shot, ...]:
        """Les plans, dans l'ordre."""
        with self._verrou:
            return tuple(self._plans)

    def mark_generated(self, shot_id: str,
                       measured_duration: Optional[float] = None) -> Shot:
        """
        Marque un plan comme généré, avec la durée **constatée** s'il y en a une.

        Args:
            shot_id: Le plan.
            measured_duration: Ce qui a réellement été mesuré. `None` quand
                rien ne l'a mesuré — jamais la durée visée recopiée.

        Raises:
            DirectionRefused: Sur un plan inconnu.
        """
        plan = self._exiger(shot_id)
        plan.state = GENERE
        plan.measured_duration = measured_duration
        return plan

    def mark_for_regeneration(self, shot_id: str, reason: str) -> Dict[str, Any]:
        """
        Marque **un seul** plan à refaire.

        Args:
            shot_id: Le plan concerné.
            reason: Pourquoi.

        Returns:
            Le plan et ce qu'il faut lui redonner. Refaire un plan ne touche
            aucun autre : c'est ce que §19 demande, et c'est possible
            uniquement parce que le plan nomme lui-même ses dépendances.
        """
        plan = self._exiger(shot_id)
        plan.state = A_REFAIRE
        return {
            "shot_id": plan.shot_id,
            "reason": reason,
            "requires": {
                "world_id": plan.world_id,
                "entity_ids": list(plan.entity_ids),
                "reference_ids": list(plan.reference_ids),
                "audio_segment_ids": list(plan.audio_segment_ids),
                "director": plan.director.as_dict(),
            },
            "affects_other_shots": False,
            "note": (
                "Un seul plan est concerné. Les autres gardent leur état : "
                "refaire toute la production pour corriger un plan coûterait "
                "le prix de la production entière."
            ),
        }

    def _exiger(self, shot_id: str) -> Shot:
        """Retourne un plan ou refuse."""
        with self._verrou:
            for plan in self._plans:
                if plan.shot_id == shot_id:
                    return plan
        raise DirectionRefused(f"Plan « {shot_id} » inconnu.")

    def report(self) -> Dict[str, Any]:
        """
        L'état du plan de tournage, écarts compris.

        Returns:
            Les plans par état, la durée visée totale, la durée constatée
            **partielle** et ce qui n'a pas été mesuré. La durée constatée
            n'est jamais complétée par la durée visée : additionner les deux
            produirait un total qui n'a jamais existé.
        """
        plans = self.shots
        visees = [p.target_duration for p in plans if p.target_duration is not None]
        mesurees = [p.measured_duration for p in plans
                    if p.measured_duration is not None]
        sans_mesure = [p.shot_id for p in plans if p.measured_duration is None]

        return {
            "shots": len(plans),
            "by_state": {etat: [p.shot_id for p in plans if p.state == etat]
                         for etat in ETATS_DE_PLAN},
            "target_duration_total": round(sum(visees), 4) if visees else None,
            "measured_duration_total": (round(sum(mesurees), 4)
                                        if mesurees else None),
            "shots_without_measurement": sans_mesure,
            "entities_used": sorted({i for p in plans for i in p.entity_ids}),
            "references_used": sorted({i for p in plans for i in p.reference_ids}),
            "note": (
                "La durée constatée n'est **jamais** complétée par la durée "
                "visée : additionner les deux produirait un total qui n'a "
                "jamais existé. Les plans non mesurés sont nommés."
            ),
        }


def allocate_effort(world: WorldState) -> Dict[str, Any]:
    """
    Répartit l'effort selon la fidélité déclarée des entités (§20).

    Args:
        world: Le monde à servir.

    Returns:
        Par niveau, les entités et la part d'effort proposée. C'est une
        **proposition** de répartition, pas une mesure de coût : aucun calcul
        n'a tourné ici, et le rapport le dit plutôt que de rendre des minutes
        de GPU que personne n'a chronométrées.
    """
    parts = {"HERO": 8, "SUPPORTING": 4, "BACKGROUND": 2, "CROWD": 1}
    par_niveau = {niveau: [e.entity_id for e in world.by_fidelity(niveau)]
                  for niveau in FIDELITES}
    total = sum(parts[niveau] * len(entites)
                for niveau, entites in par_niveau.items())

    return {
        "by_fidelity": par_niveau,
        "weights": parts,
        "relative_share": {
            niveau: (round(parts[niveau] * len(entites) / total, 4)
                     if total else None)
            for niveau, entites in par_niveau.items()
        },
        "cost_estimate": None,
        "note": (
            "Répartition **relative**, pas un coût. Aucun calcul n'a tourné "
            "ici : rendre des minutes de GPU que personne n'a chronométrées "
            "serait une mesure inventée."
        ),
    }


def direction_report() -> Dict[str, Any]:
    """
    Ce que la réalisation garantit, et ce qu'elle refuse.

    Returns:
        Les vocabulaires déclarés et les règles tenues.
    """
    return {
        "shot_sizes": list(ECHELLES),
        "camera_heights": list(HAUTEURS),
        "movements": list(MOUVEMENTS),
        "lighting": list(LUMIERES),
        "transitions": list(TRANSITIONS),
        "shot_states": list(ETATS_DE_PLAN),
        "mood_adjectives": list(ADJECTIFS_SANS_DECISION),
        "rules": [
            "Une instruction de réalisation est **structurée** : échelle, "
            "hauteur, focale, mouvement, lumière. « Plus cinématographique » "
            "ne se conteste pas et ne se révise pas (§18).",
            "Un plan **nomme ses dépendances** — monde, entités, références, "
            "segments audio. Sans cela, refaire le plan 7 oblige à refaire "
            "tout ce qui le précède (§19).",
            "Durée visée et durée constatée sont **deux champs** : écrire "
            "l'une dans l'autre crée une mesure que personne n'a prise.",
            "Un plan citant une entité absente du monde est refusé : le "
            "générer produirait un plan sur un monde qui ne la contient pas.",
            "La régénération est **par plan** : refaire toute la production "
            "pour corriger un plan en coûterait le prix entier.",
            "La répartition d'effort est **relative** et ne prétend pas être "
            "un coût : aucun calcul n'a tourné.",
        ],
        "does_not": [
            "Accepter un adjectif d'ambiance comme une instruction.",
            "Compléter une durée constatée par une durée visée.",
            "Refaire des plans que rien ne concerne.",
            "Rendre une estimation de coût que personne n'a mesurée.",
        ],
    }
