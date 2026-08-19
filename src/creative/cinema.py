"""
La couche cinéma : boîtier, objectif, mouvement — structurés, jamais en prose
(K06, §10 de la directive Creative Canvas).

## Ce que ce module n'est pas

Ce n'est **pas** une seconde spécification de plan. `direction.py` en porte déjà
une, et elle est bonne : `DirectorSpec` déclare échelle, hauteur, mouvement,
focale, profondeur de champ, lumière, placement, regard et transition, chacun
refusé quand la valeur n'est pas dans son vocabulaire.

Ce module ajoute **ce qui manque**, et rien d'autre :

- l'ouverture comme **nombre**, pas comme intention (`shallow` / `deep`) ;
- la famille d'objectif, qui change l'image sans changer le cadre ;
- le format de capteur, quand il est déclaré ;
- le mouvement en **quatre axes signés**, qui précisent le mouvement catégoriel
  au lieu de le remplacer.

**La focale reste dans `DirectorSpec.lens_mm`.** La porter aussi ici créerait
deux endroits où lire la même chose, donc un endroit où elles peuvent diverger.
C'est la discipline que K00 réclamait après avoir compté trois registres.

## Ce que ce module refuse de calculer

L'audit K01 a lu une implémentation de référence qui répond à tout :

```js
const depthEffect = APERTURE_EFFECT[aperture] || "";   // 3 clés
```

Trois ouvertures ont une réponse, toutes les autres deviennent la chaîne vide —
sans avertissement. Ici, c'est l'inverse : **une question sans les données pour y
répondre rend `UNKNOWN`**, et dit laquelle manque.

- Le champ de vision se calcule à partir de la largeur du capteur et de la
  focale. Sans largeur déclarée, il rend `UNKNOWN` — il ne suppose pas un
  Super 35 parce que c'est le plus courant.
- La profondeur de champ dépend de la focale, de l'ouverture, du capteur **et de
  la distance au sujet**. Trois valeurs sur quatre ne font pas une réponse, elles
  font une réponse fausse avec l'air d'être juste.

## La contradiction que le module attrape

`DirectorSpec.movement` dit `static` et un axe de mouvement vaut `+50` : ce plan
bouge et déclare ne pas bouger. C'est exactement ce que produit un préréglage
qui pose un panoramique que personne n'a demandé (K01), et c'est refusé ici
plutôt que rendu.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .direction import MOUVEMENTS, DirectorSpec

#: Les familles d'objectif déclarées. Elles changent le rendu sans changer le
#: cadrage — un anamorphique et un sphérique de même focale cadrent pareil.
FAMILLES_D_OBJECTIF = (
    "spherical", "anamorphic", "macro", "tilt_shift", "diffusion",
)

#: Les formats de capteur **nommables**. Ce sont des noms, pas des mesures :
#: aucune dimension n'est posée ici, parce qu'une dimension écrite de mémoire
#: serait une mesure inventée. La largeur se déclare sur `CameraSpec`.
FORMATS_DE_CAPTEUR = (
    "16mm", "super16", "super35", "full_frame", "large_format", "65mm",
)

#: Les quatre axes de mouvement, signés. Le vocabulaire vient de l'idée retenue
#: en K01 ; l'amplitude est un entier de -100 à +100, et `0` veut dire « pas de
#: mouvement sur cet axe », ce qui est une décision.
AXES_DE_MOUVEMENT = ("pan", "tilt", "zoom", "dolly")

#: L'amplitude maximale d'un axe.
AMPLITUDE_MAX = 100

#: Rendu par toute question à laquelle les données déclarées ne répondent pas.
INCONNU = "UNKNOWN"

#: Les deux façons de remettre un plan à un fournisseur.
STRUCTURE = "STRUCTURED"
TEXTE_RENDU = "RENDERED_TEXT"


class CinemaRefused(ValueError):
    """Une spécification cinéma impossible, ou contradictoire avec la direction."""


@dataclass(frozen=True)
class CameraSpec:
    """
    Le boîtier — ce qui est déclaré de lui, et rien de plus.

    Attributes:
        sensor_format: Le format nommé, parmi `FORMATS_DE_CAPTEUR`. Vide quand
            il n'est pas décidé.
        sensor_width_mm: La largeur du capteur, en millimètres. `None` = **non
            déclarée**, jamais déduite du nom du format : le nom est un nom, et
            deux boîtiers du même format n'ont pas la même largeur exacte.
        frame_rate: Les images par seconde. `None` = non décidé.
        shutter_angle: L'angle d'obturation, en degrés. `None` = non décidé.
    """

    sensor_format: str = ""
    sensor_width_mm: Optional[float] = None
    frame_rate: Optional[float] = None
    shutter_angle: Optional[float] = None

    def __post_init__(self) -> None:
        if self.sensor_format and self.sensor_format not in FORMATS_DE_CAPTEUR:
            raise CinemaRefused(
                f"Format « {self.sensor_format} » non déclaré. Déclarés : "
                f"{list(FORMATS_DE_CAPTEUR)}."
            )
        for valeur, nom in ((self.sensor_width_mm, "largeur de capteur"),
                            (self.frame_rate, "cadence"),
                            (self.shutter_angle, "angle d'obturation")):
            if valeur is not None and valeur <= 0:
                raise CinemaRefused(f"{nom.capitalize()} {valeur} impossible.")
        if self.shutter_angle is not None and self.shutter_angle > 360:
            raise CinemaRefused(
                f"Angle d'obturation {self.shutter_angle}° impossible : 360° est "
                "le tour complet."
            )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "sensor_format": self.sensor_format,
            "sensor_width_mm": self.sensor_width_mm,
            "frame_rate": self.frame_rate,
            "shutter_angle": self.shutter_angle,
        }


@dataclass(frozen=True)
class LensSpec:
    """
    L'objectif — **sans la focale**, qui vit dans `DirectorSpec.lens_mm`.

    Attributes:
        aperture_f: L'ouverture comme nombre : `1.4`, pas `"f/1.4"`. Une chaîne
            ne se compare pas, ne s'ordonne pas et ne se calcule pas ; c'est
            pour cela que l'implémentation auditée en K01 avait besoin d'une
            table à trois entrées.
        family: La famille, parmi `FAMILLES_D_OBJECTIF`.
        name: Le nom donné à l'objectif, tel qu'écrit. Purement documentaire :
            aucune propriété physique n'en est déduite.
    """

    aperture_f: Optional[float] = None
    family: str = "spherical"
    name: str = ""

    def __post_init__(self) -> None:
        if self.family not in FAMILLES_D_OBJECTIF:
            raise CinemaRefused(
                f"Famille « {self.family} » non déclarée. Déclarées : "
                f"{list(FAMILLES_D_OBJECTIF)}."
            )
        if self.aperture_f is not None and self.aperture_f <= 0:
            raise CinemaRefused(f"Ouverture f/{self.aperture_f} impossible.")

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {"aperture_f": self.aperture_f, "family": self.family,
                "name": self.name}


@dataclass(frozen=True)
class MotionSpec:
    """
    Le mouvement en quatre axes signés, qui **précise** `DirectorSpec.movement`.

    Attributes:
        pan: Négatif = vers la gauche, positif = vers la droite.
        tilt: Négatif = vers le bas, positif = vers le haut.
        zoom: Négatif = arrière, positif = avant.
        dolly: Négatif = recul, positif = avance.

    Note:
        Les quatre axes à `0` décrivent un plan fixe, et c'est une décision —
        pas une absence de décision. `direction.py` dit déjà la même chose de
        son mouvement `static`.
    """

    pan: int = 0
    tilt: int = 0
    zoom: int = 0
    dolly: int = 0

    def __post_init__(self) -> None:
        for axe in AXES_DE_MOUVEMENT:
            valeur = getattr(self, axe)
            if not isinstance(valeur, int) or isinstance(valeur, bool):
                raise CinemaRefused(
                    f"L'axe « {axe} » vaut {valeur!r} : une amplitude est un "
                    "entier."
                )
            if abs(valeur) > AMPLITUDE_MAX:
                raise CinemaRefused(
                    f"Amplitude {valeur} hors bornes sur « {axe} » : "
                    f"-{AMPLITUDE_MAX} à +{AMPLITUDE_MAX}."
                )

    @property
    def is_static(self) -> bool:
        """Vrai quand aucun axe ne bouge."""
        return all(getattr(self, axe) == 0 for axe in AXES_DE_MOUVEMENT)

    def moving_axes(self) -> Dict[str, int]:
        """Les axes non nuls, avec leur amplitude signée."""
        return {axe: getattr(self, axe) for axe in AXES_DE_MOUVEMENT
                if getattr(self, axe) != 0}

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {axe: getattr(self, axe) for axe in AXES_DE_MOUVEMENT}


@dataclass(frozen=True)
class ShotSpec:
    """
    Un plan complet : la direction existante, plus ce que ce module ajoute.

    Attributes:
        direction: Le `DirectorSpec` — il reste la source de l'échelle, de la
            hauteur, de la focale, de la lumière et du mouvement catégoriel.
        camera: Le boîtier déclaré.
        lens: L'objectif déclaré.
        motion: Les quatre axes.

    Raises:
        CinemaRefused: Quand le mouvement catégoriel et les axes se
            contredisent. Un plan qui se dit fixe et bouge, ou qui annonce un
            mouvement sans qu'aucun axe ne bouge, ne décrit rien de
            reproductible.
    """

    direction: DirectorSpec
    camera: CameraSpec = CameraSpec()
    lens: LensSpec = LensSpec()
    motion: MotionSpec = MotionSpec()

    def __post_init__(self) -> None:
        if self.direction.movement not in MOUVEMENTS:      # ceinture et bretelles
            raise CinemaRefused(
                f"Mouvement « {self.direction.movement} » non déclaré."
            )
        if self.direction.movement == "static" and not self.motion.is_static:
            raise CinemaRefused(
                "Le plan est déclaré `static` et "
                f"{list(self.motion.moving_axes())} bouge(nt). Un mouvement "
                "qu'aucune direction n'a demandé est exactement ce que §6 "
                "interdit d'ajouter."
            )
        if self.direction.movement != "static" and self.motion.is_static:
            raise CinemaRefused(
                f"Le plan annonce « {self.direction.movement} » et aucun axe ne "
                "bouge. Le mouvement est annoncé sans être décrit."
            )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, sans dupliquer la focale."""
        return {
            "direction": self.direction.as_dict(),
            "camera": self.camera.as_dict(),
            "lens": self.lens.as_dict(),
            "motion": self.motion.as_dict(),
        }


