"""
The two ways work reaches the orchestrator, side by side.

After VOLET 64 there are exactly two: a person asking (`POST /process`), and a
routine firing with nobody watching (`POST /routines/tick`). They run **the same
engine** — the same plan, the same checkpoints, the same execution history, the
same audit event. That is the whole point of the volet: a second execution path
with none of those guarantees was the parallel implementation the directive
forbids.

What differs is not the machinery, it is what can be *decided*:

- **An approval cannot be granted by absence.** An unattended run that reaches a
  step needing a human stops there and is reported `suspended`. It keeps its
  checkpoint, so the decision is taken later by someone, not skipped.
- **An owner is never inferred.** At three in the morning there is no session to
  read it from, so the owner comes from the routine's declaration or the run is
  refused before it exists.
- **A workflow is checked when the routine is written**, not discovered broken
  every night by nobody.

This module reports that, and counts what it can count. Anything it cannot
measure it names as unmeasured rather than assuming a number.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

#: Les deux chemins d'entrée de l'orchestrateur.
CHEMIN_DEMANDE = "attended"
CHEMIN_ROUTINE = "unattended"


def orchestration_paths(
    workflow_loader: Optional[Any] = None,
    routine_registry: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Les chemins par lesquels un travail atteint l'orchestrateur, mesurés.

    Args:
        workflow_loader: Le chargeur de workflows, pour compter ce qui est
            déclaré et ce qui est réellement exécutable. Absent, le compte est
            rapporté comme non mesuré — jamais deviné.
        routine_registry: Le registre des routines, pour compter celles qui
            déclenchent un workflow.

    Returns:
        Les deux chemins, ce qu'ils partagent, et ce que le second ne peut pas
        décider.
    """
    return {
        "paths": {
            CHEMIN_DEMANDE: {
                "entry_point": "POST /process",
                "triggered_by": "Quelqu'un, dans une session.",
                "owner_from": "La clé d'appel : l'appelant est le propriétaire.",
                "may_ask_a_human": True,
            },
            CHEMIN_ROUTINE: {
                "entry_point": "POST /routines/tick",
                "triggered_by": (
                    "Une routine dont le tour est venu. Aucune boucle ne tourne "
                    "d'elle-même : le tour est provoqué."
                ),
                "owner_from": (
                    "La déclaration de la routine. À trois heures du matin, il "
                    "n'y a pas de session dont le déduire."
                ),
                "may_ask_a_human": False,
            },
        },
        # Ce que les deux chemins partagent est le cœur du VOLET : un second
        # chemin qui n'aurait rien de tout cela serait une implémentation
        # parallèle.
        "shared": [
            "Le même plan d'exécution, tiré du même registre de workflows.",
            "Les mêmes points de reprise : une exécution interrompue se reprend "
            "sans refaire les étapes déjà abouties.",
            "Le même historique d'exécution, donc le même taux de succès.",
            "Le même événement d'audit `REQUEST`, marqué `unattended` selon le "
            "chemin — l'exécution ne change pas, sa lecture d'après si.",
        ],
        "unattended_cannot": [
            "Accorder une approbation. Une exécution qui en attend une est "
            "rendue `suspended`, avec son `run_id` : l'absence de quelqu'un "
            "pour refuser n'est pas un accord.",
            "Déduire un propriétaire d'une session : il vient de la routine.",
            "Déclencher un workflow inconnu ou inexécutable : c'est vérifié à "
            "la déclaration de la routine.",
            "Toucher la donnée d'une personne au nom de la plateforme : une "
            "routine de plateforme n'appartient à personne, donc ne lit "
            "personne.",
        ],
        "measured": _mesures(workflow_loader, routine_registry),
    }


def _mesures(
    workflow_loader: Optional[Any], routine_registry: Optional[Any]
) -> Dict[str, Any]:
    """
    Ce qui est comptable, compté ; le reste, nommé non mesuré.

    Un rapport qui rendrait `0` faute de registre ferait passer « personne n'a
    regardé » pour « il n'y en a aucune », ce que ce dépôt distingue partout
    ailleurs.
    """
    mesures: Dict[str, Any] = {}

    if workflow_loader is None:
        mesures["workflows"] = "NOT_MEASURED — aucun chargeur fourni."
    else:
        declares = list(workflow_loader.get_all_workflows())
        mesures["workflows_declared"] = len(declares)
        mesures["workflows_executable"] = sum(
            1 for identifiant in declares if workflow_loader.is_executable(identifiant)
        )

    if routine_registry is None:
        mesures["routines"] = "NOT_MEASURED — aucun registre fourni."
    else:
        # Des nombres, jamais des identifiants : la liste des routines de
        # quelqu'un dit ce qu'il surveille, et un rapport d'orchestration n'a
        # pas à la porter.
        comptes = routine_registry.counts()
        mesures["routines_declared"] = comptes["declared"]
        mesures["routines_enabled"] = comptes["enabled"]
        mesures["routines_running_a_workflow"] = comptes["running_a_workflow"]

    return mesures
