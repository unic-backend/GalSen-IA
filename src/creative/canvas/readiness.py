"""
L'état de chaque nœud — calculé, jamais écrit (K07, ADR-031 décision 5).

## La forme, et d'où elle vient

`src/media/readiness.py` parcourt dix-sept étapes de la chaîne de production et
répond ce qu'il a mesuré. Ce module fait la même chose pour un graphe, avec le
même vocabulaire, et pour la même raison : un verdict écrit à la main devient
faux au premier changement, et personne ne s'en aperçoit.

## Trois règles, chacune déjà tenue ailleurs

1. **Aucun booléen global.** Un graphe se rapporte nœud par nœud. « Le canvas
   n'est pas prêt » n'apprend rien à un opérateur ; « le nœud 3 attend `ffmpeg` »
   lui dit quoi installer.
2. **Aucune note.** `src/security/posture.py` refuse de se noter parce qu'une
   moyenne fait disparaître la faille qui compte derrière celles qui ne comptent
   pas. Une note de disponibilité la ferait disparaître pareil.
3. **Un nœud bloqué rapporte ; il ne rend jamais un résultat plausible.**

## Ce que cela donne aujourd'hui

**Tous les nœuds de génération sont `BLOCKED`.** Rien dans cette plateforme ne
produit une image ni une vidéo — K00 l'a remesuré : dix-sept étapes média, dix
`READY`, six `BLOCKED`, une `ABSENT`, et les deux adaptateurs refusent. Un canvas
qui afficherait ces nœuds comme disponibles annoncerait une capacité qu'aucune
mesure ne soutient.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .graph import DECIDE_PAR_LE_FOURNISSEUR, CanvasGraph

#: L'état d'un nœud. Quatre, et chacun dit autre chose.
PRET = "READY"
BLOQUE = "BLOCKED"
NON_IMPLEMENTE = "NOT_IMPLEMENTED"
ABSENT = "ABSENT"
ETATS = (PRET, BLOQUE, NON_IMPLEMENTE, ABSENT)


def _generation_est_possible() -> Dict[str, Any]:
    """
    Interroge la plateforme plutôt que de se souvenir d'elle.

    Returns:
        Si un fournisseur de génération peut tourner ici, et pourquoi non.
    """
    try:
        from ...media.readiness import readiness as media_readiness
        etat = media_readiness()
    except Exception as erreur:                     # pragma: no cover - défensif
        return {"possible": False,
                "reason": f"L'état du moteur média n'a pas pu être lu : {erreur}"}
    verdict = str(etat.get("state") or "état non rendu")
    return {
        "possible": False,
        "reason": (f"Aucun fournisseur de génération ne tourne ici. "
                   f"Moteur média : {verdict}"),
    }


def node_state(graph: CanvasGraph, node_id: str) -> Dict[str, Any]:
    """
    L'état d'un nœud, mesuré maintenant.

    Args:
        graph: Le graphe.
        node_id: Le nœud.

    Returns:
        `state`, et `blocked_by` quand il ne l'est pas — une liste de causes
        nommées, jamais un simple `False`.
    """
    noeud = graph.nodes[node_id]
    causes: List[str] = []

    manquantes = [m for m in graph.unconnected_required_inputs()
                  if m["node_id"] == node_id]
    for manquante in manquantes:
        causes.append(f"entrée requise « {manquante['port']} » non branchée "
                      f"({manquante['port_type']})")

    if noeud.node_type.trust == DECIDE_PAR_LE_FOURNISSEUR:
        generation = _generation_est_possible()
        if not generation["possible"]:
            causes.append(generation["reason"])

    return {
        "node_id": node_id,
        "type": noeud.type_name,
        "state": BLOQUE if causes else PRET,
        "blocked_by": causes,
    }


def graph_readiness(graph: CanvasGraph) -> Dict[str, Any]:
    """
    L'état du graphe, nœud par nœud.

    Args:
        graph: Le graphe.

    Returns:
        Un état par nœud, les comptes par état, et **aucun booléen global ni
        aucune note**. `blocking_reasons` regroupe les causes distinctes : c'est
        la liste qu'un opérateur peut traiter, et elle est souvent plus courte
        que le nombre de nœuds bloqués — une installation en débloque plusieurs.
    """
    etats = [node_state(graph, identifiant)
             for identifiant in graph.topological_order()]
    comptes = {etat: sum(1 for e in etats if e["state"] == etat)
               for etat in ETATS}
    causes = sorted({cause for e in etats for cause in e["blocked_by"]})
    return {
        "nodes": etats,
        "counts": comptes,
        "blocking_reasons": causes,
        "score": None,
        "note": ("Aucune note et aucun booléen global : une moyenne ferait "
                 "disparaître le nœud qui bloque derrière ceux qui ne bloquent "
                 "pas, et « pas prêt » n'apprend pas quoi installer."),
    }
