"""
Agrégation analytique (VOLET 09, chapitres 02, 04, 05 et 06).

Le manuel décrit sept composants : collecteur d'événements, pipeline de données,
processeur analytique, moteur de métriques, service de rapport, couche de
tableau de bord, module de gouvernance. La plateforme en possédait deux —
l'audit collecte les événements, `/metrics` compte le trafic — et rien ne
transformait cela en indicateurs.

Ce module est le processeur et le service de rapport. Il **agrège des sources
existantes** et n'en crée aucune : une seconde collecte à côté de l'audit
produirait deux comptes différents des mêmes exécutions, et la question « lequel
est juste » n'aurait pas de réponse.

Vie privée (chapitre 01, « privacy by design ») : aucune requête utilisateur,
aucun sujet et aucun identifiant de clé n'entre dans un rapport. Ce qui est
mesuré est le comportement du système, pas ce que les gens demandent.
"""

from typing import Any, Dict, Iterable, Optional

# Sources de données nommées par le chapitre 04, et ce qui les alimente.
# Une source non branchée est déclarée comme telle : la liste du manuel ne doit
# pas se lire comme un inventaire de ce qui existe.
SOURCES_ATTENDUES: Dict[str, str] = {
    "user_interactions": "compteurs HTTP (`RequestMetricsMiddleware`)",
    "ai_services": "événements d'audit par agent",
    "workflow_engine": "`WorkflowHistory` (VOLET 08)",
    "knowledge_engine": "compteurs de recherche (VOLET 14)",
    "memory_engine": "",
    "system_logs": "",
    "external_integrations": "",
}

# Ce que l'analytique ne sait pas produire ici, et pourquoi.
UNAVAILABLE_CAPABILITIES: Dict[str, str] = {
    "trends": (
        "aucune série temporelle n'est conservée : les compteurs et l'historique "
        "vivent en mémoire du processus et repartent de zéro au redémarrage (ADR-009)"
    ),
    "anomaly_detection": (
        "sans historique conservé, il n'existe aucune ligne de base à laquelle "
        "comparer une exécution"
    ),
    "dashboards": (
        "aucune couche de visualisation : le rapport est une réponse JSON, lue par "
        "un opérateur ou un outil"
    ),
}


def source_coverage() -> Dict[str, Any]:
    """
    Dit lesquelles des sept sources du chapitre 04 sont réellement branchées.

    Returns:
        Par source : `wired` et ce qui l'alimente, plus le compte des sources
        branchées sur le total déclaré.
    """
    sources = {
        nom: {"wired": bool(alimentation), "fed_by": alimentation or None}
        for nom, alimentation in SOURCES_ATTENDUES.items()
    }
    return {
        "sources": sources,
        "wired_count": sum(1 for s in sources.values() if s["wired"]),
        "declared_count": len(sources),
    }


def _agent_breakdown(evenements: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
    """
    Calcule, par agent, le nombre d'exécutions, le taux de succès et la durée.

    Ne compte que les événements de type `agent` : un événement d'outil ou de
    requête décrit autre chose, et les mélanger gonflerait le compte d'exécutions.
    """
    par_agent: Dict[str, Dict[str, Any]] = {}
    for evenement in evenements:
        type_ = getattr(getattr(evenement, "event_type", None), "value", None)
        if type_ != "agent":
            continue

        agent = getattr(evenement, "agent_id", None) or "inconnu"
        statut = getattr(getattr(evenement, "status", None), "value", "inconnu")
        duree = getattr(evenement, "execution_time_seconds", None)

        entree = par_agent.setdefault(agent, {"executions": 0, "by_status": {}, "_durees": []})
        entree["executions"] += 1
        entree["by_status"][statut] = entree["by_status"].get(statut, 0) + 1
        if isinstance(duree, (int, float)):
            entree["_durees"].append(float(duree))

    for entree in par_agent.values():
        durees = sorted(entree.pop("_durees"))
        total = entree["executions"]
        succes = entree["by_status"].get("success", 0)
        entree["success_rate"] = round(succes / total, 4) if total else None
        entree["median_duration_seconds"] = durees[len(durees) // 2] if durees else None
        entree["max_duration_seconds"] = durees[-1] if durees else None
    return par_agent


def build_report(audit_manager: Optional[Any] = None,
                 workflow_history: Optional[Any] = None,
                 metrics: Optional[Dict[str, Any]] = None,
                 event_limit: int = 5000) -> Dict[str, Any]:
    """
    Construit le rapport analytique à partir des sources disponibles.

    Args:
        audit_manager: moteur d'audit, pour les exécutions d'agents
        workflow_history: historique des workflows (VOLET 08)
        metrics: instantané de `/metrics`
        event_limit: nombre maximal d'événements d'audit examinés

    Returns:
        Un rapport portant les sections alimentées, la couverture des sources et
        les capacités que la plateforme ne sait pas produire. Une source absente
        laisse sa section à `None` — jamais à zéro, qui se lirait comme une mesure.
    """
    rapport: Dict[str, Any] = {
        "coverage": source_coverage(),
        "unavailable": dict(UNAVAILABLE_CAPABILITIES),
        "scope": (
            "mémoire du processus : un redémarrage remet tout à zéro et une autre "
            "instance a ses propres chiffres (ADR-009)"
        ),
    }

    if audit_manager is not None:
        try:
            evenements = audit_manager.list_events(limit=event_limit)
            statistiques = audit_manager.stats()
            rapport["agents"] = {
                "by_agent": _agent_breakdown(evenements),
                "audited_events": statistiques.get("total_events", 0),
                "by_type": statistiques.get("by_type", {}),
            }
        except Exception as erreur:  # pragma: no cover - chemin de secours
            rapport["agents"] = {"unavailable": f"audit illisible : {erreur}"}
    else:
        rapport["agents"] = None

    if workflow_history is not None:
        rapport["workflows"] = workflow_history.stats()
    else:
        rapport["workflows"] = None

    if metrics is not None:
        # Reprise stricte de ce que `/metrics` expose déjà : recalculer ces
        # chiffres ici créerait une deuxième vérité sur le même trafic.
        rapport["requests"] = {
            "total": metrics.get("requests_total", 0),
            "error_rate": metrics.get("error_rate"),
            "auth": metrics.get("auth"),
        }
        rapport["search"] = metrics.get("search")
    else:
        rapport["requests"] = None
        rapport["search"] = None

    return rapport
