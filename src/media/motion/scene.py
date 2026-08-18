"""
An animation described as data, so that two renders can be compared.

Directive §8 asks for motion design generated from structured scene
descriptions, and for the visual style not to be hardcoded. Those two demands
are the same demand: if the description is data and the style is data, then a
render is a pure function of them, and the same input produces the same frames.
That property is what makes anything downstream checkable — a quality control
that cannot re-render the same thing twice has nothing to compare.

So the model here is deliberately small and completely explicit.

**Time is a frame index at a declared rate.** Not "roughly 2 seconds in". Frame
n happens at exactly `n / fps`, and a track's value at frame n is computed, not
sampled from a clock. A renderer that reads the wall clock produces a different
video every run and nobody notices until a QC diff is compared.

**Easing is declared, not hidden.** Three curves exist, they are named, and a
caller can pass their own. A hidden default easing is a style decision made by
whoever wrote the framework rather than by whoever is making the film.

**The visual identity is data.** Colours, fonts, sizes and spacings live in a
`VisualIdentity` passed in at render time. Two identities over the same scene
produce different pixels and identical structure — which is what "support
multiple visual identities" has to mean if it is to mean anything.

What is *not* implemented is listed by name in `NON_IMPLEMENTE` rather than
implied. Particles, masks and 3D are real features with real costs; claiming
them because the directive lists them would be the fabrication this repository
refuses everywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

#: Les primitives réellement rendues aujourd'hui.
PRIMITIVES = ("rect", "text", "line", "image")

#: Ce qui n'est **pas** implémenté, avec la raison. Nommé plutôt que sous-entendu :
#: prétendre porter ces capacités parce que la directive les cite serait la
#: fabrication que ce dépôt refuse partout ailleurs.
NON_IMPLEMENTE = {
    "particles": "Demande un simulateur et un budget GPU. Aucun n'existe ici.",
    "masks": "Demande une composition par canaux alpha empilés, non écrite.",
    "3d": "Demande un moteur de rendu 3D (Three.js, WebGL) — voir le backend "
          "navigateur, aujourd'hui DEGRADE faute de pilote.",
    "object_tracking": "Demande une analyse vidéo par trame, et le décodage "
                       "vidéo est DEGRADE sur cette machine.",
}

#: Les courbes d'animation déclarées. Une accélération cachée est une décision
#: de style prise par l'auteur du cadre, pas par l'auteur du film.
COURBES: Dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "ease_in": lambda t: t * t,
    "ease_out": lambda t: 1 - (1 - t) * (1 - t),
    "ease_in_out": lambda t: 2 * t * t if t < 0.5 else 1 - 2 * (1 - t) ** 2,
}


class MotionRefused(ValueError):
    """Une animation qui ne peut pas être décrite telle quelle."""


@dataclass(frozen=True)
class VisualIdentity:
    """
    Le style, en données — jamais en dur dans le moteur.

    Attributes:
        name: Son nom, pour qu'un rendu dise sous quelle identité il a été fait.
        background: Le fond, en RGB.
        primary: La couleur d'accent.
        text_color: La couleur du texte.
        font_size: La taille de base.
        margin: La marge de sécurité, en pixels.
    """

    name: str = "default"
    background: Tuple[int, int, int] = (12, 14, 20)
    primary: Tuple[int, int, int] = (220, 90, 40)
    text_color: Tuple[int, int, int] = (240, 240, 240)
    font_size: int = 20
    margin: int = 24

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "name": self.name, "background": list(self.background),
            "primary": list(self.primary), "text_color": list(self.text_color),
            "font_size": self.font_size, "margin": self.margin,
        }


@dataclass(frozen=True)
class Track:
    """
    Une propriété qui change dans le temps.

    Attributes:
        prop: La propriété animée — `x`, `y`, `opacity`, `width`, `height`.
        start_frame: Première trame du mouvement, incluse.
        end_frame: Dernière trame, incluse.
        start_value: Valeur au début.
        end_value: Valeur à la fin.
        easing: La courbe, parmi `COURBES`.
    """

    prop: str
    start_frame: int
    end_frame: int
    start_value: float
    end_value: float
    easing: str = "linear"

    def __post_init__(self) -> None:
        if self.easing not in COURBES:
            raise MotionRefused(
                f"Courbe « {self.easing} » non déclarée. Les courbes sont "
                f"{sorted(COURBES)} : en deviner une ferait bouger deux scènes "
                "différemment sans que personne l'ait décidé."
            )
        if self.end_frame < self.start_frame:
            raise MotionRefused(
                f"Piste « {self.prop} » : trame de fin {self.end_frame} avant "
                f"le début {self.start_frame}."
            )

    def value_at(self, frame: int) -> float:
        """
        La valeur à une trame donnée — calculée, jamais échantillonnée.

        Args:
            frame: L'index de la trame.

        Returns:
            La valeur interpolée. Avant le début elle vaut `start_value`, après
            la fin `end_value` : une piste ne « disparaît » pas hors de son
            intervalle, elle y tient sa dernière valeur.
        """
        if frame <= self.start_frame:
            return self.start_value
        if frame >= self.end_frame:
            return self.end_value
        duree = self.end_frame - self.start_frame
        avancement = (frame - self.start_frame) / duree
        return self.start_value + (
            self.end_value - self.start_value
        ) * COURBES[self.easing](avancement)


@dataclass(frozen=True)
class Element:
    """
    Un objet dessiné, et ce qui l'anime.

    Attributes:
        kind: Une primitive de `PRIMITIVES`.
        props: Ses propriétés fixes.
        tracks: Ce qui change dans le temps.
        z: L'ordre de dessin, du plus petit au plus grand.
    """

    kind: str
    props: Dict[str, Any] = field(default_factory=dict)
    tracks: Tuple[Track, ...] = ()
    z: int = 0

    def __post_init__(self) -> None:
        if self.kind not in PRIMITIVES:
            raise MotionRefused(
                f"Primitive « {self.kind} » non rendue. Rendues : "
                f"{list(PRIMITIVES)}. Non implémentées et nommées : "
                f"{sorted(NON_IMPLEMENTE)}."
            )

    def state_at(self, frame: int) -> Dict[str, Any]:
        """
        L'état complet de l'élément à une trame.

        Les propriétés fixes d'abord, les pistes ensuite : une piste écrase la
        valeur fixe de la même propriété, ce qui rend un élément immobile
        animable sans le réécrire.
        """
        etat = dict(self.props)
        for piste in self.tracks:
            etat[piste.prop] = piste.value_at(frame)
        return etat


@dataclass(frozen=True)
class MotionScene:
    """
    Une scène animée, entièrement décrite.

    Attributes:
        width: Largeur en pixels.
        height: Hauteur en pixels.
        fps: Cadence **déclarée** — c'est elle qui définit l'instant d'une trame.
        frames: Nombre de trames.
        elements: Ce qui est dessiné.
    """

    width: int
    height: int
    fps: float
    frames: int
    elements: Tuple[Element, ...] = ()

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise MotionRefused(
                f"Dimensions impossibles : {self.width}×{self.height}."
            )
        if self.fps <= 0:
            raise MotionRefused(
                f"Cadence {self.fps} : sans cadence positive, l'instant d'une "
                "trame n'est pas défini."
            )
        if self.frames <= 0:
            raise MotionRefused(
                "Une scène sans trame ne produit aucune image, et l'accepter "
                "ferait rendre un fichier vide qui s'encode sans erreur."
            )

    @property
    def duration(self) -> float:
        """La durée de la scène, en secondes."""
        return round(self.frames / self.fps, 4)

    def time_of(self, frame: int) -> float:
        """
        L'instant exact d'une trame.

        La trame `n` arrive à `n / fps`, calculé — jamais lu sur une horloge.
        Un rendu qui consulte l'heure produit une vidéo différente à chaque
        exécution, et personne ne s'en aperçoit avant de comparer deux
        contrôles qualité.
        """
        return round(frame / self.fps, 6)

    def draw_order(self, frame: int) -> List[Tuple[Element, Dict[str, Any]]]:
        """Les éléments et leur état, dans l'ordre de dessin."""
        return [
            (element, element.state_at(frame))
            for element in sorted(self.elements, key=lambda e: e.z)
        ]

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "width": self.width, "height": self.height, "fps": self.fps,
            "frames": self.frames, "duration": self.duration,
            "elements": [
                {"kind": e.kind, "z": e.z, "props": dict(e.props),
                 "tracks": [
                     {"prop": t.prop, "from": t.start_frame, "to": t.end_frame,
                      "easing": t.easing}
                     for t in e.tracks
                 ]}
                for e in self.elements
            ],
        }


