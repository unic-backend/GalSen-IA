"""
The sixteen media tools, what each one needs before it can run, and what
chaining them actually requires.

Directive §24 lists the tools and ends on the sentence that carries the work:
*the main AI should be able to chain these tools.* Chaining is where an agentic
media pipeline fails, and it fails quietly. A model asked to make a video will
call `render_video` before `create_edit_plan` — the call is well-formed, the
arguments are plausible, and what comes back is a file nobody planned. The error
surfaces three steps later as "the render does not match the brief".

So every tool declares what it **consumes** and what it **produces**, and
`plan_chain()` walks a proposed sequence refusing the first tool whose input
nothing has produced — naming which tool would have produced it. That check is
deterministic and costs nothing, which is exactly §1's argument: the model
decides *what* to make, the catalogue decides whether the order is possible.

Two declarations rather than one tool, because they are not the same act:

- `media` reads someone's footage and writes files **on this machine**. It is
  the precedent `memory` already set — user-private, local, unattended.
- `media_generation` sends that footage to a generation provider, which takes
  it **off** the machine. Private data plus an external effect is the
  exfiltration shape `src/tool/capabilities.py` refuses to let run unattended,
  and it is right to: nobody uploads a client's rushes by accident twice.

A tool whose capability is missing here reports `NOT_CONFIGURED` and names what
is absent. It never returns a plausible result — a fabricated duration or an
invented transcript is worse than an error, because an error stops the chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ...integration.degradation import DISPONIBLE
from ..core.capabilities import probe

#: L'outil local : il lit des médias et écrit des fichiers sur cette machine.
OUTIL_LOCAL = "media"

#: L'outil génératif : il fait **sortir** la donnée de la machine.
OUTIL_GENERATIF = "media_generation"


class ToolCatalogError(ValueError):
    """Un outil média inconnu, ou un enchaînement impossible."""


@dataclass(frozen=True)
class MediaToolSpec:
    """
    Un outil média déclaré : ce qu'il fait, ce qu'il exige, ce qu'il rend.

    Attributes:
        name: Le nom appelé par l'agent (§24).
        tool_id: L'outil enregistré qui le porte — `media` ou
            `media_generation`.
        summary: Ce qu'il fait, en une ligne.
        requires: Les capacités média nécessaires, telles que déclarées dans
            `src/media/core/capabilities.py`.
        consumes: Ce qui doit **déjà exister** pour l'appeler.
        produces: Ce qu'il rend disponible pour la suite.
        writes: S'il écrit un fichier.
        external: S'il fait sortir la donnée de la machine.
        module: Où vit l'implémentation — pour qu'un appelant la lise plutôt
            que d'en écrire une deuxième.
    """

    name: str
    tool_id: str
    summary: str
    requires: Tuple[str, ...] = ()
    consumes: Tuple[str, ...] = ()
    produces: Tuple[str, ...] = ()
    writes: bool = False
    external: bool = False
    module: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, pour l'API et les rapports."""
        return {
            "name": self.name, "tool_id": self.tool_id,
            "summary": self.summary, "requires": list(self.requires),
            "consumes": list(self.consumes), "produces": list(self.produces),
            "writes": self.writes, "external": self.external,
            "module": self.module,
        }


