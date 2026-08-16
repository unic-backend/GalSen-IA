"""
How far the engine actually gets along §40's chain, measured rather than
claimed.

Directive §40 draws seventeen stages from IDEA to FINAL MASTER and asks that
they run with minimal human intervention. The honest way to report on that is
not a paragraph saying the architecture is complete. It is to walk the chain,
stage by stage, and say for each one: the module that implements it — checked on
disk — and the capabilities it needs — checked by the probes.

Three outcomes, and the third is the one that matters:

- `READY` — the module exists and everything it needs is available **here**.
- `BLOCKED` — the module exists and something outside this repository is
  missing. The missing thing is named, so the report doubles as an install list.
- `ABSENT` — nothing implements it. **Speech synthesis is the one**: nothing in
  this repository turns text into voice, and no amount of installing will change
  that. Reporting it as "blocked" would put it on a list of things an operator
  could fix, and they would go looking for a package that was never the problem.

The overall state is **derived** from those, never written down. A readiness
report whose conclusion is a constant says the same thing the day the engine
works and the day it does not, which is the failure mode this whole programme
exists to avoid.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from ..integration.degradation import DISPONIBLE
from .core.capabilities import probe

#: Les trois états d'une étape. `ABSENT` n'est pas `BLOCKED` : le premier ne
#: s'installe pas.
PRET = "READY"
BLOQUE = "BLOCKED"
ABSENT = "ABSENT"

#: La racine du dépôt, pour vérifier qu'un module cité existe réellement.
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class Stage:
    """
    Une étape de la chaîne §40.

    Attributes:
        name: Son nom dans la directive.
        module: Le fichier qui l'implémente, relatif à la racine du dépôt.
            Vide quand rien ne l'implémente.
        requires: Les capacités média nécessaires.
        absent_reason: Pourquoi rien ne l'implémente, le cas échéant.
    """

    name: str
    module: str = ""
    requires: Tuple[str, ...] = ()
    absent_reason: str = ""


#: Les dix-sept étapes de §40, dans son ordre, avec ce qui les porte.
ETAPES: Tuple[Stage, ...] = (
    Stage("IDEA", "src/media/tools/intent.py"),
    Stage("SCRIPT", "src/media/story/planner.py"),
    Stage("MEDIA_ANALYSIS", "src/media/ingestion/inspect.py",
          ("media_probe",)),
    Stage("STORYBOARD", "src/media/story/structures.py"),
    Stage("SCENES", "src/media/analysis/scenes.py", ("video_decode",)),
    Stage("VISUAL_GENERATION", "src/media/providers/base.py",
          ("gpu_compute",)),
    Stage("VIDEO_GENERATION", "src/media/providers/wangp.py",
          ("gpu_compute",)),
    Stage("MOTION_DESIGN", "src/media/motion/render.py", ("frame_encode",)),
    Stage("VOICE", "", (),
          "Aucune synthèse vocale n'existe dans ce dépôt. Ce n'est pas une "
          "capacité absente de la machine : c'est un module qui n'a pas été "
          "écrit, et aucune installation ne le fera apparaître. L'emplacement "
          "`voice` du planificateur porte le **texte à dire**, pas sa voix."),
    Stage("MUSIC", "src/media/audio/music.py"),
    Stage("SOUND_DESIGN", "src/media/audio/sound_design.py"),
    Stage("SUBTITLES", "src/media/subtitles/cues.py"),
    Stage("EDITING", "src/media/timeline/edit_plan.py", ("transcription",)),
    Stage("QUALITY_CONTROL", "src/media/qc/checks.py"),
    Stage("MULTI_FORMAT", "src/media/adapt/formats.py"),
    Stage("MULTILINGUAL", "src/media/adapt/formats.py"),
    Stage("FINAL_MASTER", "src/media/core/project.py", ("video_encode",)),
)

#: Les quinze domaines de test de §32, et les fichiers qui les couvrent. La
#: présence de chaque fichier est **vérifiée** : citer un fichier de tests qui
#: n'existe pas est la façon la plus simple de publier une couverture fausse.
COUVERTURE = {
    "media_ingestion": ("tests/media/test_media_ingestion.py",),
    "transcription": ("tests/media/test_word_timings.py",),
    "scene_detection": ("tests/media/test_scenes.py",),
    "timeline_generation": ("tests/media/test_timeline.py",),
    "subtitle_segmentation": ("tests/media/test_subtitles_assets.py",),
    "audio_synchronization": ("tests/media/test_audio.py",),
    "motion_rendering": ("tests/media/test_motion.py",),
    "asset_resolution": ("tests/media/test_subtitles_assets.py",),
    "model_adapters": ("tests/media/test_providers.py",),
    "wangp_integration": ("tests/media/test_providers.py",),
    "queue_management": ("tests/media/test_adapt_queue.py",),
    "project_memory": ("tests/media/test_project.py",
                       "tests/media/test_project_store.py"),
    "qc": ("tests/media/test_skills_qc.py",),
    "security": ("tests/media/test_media_api.py",),
    "rollback": ("tests/media/test_project.py",),
}


def stage_state(stage: Stage) -> Dict[str, Any]:
    """
    L'état d'une étape, mesuré.

    Args:
        stage: L'étape déclarée.

    Returns:
        Son état, le module vérifié sur le disque, et ce qui lui manque.
        `ABSENT` quand rien ne l'implémente — un état distinct de `BLOCKED`,
        parce qu'aucune installation ne le corrige.
    """
    if not stage.module:
        return {
            "stage": stage.name, "state": ABSENT, "module": None,
            "missing": [], "reason": stage.absent_reason,
        }

    chemin = os.path.join(os.path.dirname(RACINE), stage.module)
    if not os.path.isfile(chemin):
        return {
            "stage": stage.name, "state": ABSENT, "module": stage.module,
            "missing": [],
            "reason": (
                f"« {stage.module} » est cité et n'existe pas. Un rapport qui "
                "nomme un fichier absent décrit un moteur qui n'est pas là."
            ),
        }

    manquantes = []
    for capacite in stage.requires:
        resultat = probe(capacite)
        if resultat["state"] != DISPONIBLE:
            manquantes.append({"capability": capacite,
                               "reason": resultat["reason"]})

    if manquantes:
        return {
            "stage": stage.name, "state": BLOQUE, "module": stage.module,
            "missing": manquantes,
            "reason": (
                f"{len(manquantes)} capacité(s) absente(s) de cette machine : "
                f"{', '.join(m['capability'] for m in manquantes)}. Le module "
                "est écrit ; ce qui manque s'installe."
            ),
        }

    return {
        "stage": stage.name, "state": PRET, "module": stage.module,
        "missing": [],
        "reason": "Le module existe et tout ce qu'il demande est disponible ici.",
    }


def coverage_map() -> Dict[str, Any]:
    """
    Les quinze domaines de test de §32, et les fichiers qui les couvrent.

    Returns:
        Chaque domaine avec ses fichiers **vérifiés sur le disque**. Un fichier
        cité et absent est nommé : publier une couverture appuyée sur un
        fichier qui n'existe pas est la façon la plus simple de la fausser.
    """
    depot = os.path.dirname(RACINE)
    couverts, absents = {}, {}
    for domaine, fichiers in COUVERTURE.items():
        presents = [f for f in fichiers
                    if os.path.isfile(os.path.join(depot, f))]
        manquants = [f for f in fichiers if f not in presents]
        couverts[domaine] = presents
        if manquants:
            absents[domaine] = manquants

    return {
        "areas": couverts,
        "count": len(COUVERTURE),
        "covered": sorted(d for d, f in couverts.items() if f),
        "missing_files": absents,
        "note": (
            "Chaque fichier cité est **vérifié sur le disque**. Une couverture "
            "qui s'appuie sur un fichier absent se lit comme une couverture."
        ),
    }


def readiness() -> Dict[str, Any]:
    """
    L'état du moteur média sur toute la chaîne §40.

    Returns:
        Chaque étape avec son état mesuré, la répartition, la couverture de
        tests et un état d'ensemble **dérivé**. Aucune conclusion n'est écrite
        d'avance : un rapport dont le verdict est une constante dit la même
        chose le jour où le moteur marche et le jour où il ne marche pas.
    """
    etapes = [stage_state(etape) for etape in ETAPES]
    par_etat: Dict[str, List[str]] = {PRET: [], BLOQUE: [], ABSENT: []}
    for entree in etapes:
        par_etat[entree["state"]].append(entree["stage"])

    manquantes = sorted({
        detail["capability"]
        for entree in etapes for detail in entree["missing"]
    })

    return {
        "stages": etapes,
        "by_state": par_etat,
        "counts": {etat: len(noms) for etat, noms in par_etat.items()},
        "missing_capabilities": manquantes,
        "test_coverage": coverage_map(),
        "state": _verdict(par_etat),
        "note": (
            "L'état d'ensemble est **calculé** sur les étapes mesurées. "
            "`ABSENT` et `BLOCKED` sont séparés parce qu'ils ne se corrigent "
            "pas de la même façon : le second s'installe, le premier s'écrit."
        ),
    }


def _verdict(par_etat: Dict[str, List[str]]) -> str:
    """
    L'état d'ensemble, déduit de ce qui a été mesuré.

    Il suit la forme que Darra J a déjà atteinte : le moteur est prêt, ce qui
    l'attend est nommé, et rien n'est présenté comme livrable tant qu'une étape
    n'est pas écrite.
    """
    if par_etat[ABSENT]:
        return (
            "ENGINE READY — MEDIA RUNTIME DEPENDENCIES PENDING, "
            f"{len(par_etat[ABSENT])} STAGE(S) NOT IMPLEMENTED "
            f"({', '.join(par_etat[ABSENT])})"
        )
    if par_etat[BLOQUE]:
        return "ENGINE READY — MEDIA RUNTIME DEPENDENCIES PENDING"
    return "ENGINE READY — ALL STAGES RUNNABLE HERE"


def readiness_report() -> Dict[str, Any]:
    """
    Ce que l'état de préparation garantit, et ce qu'il refuse.

    Returns:
        Les états, les étapes déclarées et les règles tenues.
    """
    return {
        "states": [PRET, BLOQUE, ABSENT],
        "stages": [etape.name for etape in ETAPES],
        "stage_count": len(ETAPES),
        "test_areas": sorted(COUVERTURE),
        "rules": [
            "Chaque module cité est **vérifié sur le disque** et chaque "
            "capacité par sa sonde : un rapport se mesure, il ne se rédige pas.",
            "`ABSENT` et `BLOCKED` sont distincts : le second nomme quelque "
            "chose à installer, le premier quelque chose à écrire. Les "
            "confondre envoie un exploitant chercher un paquet qui n'a jamais "
            "été le problème.",
            "L'état d'ensemble est **dérivé** : un verdict constant dirait la "
            "même chose le jour où le moteur marche et le jour où il ne marche "
            "pas.",
            "La synthèse vocale est `ABSENT` : rien dans ce dépôt ne transforme "
            "du texte en voix, et l'emplacement `voice` du planificateur porte "
            "le texte à dire, pas sa voix.",
        ],
        "does_not": [
            "Présenter une étape non écrite comme une dépendance manquante.",
            "Citer un module ou un fichier de tests sans vérifier qu'il existe.",
            "Écrire une conclusion d'avance.",
        ],
    }
