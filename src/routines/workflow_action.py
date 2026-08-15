"""
A routine that runs a workflow, and what an unattended run may never decide.

Until now a routine could call **tools** and nothing else. `types.py` says it in
its own comment: past ten actions "it is no longer a routine but a workflow,
which has its own engine with resume and checkpoints — things a routine does not
have." That sentence describes a wall, and the wall was real: scheduled work
went straight to the tool engine, so it had no checkpoint, no execution history,
no retry and no `REQUEST` audit event. The platform's orchestrator existed and
the unattended path could not reach it.

This closes that, and adds exactly one rule of its own.

**An approval is never granted by the absence of someone to refuse it.** A
workflow run at three in the morning can stop on `requires_approval` like any
other. It is then **suspended**, not successful: the run keeps its checkpoint,
the routine reports the `run_id`, and a human resumes it. Counting it as a
success would make "nobody was there to answer" mean "yes".

The declaration check follows the rule the rest of this package already holds:
what can be verified when the routine is written is verified then. A workflow
that does not exist, or that the loader refuses to execute, is refused at
declaration — not discovered every night by nobody.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .types import RoutineAction

#: L'identifiant d'outil porté par une action de workflow. Ce n'est pas un
#: outil : c'est ce que l'action affiche là où les autres nomment le leur, pour
#: qu'un compte rendu reste lisible sans connaître le type de l'action.
ACTION_WORKFLOW = "workflow"

#: Le statut d'une exécution suspendue en attente d'une décision humaine.
STATUT_SUSPENDU = "suspended"


@dataclass(frozen=True)
class WorkflowAction(RoutineAction):
    """
    Une action de routine qui fait tourner un workflow complet.

    Attributes:
        workflow_id: Le workflow déclaré dans `workflows/workflows.yaml`.
        tool_id: Toujours `workflow` — l'action n'appelle pas d'outil
            directement, elle passe par l'orchestrateur.
        operation: La demande soumise au workflow. Vide, la description de la
            routine est utilisée : une exécution sans demande n'aurait rien à
            traiter.
    """

    tool_id: str = ACTION_WORKFLOW
    workflow_id: str = ""

    def as_dict(self) -> dict:
        """Représentation sérialisable, disant qu'il s'agit d'un workflow."""
        base = super().as_dict()
        base["workflow_id"] = self.workflow_id
        base["kind"] = ACTION_WORKFLOW
        return base


def workflow_runnable_unattended(
    workflow_id: str, loader: Optional[Any] = None
) -> Tuple[bool, str]:
    """
    Dit si un workflow peut être déclenché sans personne devant.

    Deux questions, toutes deux répondables à la déclaration : le workflow
    existe-t-il, et le chargeur accepte-t-il de l'exécuter ? Un workflow
    inexécutable refusé ici est un échec de moins à trois heures du matin, et un
    refus qu'un auteur peut corriger tout de suite.

    Args:
        workflow_id: Le workflow visé.
        loader: Le chargeur de workflows. Celui du dépôt par défaut.

    Returns:
        `(autorisé, motif)`. Le motif est vide quand c'est autorisé.
    """
    identifiant = (workflow_id or "").strip()
    if not identifiant:
        return False, (
            "Aucun workflow nommé. Une action de workflow sans workflow ne "
            "ferait rien, chaque nuit, sans que personne le voie."
        )

    chargeur = loader if loader is not None else _chargeur_par_defaut()
    if chargeur is None:
        return False, (
            "Aucun chargeur de workflows disponible : impossible de vérifier "
            "que ce workflow existe. Refusé plutôt que supposé."
        )

    try:
        chargeur.get_workflow(identifiant)
    except KeyError:
        return False, f"Workflow '{identifiant}' inconnu."

    if not chargeur.is_executable(identifiant):
        problemes = "; ".join(
            probleme.message
            for probleme in chargeur.get_problems(identifiant)
            if probleme.gravite == "error"
        )
        return False, (
            f"Workflow '{identifiant}' inexécutable : {problemes or 'cause non nommée'}."
        )

    return True, ""


def _chargeur_par_defaut() -> Optional[Any]:
    """
    Le chargeur de workflows du dépôt, ouvert et **validé** à la demande.

    La validation compte : `is_executable()` répond à partir de la dernière
    validation, et un chargeur qui n'en a jamais subi déclare tout exécutable.
    Elle est faite ici, contre les agents réellement enregistrés — sinon le
    contrôle de déclaration dirait « oui » sans avoir rien regardé.

    Chargé à l'appel et non à l'import : le registre des routines ne doit pas
    tirer l'orchestrateur entier dans un processus qui ne déclare aucune routine
    de workflow.
    """
    import os

    from ..router.agent_loader import AgentLoader
    from ..router.workflow_loader import WorkflowLoader

    racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        chargeur = WorkflowLoader(os.path.join(racine, "workflows", "workflows.yaml"))
        agents = AgentLoader(os.path.join(racine, "agents", "registry.yaml"))
        chargeur.validate(agents.get_all_agents().keys(), journaliser=False)
        return chargeur
    except Exception:  # pragma: no cover - dépend d'un fichier absent
        return None
