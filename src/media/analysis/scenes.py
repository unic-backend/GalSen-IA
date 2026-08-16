"""
Where the picture changes — computed from the frames, never proposed by a model.

This is directive §1 at its sharpest. A model asked "where are the scene changes
in this video?" will answer with timestamps, fluently and immediately, and they
will be invented. Scene boundaries are a *measurement*: consecutive frames either
differ or they do not, and the difference is a number anyone can recompute.

So the split of labour is fixed here and the module holds one half of it. The
detector says **where** the picture changes. What that means — which shot is a
bad take, which one carries the argument, which one to keep — is decided
elsewhere, by something that can reason. Neither side is allowed to do the
other's job.

Three rules give the measurement its shape.

**A boundary is a frame index until an FPS is measured.** Converting index to
seconds needs a frame rate, and on a machine with no `ffprobe` there is none
(`inspect.py` reports it unknown rather than guessing 25). Emitting `t = 2.4 s`
from an assumed 25 fps would be a fabricated timestamp wearing a measurement's
clothes — and a cut placed on it lands in the middle of a word. So times appear
only when someone measured the frame rate, and are absent otherwise.

**The threshold is declared.** A cut detector is a threshold and nothing else,
and an implicit one is a policy nobody can argue with. `SEUIL_COUPURE` is a
module constant, overridable per call, and every result carries the threshold it
was judged against plus the raw distances — so a disagreement is checkable
rather than a matter of opinion.

**A distance is not a confidence.** The detector reports how far apart two
frames were, not how sure it is. Rescaling a histogram distance into a
percentage would invent a probability out of a difference, and the two are not
the same quantity.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

#: Distance au-delà de laquelle deux trames consécutives sont considérées comme
#: appartenant à deux plans. Déclarée, donc contestable — un détecteur de coupe
#: **est** un seuil, et un seuil implicite est une politique que personne ne peut
#: discuter. La valeur vient de la distance de Bhattacharyya entre histogrammes,
#: dont l'échelle va de 0 (identiques) à 1 (sans recouvrement).
SEUIL_COUPURE = 0.45

#: Nombre de casiers par canal pour l'histogramme. Assez pour distinguer deux
#: plans, assez peu pour qu'un grain de compression ne déclenche pas une coupe.
CASIERS = 32

#: Longueur minimale d'un plan, en trames. En dessous, deux « coupures »
#: consécutives décrivent un scintillement, pas deux plans.
PLAN_MINIMAL = 2


class SceneDetectionRefused(ValueError):
    """Une détection qui ne peut pas être faite sur ce qui a été fourni."""


def _histogramme(trame: Any) -> Any:
    """
    L'histogramme couleur normalisé d'une trame.

    Args:
        trame: Un tableau `numpy` en BGR ou en niveaux de gris.

    Returns:
        L'histogramme, normalisé pour que deux trames de tailles différentes
        restent comparables.
    """
    import cv2
    import numpy

    tableau = numpy.asarray(trame)
    if tableau.ndim == 2:
        tableau = cv2.cvtColor(tableau, cv2.COLOR_GRAY2BGR)
    histogramme = cv2.calcHist(
        [tableau], [0, 1, 2], None, [CASIERS] * 3, [0, 256] * 3,
    )
    return cv2.normalize(histogramme, histogramme).flatten()


def frame_distances(frames: Sequence[Any]) -> List[float]:
    """
    La distance entre chaque paire de trames consécutives.

    Args:
        frames: Les trames, dans l'ordre.

    Returns:
        `len(frames) - 1` distances, entre 0 (identiques) et 1 (sans
        recouvrement). Ce sont les **mesures brutes** : elles sont rendues avec
        tout verdict pour qu'un désaccord soit vérifiable au lieu d'être une
        affaire d'opinion.

    Raises:
        SceneDetectionRefused: Avec moins de deux trames. Une seule trame ne
            contient aucune transition, et rendre une liste vide laisserait
            croire qu'on a cherché.
    """
    if len(frames) < 2:
        raise SceneDetectionRefused(
            f"{len(frames)} trame(s) : il en faut au moins deux pour qu'une "
            "transition existe. Rendre une liste vide laisserait croire qu'on "
            "a cherché."
        )
    import cv2

    histogrammes = [_histogramme(trame) for trame in frames]
    return [
        float(cv2.compareHist(histogrammes[i], histogrammes[i + 1],
                              cv2.HISTCMP_BHATTACHARYYA))
        for i in range(len(histogrammes) - 1)
    ]


def detect_cuts(
    frames: Sequence[Any],
    threshold: float = SEUIL_COUPURE,
    min_shot: int = PLAN_MINIMAL,
    fps: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Détecte les changements de plan, en trames et — si possible — en secondes.

    Args:
        frames: Les trames, dans l'ordre.
        threshold: Le seuil de coupure. Le défaut est déclaré et discutable.
        min_shot: Longueur minimale d'un plan, en trames.
        fps: La cadence **mesurée**. Absente, aucun temps n'est rendu.

    Returns:
        Les frontières en index de trame, les distances brutes, le seuil
        employé, et les temps **uniquement si `fps` a été mesuré**. Convertir
        avec une cadence supposée fabriquerait un horodatage habillé en mesure,
        et une coupe posée dessus tombe au milieu d'un mot.

    Raises:
        SceneDetectionRefused: Moins de deux trames, ou seuil hors de [0, 1].
    """
    if not 0.0 <= threshold <= 1.0:
        raise SceneDetectionRefused(
            f"Seuil {threshold} hors de [0, 1] : la distance mesurée vit dans "
            "cet intervalle, et un seuil au-delà ne déclencherait jamais."
        )

    distances = frame_distances(frames)

    frontieres: List[int] = []
    derniere = -min_shot
    for index, distance in enumerate(distances):
        if distance <= threshold:
            continue
        # Deux « coupures » trop rapprochées décrivent un scintillement, pas
        # deux plans. La seconde est retenue comme information, pas comme
        # frontière.
        if index + 1 - derniere < min_shot:
            continue
        frontieres.append(index + 1)
        derniere = index + 1

    plans = _plans(frontieres, len(frames))
    resultat: Dict[str, Any] = {
        "frame_count": len(frames),
        "boundaries": frontieres,
        "shots": plans,
        "distances": [round(valeur, 4) for valeur in distances],
        "threshold": threshold,
        "min_shot_frames": min_shot,
        "times_available": fps is not None,
    }

    if fps is None:
        resultat["times"] = None
        resultat["why_no_times"] = (
            "Aucune cadence mesurée. La convertir depuis une valeur supposée "
            "fabriquerait un horodatage habillé en mesure — et une coupe posée "
            "dessus tombe au milieu d'un mot."
        )
    elif fps <= 0:
        raise SceneDetectionRefused(
            f"Cadence {fps} impossible : une cadence nulle ou négative ne "
            "convertit rien."
        )
    else:
        resultat["fps"] = fps
        resultat["times"] = [round(index / fps, 4) for index in frontieres]
        resultat["shot_times"] = [
            {"start": round(plan["start"] / fps, 4),
             "end": round(plan["end"] / fps, 4)}
            for plan in plans
        ]
    return resultat


