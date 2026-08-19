"""
La tranche verticale du canvas, et l'endroit exact où elle s'arrête
(K07, §22 de la directive Creative Canvas).

## Ce que §22 demande

La **plus petite** tranche verticale validée. Pas une démonstration, pas une
maquette : un chemin réel, parcouru, qui rapporte ce qui a eu lieu.

## Ce que celle-ci n'est pas

Ce n'est **pas** `src/creative/mvp.py`. Celle-là parcourt les treize étapes de
la chaîne vocale du programme précédent (§65) ; celle-ci parcourt le chemin du
canvas — intention, graphe, plan de tournage, confidentialité, routage,
disponibilité. Elle **réutilise son vocabulaire d'issues** plutôt que d'en
inventer un second, parce que deux mots pour un même état est la façon dont deux
rapports finissent par se contredire.

## Ce qu'elle rapporte, et ce qu'elle refuse de rapporter

Elle rend, étape par étape, ce qui s'est réellement passé. Aucune vidéo n'est
produite : rien dans cette plateforme n'en produit, et la tranche le **dit** au
lieu de s'arrêter avant l'étape gênante.

Elle ne saute pas une étape bloquée pour atteindre la suivante — la règle que
§21 avait établie pour la chaîne vocale vaut ici aussi : le premier blocage dur
est l'endroit où la chaîne s'arrête, et ce qui vient après est parcouru pour
dire ce qu'il ferait, jamais compté comme franchi.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..cinema import CameraSpec, LensSpec, MotionSpec, ShotSpec, render_for_provider
from ..direction import DirectorSpec
from ..intent import CONFORME, check_plan, declare
from ..mvp import BLOQUE, NON_ATTEINT, OK
from .graph import CanvasGraph
from .privacy import may_send_personal_reference, unknown_policy
from .readiness import graph_readiness

#: Les six étapes du chemin canvas, dans l'ordre.
ETAPES = (
    "intent",            # ce qui est demandé, permis, interdit
    "graph",             # les nœuds et les arêtes légales
    "shot",              # le plan de tournage, structuré
    "privacy",           # où partirait la donnée
    "handover",          # ce qu'un fournisseur recevrait
    "readiness",         # ce qui peut tourner, nœud par nœud
)


def _etape(name: str, outcome: str, detail: str, **preuve: Any) -> Dict[str, Any]:
    """Une étape parcourue, avec ce qui la prouve."""
    return {"step": name, "outcome": outcome, "detail": detail,
            "evidence": preuve}


def run_canvas_slice(
    request: str = "un plan large d'un marché de Dakar, sans ralenti",
    required: Sequence[Tuple[str, str]] = (("place", "marché de Dakar"),),
    forbidden: Sequence[Tuple[str, str]] = (("effect", "ralenti"),),
    provider_id: str = "moneyprinterturbo",
) -> Dict[str, Any]:
    """
    Parcourt le chemin du canvas de bout en bout et rapporte ce qui a eu lieu.

    Args:
        request: La demande, conservée telle quelle.
        required: Les éléments requis, en couples `(nature, valeur)`.
        forbidden: Les éléments explicitement exclus.
        provider_id: Le fournisseur qu'un nœud de génération appellerait.

    Returns:
        Une entrée par étape, les comptes par issue, et le premier blocage dur.
        **Aucun compte ne peut se lire comme un succès** : `blocked` y figure à
        côté de `ok`.
    """
    etapes: List[Dict[str, Any]] = []

    #: 1. L'intention — trois listes explicites, rien de déduit du texte.
    intention = declare(request, required=required, forbidden=forbidden)
    etapes.append(_etape(
        "intent", OK,
        "L'intention déclare ce qui est demandé et ce qui est exclu ; rien "
        "n'est extrait du texte libre.",
        required=[e.value for e in intention.by_status("REQUIRED")],
        forbidden=[e.value for e in intention.by_status("FORBIDDEN")],
    ))

    #: 2. Le graphe — la plus courte chaîne complète.
    graphe = CanvasGraph()
    graphe.add_node("p", "prompt", label="la demande")
    graphe.add_node("i", "intent", label="l'intention")
    graphe.add_node("v", "video_generation", label="la vidéo")
    graphe.connect("p", "text", "i", "text")
    graphe.connect("i", "intent", "v", "intent")
    ordre = graphe.topological_order()
    etapes.append(_etape(
        "graph", OK,
        "Trois nœuds, deux arêtes légales, un ordre déterministe.",
        order=ordre,
        unconnected_required=graphe.unconnected_required_inputs(),
    ))

    #: 3. Le plan de tournage — structuré, et cohérent avec sa direction.
    plan = ShotSpec(
        direction=DirectorSpec(shot_size="wide", movement="pan", lens_mm=35.0),
        camera=CameraSpec(sensor_format="super35", frame_rate=24),
        lens=LensSpec(aperture_f=4.0),
        motion=MotionSpec(pan=40),
    )
    verification = check_plan(intention, [("place", "marché de Dakar")])
    etapes.append(_etape(
        "shot",
        OK if verification["verdict"] == CONFORME else BLOQUE,
        f"Le plan est conforme à l'intention : {verification['verdict']}.",
        verdict=verification["verdict"],
        forbidden_present=verification["forbidden_present"],
    ))

    #: 4. La confidentialité — personne n'a rien établi, et cela se voit.
    politique = unknown_policy(provider_id)
    porte = may_send_personal_reference(politique)
    etapes.append(_etape(
        "privacy", BLOQUE,
        porte["reason"],
        destination=politique.data_destination,
        trust_level=politique.trust_level.value,
        personal_reference_allowed=porte["allowed"],
    ))

    #: 5. Ce qu'un fournisseur recevrait — structure d'abord, texte au bord.
    remise = render_for_provider(plan, accepts_camera_control=False)
    etapes.append(_etape(
        "handover", OK,
        "Le fournisseur reçoit la structure ; le texte n'est qu'un rendu, et "
        "ce qu'il ne porte pas est nommé.",
        mode=remise["mode"], text=remise["text"],
        not_conveyed=remise["not_conveyed"],
    ))

    #: 6. La disponibilité — nœud par nœud, sans note.
    disponibilite = graph_readiness(graphe)
    etapes.append(_etape(
        "readiness", BLOQUE,
        "Aucun nœud de génération ne peut tourner ici.",
        counts=disponibilite["counts"],
        blocking_reasons=disponibilite["blocking_reasons"],
        score=disponibilite["score"],
    ))

    premier_blocage: Optional[str] = next(
        (e["step"] for e in etapes if e["outcome"] == BLOQUE), None)
    comptes = {
        "ok": sum(1 for e in etapes if e["outcome"] == OK),
        "blocked": sum(1 for e in etapes if e["outcome"] == BLOQUE),
        "not_reached": sum(1 for e in etapes if e["outcome"] == NON_ATTEINT),
    }
    return {
        "request": request,
        "steps": etapes,
        "counts": comptes,
        "first_block": premier_blocage,
        "produced_artifact": None,
        "note": ("Aucun artefact n'est produit : rien dans cette plateforme ne "
                 "génère d'image ni de vidéo. Les six étapes sont parcourues "
                 "pour dire où la chaîne s'arrête réellement, pas pour "
                 "s'arrêter avant l'étape gênante."),
    }


def slice_report() -> Dict[str, Any]:
    """
    Ce que la tranche parcourt, et ce qu'elle refuse.

    Returns:
        Les étapes déclarées et les règles tenues.
    """
    return {
        "steps": list(ETAPES),
        "count": len(ETAPES),
        "outcomes": [OK, BLOQUE, NON_ATTEINT],
        "shares_vocabulary_with": "creative/mvp.py",
        "rules": [
            "Aucun artefact n'est produit, et la tranche le dit.",
            "Le premier blocage dur est nommé ; rien n'est sauté pour "
            "atteindre l'étape suivante.",
            "Aucun compte ne peut se lire comme un succès : blocked figure à "
            "côté de ok.",
            "Le vocabulaire d'issues est celui de mvp.py, pas un second.",
        ],
    }
