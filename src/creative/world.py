"""
The world, the entities in it, and what a memory is allowed to promise.

Directive §16 makes `WorldState` the canonical source of truth for continuity,
and §17 adds a separation that looks pedantic until the first correction:
`WorldMemory` must stay independent of `CharacterMemory`. A recurring shop and a
recurring shopkeeper are different facts. Merge them and "the shop moved to the
other side of the street" cannot be fixed without touching the person who works
there — which is how a continuity fix in shot 4 changes someone's face in shot 9.

Two more separations do the same kind of work:

**Style is not part of the world** (§46). The same street at the same hour can
be rendered photorealistic or animated; a style stored inside `WorldState` makes
those two different worlds, and every continuity check then compares a
documentary against a cartoon.

**A memory conditions, it does not guarantee.** §18 forbids claiming perfect
character consistency, so `CharacterMemory` here has no field and no method that
asserts one. It supplies what a generator should be told; whether the generator
obeyed is a question for verification (ADR-026), and the two must never be read
from the same object.

Fidelity is declared per entity (§20) because it decides where effort goes. A
background pedestrian and a hero get different budgets, and pretending otherwise
spends a GPU-minute on someone nobody will look at.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

#: Les niveaux de fidélité (§20), du plus soigné au moins. Ils décident de
#: l'allocation : vérifier un figurant comme un premier rôle dépense un temps
#: de calcul que personne ne regardera.
HERO = "HERO"
SECONDAIRE = "SUPPORTING"
ARRIERE_PLAN = "BACKGROUND"
FOULE = "CROWD"
FIDELITES = (HERO, SECONDAIRE, ARRIERE_PLAN, FOULE)

#: Ce qu'une valeur du monde vaut. Reprend le vocabulaire déjà employé par
#: `src/media/analysis/scene_model.py` : un troisième mot pour la même idée
#: finirait par diverger.
MESURE = "MEASURED"
DERIVE = "AI_DERIVED"
DECLARE = "DECLARED"
ABSENT = "ABSENT"
ORIGINES = (MESURE, DERIVE, DECLARE, ABSENT)


class WorldRefused(ValueError):
    """Un monde ou une entité impossible à déclarer tel quel."""


@dataclass(frozen=True)
class EntityState:
    """
    Une entité dans le monde, à un instant.

    Attributes:
        entity_id: Son identité.
        entity_type: Ce qu'elle est.
        reference_id: La référence qui la conditionne, s'il y en a une.
        fidelity: Son niveau de soin, parmi `FIDELITES`.
        position: Où elle est, en coordonnées relatives.
        action: Ce qu'elle fait.
        gaze: Où elle regarde.
        emotion: Ce qu'elle exprime.
        clothing: Ce qu'elle porte.
        props: Ce qu'elle tient.
    """

    entity_id: str
    entity_type: str
    reference_id: Optional[str] = None
    fidelity: str = SECONDAIRE
    position: Optional[Tuple[float, float]] = None
    action: str = ""
    gaze: str = ""
    emotion: str = ""
    clothing: str = ""
    props: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.fidelity not in FIDELITES:
            raise WorldRefused(
                f"Fidélité « {self.fidelity} » non déclarée. Déclarées : "
                f"{list(FIDELITES)} — elle décide du budget, donc elle ne se "
                "devine pas."
            )
        if self.position is not None:
            for valeur in self.position:
                if not 0.0 <= valeur <= 1.0:
                    raise WorldRefused(
                        f"Position {self.position} hors de [0, 1]. Les "
                        "coordonnées sont relatives : des pixels absolus n'ont "
                        "de sens que dans la taille où ils ont été écrits."
                    )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "entity_id": self.entity_id, "entity_type": self.entity_type,
            "reference_id": self.reference_id, "fidelity": self.fidelity,
            "position": list(self.position) if self.position else None,
            "action": self.action, "gaze": self.gaze, "emotion": self.emotion,
            "clothing": self.clothing, "props": list(self.props),
        }


@dataclass(frozen=True)
class WorldFact:
    """
    Un fait du monde, avec son origine.

    Attributes:
        name: Le fait — `lighting`, `weather`, `time_of_day`, `location`…
        value: Sa valeur. `None` quand personne ne l'a posée.
        origin: D'où elle vient, parmi `ORIGINES`.
        source: Ce qui l'a fournie.
        reason: Pourquoi elle est absente, le cas échéant.
    """

    name: str
    value: Any = None
    origin: str = ABSENT
    source: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        if self.origin not in ORIGINES:
            raise WorldRefused(
                f"Origine « {self.origin} » non déclarée. Déclarées : "
                f"{list(ORIGINES)}."
            )
        if self.origin == ABSENT and self.value is not None:
            raise WorldRefused(
                f"« {self.name} » porte une valeur et se dit absent."
            )
        if self.origin == ABSENT and not str(self.reason or "").strip():
            raise WorldRefused(
                f"« {self.name} » est absent sans raison. Un monde dont les "
                "trous ne sont pas nommés se lit comme un monde complet."
            )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {"name": self.name, "value": self.value,
                "origin": self.origin, "source": self.source,
                "reason": self.reason}


class WorldState:
    """
    L'état du monde : la source de vérité de la continuité (§16).

    Le style n'y est **pas** (§46) : le même monde peut être rendu
    photoréaliste ou animé, et l'y ranger ferait comparer un documentaire à un
    dessin animé au premier contrôle de continuité.
    """

    def __init__(self, world_id: str = "", environment: str = "") -> None:
        """
        Ouvre un monde.

        Args:
            world_id: Son identité. Tirée au sort si absente.
            environment: Où il se situe.
        """
        self._verrou = threading.RLock()
        self.world_id = world_id or f"world-{uuid.uuid4().hex[:10]}"
        self.environment = environment
        self.created_at = time.time()
        self._entites: Dict[str, EntityState] = {}
        self._faits: Dict[str, WorldFact] = {}
        self._contraintes: List[str] = []

    def place(self, entity: EntityState) -> EntityState:
        """Place ou remplace une entité dans le monde."""
        with self._verrou:
            self._entites[entity.entity_id] = entity
            return entity

    def entity(self, entity_id: str) -> Optional[EntityState]:
        """Une entité par son identité."""
        with self._verrou:
            return self._entites.get(entity_id)

    @property
    def entities(self) -> Tuple[EntityState, ...]:
        """Toutes les entités, triées par identité."""
        with self._verrou:
            return tuple(self._entites[i] for i in sorted(self._entites))

    def by_fidelity(self, fidelity: str) -> Tuple[EntityState, ...]:
        """Les entités d'un niveau de fidélité donné."""
        return tuple(e for e in self.entities if e.fidelity == fidelity)

    def set_fact(self, fact: WorldFact) -> WorldFact:
        """Pose un fait du monde."""
        with self._verrou:
            self._faits[fact.name] = fact
            return fact

    def fact(self, name: str) -> WorldFact:
        """
        Un fait, ou une absence **déclarée**.

        Un fait jamais posé rend un `WorldFact` `ABSENT` portant sa raison, et
        non `None` : un monde dont les trous ne sont pas nommés se lit comme un
        monde complet, et la continuité est alors vérifiée contre du vide.
        """
        with self._verrou:
            existant = self._faits.get(name)
        if existant is not None:
            return existant
        return WorldFact(
            name=name, origin=ABSENT,
            reason="Jamais posé sur ce monde : personne ne l'a établi.",
        )

    def add_constraint(self, constraint: str) -> str:
        """Ajoute une contrainte de continuité."""
        with self._verrou:
            self._contraintes.append(constraint)
            return constraint

    @property
    def constraints(self) -> Tuple[str, ...]:
        """Les contraintes de continuité déclarées."""
        with self._verrou:
            return tuple(self._contraintes)

    def as_dict(self) -> Dict[str, Any]:
        """Le monde complet, absences comprises."""
        with self._verrou:
            faits = [f.as_dict() for f in
                     (self._faits[n] for n in sorted(self._faits))]
        return {
            "world_id": self.world_id,
            "environment": self.environment,
            "entities": [e.as_dict() for e in self.entities],
            "facts": faits,
            "established_facts": sorted(
                f["name"] for f in faits if f["origin"] != ABSENT),
            "constraints": list(self.constraints),
            "by_fidelity": {
                niveau: [e.entity_id for e in self.by_fidelity(niveau)]
                for niveau in FIDELITES
            },
            "note": (
                "Le style ne fait pas partie du monde (§46) : le même monde "
                "peut être rendu photoréaliste ou animé."
            ),
        }