def _plans(frontieres: List[int], total: int) -> List[Dict[str, int]]:
    """
    Les plans délimités par ces frontières, en index de trame.

    Les bornes sont `[start, end)` : le dernier plan va jusqu'à la fin, et une
    vidéo sans frontière est **un** plan, jamais zéro.
    """
    bornes = [0] + list(frontieres) + [total]
    return [
        {"start": bornes[i], "end": bornes[i + 1],
         "frames": bornes[i + 1] - bornes[i]}
        for i in range(len(bornes) - 1)
        if bornes[i + 1] > bornes[i]
    ]


def load_frames(paths: Sequence[str]) -> List[Any]:
    """
    Charge des trames depuis des fichiers image.

    Args:
        paths: Les chemins, **déjà résolus** par `src/storage/roots.py`.

    Returns:
        Les trames chargées, dans l'ordre donné.

    Raises:
        SceneDetectionRefused: Dès qu'une trame est illisible. Sauter une trame
            décalerait toutes les frontières suivantes sans que rien ne le dise,
            ce qui est pire que refuser.
    """
    import cv2

    trames: List[Any] = []
    for chemin in paths:
        trame = cv2.imread(chemin)
        if trame is None:
            raise SceneDetectionRefused(
                f"Trame illisible : « {chemin} ». La sauter décalerait toutes "
                "les frontières suivantes sans que rien ne le dise."
            )
        trames.append(trame)
    return trames


def scene_detection_report() -> Dict[str, Any]:
    """
    Ce que la détection garantit, et ce qu'elle refuse.

    Returns:
        Les seuils déclarés et les règles tenues.
    """
    return {
        "threshold": SEUIL_COUPURE,
        "bins_per_channel": CASIERS,
        "min_shot_frames": PLAN_MINIMAL,
        "metric": "bhattacharyya_histogram_distance",
        "rules": [
            "Une frontière est **mesurée** sur les trames, jamais proposée par "
            "un modèle : un modèle répondrait avec des horodatages inventés, "
            "immédiatement et avec aplomb.",
            "Une frontière est un **index de trame** tant qu'aucune cadence "
            "n'a été mesurée. Convertir avec une cadence supposée fabriquerait "
            "un horodatage habillé en mesure.",
            "Le seuil est déclaré et rendu avec le résultat, accompagné des "
            "distances brutes : un désaccord doit être vérifiable, pas une "
            "affaire d'opinion.",
            "Une distance n'est pas une confiance : la remettre à l'échelle en "
            "pourcentage inventerait une probabilité à partir d'un écart.",
            "Une trame illisible **arrête** la détection : la sauter décalerait "
            "toutes les frontières suivantes en silence.",
        ],
        "does_not": [
            "Convertir des index en secondes sans cadence mesurée.",
            "Décider quel plan est important, bon ou à garder.",
            "Rendre une confiance là où il n'y a qu'un écart.",
            "Traiter une vidéo sans coupure comme une vidéo sans plan.",
        ],
    }
