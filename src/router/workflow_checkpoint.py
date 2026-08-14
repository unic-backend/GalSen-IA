"""
Workflow checkpoints: what a long run remembers, and what it refuses to redo.

The repository already loads workflows (`workflow_loader.py`) and records what
they did once finished (`workflow_history.py`). What it has never had is the
state of a run **while it is still going** — so a workflow of ten agents that
dies at the eighth starts again at the first, and the seven steps that already
touched the world touch it again.

That is the rule this module exists for:

**A completed step is never redone.** Re-running a step that already had an
outside effect is how one email becomes two — the same lesson the request
executor learned about retries (VOLET 44). Resuming starts at the first step
that has not finished, and a run whose steps are all done is finished, not
restartable.

Two consequences follow, and neither is optional.

**A checkpoint holds real work product, so it has an owner.** Unlike the routine
journal — which deliberately keeps nothing a routine read — a checkpoint must
carry each finished step's output, or it could not resume. That makes it a data
store, and it therefore obeys the isolation boundary like any other: a run
started by someone belongs to them, and nobody else resumes it. Resuming another
person's workflow would mean running agents over their data.

**Cancelling is terminal.** A cancelled run does not resume. If it did, "cancel"
would mean "pause", and the difference matters exactly once — to whoever
cancelled it believing it stopped.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..security.isolation import Audience, Owner, may_read

#: Taille maximale, en caractères, du résultat conservé pour une étape. Un
#: point de reprise doit tenir en mémoire et se relire ; un agent qui rend
#: cinquante mille lignes rendrait le point de reprise plus coûteux que le
#: travail qu'il évite de refaire.
TAILLE_MAXIMALE_ETAPE = 20_000

#: Nombre de reprises autorisées pour une même exécution. Trois : au-delà, ce
#: n'est plus une panne passagère mais une étape qui ne passera jamais, et
#: reprendre indéfiniment consomme sans avancer.
REPRISES_MAXIMUM = 3

#: Exécutions conservées. Le routeur ouvre un point de reprise à **chaque**
#: requête (phase 49.2) : sans borne, la mémoire du serveur croîtrait avec son
#: trafic. Les terminées partent les premières, et ce qui est oublié est
#: compté — un point de reprise perdu en silence est une reprise impossible
#: dont personne ne connaît la cause.
EXECUTIONS_CONSERVEES = 200


class RunStatus(str, Enum):
    """Où en est une exécution de workflow."""

    #: En cours, ou reprise possible.
    RUNNING = "running"

    #: Toutes les étapes ont abouti.
    COMPLETED = "completed"

    #: Une étape a échoué. La reprise est possible tant que le quota le permet.
    FAILED = "failed"

    #: Annulée. **Terminal** : ne reprend pas.
    CANCELLED = "cancelled"

    @property
    def resumable(self) -> bool:
        """Vrai si une reprise a encore un sens."""
        return self in (RunStatus.RUNNING, RunStatus.FAILED)


class CheckpointRefused(ValueError):
    """Une opération impossible sur un point de reprise, avec sa raison."""


@dataclass
class StepRecord:
    """
    Une étape terminée, et ce qu'elle a produit.

    Attributes:
        agent_id: L'agent qui l'a exécutée.
        ok: A-t-elle abouti.
        output: Ce qu'elle a rendu, tronqué au besoin.
        truncated: Vrai si la sortie a été coupée — dit, jamais silencieux.
        skipped: Pourquoi l'étape n'a pas été exécutée, si elle ne l'a pas été.
            Une étape sautée compte comme faite — elle ne sera pas exécutée à
            la reprise non plus — mais elle ne prétend pas avoir produit
            quelque chose.
        finished_at: Quand.
    """

    agent_id: str
    ok: bool
    output: str = ""
    truncated: bool = False
    skipped: str = ""
    finished_at: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "agent_id": self.agent_id,
            "ok": self.ok,
            "output": self.output,
            "truncated": self.truncated,
            "skipped": self.skipped,
            "finished_at": self.finished_at,
        }


@dataclass
class WorkflowRun:
    """
    L'état d'une exécution, en cours ou terminée.

    Attributes:
        run_id: Son identifiant.
        workflow_id: Le workflow exécuté.
        steps: Les agents prévus, dans l'ordre.
        subject: Qui l'a lancée. `None` pour la plateforme.
        completed: Les étapes terminées.
        status: Où elle en est.
        resumes: Combien de fois elle a été reprise.
        started_at: Quand elle a commencé.
        updated_at: Dernier changement.
        cancelled_reason: Pourquoi elle a été annulée, s'il y a lieu.
    """

    run_id: str
    workflow_id: str
    steps: List[str]
    subject: Optional[str] = None
    completed: List[StepRecord] = field(default_factory=list)
    status: RunStatus = RunStatus.RUNNING
    resumes: int = 0
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    cancelled_reason: str = ""

    @property
    def done_agents(self) -> List[str]:
        """Les agents dont l'étape a abouti."""
        return [etape.agent_id for etape in self.completed if etape.ok]

    def next_step(self) -> Optional[str]:
        """
        La première étape qui n'a pas abouti.

        Returns:
            L'agent à exécuter, ou `None` si tout est fait.
        """
        faites = set(self.done_agents)
        for agent in self.steps:
            if agent not in faites:
                return agent
        return None

    @property
    def progress(self) -> str:
        """Où en est l'exécution, en une chaîne lisible."""
        return f"{len(self.done_agents)}/{len(self.steps)}"

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "subject": self.subject,
            "status": self.status.value,
            "steps": list(self.steps),
            "completed": [etape.as_dict() for etape in self.completed],
            "next_step": self.next_step(),
            "progress": self.progress,
            "resumes": self.resumes,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "cancelled_reason": self.cancelled_reason,
        }