class CharacterMemory:
    """
    Ce qu'on retient d'une entité récurrente — **sans rien garantir**.

    §18 interdit d'affirmer une cohérence de personnage parfaite. Cette classe
    n'a donc aucun champ ni aucune méthode qui l'affirme : elle fournit ce qu'il
    faut **dire** au générateur, et si le générateur a obéi est une question de
    vérification (ADR-026). Lire les deux dans le même objet reviendrait à faire
    répondre le conditionnement à la place de la mesure.
    """

    def __init__(self, entity_id: str) -> None:
        """
        Ouvre la mémoire d'une entité.

        Args:
            entity_id: L'entité concernée.
        """
        self._verrou = threading.RLock()
        self.entity_id = entity_id
        self._traits: Dict[str, WorldFact] = {}
        self._references: List[str] = []
        self._relations: Dict[str, str] = {}

    def remember(self, trait: WorldFact) -> WorldFact:
        """Retient un trait, avec son origine."""
        with self._verrou:
            self._traits[trait.name] = trait
            return trait

    def link_reference(self, reference_id: str) -> str:
        """Rattache une référence qui conditionne cette entité."""
        with self._verrou:
            if reference_id not in self._references:
                self._references.append(reference_id)
            return reference_id

    def relate(self, other_entity_id: str, relation: str) -> str:
        """Déclare une relation avec une autre entité."""
        with self._verrou:
            self._relations[other_entity_id] = relation
            return relation

    def conditioning(self) -> Dict[str, Any]:
        """
        Ce qu'il faut transmettre au générateur — et rien de plus.

        Returns:
            Les traits retenus, les références rattachées, les relations. Le
            mot « conditioning » est choisi : ce sont des instructions, pas des
            promesses. Aucune clé ne dit que le résultat sera conforme, parce
            que rien ici ne le sait.
        """
        with self._verrou:
            return {
                "entity_id": self.entity_id,
                "traits": [t.as_dict() for t in
                           (self._traits[n] for n in sorted(self._traits))],
                "references": list(self._references),
                "relations": dict(self._relations),
                "guarantees": None,
                "note": (
                    "Conditionnement, pas garantie. §18 interdit d'affirmer "
                    "une cohérence parfaite ; savoir si le générateur a suivi "
                    "relève de la vérification (ADR-026), pas de cet objet."
                ),
            }