def horizontal_field_of_view(shot: ShotSpec) -> Dict[str, Any]:
    """
    Le champ de vision horizontal, quand les données déclarées permettent de le
    calculer.

    Args:
        shot: Le plan.

    Returns:
        `degrees` et `status`. `status` vaut `UNKNOWN` — et `missing` nomme ce
        qui manque — dès qu'une des deux entrées n'est pas déclarée.

    Note:
        La formule est de la trigonométrie, pas une table : `2·atan(w / 2f)`.
        Ce qui est refusé, c'est de **supposer** `w`. Un format nommé
        « super35 » ne porte pas sa largeur : deux boîtiers du même format n'ont
        pas la même, et poser une valeur moyenne rendrait un angle faux avec
        l'air d'être mesuré.
    """
    manquants = []
    if shot.camera.sensor_width_mm is None:
        manquants.append("sensor_width_mm")
    if shot.direction.lens_mm is None:
        manquants.append("lens_mm")
    if manquants:
        return {
            "status": INCONNU, "degrees": None, "missing": manquants,
            "reason": ("Le champ de vision se calcule ; il ne se devine pas à "
                       "partir du nom du format."),
        }
    largeur = float(shot.camera.sensor_width_mm)
    focale = float(shot.direction.lens_mm)
    angle = 2.0 * math.atan(largeur / (2.0 * focale))
    return {"status": "MEASURED", "degrees": round(math.degrees(angle), 2),
            "missing": [], "reason": ""}


