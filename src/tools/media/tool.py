"""
The media engine as a tool the agent system can call and chain (§24).

Two tools are registered rather than one, and the split is not cosmetic:
`media` works on this machine, `media_generation` sends the material off it.
`src/tool/capabilities.py` already refuses to run user-private data plus an
external effect unattended, and that refusal is the whole point — nobody
uploads a client's rushes by accident twice.

Every operation goes through three gates before any work happens:

1. **The name exists.** An unknown operation is refused with the list; nothing
   is matched approximately, because an approximate match runs a tool nobody
   called.
2. **The capability is measured.** A missing capability returns
   `NOT_CONFIGURED` naming what is absent — never a plausible result.
3. **The engine's own refusal is preserved.** When a module refuses (no
   measured word timings, unknown music rights, a quote that appears twice),
   the reason it gives is returned **verbatim**. Rewriting it into "operation
   failed" throws away the only part a caller can act on.

Nothing here reimplements the engine. Each operation is a call into the module
that already does the work, and the module path is declared in the catalogue so
a reader finds it without searching.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.media.tools.catalog import (
    CATALOGUE,
    OUTIL_GENERATIF,
    OUTIL_LOCAL,
    ToolCatalogError,
    availability,
    catalog_report,
    plan_chain,
    runnable_now,
    spec_for,
)
from src.tool.base import BaseTool

logger = logging.getLogger(__name__)

#: Les opérations qui ne consomment aucune capacité média : elles servent à
#: savoir ce qui est possible **avant** d'essayer.
OPERATIONS_DE_SERVICE = frozenset({
    "catalog", "availability", "runnable", "plan_chain",
})

#: Les refus **déclarés** du moteur. Ce sont des décisions, pas des pannes :
#: leur message porte la raison, et c'est la seule chose sur laquelle un
#: appelant peut agir.
REFUS_DECLARES = (ValueError, RuntimeError)


def _refus(nom: str, erreur: Exception) -> Dict[str, Any]:
    """Le refus d'un module, rendu tel quel."""
    return {
        "status": "REFUSED",
        "tool": nom,
        "error": type(erreur).__name__,
        "reason": str(erreur),
        "note": (
            "Refus du moteur, rendu **mot pour mot**. Le réécrire en « échec » "
            "jetterait la seule information exploitable."
        ),
    }


