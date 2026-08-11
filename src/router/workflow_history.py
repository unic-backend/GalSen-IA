"""
Historique d'exécution des workflows (VOLET 08, chapitres 03 et 09).

Le chapitre 03 demande de « suivre l'historique d'exécution » et le chapitre 09
fait du **taux de succès** sa première métrique de qualité. Ni l'un ni l'autre
n'existait : chaque exécution rapportait son propre statut et disparaissait, si
bien qu'on ne pouvait pas dire si un workflow échouait une fois sur dix ou neuf
fois sur dix.

L'historique est borné et tenu en mémoire du processus, comme le reste de l'état
(ADR-009) : un redémarrage le remet à zéro, et le rapport le dit plutôt que de
laisser croire à une série longue.
"""

import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Iterable, List, Optional

# Nombre d'exécutions conservées. Au-delà, la plus ancienne sort : un historique
# non borné est la dette que le journal de la plateforme a déjà coûtée une fois.
DEFAULT_CAPACITY = 500


class WorkflowHistory:
    """Journal borné des exécutions de workflows."""

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        """
        Args:
            capacity: nombre maximal d'exécutions conservées
        """
        self._executions: Deque[Dict[str, Any]] = deque(maxlen=capacity)
        self._lock = threading.RLock()
        self._capacity = capacity

    def record(self, workflow_id: str, status: str, duration_seconds: float,
               agents_executed: int = 0, failed_agents: int = 0,
               request_id: Optional[str] = None) -> None:
        """
        Enregistre une exécution terminée.

        La requête de l'utilisateur n'est pas conservée : un historique
        d'exécution sert à mesurer un workflow, pas à archiver ce que les gens
        demandent — même raisonnement que pour les métriques de recherche.
        """
        with self._lock:
            self._executions.append({
                "workflow": workflow_id,
                "status": status,
                "duration_seconds": round(duration_seconds, 3),
                "agents_executed": agents_executed,
                "failed_agents": failed_agents,
                "request_id": request_id,
                "at": time.time(),
            })

    def recent(self, limit: int = 20, workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retourne les exécutions les plus récentes, de la plus récente à la plus ancienne."""
        with self._lock:
            executions = list(self._executions)
        if workflow_id is not None:
            executions = [e for e in executions if e["workflow"] == workflow_id]
        return list(reversed(executions))[:limit]

    def stats(self, workflow_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calcule le taux de succès et les durées observées.

        Returns:
            Le nombre d'exécutions, la répartition par statut, le taux de succès
            et les durées médiane et maximale. Le taux vaut `None` quand rien n'a
            été exécuté : 0.0 se lirait comme « tout échoue ».
        """
        with self._lock:
            executions = list(self._executions)
        if workflow_id is not None:
            executions = [e for e in executions if e["workflow"] == workflow_id]

        total = len(executions)
        par_statut: Dict[str, int] = {}
        for execution in executions:
            par_statut[execution["status"]] = par_statut.get(execution["status"], 0) + 1

        durees = sorted(e["duration_seconds"] for e in executions)
        succes = par_statut.get("success", 0)

        return {
            "executions": total,
            "by_status": par_statut,
            "success_rate": round(succes / total, 4) if total else None,
            "median_duration_seconds": durees[len(durees) // 2] if durees else None,
            "max_duration_seconds": durees[-1] if durees else None,
            "capacity": self._capacity,
            "scope": (
                "mémoire du processus : un redémarrage remet l'historique à zéro "
                "et une autre instance a le sien (ADR-009)"
            ),
        }

    def clear(self) -> None:
        """Vide l'historique. Réservé aux tests, qui doivent partir d'un état connu."""
        with self._lock:
            self._executions.clear()
