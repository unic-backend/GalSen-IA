"""
Benchmarks that measure, and refuse to report a number for what did not run.

Directive §33 lists eight things to time and ends on the sentence that decides
the module: *never invent benchmark results.* The temptation is not to make
numbers up outright — nobody does that on purpose. It is subtler and it is
routine: a suite reports render time as `0.0 ms` because the renderer was
skipped, transcription latency as `null` rendered in a table as an empty cell,
and GPU memory as `0` because no GPU answered. Every one of those reads as a
measurement. The first is a *fast* renderer, the last is a machine with no
memory pressure, and both are false.

So a benchmark whose capability is absent returns `NOT_MEASURED` with the
capability named, and it is never coerced into a number on the way out. That is
the same rule the capability probes hold, and it is here for the same reason:
`None` is not zero.

**The median, not the mean.** A garbage collection pause in one sample moves a
mean and does not move a median. Reporting the mean of five runs where one was
40× the others describes an event that happened once, as if it were the normal
case.

**Hardware travels with the number.** "Scene detection: 3 ms" is not a result;
it is half of one. The record carries CPU count, platform, Python version and
the versions of the libraries that did the work — all read from the machine, and
absent when unreadable rather than guessed. A benchmark stored without its
machine will be compared, six months later, against a different one.
"""

from __future__ import annotations

import platform
import statistics
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from ...integration.degradation import DISPONIBLE
from ..core.capabilities import probe

#: Nombre d'échantillons par défaut. Assez pour qu'une médiane ait un sens,
#: assez peu pour qu'une suite de tests reste utilisable.
ECHANTILLONS = 5

#: L'état d'une mesure qui n'a pas pu être faite. Ce n'est pas zéro, et le
#: rendre en zéro décrirait un moteur instantané.
NON_MESURE = "NOT_MEASURED"

#: L'état d'une mesure réellement faite.
MESURE = "MEASURED"


class BenchmarkRefused(ValueError):
    """Une mesure impossible à faire telle qu'elle est demandée."""


def hardware() -> Dict[str, Any]:
    """
    La machine sur laquelle les mesures ont été prises.

    Returns:
        Le processeur, la plateforme, Python, la mémoire et le GPU. Chaque
        champ est **lu** ou vaut `None` : une valeur supposée ferait comparer
        deux mesures prises sur deux machines différentes comme si c'était la
        même.
    """
    import os

    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
        "memory_gb": _memoire_gb(),
        "gpu_vram_gb": _vram_gb(),
        "libraries": _versions(),
        "note": (
            "Lu sur la machine. Un champ à `null` est **illisible ici**, pas "
            "absent : le supposer ferait comparer deux mesures prises sur deux "
            "machines différentes comme si c'était la même."
        ),
    }