class MediaTool(BaseTool):
    """
    Les seize outils média de la directive §24, derrière une seule entrée.

    Opérations : les noms du catalogue, plus `catalog`, `availability`,
    `plan_chain` et `runnable`, qui permettent à un agent de savoir ce qu'il
    peut enchaîner **avant** d'essayer.

    Exemple:
        tool.execute("plan_chain", ["analyze_media", "create_edit_plan"],
                     available=["media"])
    """

    def __init__(self, config: dict = None) -> None:
        """
        Initialise l'outil média.

        Args:
            config: Configuration optionnelle. `tool_id` restreint les
                opérations à l'une des deux déclarations (`media` ou
                `media_generation`) : c'est ainsi que le plafond du registre
                s'applique réellement, au lieu d'être un commentaire.
        """
        super().__init__(config)
        self.tool_id = (self.config or {}).get("tool_id", OUTIL_LOCAL)

    def available_operations(self) -> List[str]:
        """
        Les opérations de **cette** déclaration, plus les opérations de service.

        Un outil local ne liste pas les opérations génératives : une liste qui
        les annonce ferait proposer par un agent un appel que le registre
        refusera de toute façon.
        """
        portees = {spec.name for spec in CATALOGUE
                   if spec.tool_id == self.tool_id}
        return sorted(
            nom for nom in super().available_operations()
            if nom in portees | OPERATIONS_DE_SERVICE
        )

    # ------------------------------------------------------------------
    # Ce qu'un agent demande avant d'agir
    # ------------------------------------------------------------------

    def _op_catalog(self, **kwargs: Any) -> Dict[str, Any]:
        """Le catalogue déclaré, avec ce que chaque outil consomme et produit."""
        return catalog_report()

    def _op_availability(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Ce qui manque à un outil pour s'exécuter ici.

        Args:
            name: Le nom de l'outil média.
        """
        return availability(name)

    def _op_runnable(self, **kwargs: Any) -> Dict[str, Any]:
        """Les outils exécutables sur cette machine, et ce qui bloque les autres."""
        return runnable_now()

    def _op_plan_chain(
        self, names: List[str], available: List[str] = None, **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Vérifie qu'un enchaînement est possible **avant** de l'exécuter.

        Args:
            names: Les outils, dans l'ordre proposé.
            available: Ce qui existe déjà, par exemple `["media"]`.
        """
        return plan_chain(names, available)

    # ------------------------------------------------------------------
    # Les seize outils
    # ------------------------------------------------------------------

    def _op_create_video_project(
        self, objective: str, created_by: str = "", **kwargs: Any,
    ) -> Dict[str, Any]:
        """Ouvre une production versionnée."""
        from src.media.core.project import MediaProject

        projet = MediaProject(objective=objective, created_by=created_by)
        return {"status": "OK", "project_id": projet.project_id,
                "objective": projet.objective}

    def _op_analyze_media(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        """Mesure ce qu'un fichier porte réellement."""
        from src.media.ingestion.inspect import inspect_media

        return {"status": "OK", "info": inspect_media(path).as_dict()}

    def _op_transcribe_media(
        self, path: str, language: str = None, **kwargs: Any,
    ) -> Dict[str, Any]:
        """Parole en texte, par `src/multimodal/` — jamais réimplémentée ici."""
        from src.media.transcription.words import transcribe_media

        return {"status": "OK", "transcript": transcribe_media(path, language)}

    def _op_detect_scenes(
        self, frame_paths: List[str], fps: float = None, **kwargs: Any,
    ) -> Dict[str, Any]:
        """Trouve les changements de plan sur des trames réellement lues."""
        from src.media.analysis.scenes import detect_cuts, load_frames

        trames = load_frames(frame_paths)
        return {"status": "OK", "scenes": detect_cuts(trames, fps=fps)}

    def _op_create_storyboard(
        self, assignment: Dict[str, Any], **kwargs: Any,
    ) -> Dict[str, Any]:
        """Planifie les scènes à partir de rôles narratifs remplis."""
        from src.media.story.planner import plan_scenes

        return {"status": "OK", "storyboard": plan_scenes(assignment, **kwargs)}

    def _op_create_edit_plan(
        self, selections: List[Any], words: List[Any], **kwargs: Any,
    ) -> Dict[str, Any]:
        """Résout des sélections en segments, sur des temps **mesurés**."""
        from src.media.timeline.edit_plan import build_plan

        return {"status": "OK", "plan": build_plan(selections, words, **kwargs)}

    def _op_generate_visual(
        self, request: Any = None, **kwargs: Any,
    ) -> Dict[str, Any]:
        """Choisit un fournisseur d'image, ou dit pourquoi aucun ne convient."""
        from src.media.providers.base import select_provider

        return {"status": "OK", "selection": select_provider(request, **kwargs)}

    def _op_generate_video(
        self, request: Any = None, **kwargs: Any,
    ) -> Dict[str, Any]:
        """Choisit un fournisseur vidéo, ou dit pourquoi aucun ne convient."""
        from src.media.providers.base import select_provider

        return {"status": "OK", "selection": select_provider(request, **kwargs)}

    def _op_create_motion_graphic(
        self, scene: Any, output_path: str, **kwargs: Any,
    ) -> Dict[str, Any]:
        """Rend une scène de motion design en vidéo réelle."""
        from src.media.motion.render import render_video

        return {"status": "OK", "rendered": render_video(
            scene, output_path, **kwargs)}

    def _op_generate_subtitles(
        self, words: List[Any], language: str = "fr", **kwargs: Any,
    ) -> Dict[str, Any]:
        """Découpe des sous-titres sur des mots mesurés."""
        from src.media.subtitles.cues import build_cues

        return {"status": "OK", "subtitles": build_cues(
            words, language=language, **kwargs)}

    def _op_select_music(
        self, track: Any, scene_starts: List[float] = None, **kwargs: Any,
    ) -> Dict[str, Any]:
        """Aligne une musique dont les droits sont établis."""
        from src.media.audio.music import sync_to_scenes

        return {"status": "OK", "music": sync_to_scenes(
            track, scene_starts or [], **kwargs)}

    def _op_select_sfx(
        self, events: List[Any], **kwargs: Any,
    ) -> Dict[str, Any]:
        """Pose des sons sur des événements réels de la timeline."""
        from src.media.audio.sound_design import place_sounds

        return {"status": "OK", "sfx": place_sounds(events, **kwargs)}

    def _op_render_video(
        self, scene: Any, output_path: str, **kwargs: Any,
    ) -> Dict[str, Any]:
        """Encode le master. Un encodage réussi n'est pas une production réussie."""
        from src.media.motion.render import render_video

        rendu = render_video(scene, output_path, **kwargs)
        return {"status": "OK", "rendered": rendu,
                "note": "Encodage écrit. Le verdict de production vient de "
                        "`inspect_video` (§21)."}

    def _op_inspect_video(
        self, path: str, expected_format: str = "", **kwargs: Any,
    ) -> Dict[str, Any]:
        """Contrôle le rendu ; un contrôle impossible reste `NOT_CHECKED`."""
        from src.media.qc.checks import check_file, verdict

        controles = check_file(path, expected_format)
        return {"status": "OK", "checks": controles,
                "verdict": verdict(controles)}

    def _op_repair_video(
        self, inspection: Dict[str, Any], **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Nomme les défauts **constatés** à corriger.

        La règle vit dans `src/media/qc/checks.py`, à côté des trois issues
        qu'elle départage, et la réparation elle-même passe par le harnais
        existant (`src/agent/`, §26) : ni l'une ni l'autre n'est réécrite ici.
        """
        from src.media.qc.checks import repairable

        resultat = repairable(inspection.get("checks") or [])
        return {
            **resultat,
            "harness": "src/agent/ — réutilisé tel quel (§26), jamais dupliqué.",
        }

    def _op_export_video(
        self, project: Any, path: str, produced_by: str = "", **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Déclare la version de diffusion sur la production.

        L'artefact porte son origine et son producteur : un export sans
        provenance complète est **rapporté incomplet**, jamais présenté comme
        libre de droits (§31).
        """
        from src.media.core.project import ORIGINE_GENEREE, Artifact

        version = project.current
        artefact = Artifact(
            artifact_id=f"{version.version_id}-export", kind="export",
            path=path, origin=ORIGINE_GENEREE, produced_by=produced_by,
        )
        return {
            "status": "OK", "artifact": artefact.as_dict(),
            "version": version.version_id,
            "provenance_complete": artefact.provenance_complete,
        }

    # ------------------------------------------------------------------
    # Répartition
    # ------------------------------------------------------------------

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """
        Exécute une opération média.

        Args:
            *args: L'opération, puis ses arguments.
            **kwargs: Options propres à l'opération.

        Returns:
            Le résultat, ou l'état de la capacité manquante. Un outil du
            catalogue est d'abord confronté aux **capacités mesurées** de la
            machine : `NOT_CONFIGURED` est rendu avant tout travail, parce
            qu'un résultat plausible laisserait la chaîne continuer sur une
            donnée fausse.

        Raises:
            ValueError: Opération inconnue, ou opération appartenant à l'autre
                déclaration — le plafond du registre s'applique ici, pas en
                commentaire.
        """
        if not args:
            raise ValueError(
                "Une opération est requise. Disponibles : "
                f"{', '.join(self.available_operations())}"
            )

        operation = str(args[0])
        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. Disponibles : "
                f"{', '.join(self.available_operations())}"
            )

        try:
            spec = spec_for(operation)
        except ToolCatalogError:
            # Opération de service (`catalog`, `availability`, `plan_chain`,
            # `runnable`) : elle ne consomme aucune capacité média.
            return handler(*args[1:], **kwargs)

        if spec.tool_id != self.tool_id:
            raise ValueError(
                f"« {operation} » appartient à la déclaration "
                f"« {spec.tool_id} », pas à « {self.tool_id} ». La génération "
                "fait sortir la donnée de la machine : elle a sa propre "
                "déclaration et sa propre approbation."
            )

        etat = availability(operation)
        if etat["status"] != "AVAILABLE":
            return etat

        try:
            return handler(*args[1:], **kwargs)
        except REFUS_DECLARES as erreur:
            logger.info("Outil média « %s » refusé : %s", operation, erreur)
            return _refus(operation, erreur)


class MediaGenerationTool(MediaTool):
    """
    Les outils média qui font **sortir** la donnée de la machine.

    Déclaration séparée parce que l'acte est différent : envoyer les rushes de
    quelqu'un à un fournisseur génératif est un chemin d'exfiltration, et le
    registre le soumet à une approbation humaine.
    """

    def __init__(self, config: dict = None) -> None:
        """Initialise l'outil génératif, borné à sa propre déclaration."""
        super().__init__({**(config or {}), "tool_id": OUTIL_GENERATIF})
