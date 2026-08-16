"""
Crowds and background motion, budgeted by what a viewer will actually look at.

Directive §20 asks for pedestrians, vehicles, animals, vendors and environmental
motion, and gives the rule that makes it tractable: **hierarchical fidelity**,
with resource allocation reflecting visual importance. The failure it prevents
is not aesthetic. Treating a background pedestrian like a hero spends the same
verification and the same compute on someone who occupies forty pixels for half
a second — and on a machine with a finite GPU budget, that is time taken from
the face the audience is watching.

Two decisions follow from measuring rather than assuming:

**A crowd is a declared population, not a number of individuals.** Fifty
pedestrians are not fifty entities with names, memories and identity checks.
They are a population with a density, a direction of travel and a variation
range — and the moment one of them needs a name, it stops being crowd and
becomes an entity. The boundary is explicit so nobody crosses it by accident.

**Nothing here estimates a cost.** Shares are relative and the cost field is
`None`, because no generator has run on this machine and GPU-minutes nobody
timed would be an invented measurement — the same refusal the media benchmarks
already hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from .world import ARRIERE_PLAN, FIDELITES, FOULE, WorldState

#: Ce qui peuple un arrière-plan. Une catégorie inconnue est refusée pour être
#: **ajoutée ici** : un piéton et un véhicule n'ont ni la même trajectoire ni
#: la même vitesse, et les confondre produit une foule qui glisse.
POPULATIONS = ("pedestrian", "vehicle", "animal", "bird", "vendor",
               "customer", "boat", "cyclist")

#: Les mouvements d'ambiance déclarés.
MOUVEMENTS_D_AMBIANCE = ("wind", "water", "smoke", "dust", "foliage", "rain",
                         "traffic_flow", "none")

#: Densités déclarées, avec ce qu'elles veulent dire. Un nombre libre ferait
#: écrire « densité 0.73 » sans que personne sache à quoi cela correspond.
DENSITES = {
    "sparse": "Quelques individus visibles, largement séparés.",
    "moderate": "Une présence continue sans encombrement.",
    "dense": "Un flux ininterrompu ; les individus se recouvrent.",
    "packed": "Une masse où les individus ne se distinguent plus.",
}


class CrowdRefused(ValueError):
    """Une population ou un mouvement d'ambiance impossible tel quel."""


@dataclass(frozen=True)
class Population:
    """
    Un groupe d'arrière-plan, décrit comme un groupe.

    Attributes:
        population_id: Son identité.
        kind: Ce qui la compose, parmi `POPULATIONS`.
        density: Sa densité, parmi `DENSITES`.
        direction: Le sens de circulation dominant, s'il y en a un.
        speed: `slow`, `normal`, `fast`, ou vide quand ce n'est pas décidé.
        variation: De 0 à 1 : à quel point les individus diffèrent entre eux.
        area: La zone occupée, en coordonnées relatives (x, y, largeur, hauteur).
        fidelity: `CROWD` ou `BACKGROUND` — jamais plus haut. Une population
            qui mérite mieux n'est plus une population.
    """

    population_id: str
    kind: str
    density: str = "moderate"
    direction: str = ""
    speed: str = ""
    variation: float = 0.5
    area: Optional[Tuple[float, float, float, float]] = None
    fidelity: str = FOULE

    def __post_init__(self) -> None:
        if self.kind not in POPULATIONS:
            raise CrowdRefused(
                f"Population « {self.kind} » non déclarée. Déclarées : "
                f"{list(POPULATIONS)} — un piéton et un véhicule n'ont ni la "
                "même trajectoire ni la même vitesse."
            )
        if self.density not in DENSITES:
            raise CrowdRefused(
                f"Densité « {self.density} » non déclarée. Déclarées : "
                f"{sorted(DENSITES)}. Un nombre libre ferait écrire "
                "« densité 0.73 » sans que personne sache à quoi cela "
                "correspond."
            )
        if self.fidelity not in (FOULE, ARRIERE_PLAN):
            raise CrowdRefused(
                f"Fidélité « {self.fidelity} » impossible pour une "
                f"population : seules {[FOULE, ARRIERE_PLAN]} le sont. Une "
                "population qui mérite mieux n'est plus une population — "
                "c'est une entité, et elle a un nom."
            )
        if not 0.0 <= self.variation <= 1.0:
            raise CrowdRefused(
                f"Variation {self.variation} hors de [0, 1]."
            )
        if self.speed and self.speed not in ("slow", "normal", "fast"):
            raise CrowdRefused(
                f"Vitesse « {self.speed} » non déclarée. Déclarées : "
                "['slow', 'normal', 'fast']."
            )
        if self.area is not None:
            for valeur in self.area:
                if not 0.0 <= valeur <= 1.0:
                    raise CrowdRefused(
                        f"Zone {self.area} hors de [0, 1] : les coordonnées "
                        "sont relatives au cadre."
                    )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "population_id": self.population_id, "kind": self.kind,
            "density": self.density, "density_means": DENSITES[self.density],
            "direction": self.direction, "speed": self.speed,
            "variation": self.variation,
            "area": list(self.area) if self.area else None,
            "fidelity": self.fidelity,
            "individuals_named": False,
        }


