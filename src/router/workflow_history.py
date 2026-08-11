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

# Version portée par une exécution dont l'appelant n'a pas dit laquelle. Une
# valeur nommée plutôt qu'une chaîne vide : elle se lit dans un rapport, et elle
# ne se confond pas avec la version « unversioned » d'un workflow qui n'en
# déclare pas — les deux cas sont différents et le rapport doit les distinguer.
VERSION_INCONNUE = "unrecorded"


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
               request_id: Optional[str] = None,
               workflow_version: str = VERSION_INCONNUE,
               failing_agents: Optional[Iterable[str]] = None,
               agent_durations: Optional[Dict[str, float]] = None) -> None:
        """
        Enregistre une exécution terminée.

        La requête de l'utilisateur n'est pas conservée : un historique
        d'exécution sert à mesurer un workflow, pas à archiver ce que les gens
        demandent — même raisonnement que pour les métriques de recherche.

        La **version** en fait partie (VOLET 18, ch. 03 étape 7). Sans elle, un
        changement de pipeline laisse les deux définitions sous le même nom et
        le taux de succès mélange ce qu'on cherchait justement à comparer.
        """
        with self._lock:
            self._executions.append({
                "workflow": workflow_id,
                "workflow_version": workflow_version,
                "status": status,
                "duration_seconds": round(duration_seconds, 3),
                "agents_executed": agents_executed,
                "failed_agents": failed_agents,
                "failing_agents": sorted(set(failing_agents or ())),
                "agent_durations": dict(agent_durations or {}),
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
            # Le taux global reste servi, mais il ne suffit pas : c'est celui
            # d'un mélange. La ventilation par version dit laquelle des
            # définitions échoue (VOLET 18, ch. 03 étape 7 et ch. 06).
            "by_version": self._par_version(executions),
            # Nommer l'agent qui échoue, pas seulement en compter (ch. 06).
            "failing_agents": self._agents_en_echec(executions),
            # Où passe le temps (VOLET 19, ch. 03 étapes 5 et 7). Une durée
            # totale ne dit pas quel agent la consomme, et on n'optimise pas ce
            # qu'on ne mesure pas.
            "agent_time": self._temps_par_agent(executions),
            "median_duration_seconds": durees[len(durees) // 2] if durees else None,
            "max_duration_seconds": durees[-1] if durees else None,
            "capacity": self._capacity,
            "scope": (
                "mémoire du processus : un redémarrage remet l'historique à zéro "
                "et une autre instance a le sien (ADR-009)"
            ),
        }

    @staticmethod
    def _temps_par_agent(executions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Agrège le temps passé par agent, du plus coûteux au moins coûteux.

        Args:
            executions: les exécutions déjà filtrées par l'appelant.

        Returns:
            Pour chaque agent : le nombre d'exécutions, le temps total et la
            part du temps d'agent qu'il représente. La part est calculée sur la
            somme des durées d'agents, pas sur la durée des requêtes : ce qui se
            passe entre deux agents n'appartient à aucun d'eux.
        """
        totaux: Dict[str, float] = {}
        comptes: Dict[str, int] = {}
        for execution in executions:
            for agent, duree in (execution.get("agent_durations") or {}).items():
                totaux[agent] = totaux.get(agent, 0.0) + duree
                comptes[agent] = comptes.get(agent, 0) + 1

        somme = sum(totaux.values())
        return {
            agent: {
                "executions": comptes[agent],
                "total_seconds": round(total, 3),
                "share": round(total / somme, 4) if somme else None,
            }
            for agent, total in sorted(totaux.items(), key=lambda paire: paire[1], reverse=True)
        }

    @staticmethod
    def _agents_en_echec(executions: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Compte les échecs par agent, du plus fréquent au moins fréquent.

        Args:
            executions: les exécutions déjà filtrées par l'appelant.

        Returns:
            Un dictionnaire agent → nombre d'exécutions où il a échoué. Vide
            quand rien n'a échoué : un classement sans échec n'existe pas.
        """
        comptes: Dict[str, int] = {}
        for execution in executions:
            for agent in execution.get("failing_agents", ()):
                comptes[agent] = comptes.get(agent, 0) + 1
        return dict(sorted(comptes.items(), key=lambda paire: paire[1], reverse=True))

    @staticmethod
    def _par_version(executions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Ventile les exécutions par version de workflow.

        Args:
            executions: les exécutions déjà filtrées par l'appelant.

        Returns:
            Pour chaque version rencontrée : le nombre d'exécutions et son taux
            de succès. Les versions sont triées, un rapport se lit.
        """
        groupes: Dict[str, List[Dict[str, Any]]] = {}
        for execution in executions:
            groupes.setdefault(execution.get("workflow_version", VERSION_INCONNUE), []).append(execution)

        return {
            version: {
                "executions": len(lot),
                "success_rate": round(
                    sum(1 for e in lot if e["status"] == "success") / len(lot), 4
                ),
            }
            for version, lot in sorted(groupes.items())
        }

    def clear(self) -> None:
        """Vide l'historique. Réservé aux tests, qui doivent partir d'un état connu."""
        with self._lock:
            self._executions.clear()