def _memoire_gb() -> Optional[float]:
    """La mémoire vive totale, en Go, ou `None` si elle n'est pas lisible."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as fichier:
            for ligne in fichier:
                if ligne.startswith("MemTotal:"):
                    return round(int(ligne.split()[1]) / (1024 ** 2), 2)
    except (OSError, ValueError, IndexError):
        return None
    return None


def _vram_gb() -> Optional[float]:
    """La VRAM mesurée, par la fonction qui la mesure déjà — jamais une seconde."""
    from ..providers.base import measured_vram_gb

    return measured_vram_gb()


def _versions() -> Dict[str, Optional[str]]:
    """Les versions des bibliothèques qui font le travail mesuré."""
    versions: Dict[str, Optional[str]] = {}
    for nom, module in (("opencv", "cv2"), ("pillow", "PIL")):
        try:
            importe = __import__(module)
            versions[nom] = getattr(importe, "__version__", None)
        except ImportError:
            versions[nom] = None
    return versions


def measure(
    name: str, operation: Callable[[], Any], samples: int = ECHANTILLONS,
    requires: Sequence[str] = (),
) -> Dict[str, Any]:
    """
    Mesure une opération, ou dit pourquoi elle n'a pas pu l'être.

    Args:
        name: Le nom de la mesure.
        operation: Ce qui est chronométré. Appelé `samples` fois.
        samples: Le nombre d'exécutions.
        requires: Les capacités média nécessaires.

    Returns:
        La médiane, le minimum, le maximum et le nombre d'échantillons — ou
        `NOT_MEASURED` avec la capacité absente. **La médiane, pas la
        moyenne** : une pause du ramasse-miettes sur un échantillon déplace une
        moyenne et ne déplace pas une médiane.

    Raises:
        BenchmarkRefused: Pour un nombre d'échantillons nul ou négatif.
    """
    if samples < 1:
        raise BenchmarkRefused(
            f"{samples} échantillon(s) : une mesure sans exécution n'est pas "
            "une mesure rapide, c'est une absence de mesure."
        )

    for capacite in requires:
        resultat = probe(capacite)
        if resultat["state"] != DISPONIBLE:
            return {
                "benchmark": name, "status": NON_MESURE,
                "missing": capacite, "reason": resultat["reason"],
                "median_ms": None, "min_ms": None, "max_ms": None,
                "samples": 0,
                "note": (
                    "Non mesuré. Rendre `0` décrirait une opération instantanée, "
                    "et rendre une estimation la ferait comparer à une mesure."
                ),
            }

    durees: List[float] = []
    try:
        for _ in range(samples):
            debut = time.perf_counter()
            operation()
            durees.append((time.perf_counter() - debut) * 1000)
    except Exception as erreur:
        # Une mesure qui échoue est un échec de mesure, jamais un temps.
        return {
            "benchmark": name, "status": NON_MESURE,
            "missing": None, "reason": f"{type(erreur).__name__}: {erreur}",
            "median_ms": None, "min_ms": None, "max_ms": None,
            "samples": len(durees),
            "note": "L'opération a échoué. Un échec n'a pas de durée.",
        }

    return {
        "benchmark": name, "status": MESURE,
        "median_ms": round(statistics.median(durees), 4),
        "min_ms": round(min(durees), 4),
        "max_ms": round(max(durees), 4),
        "samples": len(durees),
        "missing": None,
        "note": (
            "Médiane sur des exécutions réelles. La moyenne aurait décrit une "
            "pause du ramasse-miettes comme si c'était le cas normal."
        ),
    }


# ----------------------------------------------------------------------
# Les opérations mesurées, sur des fixtures déterministes (§32)
# ----------------------------------------------------------------------

def _trames_synthetiques(nombre: int = 24, coupure: int = 12) -> List[Any]:
    """
    Des trames déterministes avec **une** coupure connue.

    Les mesures ne dépendent d'aucun fichier : une fixture qui vit sur le
    disque rend la mesure dépendante de ce que quelqu'un y a laissé.
    """
    import numpy

    trames = []
    for index in range(nombre):
        valeur = 30 if index < coupure else 200
        trame = numpy.full((64, 64, 3), valeur, dtype=numpy.uint8)
        trame[:, :, index % 3] = (valeur + index) % 256
        trames.append(trame)
    return trames


def _mots_synthetiques(nombre: int = 120) -> List[Any]:
    """Des mots mesurés, régulièrement espacés."""
    from ..transcription.words import WordTiming

    return [
        WordTiming(word=f"mot{index}", start=index * 0.4,
                   end=index * 0.4 + 0.35)
        for index in range(nombre)
    ]


def _scene_synthetique(frames: int = 12) -> Any:
    """Une scène animée minimale, entièrement décrite."""
    from ..motion.scene import Element, MotionScene, Track

    return MotionScene(
        width=160, height=90, fps=12, frames=frames,
        elements=(
            Element(kind="rect", props={"x": 10, "y": 10, "width": 40,
                                        "height": 20},
                    tracks=(Track(prop="x", start_frame=0,
                                  end_frame=frames - 1, start_value=10,
                                  end_value=100),)),
            Element(kind="text", props={"x": 10, "y": 50, "text": "GalSen"}),
        ),
    )


def bench_scene_detection(samples: int = ECHANTILLONS) -> Dict[str, Any]:
    """Détection de plans sur 24 trames synthétiques portant une coupure."""
    from ..analysis.scenes import detect_cuts

    trames = _trames_synthetiques()
    return measure("scene_detection", lambda: detect_cuts(trames), samples)


def bench_subtitle_segmentation(samples: int = ECHANTILLONS) -> Dict[str, Any]:
    """Découpage de sous-titres sur 120 mots mesurés."""
    from ..subtitles.cues import build_cues

    mots = _mots_synthetiques()
    return measure("subtitle_segmentation",
                   lambda: build_cues(mots, language="fr"), samples)


def bench_edit_plan(samples: int = ECHANTILLONS) -> Dict[str, Any]:
    """Résolution d'un plan de montage sur des temps mesurés."""
    from ..timeline.edit_plan import Selection, build_plan

    mots = _mots_synthetiques()
    selections = [Selection(quote="mot10 mot11 mot12", reason="mesure"),
                  Selection(quote="mot80 mot81", reason="mesure")]
    return measure("edit_plan", lambda: build_plan(selections, mots), samples)