#: Les seize outils de la directive §24, dans l'ordre où elle les nomme.
#:
#: `consumes` / `produces` sont ce qui rend l'enchaînement vérifiable : un plan
#: de montage consomme une transcription **mesurée**, ce qui interdit
#: structurellement à un modèle de placer des points de coupe avant qu'on ait
#: mesuré où sont les mots (§5).
CATALOGUE: Tuple[MediaToolSpec, ...] = (
    MediaToolSpec(
        name="create_video_project", tool_id=OUTIL_LOCAL,
        summary="Ouvre une production versionnée avec son manifeste.",
        produces=("project",), module="src/media/core/project.py",
    ),
    MediaToolSpec(
        name="analyze_media", tool_id=OUTIL_LOCAL,
        summary="Mesure durée, FPS, codec et pistes d'un fichier.",
        requires=("media_probe",), consumes=("media",),
        produces=("media_info",), module="src/media/ingestion/inspect.py",
    ),
    MediaToolSpec(
        name="transcribe_media", tool_id=OUTIL_LOCAL,
        summary="Parole en texte avec les temps par mot.",
        requires=("transcription",), consumes=("media",),
        produces=("transcript",), module="src/media/transcription/words.py",
    ),
    MediaToolSpec(
        name="detect_scenes", tool_id=OUTIL_LOCAL,
        summary="Trouve les changements de plan par distance d'histogramme.",
        requires=("video_decode",), consumes=("media",),
        produces=("scenes",), module="src/media/analysis/scenes.py",
    ),
    MediaToolSpec(
        name="create_storyboard", tool_id=OUTIL_LOCAL,
        summary="Planifie les scènes selon la structure du domaine.",
        consumes=("project",), produces=("storyboard",),
        module="src/media/story/planner.py",
    ),
    MediaToolSpec(
        name="create_edit_plan", tool_id=OUTIL_LOCAL,
        summary="Place les coupes sur des frontières de mots mesurées.",
        consumes=("transcript",), produces=("edit_plan",),
        module="src/media/timeline/edit_plan.py",
    ),
    MediaToolSpec(
        name="generate_visual", tool_id=OUTIL_GENERATIF,
        summary="Produit une image par un fournisseur génératif.",
        requires=("gpu_compute",), consumes=("storyboard",),
        produces=("visual",), external=True, writes=True,
        module="src/media/providers/base.py",
    ),
    MediaToolSpec(
        name="generate_video", tool_id=OUTIL_GENERATIF,
        summary="Produit un plan vidéo par un fournisseur génératif.",
        requires=("gpu_compute",), consumes=("storyboard",),
        produces=("clip",), external=True, writes=True,
        module="src/media/providers/base.py",
    ),
    MediaToolSpec(
        name="create_motion_graphic", tool_id=OUTIL_LOCAL,
        summary="Rend une scène de motion design en trames déterministes.",
        requires=("frame_encode",), consumes=("storyboard",),
        produces=("frames", "render"), writes=True,
        module="src/media/motion/render.py",
    ),
    MediaToolSpec(
        name="generate_subtitles", tool_id=OUTIL_LOCAL,
        summary="Découpe des sous-titres sur des mots mesurés.",
        consumes=("transcript",), produces=("cues",),
        module="src/media/subtitles/cues.py",
    ),
    MediaToolSpec(
        name="select_music", tool_id=OUTIL_LOCAL,
        summary="Aligne une musique dont les droits sont établis.",
        consumes=("scenes",), produces=("music",),
        module="src/media/audio/music.py",
    ),
    MediaToolSpec(
        name="select_sfx", tool_id=OUTIL_LOCAL,
        summary="Pose des sons sur des événements réels de la timeline.",
        consumes=("scenes",), produces=("sfx",),
        module="src/media/audio/sound_design.py",
    ),
    MediaToolSpec(
        name="render_video", tool_id=OUTIL_LOCAL,
        summary="Encode le master à partir du plan de montage.",
        requires=("video_encode",), consumes=("edit_plan",),
        produces=("render",), writes=True,
        module="src/media/motion/render.py",
    ),
    MediaToolSpec(
        name="inspect_video", tool_id=OUTIL_LOCAL,
        summary="Contrôle le rendu ; un contrôle impossible reste NOT_CHECKED.",
        requires=("media_probe",), consumes=("render",),
        produces=("inspection",), module="src/media/qc/checks.py",
    ),
    MediaToolSpec(
        name="repair_video", tool_id=OUTIL_LOCAL,
        summary="Corrige un défaut constaté, jamais un défaut supposé.",
        requires=("video_encode",), consumes=("inspection",),
        produces=("render",), writes=True,
        module="src/media/qc/checks.py",
    ),
    MediaToolSpec(
        name="export_video", tool_id=OUTIL_LOCAL,
        summary="Écrit la version de diffusion et son manifeste.",
        requires=("video_encode",), consumes=("render", "inspection"),
        produces=("export",), writes=True,
        module="src/media/core/project.py",
    ),
)

#: Index par nom, pour ne pas parcourir le catalogue à chaque appel.
PAR_NOM: Dict[str, MediaToolSpec] = {spec.name: spec for spec in CATALOGUE}


def spec_for(name: str) -> MediaToolSpec:
    """
    La déclaration d'un outil média.

    Raises:
        ToolCatalogError: Pour un nom inconnu. Approcher le nom demandé du plus
            proche voisin ferait exécuter un outil que personne n'a appelé.
    """
    if name not in PAR_NOM:
        raise ToolCatalogError(
            f"Outil média « {name} » inconnu. Déclarés : {sorted(PAR_NOM)}."
        )
    return PAR_NOM[name]


def availability(name: str) -> Dict[str, Any]:
    """
    Ce qui manque à un outil pour s'exécuter **ici**.

    Args:
        name: Le nom de l'outil.

    Returns:
        Son état — `AVAILABLE` quand toutes ses capacités le sont, sinon
        `NOT_CONFIGURED` avec les capacités manquantes et ce que leur absence
        empêche. L'état est **mesuré** par les sondes, jamais déduit de la
        présence d'un binaire.
    """
    spec = spec_for(name)
    manquantes = []
    for capacite in spec.requires:
        resultat = probe(capacite)
        if resultat["state"] != DISPONIBLE:
            manquantes.append({
                "capability": capacite, "state": resultat["state"],
                "reason": resultat["reason"],
                "without_it": resultat["without_it"],
            })

    return {
        "tool": name,
        "status": "AVAILABLE" if not manquantes else "NOT_CONFIGURED",
        "missing": manquantes,
        "requires": list(spec.requires),
        "note": (
            "Prêt : toutes ses capacités sont mesurées disponibles."
            if not manquantes else
            "Indisponible ici. L'appel rend cet état — jamais un résultat "
            "plausible : une durée par défaut ou une transcription inventée "
            "laisserait la chaîne continuer sur une donnée fausse."
        ),
    }