class WorldMemory:
    """
    Ce qui revient d'un monde à l'autre — **indépendamment des personnages**.

    §17 exige la séparation, et la raison se voit à la première correction :
    fusionner la boutique et le boutiquier fait qu'on ne peut pas déplacer la
    boutique sans toucher à la personne qui y travaille.
    """

    def __init__(self) -> None:
        self._verrou = threading.RLock()
        self._mondes: Dict[str, Dict[str, Any]] = {}
        self._recurrents: Dict[str, int] = {}

    def record(self, world: WorldState) -> Dict[str, Any]:
        """
        Enregistre un monde et compte ce qui y revient.

        Args:
            world: Le monde observé.

        Returns:
            L'instantané enregistré. Les **entités ne sont pas comptées ici** :
            elles relèvent de `CharacterMemory`, et les mêler rendrait
            impossible de corriger l'une sans toucher l'autre.
        """
        with self._verrou:
            instantane = {
                "world_id": world.world_id,
                "environment": world.environment,
                "facts": [f.as_dict() for f in
                          (world.fact(n) for n in
                           sorted({fait["name"]
                                   for fait in world.as_dict()["facts"]}))],
                "recorded_at": time.time(),
            }
            self._mondes[world.world_id] = instantane
            if world.environment:
                self._recurrents[world.environment] = (
                    self._recurrents.get(world.environment, 0) + 1)
            return instantane

    def recurring(self, minimum: int = 2) -> List[Dict[str, Any]]:
        """
        Les environnements revus au moins `minimum` fois.

        Returns:
            Les décors récurrents, avec leur compte. Un décor vu deux fois est
            un décor dont la continuité compte ; un décor vu une fois n'est pas
            encore récurrent, et le déclarer tel ferait imposer une continuité
            que personne n'a observée.
        """
        with self._verrou:
            return [{"environment": nom, "seen": compte}
                    for nom, compte in sorted(self._recurrents.items())
                    if compte >= minimum]

    def report(self) -> Dict[str, Any]:
        """L'état de la mémoire des mondes."""
        with self._verrou:
            return {
                "worlds": len(self._mondes),
                "environments": dict(sorted(self._recurrents.items())),
                "recurring": self.recurring(),
                "holds_characters": False,
                "note": (
                    "Cette mémoire ne retient **aucun personnage** (§17). "
                    "Fusionner les deux rendrait impossible de déplacer une "
                    "boutique sans toucher au boutiquier."
                ),
            }


def world_report() -> Dict[str, Any]:
    """
    Ce que le monde garantit, et ce qu'il refuse.

    Returns:
        Le vocabulaire déclaré et les règles tenues.
    """
    return {
        "fidelities": list(FIDELITES),
        "origins": list(ORIGINES),
        "rules": [
            "`WorldState` est la source de vérité de la continuité (§16) : "
            "chaque plan s'y réfère.",
            "Le **style n'est pas dans le monde** (§46) : le même monde peut "
            "être photoréaliste ou animé, et l'y ranger ferait comparer un "
            "documentaire à un dessin animé.",
            "`WorldMemory` ne retient **aucun personnage** (§17) : fusionner "
            "la boutique et le boutiquier empêche de corriger l'une sans "
            "toucher l'autre.",
            "Une `CharacterMemory` **conditionne**, elle ne garantit pas "
            "(§18) : savoir si le générateur a suivi relève de la "
            "vérification.",
            "Un fait jamais posé rend une absence **déclarée** : un monde dont "
            "les trous ne sont pas nommés se lit comme un monde complet.",
            "La fidélité est déclarée par entité (§20) : elle décide du "
            "budget, donc elle ne se devine pas.",
        ],
        "does_not": [
            "Ranger le style dans l'état du monde.",
            "Mêler mémoire de monde et mémoire de personnage.",
            "Affirmer une cohérence de personnage.",
            "Laisser un fait absent sans raison.",
        ],
    }