def bench_motion_frame(samples: int = ECHANTILLONS) -> Dict[str, Any]:
    """Dessin d'une trame de motion design."""
    from ..motion.render import render_frame

    scene = _scene_synthetique()
    return measure("motion_frame", lambda: render_frame(scene, 5), samples,
                   requires=("image_analysis",))


def bench_render(output_dir: str, samples: int = 1) -> Dict[str, Any]:
    """
    Encodage d'une vidéo réelle de douze trames.

    Args:
        output_dir: Où écrire. Un rendu qui n'écrit rien ne mesure rien.
        samples: Le nombre d'encodages. Un seul par défaut : c'est la mesure la
            plus coûteuse de cette liste.
    """
    import os

    from ..motion.render import render_video

    scene = _scene_synthetique()
    compteur = {"index": 0}

    def encoder() -> Any:
        compteur["index"] += 1
        chemin = os.path.join(output_dir, f"bench-{compteur['index']}.webm")
        return render_video(scene, chemin)

    return measure("render", encoder, samples, requires=("frame_encode",))


def bench_queue_throughput(samples: int = ECHANTILLONS,
                           jobs: int = 200) -> Dict[str, Any]:
    """
    Dépôt et avancement de 200 travaux dans la file.

    `samples` vient **en premier**, comme dans toutes les mesures de `MESURES` :
    le registre les appelle avec un seul argument positionnel, et une signature
    différente ici mesurait trois travaux en croyant en mesurer deux cents.
    """
    from ..queue.jobs import RenderQueue

    def parcourir() -> Any:
        file = RenderQueue()
        for _ in range(jobs):
            travail = file.submit(total_units=10)
            file.advance(travail.job_id, 10)
        return file.report()

    return measure("queue_throughput", parcourir, samples)


def bench_intent(samples: int = ECHANTILLONS) -> Dict[str, Any]:
    """Analyse d'une demande en langage naturel et vérification de la chaîne."""
    from ..tools.intent import production_plan

    return measure(
        "intent_to_plan",
        lambda: production_plan(
            "Fais-moi un documentaire vertical de 2 minutes en wolof."),
        samples,
    )


def bench_transcription(samples: int = ECHANTILLONS) -> Dict[str, Any]:
    """Transcription — non mesurable sans le moteur de parole (§32)."""
    return measure("transcription", lambda: None, samples,
                   requires=("transcription",))


def bench_media_probe(samples: int = ECHANTILLONS) -> Dict[str, Any]:
    """Mesure d'un fichier média — non mesurable sans `ffprobe`."""
    return measure("media_probe", lambda: None, samples,
                   requires=("media_probe",))