def depth_of_field_estimate(shot: ShotSpec,
                            subject_distance_m: Optional[float] = None
                            ) -> Dict[str, Any]:
    """
    La profondeur de champ — ou la liste de ce qui manque pour l'établir.

    Args:
        shot: Le plan.
        subject_distance_m: La distance au sujet, en mètres. `None` = inconnue.

    Returns:
        Toujours `status: UNKNOWN` aujourd'hui, avec `missing` nommant les
        entrées absentes.

    Note:
        **Ce module ne rend jamais de profondeur de champ chiffrée**, même
        quand les quatre entrées sont là. La formule dépend en plus du cercle de
        confusion admissible, qui dépend du support de diffusion — donc d'une
        décision que personne n'a prise ici. `DirectorSpec.depth_of_field` porte
        l'intention (`shallow` / `deep`), et une intention n'est pas une mesure :
        les confondre est exactement ce que fait la table à trois entrées lue en
        K01.
    """
    manquants = []
    if shot.lens.aperture_f is None:
        manquants.append("aperture_f")
    if shot.direction.lens_mm is None:
        manquants.append("lens_mm")
    if shot.camera.sensor_width_mm is None:
        manquants.append("sensor_width_mm")
    if subject_distance_m is None:
        manquants.append("subject_distance_m")
    return {
        "status": INCONNU,
        "meters": None,
        "missing": manquants,
        "intent": shot.direction.depth_of_field,
        "reason": ("Aucune profondeur de champ chiffrée n'est rendue : le "
                   "cercle de confusion dépend du support de diffusion, que "
                   "rien ici ne déclare. L'intention est rendue telle quelle, "
                   "et elle n'est pas une mesure."),
    }