class WorkflowCheckpoints:
    """
    Les points de reprise des exécutions, en mémoire et thread-safe.

    Ce qu'il conserve appartient à quelqu'un : le filtre par audience est le
    même que celui des routines et de la mémoire.
    """

    def __init__(self, max_runs: int = EXECUTIONS_CONSERVEES) -> None:
        """
        Args:
            max_runs: Exécutions conservées. Au-delà, les plus anciennes sont
                oubliées — les terminées d'abord.
        """
        self._verrou = threading.RLock()
        self._runs: Dict[str, WorkflowRun] = {}
        self._maximum = max(1, int(max_runs))
        self._oubliees = 0
        self._oubliees_reprenables = 0

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def start(
        self, workflow_id: str, steps: List[str], subject: Optional[str] = None
    ) -> WorkflowRun:
        """
        Ouvre une exécution.

        Args:
            workflow_id: Le workflow lancé.
            steps: Les agents prévus, dans l'ordre.
            subject: Qui la lance.

        Returns:
            L'exécution ouverte.

        Raises:
            CheckpointRefused: Si aucune étape n'est prévue — une exécution
                sans étape n'a rien à reprendre et masquerait un workflow vide.
        """
        if not steps:
            raise CheckpointRefused(
                f"Workflow '{workflow_id}' : aucune étape. Une exécution sans "
                "étape n'a rien à reprendre, et l'ouvrir masquerait un "
                "workflow vide."
            )

        execution = WorkflowRun(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            workflow_id=workflow_id,
            steps=list(steps),
            subject=(subject or "").strip() or None,
        )
        with self._verrou:
            self._runs[execution.run_id] = execution
            self._elaguer()
        return execution

    def _elaguer(self) -> None:
        """
        Ramène le nombre d'exécutions sous la borne.

        Les terminées partent d'abord : oublier une exécution reprenable, c'est
        perdre la reprise elle-même. Quand il ne reste que des reprenables, les
        plus anciennes partent quand même — mais elles sont **comptées à part**,
        parce qu'une reprise devenue impossible doit avoir une cause visible.

        Appelé sous verrou.
        """
        if len(self._runs) <= self._maximum:
            return

        par_age = sorted(self._runs.values(), key=lambda e: e.updated_at)
        ordre = [e for e in par_age if not e.status.resumable]
        ordre += [e for e in par_age if e.status.resumable]

        for execution in ordre:
            if len(self._runs) <= self._maximum:
                return
            del self._runs[execution.run_id]
            self._oubliees += 1
            if execution.status.resumable:
                self._oubliees_reprenables += 1

    def record_step(
        self, run_id: str, agent_id: str, ok: bool, output: Any = "",
        subject: Optional[str] = None, skipped: str = "",
    ) -> WorkflowRun:
        """
        Consigne une étape terminée.

        Args:
            run_id: L'exécution.
            agent_id: L'agent qui vient de finir.
            ok: A-t-il abouti.
            output: Ce qu'il a rendu.
            subject: Qui consigne, pour le contrôle d'accès.
            skipped: Raison, si l'étape a été franchie sans tourner. Passer par
                `record_skip`, qui l'exige.

        Returns:
            L'exécution mise à jour.

        Raises:
            CheckpointRefused: Si l'exécution est inconnue, invisible, ou déjà
                terminée. Consigner une étape sur une exécution annulée
                effacerait le sens de l'annulation.
        """
        execution = self._exiger(run_id, subject)
        if not execution.status.resumable:
            raise CheckpointRefused(
                f"Exécution '{run_id}' : statut '{execution.status.value}'. "
                "Consigner une étape sur une exécution terminée ou annulée "
                "effacerait le sens de son statut."
            )

        texte = "" if output is None else str(output)
        tronque = len(texte) > TAILLE_MAXIMALE_ETAPE
        if tronque:
            texte = texte[:TAILLE_MAXIMALE_ETAPE]

        with self._verrou:
            execution.completed.append(StepRecord(
                agent_id=agent_id, ok=ok, output=texte, truncated=tronque,
                skipped=skipped,
            ))
            execution.updated_at = time.time()
            if not ok:
                execution.status = RunStatus.FAILED
            elif execution.next_step() is None:
                execution.status = RunStatus.COMPLETED
        return execution

    def record_skip(
        self, run_id: str, agent_id: str, reason: str, subject: Optional[str] = None
    ) -> WorkflowRun:
        """
        Consigne une étape qui n'a pas été exécutée et ne le sera pas.

        Un agent désactivé, ou écarté par le planificateur, ne tournera pas
        davantage à la reprise : le laisser « à faire » rendrait une exécution
        indéfiniment inachevée. Il compte donc comme franchi — mais l'étape
        porte la raison et ne prétend rien avoir produit.

        Args:
            run_id: L'exécution.
            agent_id: L'agent écarté.
            reason: Pourquoi.
            subject: Qui consigne.

        Returns:
            L'exécution mise à jour.

        Raises:
            CheckpointRefused: Si la raison manque, ou aux mêmes conditions que
                `record_step`.
        """
        if not (reason or "").strip():
            raise CheckpointRefused(
                f"Étape '{agent_id}' sautée sans raison : une étape franchie "
                "sans avoir tourné doit dire pourquoi, sinon elle se lit comme "
                "un succès."
            )
        return self.record_step(
            run_id, agent_id, ok=True, output="", subject=subject,
            skipped=reason.strip(),
        )

    def resume(self, run_id: str, subject: Optional[str] = None) -> WorkflowRun:
        """
        Reprend une exécution là où elle s'est arrêtée.

        **Aucune étape terminée n'est refaite.** Refaire une étape qui a déjà
        eu un effet au-dehors est la façon dont un courriel devient deux.

        Args:
            run_id: L'exécution.
            subject: Qui reprend.

        Returns:
            L'exécution, prête à repartir à `next_step()`.

        Raises:
            CheckpointRefused: Si elle est annulée, terminée, invisible, ou si
                le quota de reprises est atteint.
        """
        execution = self._exiger(run_id, subject)

        if execution.status is RunStatus.CANCELLED:
            raise CheckpointRefused(
                f"Exécution '{run_id}' annulée : elle ne reprend pas. Si elle "
                "reprenait, « annuler » voudrait dire « suspendre », et la "
                "différence compte exactement une fois — pour celui qui a "
                "annulé en croyant que cela s'arrêtait."
            )
        if execution.status is RunStatus.COMPLETED:
            raise CheckpointRefused(
                f"Exécution '{run_id}' terminée : toutes ses étapes ont abouti. "
                "La relancer serait refaire un travail déjà fait."
            )
        if execution.resumes >= REPRISES_MAXIMUM:
            raise CheckpointRefused(
                f"Exécution '{run_id}' : {execution.resumes} reprises déjà. "
                "Au-delà, ce n'est plus une panne passagère mais une étape qui "
                "ne passera jamais, et reprendre consomme sans avancer."
            )

        with self._verrou:
            execution.resumes += 1
            execution.status = RunStatus.RUNNING
            execution.updated_at = time.time()
        return execution

    def cancel(
        self, run_id: str, reason: str, subject: Optional[str] = None
    ) -> WorkflowRun:
        """
        Annule une exécution. **Terminal.**

        Args:
            run_id: L'exécution.
            reason: Pourquoi.
            subject: Qui annule.

        Returns:
            L'exécution annulée.

        Raises:
            CheckpointRefused: Si elle est inconnue, invisible, ou si la raison
                manque.
        """
        if not (reason or "").strip():
            raise CheckpointRefused(
                "Une annulation dit pourquoi : elle est définitive, et la "
                "raison est tout ce qui restera pour l'expliquer."
            )
        execution = self._exiger(run_id, subject)

        with self._verrou:
            execution.status = RunStatus.CANCELLED
            execution.cancelled_reason = reason.strip()
            execution.updated_at = time.time()
        return execution

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def get(self, run_id: str, subject: Optional[str] = None) -> Optional[WorkflowRun]:
        """Retourne une exécution visible par cette audience, ou `None`."""
        with self._verrou:
            execution = self._runs.get(run_id)
        if execution is None or not self._visible(execution, subject):
            return None
        return execution

    def _exiger(self, run_id: str, subject: Optional[str]) -> WorkflowRun:
        """Retourne une exécution visible, ou refuse."""
        execution = self.get(run_id, subject)
        if execution is None:
            # Le même message qu'une exécution inexistante : dire « elle existe
            # mais elle n'est pas à vous » renseignerait sur ce que quelqu'un
            # d'autre fait tourner.
            raise CheckpointRefused(f"Exécution '{run_id}' inconnue.")
        return execution

    @staticmethod
    def _visible(execution: WorkflowRun, subject: Optional[str]) -> bool:
        """Applique la frontière d'isolation (VOLET 40)."""
        if execution.subject is None:
            return True
        audience = Audience.user(subject) if subject else Audience.platform()
        return may_read(audience, Owner.user(execution.subject))[0]

    def list_runs(self, subject: Optional[str] = None) -> List[Dict[str, Any]]:
        """Les exécutions visibles, de la plus récente à la plus ancienne."""
        with self._verrou:
            toutes = list(self._runs.values())
        visibles = [e for e in toutes if self._visible(e, subject)]
        return [
            e.as_dict()
            for e in sorted(visibles, key=lambda e: e.started_at, reverse=True)
        ]

    def checkpoint_report(self, subject: Optional[str] = None) -> Dict[str, Any]:
        """
        L'état des exécutions pour une audience.

        Returns:
            Le décompte par statut et les règles tenues.
        """
        with self._verrou:
            visibles = [e for e in self._runs.values() if self._visible(e, subject)]
            oubliees = (self._oubliees, self._oubliees_reprenables)

        par_statut: Dict[str, int] = {}
        for execution in visibles:
            par_statut[execution.status.value] = par_statut.get(
                execution.status.value, 0
            ) + 1

        return {
            "runs": len(visibles),
            "by_status": par_statut,
            "resumable": [
                e.run_id for e in visibles
                if e.status.resumable and e.resumes < REPRISES_MAXIMUM
            ],
            "max_resumes": REPRISES_MAXIMUM,
            "max_step_output": TAILLE_MAXIMALE_ETAPE,
            "max_runs": self._maximum,
            # Comptés, pas déduits : une reprise devenue impossible parce que
            # son point de reprise a été élagué doit avoir une cause visible.
            "forgotten": oubliees[0],
            "forgotten_resumable": oubliees[1],
            "rules": [
                "Une étape terminée n'est jamais refaite : refaire une étape "
                "qui a eu un effet au-dehors est la façon dont un courriel "
                "devient deux.",
                "Une annulation est terminale — sinon « annuler » voudrait "
                "dire « suspendre ».",
                "Un point de reprise porte du travail réel : il appartient à "
                "qui a lancé l'exécution, et nul autre ne le reprend.",
                "Une sortie tronquée le dit ; elle ne l'est jamais en silence.",
            ],
        }