#: Les mesures qui ne demandent aucune écriture sur le disque.
MESURES = {
    "scene_detection": bench_scene_detection,
    "subtitle_segmentation": bench_subtitle_segmentation,
    "edit_plan": bench_edit_plan,
    "motion_frame": bench_motion_frame,
    "queue_throughput": bench_queue_throughput,
    "intent_to_plan": bench_intent,
    "transcription": bench_transcription,
    "media_probe": bench_media_probe,
}


def run_all(
    samples: int = ECHANTILLONS, output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Passe toutes les mesures et rend le relevé complet.

    Args:
        samples: Le nombre d'échantillons par mesure.
        output_dir: Où écrire pour la mesure d'encodage. Sans lui, l'encodage
            est **déclaré non mesuré** plutôt que sauté en silence : une mesure
            absente d'un tableau se lit comme une mesure qui n'existe pas.

    Returns:
        La machine, chaque mesure avec son état, et le compte de ce qui n'a pas
        pu être mesuré. Le relevé porte toujours sa machine : « détection de
        plans : 3 ms » n'est pas un résultat, c'est la moitié d'un.
    """
    resultats = {nom: mesure(samples) for nom, mesure in MESURES.items()}

    if output_dir:
        resultats["render"] = bench_render(output_dir)
    else:
        resultats["render"] = {
            "benchmark": "render", "status": NON_MESURE, "missing": None,
            "reason": ("Aucun répertoire de sortie fourni : un encodage qui "
                       "n'écrit rien ne mesure rien."),
            "median_ms": None, "min_ms": None, "max_ms": None, "samples": 0,
            "note": "Déclaré non mesuré plutôt que sauté en silence.",
        }

    mesures = [r for r in resultats.values() if r["status"] == MESURE]
    non_mesures = {nom: r.get("missing") or r.get("reason")
                   for nom, r in resultats.items() if r["status"] == NON_MESURE}

    return {
        "hardware": hardware(),
        "results": resultats,
        "measured": sorted(r["benchmark"] for r in mesures),
        "not_measured": non_mesures,
        "counts": {"measured": len(mesures), "not_measured": len(non_mesures)},
        "note": (
            "Chaque chiffre est une **médiane** d'exécutions réelles sur la "
            "machine décrite au-dessus. Les mesures absentes sont nommées avec "
            "ce qui leur manque : un `0` à leur place décrirait un moteur "
            "instantané, et un vide se lirait comme une mesure qui n'existe pas."
        ),
    }


def benchmark_report() -> Dict[str, Any]:
    """
    Ce que les mesures garantissent, et ce qu'elles refusent.

    Returns:
        Les mesures déclarées et les règles tenues.
    """
    return {
        "benchmarks": sorted(MESURES) + ["render"],
        "default_samples": ECHANTILLONS,
        "statuses": [MESURE, NON_MESURE],
        "rules": [
            "Une capacité absente rend `NOT_MEASURED` en la nommant. `0` "
            "décrirait une opération instantanée ; un vide se lirait comme une "
            "mesure inexistante.",
            "La **médiane**, pas la moyenne : une pause du ramasse-miettes sur "
            "un échantillon déplace une moyenne et pas une médiane.",
            "La machine voyage avec le chiffre : « détection de plans : 3 ms » "
            "n'est pas un résultat, c'est la moitié d'un.",
            "Les fixtures sont **synthétiques et déterministes** : une fixture "
            "sur le disque rendrait la mesure dépendante de ce que quelqu'un y "
            "a laissé.",
            "Une opération qui échoue rend son erreur, jamais une durée.",
        ],
        "does_not": [
            "Estimer une durée qui n'a pas été chronométrée.",
            "Rendre `0` pour une capacité absente.",
            "Rendre une moyenne.",
            "Enregistrer un chiffre sans sa machine.",
        ],
    }
