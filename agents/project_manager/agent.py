"""
Project Manager Agent for GalSen IA (VOLET 34, ch. 11).

The brief asks for an agent that manages projects and workflows. The platform
already decomposes a request into tasks (planner), assigns each one to an agent,
and records what every agent produced. Nobody reads that state back.

This agent does. It is a **reporter of what happened**, not a scheduler:

- which tasks were assigned, and to whom;
- which of them ran, and with what outcome;
- which ones are **blocked** — assigned to an agent that failed, or waiting on a
  task that has not completed;
- what the next actionable task is.

## Why it invents nothing

There is no deadline, no estimate, no percentage of completion in this output.
None of those exist anywhere in the platform's state, and producing them would
mean fabricating a project status — the exact failure `.claude/rules/verification.md`
names: *an unfinished capability reports a status; it never returns a plausible
answer.*

When the planner has not run, the answer is `no_plan`, not an empty report that
reads like "nothing to do".
"""

from typing import Any, Dict, List, Optional

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module

#: Statuts qu'un agent peut rendre (`src/router/output_validation.py`). Ils sont
#: repris tels quels : réinventer un vocabulaire de suivi ferait deux vérités.
STATUTS_ECHEC = ("error",)
STATUTS_IGNORE = ("skipped",)
STATUT_ATTENTE = "requires_approval"


class ProjectManagerAgent(BaseAgent):
    """Agent qui rapporte l'état réel des tâches d'une requête."""

    agent_id = "project_manager"
    required_engines = ("memory",)

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Rapporte l'avancement des tâches décidées par le planificateur.

        Args:
            context: Contexte d'exécution.

        Returns:
            L'état des tâches, les agents en échec, ce qui bloque, et la suite.
        """
        taches = context.tasks()
        if not taches:
            return {
                "status": "no_plan",
                "reason": (
                    "Le planificateur n'a produit aucune tâche pour cette "
                    "requête : il n'y a pas d'avancement à rapporter."
                ),
                "tasks": [],
            }

        resultats = self._resultats_par_agent(context)
        suivi = [self._suivre(tache, resultats) for tache in taches]

        bloquees = [tache for tache in suivi if tache["state"] == "blocked"]
        attente = [tache for tache in suivi if tache["state"] == "awaiting_approval"]
        faites = [tache for tache in suivi if tache["state"] == "done"]
        a_faire = [tache for tache in suivi if tache["state"] == "not_started"]

        return {
            "status": "reported",
            "task_count": len(suivi),
            "tasks": suivi,
            "done": len(faites),
            "blocked": len(bloquees),
            "awaiting_approval": len(attente),
            "not_started": len(a_faire),
            "agents_involved": sorted({tache["agent"] for tache in suivi if tache["agent"]}),
            "unassigned": [tache["id"] for tache in suivi if not tache["agent"]],
            "blockers": [
                {"task": tache["id"], "agent": tache["agent"], "reason": tache["detail"]}
                for tache in bloquees
            ],
            "next_action": self._prochaine_action(bloquees, attente, a_faire),
            # Dit explicitement ce qui n'est pas rendu, pour que l'absence ne
            # passe pas pour un oubli.
            "not_reported": [
                "délais et estimations : la plateforme n'en enregistre aucun",
                "pourcentage d'avancement : il se déduirait d'estimations absentes",
            ],
        }

    def _resultats_par_agent(self, context: AgentContext) -> Dict[str, Dict[str, Any]]:
        """Indexe par agent ce que les agents déjà exécutés ont rendu."""
        resultats: Dict[str, Dict[str, Any]] = {}
        for resultat in context.previous_results:
            if isinstance(resultat, dict) and resultat.get("agent"):
                resultats[resultat["agent"]] = resultat
        return resultats

    def _suivre(
        self, tache: Dict[str, Any], resultats: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Détermine l'état d'une tâche à partir de ce que son agent a rendu.

        Une tâche dont l'agent n'a pas encore tourné est `not_started`, pas
        `done` : c'est la distinction qui empêche un rapport optimiste.
        """
        agent = tache.get("assigned_agent") or (tache.get("assigned_agents") or [None])[0]
        resultat = resultats.get(agent) if agent else None

        if resultat is None:
            etat, detail = "not_started", "L'agent assigné n'a pas encore rendu de résultat."
        elif resultat.get("status") in STATUTS_ECHEC:
            etat, detail = "blocked", resultat.get("error") or "L'agent a échoué."
        elif resultat.get("status") == STATUT_ATTENTE:
            etat, detail = "awaiting_approval", "Une décision humaine est attendue."
        elif resultat.get("status") in STATUTS_IGNORE:
            etat, detail = "skipped", "L'agent a été écarté pour cette requête."
        else:
            etat, detail = "done", "Résultat rendu."

        return {
            "id": tache.get("id"),
            "description": tache.get("description"),
            "agent": agent,
            "depends_on": tache.get("depends_on"),
            "state": etat,
            "detail": detail,
        }

    @staticmethod
    def _prochaine_action(
        bloquees: List[Dict[str, Any]],
        attente: List[Dict[str, Any]],
        a_faire: List[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Retourne la seule action qui débloque le plan.

        L'ordre n'est pas arbitraire : une approbation en attente arrête tout le
        reste, et un échec doit être traité avant de lancer la suite.
        """
        if attente:
            return (
                f"Décider sur « {attente[0]['id']} » : "
                f"l'agent {attente[0]['agent']} attend une approbation."
            )
        if bloquees:
            return (
                f"Traiter l'échec de « {bloquees[0]['id']} » "
                f"({bloquees[0]['agent']}) : {bloquees[0]['detail']}"
            )
        if a_faire:
            return f"Exécuter « {a_faire[0]['id']} » ({a_faire[0]['agent']})."
        return None


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter.

    Returns:
        Résultat de l'agent au format standard.
    """
    return run_agent_module(ProjectManagerAgent, input_data)