def runnable_now() -> Dict[str, Any]:
    """
    Les outils exécutables sur cette machine, et ceux qui attendent quelque chose.

    Returns:
        Les deux listes et, pour les seconds, les capacités à installer.
    """
    prets, bloques = [], {}
    for spec in CATALOGUE:
        etat = availability(spec.name)
        if etat["status"] == "AVAILABLE":
            prets.append(spec.name)
        else:
            bloques[spec.name] = [m["capability"] for m in etat["missing"]]
    return {
        "runnable": prets,
        "not_configured": bloques,
        "count": len(CATALOGUE),
        "note": (
            "Un outil bloqué est bloqué par une **capacité nommée**. Le rapport "
            "sert à savoir quoi installer, pas à masquer ce qui manque."
        ),
    }


def producers_of(artifact: str) -> List[str]:
    """Les outils qui produisent cette entrée."""
    return [spec.name for spec in CATALOGUE if artifact in spec.produces]


def plan_chain(
    names: Sequence[str], available: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Vérifie qu'un enchaînement d'outils est **possible dans cet ordre**.

    Args:
        names: Les outils à enchaîner, dans l'ordre proposé.
        available: Ce qui existe déjà — typiquement `("media",)` quand
            l'utilisateur a fourni un fichier.

    Returns:
        L'enchaînement accepté, ou le premier maillon impossible avec ce qui
        lui manque et l'outil qui l'aurait produit.

        C'est le contrôle que §24 rend nécessaire : un modèle à qui l'on demande
        une vidéo appellera `render_video` avant `create_edit_plan`. L'appel est
        bien formé, ses arguments sont plausibles, et ce qui revient est un
        fichier que personne n'a planifié. Ici l'ordre est refusé **avant**
        d'encoder quoi que ce soit.

    Raises:
        ToolCatalogError: Pour un outil inconnu dans la séquence.
    """
    disponibles = set(available or ())
    etapes: List[Dict[str, Any]] = []

    for rang, nom in enumerate(names, start=1):
        spec = spec_for(nom)
        manquants = [entree for entree in spec.consumes
                     if entree not in disponibles]
        if manquants:
            return {
                "ordered": False,
                "steps": etapes,
                "failed_at": {
                    "position": rang, "tool": nom,
                    "missing_inputs": manquants,
                    "produced_by": {
                        entree: producers_of(entree) for entree in manquants
                    },
                    "reason": (
                        f"« {nom} » consomme {manquants}, que rien n'a encore "
                        "produit. L'appel serait bien formé et son résultat "
                        "n'aurait aucun rapport avec la demande."
                    ),
                },
                "available_after": sorted(disponibles),
            }
        disponibles.update(spec.produces)
        etapes.append({
            "position": rang, "tool": nom,
            "produces": list(spec.produces),
            "availability": availability(nom)["status"],
        })

    return {
        "ordered": True,
        "steps": etapes,
        "available_after": sorted(disponibles),
        "blocked": [etape["tool"] for etape in etapes
                    if etape["availability"] != "AVAILABLE"],
        "note": (
            "L'ordre est possible. Les outils listés dans `blocked` le sont "
            "par une capacité absente, pas par l'ordre."
        ),
    }


def catalog_report() -> Dict[str, Any]:
    """
    Ce que le catalogue déclare, et ce qu'il refuse.

    Returns:
        Les outils, leur répartition entre les deux déclarations, et les règles.
    """
    return {
        "tools": [spec.as_dict() for spec in CATALOGUE],
        "count": len(CATALOGUE),
        "by_tool_id": {
            OUTIL_LOCAL: [s.name for s in CATALOGUE if s.tool_id == OUTIL_LOCAL],
            OUTIL_GENERATIF: [s.name for s in CATALOGUE
                              if s.tool_id == OUTIL_GENERATIF],
        },
        "rules": [
            "Chaque outil déclare ce qu'il **consomme** et ce qu'il produit : "
            "un enchaînement impossible est refusé avant d'encoder quoi que "
            "ce soit, pas trois étapes plus tard.",
            "Un plan de montage consomme une transcription **mesurée** — un "
            "modèle ne peut donc pas placer une coupe avant qu'on ait mesuré "
            "où sont les mots (§5).",
            "Une capacité absente rend `NOT_CONFIGURED` en la nommant, jamais "
            "un résultat plausible.",
            "La génération est une **déclaration séparée** : elle fait sortir "
            "la donnée de la machine, et donnée privée plus effet externe ne "
            "tourne pas sans humain.",
        ],
        "does_not": [
            "Deviner l'outil le plus proche d'un nom inconnu.",
            "Exécuter un outil dont l'entrée n'existe pas.",
            "Rendre une durée par défaut quand la mesure est impossible.",
            "Envoyer un média à un fournisseur externe sans approbation.",
        ],
    }