@dataclass(frozen=True)
class AmbientMotion:
    """
    Un mouvement d'ambiance : ce qui bouge sans que personne le regarde.

    Attributes:
        kind: Le mouvement, parmi `MOUVEMENTS_D_AMBIANCE`.
        intensity: De 0 à 1.
        source: Ce qui le motive dans le monde — un fait, un décor.
    """

    kind: str
    intensity: float = 0.3
    source: str = ""

    def __post_init__(self) -> None:
        if self.kind not in MOUVEMENTS_D_AMBIANCE:
            raise CrowdRefused(
                f"Mouvement « {self.kind} » non déclaré. Déclarés : "
                f"{list(MOUVEMENTS_D_AMBIANCE)}."
            )
        if not 0.0 <= self.intensity <= 1.0:
            raise CrowdRefused(f"Intensité {self.intensity} hors de [0, 1].")

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {"kind": self.kind, "intensity": self.intensity,
                "source": self.source}


def promote_to_entity(population: Population, entity_id: str,
                      entity_type: str = "human") -> Dict[str, Any]:
    """
    Sort un individu d'une population pour en faire une entité nommée.

    Args:
        population: La population d'origine.
        entity_id: L'identité de la nouvelle entité.
        entity_type: Ce qu'elle est.

    Returns:
        Ce qu'il faut créer, et ce que la population **perd**. La frontière est
        explicite parce qu'elle se franchit sinon par accident : dès qu'un
        figurant a un nom, il a une mémoire, une référence possible et une
        vérification d'identité — c'est-à-dire un budget entier.
    """
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "from_population": population.population_id,
        "gains": ["un nom", "une mémoire de personnage possible",
                  "une référence possible", "une vérification d'identité"],
        "costs": (
            "Le budget d'une entité, pas d'un figurant. §20 répartit l'effort "
            "selon l'importance visuelle : promouvoir sans raison prend du "
            "temps de calcul au visage que le spectateur regarde."
        ),
        "population_after": population.as_dict(),
    }


def budget(world: WorldState, populations: Sequence[Population],
           ambient: Sequence[AmbientMotion] = ()) -> Dict[str, Any]:
    """
    La répartition d'effort entre entités nommées, populations et ambiance.

    Args:
        world: Le monde, pour ses entités nommées.
        populations: Les populations déclarées.
        ambient: Les mouvements d'ambiance.

    Returns:
        Les parts **relatives** par niveau. `cost_estimate` vaut `None` : aucun
        générateur n'a tourné ici, et des minutes de GPU que personne n'a
        chronométrées seraient une mesure inventée.
    """
    poids = {"HERO": 8, "SUPPORTING": 4, "BACKGROUND": 2, "CROWD": 1}
    entites = {niveau: len(world.by_fidelity(niveau)) for niveau in FIDELITES}
    par_population = {niveau: sum(1 for p in populations
                                  if p.fidelity == niveau)
                      for niveau in (FOULE, ARRIERE_PLAN)}

    total = sum(poids[niveau] * compte for niveau, compte in entites.items())
    total += sum(poids[niveau] * compte
                 for niveau, compte in par_population.items())

    return {
        "named_entities": entites,
        "populations": par_population,
        "ambient_motions": len(ambient),
        "weights": poids,
        "relative_share": {
            niveau: (round(poids[niveau] *
                           (entites.get(niveau, 0) +
                            par_population.get(niveau, 0)) / total, 4)
                     if total else None)
            for niveau in FIDELITES
        },
        "cost_estimate": None,
        "note": (
            "Parts **relatives**, pas un coût. Aucun générateur n'a tourné "
            "ici ; rendre des minutes de GPU que personne n'a chronométrées "
            "serait une mesure inventée."
        ),
    }


def crowd_report() -> Dict[str, Any]:
    """
    Ce que la foule garantit, et ce qu'elle refuse.

    Returns:
        Les vocabulaires déclarés et les règles tenues.
    """
    return {
        "populations": list(POPULATIONS),
        "densities": dict(DENSITES),
        "ambient_motions": list(MOUVEMENTS_D_AMBIANCE),
        "allowed_fidelities": [FOULE, ARRIERE_PLAN],
        "rules": [
            "Une foule est une **population déclarée**, pas cinquante entités "
            "nommées : cinquante piétons avec mémoire et vérification "
            "d'identité coûtent le prix de cinquante premiers rôles.",
            "La frontière est explicite : dès qu'un figurant a un nom, il a un "
            "budget d'entité. `promote_to_entity()` la fait franchir "
            "sciemment.",
            "Une densité est un mot déclaré, pas un nombre libre : "
            "« densité 0.73 » ne dit rien à personne.",
            "Une population ne monte jamais au-dessus de `BACKGROUND` : celle "
            "qui mérite mieux n'est plus une population.",
            "La répartition est **relative** et le coût vaut `None` : aucun "
            "générateur n'a tourné.",
        ],
        "does_not": [
            "Nommer les individus d'une foule.",
            "Donner à un figurant le budget d'un premier rôle.",
            "Rendre une estimation de coût que personne n'a mesurée.",
            "Inventer une densité numérique.",
        ],
    }
