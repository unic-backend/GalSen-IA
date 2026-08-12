"""
Le chemin d'une requête, reconstitué (phase 26.4).

La plateforme mesure déjà : chaque appel d'outil et chaque génération inscrit un
événement d'audit portant un `request_id` et sa durée, et l'orchestrateur rend ce
`request_id` à l'appelant. Ce qui manquait n'était pas la mesure, c'était
**l'assemblage** : aucun moyen de demander « qu'est-ce qui s'est passé pour
cette requête, et où est passé le temps ». `/analytics` agrège tout le monde et
répond à une autre question.

Ce module ne collecte rien et n'instrumente rien. Il **interroge** l'audit et
ordonne ce qu'il trouve. C'est délibéré : une seconde source de vérité sur le
temps passé finirait par diverger de la première, et il faudrait alors décider
laquelle croire.

Ce qui reste hors de portée est dit plutôt que comblé : un événement sans durée
est compté à part (`unmeasured`) au lieu d'être supposé instantané.
"""

from typing import Any, Dict, List, Optional

# Nombre d'événements remontés pour une requête. Une requête qui en produirait
# davantage a un problème plus intéressant que sa trace.
LIMITE_EVENEMENTS = 500


def _duree(evenement: Dict[str, Any]) -> Optional[float]:
    """Retourne la durée d'un événement, ou None si elle n'a pas été mesurée."""
    valeur = evenement.get("execution_time_seconds")
    return float(valeur) if isinstance(valeur, (int, float)) else None


def _etape(evenement: Dict[str, Any]) -> Dict[str, Any]:
    """Réduit un événement d'audit à une étape de trace."""
    etape = {
        "type": evenement.get("event_type"),
        "action": evenement.get("action"),
        "status": evenement.get("status"),
        "timestamp": evenement.get("timestamp"),
    }
    for champ in ("agent_id", "model_id", "detail"):
        if evenement.get(champ):
            etape[champ] = evenement[champ]
    duree = _duree(evenement)
    if duree is not None:
        etape["seconds"] = round(duree, 4)
    return etape


def build_trace(audit_manager: Any, request_id: str) -> Dict[str, Any]:
    """
    Reconstitue le chemin d'une requête à partir de l'audit.

    Args:
        audit_manager: Moteur d'audit, ou None s'il est indisponible.
        request_id: Identifiant rendu par `POST /workflow/run`.

    Returns:
        Les étapes dans l'ordre chronologique et le temps passé. Une requête
        inconnue rend une trace vide — c'est une réponse, pas une erreur : un
        `request_id` peut être exact et son audit déjà purgé.
    """
    if audit_manager is None:
        return {
            "request_id": request_id,
            "available": False,
            "reason": "Moteur d'audit indisponible : aucune trace ne peut être reconstituée.",
            "steps": [],
        }

    evenements = [
        evenement.to_dict() if hasattr(evenement, "to_dict") else evenement
        for evenement in audit_manager.list_events(
            limit=LIMITE_EVENEMENTS, request_id=request_id
        )
    ]
    # L'audit rend le plus récent en premier ; une trace se lit dans l'autre sens.
    evenements.sort(key=lambda evenement: evenement.get("timestamp_unix", 0))

    etapes: List[Dict[str, Any]] = [_etape(evenement) for evenement in evenements]
    durees = [_duree(evenement) for evenement in evenements]
    mesurees = [duree for duree in durees if duree is not None]

    trace: Dict[str, Any] = {
        "request_id": request_id,
        "available": True,
        "steps": etapes,
        "step_count": len(etapes),
        # Somme des durées mesurées, et non l'écart entre le premier et le
        # dernier événement : les agents parallèles rendraient cet écart
        # trompeur dans un sens comme dans l'autre.
        "measured_seconds": round(sum(mesurees), 4),
        "unmeasured_steps": len(durees) - len(mesurees),
    }

    if etapes:
        trace["statuses"] = sorted({etape["status"] for etape in etapes if etape.get("status")})
        avec_duree = [etape for etape in etapes if "seconds" in etape]
        if avec_duree:
            plus_lente = max(avec_duree, key=lambda etape: etape["seconds"])
            # L'étape la plus lente est ce qu'on cherche en ouvrant une trace ;
            # la faire chercher à l'œil dans cinquante lignes serait inutile.
            trace["slowest_step"] = plus_lente

    return trace