def motion_report() -> Dict[str, Any]:
    """
    Ce que le motion design rend, et ce qu'il ne rend pas.

    Returns:
        Les primitives, les courbes, ce qui n'est pas implémenté, et les règles.
    """
    return {
        "primitives": list(PRIMITIVES),
        "easings": sorted(COURBES),
        "not_implemented": dict(NON_IMPLEMENTE),
        "rules": [
            "Une scène est **entièrement décrite en données** : le rendu est "
            "alors une fonction pure de la description et du style, donc deux "
            "rendus se comparent.",
            "Le temps est un index de trame à une cadence **déclarée** : la "
            "trame `n` arrive à `n / fps`, calculé et jamais lu sur une "
            "horloge.",
            "Les courbes d'animation sont déclarées : une accélération cachée "
            "est une décision de style prise par l'auteur du cadre, pas par "
            "l'auteur du film.",
            "Le style est une donnée (`VisualIdentity`) : deux identités sur la "
            "même scène donnent des pixels différents et une structure "
            "identique.",
            "Ce qui n'est pas implémenté est **nommé** — le prétendre parce que "
            "la directive le cite serait une fabrication.",
        ],
        "does_not": [
            "Lire l'horloge pendant un rendu.",
            "Appliquer une courbe d'animation non déclarée.",
            "Coder un style en dur dans le moteur.",
            "Prétendre rendre une primitive qu'il ne rend pas.",
        ],
    }


__all__ = [
    "COURBES",
    "NON_IMPLEMENTE",
    "PRIMITIVES",
    "Element",
    "MotionRefused",
    "MotionScene",
    "Track",
    "VisualIdentity",
    "motion_report",
]