#: Les mots dont chaque axe se rend, par signe. Ce sont des directions, pas des
#: intensités : l'amplitude est rendue comme un nombre à côté, jamais remplacée
#: par « subtil » ou « spectaculaire ».
_DIRECTIONS_D_AXE = {
    "pan": ("pan right-to-left", "pan left-to-right"),
    "tilt": ("tilt downward", "tilt upward"),
    "zoom": ("zoom out", "zoom in"),
    "dolly": ("dolly back", "dolly forward"),
}


def render_for_provider(shot: ShotSpec,
                        accepts_camera_control: bool) -> Dict[str, Any]:
    """
    Remet un plan à un fournisseur — structuré quand il sait le lire, rendu en
    texte **au bord** seulement quand il ne sait pas.

    Args:
        shot: Le plan.
        accepts_camera_control: Ce que le fournisseur déclare savoir faire.
            C'est la capacité `camera_control` que `routing.py` classe déjà ;
            elle n'est pas devinée ici.

    Returns:
        `mode`, `fields` (toujours la spécification structurée, entière),
        `text` (vide en mode structuré), et `not_conveyed` — les valeurs
        déclarées que le texte ne porte pas.

    Note:
        **La spécification structurée est rendue dans les deux cas.** C'est tout
        l'écart avec l'implémentation lue en K01, qui concatène boîtier,
        objectif, focale et ouverture dans une phrase anglaise et n'a plus rien
        d'autre : à partir de là, rien ne peut vérifier que le plan 4 a le même
        objectif que le plan 3, ni traduire la demande, ni router sur la
        capacité. Ici le texte est un **rendu**, pas la spécification.

        Le texte n'ajoute aucun adjectif d'ambiance. `direction.py` en tient
        déjà la liste — `cinematic`, `professional` en font partie, et ce sont
        mot pour mot ceux que l'implémentation de référence ajoute à chaque
        requête.
    """
    champs = shot.as_dict()
    if accepts_camera_control:
        return {"mode": STRUCTURE, "fields": champs, "text": "",
                "not_conveyed": [],
                "note": ("Le fournisseur lit la structure : rien n'est mis en "
                         "prose, donc rien n'est perdu.")}

    parties: List[str] = []
    rendus: set = set()

    direction = shot.direction
    parties.append(f"{direction.shot_size} shot")
    rendus.add("shot_size")
    parties.append(f"camera at {direction.camera_height}")
    rendus.add("camera_height")
    parties.append(f"{direction.lighting} lighting")
    rendus.add("lighting")

    if direction.lens_mm is not None:
        parties.append(f"{direction.lens_mm:g}mm")
        rendus.add("lens_mm")
    if shot.lens.aperture_f is not None:
        parties.append(f"f/{shot.lens.aperture_f:g}")
        rendus.add("aperture_f")
    if shot.lens.family != "spherical":
        parties.append(f"{shot.lens.family} lens")
    rendus.add("family")
    if shot.camera.frame_rate is not None:
        parties.append(f"{shot.camera.frame_rate:g} fps")
        rendus.add("frame_rate")

    axes = shot.motion.moving_axes()
    if axes:
        mouvements = [
            f"{_DIRECTIONS_D_AXE[axe][1 if amplitude > 0 else 0]} "
            f"(amplitude {abs(amplitude)} of {AMPLITUDE_MAX})"
            for axe, amplitude in axes.items()
        ]
        parties.append("camera movement: " + ", ".join(mouvements))
    else:
        parties.append("locked-off camera")
    rendus.add("motion")

    #: Les valeurs déclarées pour lesquelles aucun mot ne veut rien dire côté
    #: fournisseur. Elles sont **nommées** plutôt que silencieusement omises.
    non_portees = []
    if shot.camera.sensor_format:
        non_portees.append("sensor_format")
    if shot.camera.sensor_width_mm is not None:
        non_portees.append("sensor_width_mm")
    if shot.camera.shutter_angle is not None:
        non_portees.append("shutter_angle")
    if shot.lens.name:
        non_portees.append("lens.name")
    if direction.depth_of_field:
        non_portees.append("depth_of_field")

    return {
        "mode": TEXTE_RENDU,
        "fields": champs,
        "text": ", ".join(parties),
        "not_conveyed": non_portees,
        "note": ("Le texte est un rendu au bord ; la structure reste la "
                 "spécification. Ce que le texte ne porte pas est nommé, pas "
                 "omis."),
    }


def cinema_report() -> Dict[str, Any]:
    """
    Ce que la couche cinéma déclare, et ce qu'elle refuse.

    Returns:
        Les vocabulaires déclarés et les règles tenues.
    """
    return {
        "lens_families": list(FAMILLES_D_OBJECTIF),
        "sensor_formats": list(FORMATS_DE_CAPTEUR),
        "motion_axes": list(AXES_DE_MOUVEMENT),
        "amplitude_range": [-AMPLITUDE_MAX, AMPLITUDE_MAX],
        "focal_length_lives_in": "direction.DirectorSpec.lens_mm",
        "computed": ["horizontal_field_of_view"],
        "never_computed": ["depth_of_field"],
        "rules": [
            "La focale n'est pas dupliquée : elle reste sur DirectorSpec.",
            "Un nom de format ne porte pas de dimension ; la largeur se "
            "déclare ou reste UNKNOWN.",
            "Un plan `static` avec un axe non nul est refusé, et l'inverse "
            "aussi.",
            "L'ouverture est un nombre, jamais une chaîne.",
            "Aucune profondeur de champ chiffrée n'est rendue.",
        ],
    }
