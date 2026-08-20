"""
Jusqu'où la chaîne live va réellement, mesuré plutôt qu'affirmé
(L13.2, ADR-033, §8 et §31 à §34 de la directive Live Context).

## Pourquoi ce module calcule au lieu d'écrire

Un rapport dont la conclusion est une constante dit la même chose le jour où le
moteur marche et le jour où il ne marche pas. `media/readiness.py` a posé la
forme : parcourir la chaîne étape par étape, vérifier **sur le disque** le
module qui la porte, **par les sondes** ce dont elle a besoin, et n'en déduire
l'état d'ensemble qu'à la fin.

Citer un module qui n'existe pas est la façon la plus simple de publier un état
faux, donc chaque chemin est vérifié.

## La distinction que ce volet a mesurée avant de l'écrire

L02 avait conclu que la couche live **n'est pas un problème de perception ici,
mais un problème de représentation**. Les étapes portent donc cette distinction :

- **percevoir** — produire une mesure à partir du monde : capter, détecter la
  parole, séparer les locuteurs, identifier une langue, transcrire ;
- **représenter** — structurer ce que quelqu'un d'autre a mesuré.

Sur cette machine, **aucune étape de perception ne fonctionne** et **toutes les
étapes de représentation fonctionnent**. Ce n'est pas une demi-victoire à
présenter comme un succès : c'est exactement ce que le programme pouvait
livrer, et le verdict le dit dans ces termes.

## Trois états, et le troisième est celui qui compte

- `READY` — le module existe et tout ce qu'il lui faut est disponible **ici**.
- `BLOCKED` — le module existe et quelque chose d'extérieur manque. Ce qui
  manque est nommé, donc le rapport sert aussi de liste d'installation.
- `ABSENT` — **rien ne l'implémente**, et aucune installation n'y changera
  rien. Le ranger sous `BLOCKED` enverrait un opérateur chercher un paquet qui
  n'a jamais été le problème.

La diarisation est le cas qui mérite d'être lu deux fois : installer `pyannote`
fournirait la capacité et **laisserait toujours rien pour l'appeler**.
`speakers.py` représente des locuteurs, il n'en produit pas.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .capture import module_present, probe
from .state import MESURE

#: Les trois états d'une étape. `ABSENT` n'est pas `BLOCKED` : le premier ne
#: s'installe pas.
PRET = "READY"
BLOQUE = "BLOCKED"
ABSENT = "ABSENT"
ETATS = (PRET, BLOQUE, ABSENT)

#: Les deux natures d'étape, mesurées par L02 avant d'être écrites ici.
PERCEVOIR = "PERCEIVE"
REPRESENTER = "REPRESENT"

#: La racine du dépôt, pour vérifier qu'un module cité existe vraiment.
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class Stage:
    """
    Une étape de la chaîne live.

    Attributes:
        name: Son nom.
        nature: `PERCEIVE` ou `REPRESENT`.
        module: Le fichier qui la porte, relatif à la racine du dépôt. Vide
            quand rien ne l'implémente.
        requires_inputs: Les entrées de §7 nécessaires, sondées.
        requires_modules: Les modules Python externes nécessaires.
        absent_reason: Pourquoi rien ne l'implémente, le cas échéant.
    """

    name: str
    nature: str
    module: str = ""
    requires_inputs: Tuple[str, ...] = ()
    requires_modules: Tuple[str, ...] = ()
    absent_reason: str = ""


#: Les étapes de la chaîne §8, prolongée par ce que le programme a écrit.
ETAPES: Tuple[Stage, ...] = (
    Stage("CAPTURE", PERCEVOIR, "", ("microphone",), (),
          "Aucun module de ce dépôt ne capte quoi que ce soit. "
          "`capture.py` déclare ce qui serait captable et rapporte ce qui ne "
          "l'est pas ; `LiveCaptureProvider` est une déclaration dont aucune "
          "implémentation n'existe. Aucun périphérique n'existe ici non plus, "
          "mais c'est le second problème, pas le premier."),
    Stage("VOICE_ACTIVITY_DETECTION", PERCEVOIR, "", (), (),
          "Rien ne détecte l'activité vocale dans ce dépôt, et aucune "
          "installation ne créera le module qui l'appellerait."),
    Stage("SPEAKER_SEGMENTATION", PERCEVOIR, "", (), (),
          "Rien ne segmente par locuteur. `speakers.py` représente des "
          "locuteurs ; il n'en produit pas."),
    Stage("DIARIZATION", PERCEVOIR, "", (), (),
          "Installer `pyannote` fournirait la capacité et laisserait toujours "
          "rien pour l'appeler. C'est pourquoi l'étape est ABSENT et non "
          "BLOCKED : un opérateur qui installe ne débloque rien."),
    Stage("LANGUAGE_IDENTIFICATION", PERCEVOIR, "", (), (),
          "Rien n'identifie la langue **d'un signal audio**. "
          "`acquisition/language.py` identifie celle d'un document, ce qui ne "
          "s'applique pas à de la parole."),
    Stage("TRANSCRIPTION", PERCEVOIR, "src/multimodal/whisper_provider.py",
          (), ("faster_whisper",)),
    Stage("SCREEN_READING", PERCEVOIR, "src/tools/screen/tool.py",
          ("screen",), ()),
    Stage("SPEAKER_REPRESENTATION", REPRESENTER,
          "src/live_context/speakers.py"),
    Stage("LANGUAGE_REPRESENTATION", REPRESENTER,
          "src/live_context/languages.py"),
    Stage("SCREEN_REPRESENTATION", REPRESENTER, "src/live_context/screen.py"),
    Stage("CONTEXT_FUSION", REPRESENTER, "src/live_context/fusion.py"),
    Stage("SEMANTIC_UNDERSTANDING", REPRESENTER,
          "src/knowledge_engine/citations.py"),
    Stage("ASSISTANCE", REPRESENTER, "src/live_context/assistance.py"),
    Stage("TOOL_INTENT", REPRESENTER, "src/live_context/intent.py"),
    Stage("MEMORY_WRITE", REPRESENTER, "src/live_context/memory.py"),
    Stage("CREATIVE_LINK", REPRESENTER, "src/live_context/creative.py"),
)

#: Les domaines couverts par les tests du volet, et les fichiers qui les
#: couvrent. La présence de chaque fichier est **vérifiée** : citer un fichier
#: de tests qui n'existe pas est la façon la plus simple de publier une
#: couverture fausse.
COUVERTURE: Dict[str, Tuple[str, ...]] = {
    "observation_state": ("tests/live_context/test_live_state.py",),
    "capture_surface": ("tests/live_context/test_live_capture.py",),
    "fusion": ("tests/live_context/test_live_fusion.py",
               "tests/live_context/test_live_coverage.py"),
    "speakers": ("tests/live_context/test_live_speakers.py",),
    "languages": ("tests/live_context/test_live_languages.py",),
    "assistance": ("tests/live_context/test_live_assistance.py",),
    "tool_intent": ("tests/live_context/test_live_intent.py",),
    "screen": ("tests/live_context/test_live_screen.py",),
    "privacy_retention": ("tests/live_context/test_live_retention.py",),
    "creative_link": ("tests/live_context/test_live_creative.py",),
    "providers": ("tests/live_context/test_live_providers.py",),
}


def _module_existe(chemin: str) -> bool:
    """Dit si un fichier cité existe vraiment dans le dépôt."""
    return bool(chemin) and os.path.isfile(
        os.path.join(os.path.dirname(RACINE), chemin))


def stage_state(stage: Stage) -> Dict[str, Any]:
    """
    L'état d'une étape, mesuré.

    Args:
        stage: L'étape examinée.

    Returns:
        Son état, ce qui lui manque, et le module vérifié sur le disque.

    Note:
        Un module déclaré et introuvable est `ABSENT`, pas `READY` : ce serait
        exactement la façon de publier une chaîne qui n'existe pas.
    """
    manques: List[Dict[str, str]] = []

    if not stage.module:
        return {"stage": stage.name, "nature": stage.nature, "module": None,
                "state": ABSENT, "missing": [],
                "reason": stage.absent_reason}

    if not _module_existe(stage.module):
        return {"stage": stage.name, "nature": stage.nature,
                "module": stage.module, "state": ABSENT, "missing": [],
                "reason": (f"Le module « {stage.module} » est déclaré et "
                           "introuvable sur le disque.")}

    for nom in stage.requires_modules:
        if not module_present(nom):
            manques.append({"kind": "python_module", "name": nom,
                            "reason": f"module « {nom} » non importable ici"})

    for entree in stage.requires_inputs:
        observation = probe(entree)
        if observation.status != MESURE:
            manques.append({"kind": "input", "name": entree,
                            "reason": observation.detail})

    return {
        "stage": stage.name, "nature": stage.nature, "module": stage.module,
        "state": BLOQUE if manques else PRET,
        "missing": manques,
        "reason": "" if manques else "le module existe et rien ne lui manque",
    }


def coverage_map() -> Dict[str, Any]:
    """
    Les domaines couverts par des fichiers de tests **qui existent**.

    Returns:
        Par domaine, les fichiers cités et ceux réellement trouvés.
    """
    domaines: Dict[str, Any] = {}
    for domaine, fichiers in COUVERTURE.items():
        trouves = [f for f in fichiers if _module_existe(f)]
        domaines[domaine] = {
            "declared": list(fichiers),
            "found": trouves,
            "covered": len(trouves) == len(fichiers),
        }
    return {
        "domains": domaines,
        "covered_count": sum(1 for d in domaines.values() if d["covered"]),
        "declared_count": len(COUVERTURE),
    }


def readiness() -> Dict[str, Any]:
    """
    L'état de la chaîne live, sur toutes ses étapes.

    Returns:
        Chaque étape avec son état mesuré, la répartition par nature, la
        couverture de tests, et un état d'ensemble **dérivé**.
    """
    etapes = [stage_state(etape) for etape in ETAPES]
    par_etat: Dict[str, List[str]] = {PRET: [], BLOQUE: [], ABSENT: []}
    for entree in etapes:
        par_etat[entree["state"]].append(entree["stage"])

    par_nature: Dict[str, Dict[str, int]] = {}
    for nature in (PERCEVOIR, REPRESENTER):
        concernees = [e for e in etapes if e["nature"] == nature]
        par_nature[nature] = {
            etat: sum(1 for e in concernees if e["state"] == etat)
            for etat in ETATS
        }

    manquants = sorted({
        f"{detail['kind']}:{detail['name']}"
        for entree in etapes for detail in entree["missing"]
    })

    return {
        "stages": etapes,
        "by_state": par_etat,
        "counts": {etat: len(noms) for etat, noms in par_etat.items()},
        "by_nature": par_nature,
        "missing": manquants,
        "test_coverage": coverage_map(),
        "state": _verdict(par_etat, par_nature),
        "note": ("L'état d'ensemble est **calculé** sur les étapes mesurées. "
                 "`ABSENT` et `BLOCKED` sont séparés parce qu'ils ne se "
                 "corrigent pas de la même façon : le second s'installe, le "
                 "premier s'écrit."),
    }


def _verdict(par_etat: Dict[str, List[str]],
             par_nature: Dict[str, Dict[str, int]]) -> str:
    """
    L'état d'ensemble, déduit de ce qui a été mesuré.

    Il nomme séparément les deux moitiés de la chaîne, parce qu'une moyenne
    entre « tout représenter » et « ne rien percevoir » ne dirait rien de vrai
    sur ni l'une ni l'autre.
    """
    perception_pretes = par_nature[PERCEVOIR][PRET]
    representation_bloquees = (par_nature[REPRESENTER][BLOQUE]
                               + par_nature[REPRESENTER][ABSENT])

    if representation_bloquees:
        return (f"REPRESENTATION INCOMPLETE — {representation_bloquees} "
                "STAGE(S) NOT RUNNABLE HERE")
    if perception_pretes:
        return (f"REPRESENTATION READY — {perception_pretes} PERCEPTION "
                f"STAGE(S) RUNNABLE, {len(par_etat[ABSENT])} NOT IMPLEMENTED")
    return (f"REPRESENTATION READY — NO LIVE PERCEPTION ON THIS MACHINE, "
            f"{len(par_etat[ABSENT])} STAGE(S) NOT IMPLEMENTED, "
            f"{len(par_etat[BLOQUE])} BLOCKED")


def readiness_report() -> Dict[str, Any]:
    """
    Ce que l'état de préparation garantit, et ce qu'il refuse.

    Returns:
        Les états, les étapes déclarées, la mesure, et les règles tenues.
    """
    return {
        "states": list(ETATS),
        "natures": [PERCEVOIR, REPRESENTER],
        "declared_stages": [e.name for e in ETAPES],
        "measured": readiness(),
        "verdict_is_written": False,
        "rules": [
            "L'état d'ensemble est calculé, jamais écrit : un verdict constant "
            "dit la même chose le jour où ça marche et le jour où ça ne marche "
            "pas.",
            "Un module cité est vérifié sur le disque : en citer un qui "
            "n'existe pas publierait une chaîne qui n'existe pas.",
            "ABSENT n'est pas BLOCKED : le second s'installe, le premier "
            "s'écrit.",
            "Percevoir et représenter sont comptés séparément : une moyenne "
            "entre « tout représenter » et « ne rien percevoir » ne dirait "
            "rien de vrai sur ni l'une ni l'autre.",
            "Un fichier de tests cité est vérifié : c'est la façon la plus "
            "simple de publier une couverture fausse.",
        ],
    }
