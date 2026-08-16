"""
A render queue whose progress is counted and whose failures stay failed.

Directive §28 lists what a queue needs — progress, cancellation, retry,
priority, resource reservation, failure state, resumability — and every item is
a place where a queue can lie comfortably.

**Progress is the first one.** A percentage that moves smoothly is what a user
wants, so queues compute one from elapsed time against an estimate. It reaches
90 % and stays there. Here progress is `done / total` of a **counted** unit —
frames encoded, cues written — and a job whose total is unknown reports
`None` rather than a number. An unknown quantity is not 0 %, and it is certainly
not 90.

**A failure that a retry erases is a failure nobody investigates.** Attempts are
bounded, declared, and every one of them is kept with its error. A job that
succeeded on attempt three is not the same as a job that succeeded, and the
difference is what tells an operator that something is wrong upstream.

**Cancellation is terminal.** A cancelled job does not resume, because somebody
decided it should stop and a queue that quietly restarts it has overruled them.
That is not a new rule: `src/router/workflow_checkpoint.py` already made
`CANCELLED` terminal and `RUNNING`/`FAILED` resumable, and this module reuses
`RunStatus` rather than declaring a second vocabulary for the same idea — a
second one would drift, and this repository has already paid for that four
times.

Resource reservation is declared rather than enforced: nothing here can stop
another process from taking a GPU. A reservation records what a job *expects* to
need, so an operator can see two jobs claiming the same 12 GB before both fail.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...router.workflow_checkpoint import RunStatus

#: Les priorités déclarées. Un entier libre inviterait chaque appelant à
#: inventer la sienne, et la file finirait triée par surenchère.
PRIORITE_BASSE = 10
PRIORITE_NORMALE = 50
PRIORITE_HAUTE = 90
PRIORITES = (PRIORITE_BASSE, PRIORITE_NORMALE, PRIORITE_HAUTE)

#: Nombre maximal de tentatives. Déclaré : une reprise sans limite transforme
#: une panne durable en boucle silencieuse.
TENTATIVES_MAXIMUM = 3


class QueueRefused(ValueError):
    """Une opération de file impossible, avec sa raison."""


@dataclass
class RenderJob:
    """
    Un travail de rendu et tout ce qui permet d'en rendre compte.

    Attributes:
        job_id: Son identité.
        project_id: La production concernée.
        kind: Ce qu'il fait — `render`, `transcode`, `localise`.
        priority: Sa priorité, parmi `PRIORITES`.
        status: Son état, repris de `RunStatus`.
        total_units: Le nombre d'unités à traiter. `None` = inconnu.
        done_units: Les unités traitées.
        attempts: Les tentatives, chacune avec son issue.
        reserved: Ce que le travail **déclare** avoir besoin.
        submitted_at: Quand il a été soumis.
        output_path: Ce qu'il doit écrire.
    """

    job_id: str
    project_id: str = ""
    kind: str = "render"
    priority: int = PRIORITE_NORMALE
    status: RunStatus = RunStatus.RUNNING
    total_units: Optional[int] = None
    done_units: int = 0
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    reserved: Dict[str, Any] = field(default_factory=dict)
    submitted_at: float = 0.0
    output_path: str = ""

    def __post_init__(self) -> None:
        if self.priority not in PRIORITES:
            raise QueueRefused(
                f"Priorité {self.priority} non déclarée. Déclarées : "
                f"{list(PRIORITES)} — un entier libre ferait trier la file par "
                "surenchère."
            )
        if self.total_units is not None and self.total_units <= 0:
            raise QueueRefused(
                f"Total {self.total_units} : un travail sans unité à traiter "
                "n'a rien à faire, et l'accepter le ferait paraître terminé."
            )

    @property
    def progress(self) -> Optional[float]:
        """
        L'avancement réel, de 0 à 1, ou `None` quand le total est inconnu.

        `None` n'est pas 0 %. Une file qui calcule un pourcentage depuis le
        temps écoulé atteint 90 % et y reste — ce qu'un utilisateur voit alors
        n'est pas une mesure, c'est une animation.
        """
        if self.total_units is None:
            return None
        return round(min(self.done_units / self.total_units, 1.0), 4)

    @property
    def attempt_count(self) -> int:
        """Le nombre de tentatives déjà faites."""
        return len(self.attempts)

    @property
    def can_retry(self) -> bool:
        """
        Vrai si une reprise a encore un sens.

        Une annulation est **terminale** : quelqu'un a décidé d'arrêter, et une
        file qui redémarre en douce l'a contredit.
        """
        return self.status.resumable and self.attempt_count < TENTATIVES_MAXIMUM

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences comprises."""
        return {
            "job_id": self.job_id, "project_id": self.project_id,
            "kind": self.kind, "priority": self.priority,
            "status": self.status.value,
            "total_units": self.total_units, "done_units": self.done_units,
            "progress": self.progress,
            "attempts": list(self.attempts),
            "attempt_count": self.attempt_count,
            "can_retry": self.can_retry,
            "reserved": dict(self.reserved),
            "submitted_at": self.submitted_at,
            "output_path": self.output_path,
            "progress_note": (
                "Avancement compté en unités traitées."
                if self.total_units is not None else
                "Total inconnu : aucun pourcentage n'est rendu. Un inconnu "
                "n'est pas 0 %, et surtout pas 90 %."
            ),
        }


class RenderQueue:
    """
    La file des travaux de rendu.

    Les états viennent de `RunStatus` (`src/router/workflow_checkpoint.py`) :
    un second vocabulaire pour la même idée finirait par diverger, et ce dépôt
    a déjà payé quatre fois ce mode de défaillance.
    """

    def __init__(self, max_attempts: int = TENTATIVES_MAXIMUM) -> None:
        self._verrou = threading.RLock()
        self._jobs: Dict[str, RenderJob] = {}
        self._max = max(1, int(max_attempts))

    def submit(
        self, project_id: str = "", kind: str = "render",
        priority: int = PRIORITE_NORMALE, total_units: Optional[int] = None,
        reserved: Optional[Dict[str, Any]] = None, output_path: str = "",
    ) -> RenderJob:
        """
        Dépose un travail.

        Args:
            project_id: La production concernée.
            kind: Ce que le travail fait.
            priority: Sa priorité.
            total_units: Le nombre d'unités à traiter, s'il est connu.
            reserved: Ce que le travail déclare avoir besoin.
            output_path: Ce qu'il doit écrire.

        Returns:
            Le travail déposé, à l'état `RUNNING`.
        """
        job = RenderJob(
            job_id=f"job-{uuid.uuid4().hex[:12]}",
            project_id=project_id, kind=kind, priority=priority,
            total_units=total_units, reserved=dict(reserved or {}),
            submitted_at=time.time(), output_path=output_path,
        )
        with self._verrou:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Optional[RenderJob]:
        """Un travail par son identité."""
        with self._verrou:
            return self._jobs.get(job_id)

    def _exiger(self, job_id: str) -> RenderJob:
        """Retourne un travail ou refuse."""
        job = self.get(job_id)
        if job is None:
            raise QueueRefused(f"Travail « {job_id} » inconnu.")
        return job

    def next_job(self) -> Optional[RenderJob]:
        """
        Le prochain travail à exécuter : priorité, puis ordre de dépôt.

        Returns:
            Le travail, ou `None` si la file n'en a aucun d'exécutable. À
            priorité égale, le plus ancien passe — sinon un travail de priorité
            normale déposé le matin attendrait indéfiniment derrière ceux de
            l'après-midi.
        """
        with self._verrou:
            candidats = [
                job for job in self._jobs.values()
                if job.status is RunStatus.RUNNING
            ]
        if not candidats:
            return None
        return sorted(
            candidats, key=lambda job: (-job.priority, job.submitted_at),
        )[0]

    def advance(self, job_id: str, done_units: int) -> RenderJob:
        """
        Met à jour l'avancement **compté**.

        Raises:
            QueueRefused: Si l'avancement recule ou dépasse le total. Un
                avancement qui recule est un défaut de comptage, et le laisser
                passer rendrait la barre de progression menteuse dans les deux
                sens.
        """
        with self._verrou:
            job = self._exiger(job_id)
            if done_units < job.done_units:
                raise QueueRefused(
                    f"Avancement en recul ({job.done_units} → {done_units}) : "
                    "c'est un défaut de comptage, pas une progression."
                )
            if job.total_units is not None and done_units > job.total_units:
                raise QueueRefused(
                    f"{done_units} unités traitées pour un total de "
                    f"{job.total_units}."
                )
            job.done_units = done_units
            return job

    def record_attempt(
        self, job_id: str, outcome: str, error: str = "",
    ) -> RenderJob:
        """
        Consigne une tentative, réussie ou non.

        Args:
            job_id: Le travail.
            outcome: `succeeded` ou `failed`.
            error: L'erreur, quand il y en a une.

        Returns:
            Le travail. Chaque tentative est **conservée** : un travail qui a
            réussi à la troisième n'est pas un travail qui a réussi, et la
            différence est ce qui apprend à un exploitant que quelque chose ne
            va pas en amont.

        Raises:
            QueueRefused: Sur un travail annulé — il ne reprend pas.
        """
        with self._verrou:
            job = self._exiger(job_id)
            if job.status is RunStatus.CANCELLED:
                raise QueueRefused(
                    f"« {job_id} » a été annulé. Quelqu'un a décidé de "
                    "l'arrêter, et une file qui redémarre en douce l'a "
                    "contredit."
                )
            job.attempts.append({
                "at": time.time(), "outcome": outcome, "error": error,
                "attempt": job.attempt_count + 1,
            })
            if outcome == "succeeded":
                job.status = RunStatus.COMPLETED
            else:
                job.status = RunStatus.FAILED
            return job

    def retry(self, job_id: str) -> RenderJob:
        """
        Relance un travail échoué, dans la limite déclarée.

        Raises:
            QueueRefused: Après épuisement des tentatives, ou sur un travail
                annulé. Une reprise sans limite transforme une panne durable en
                boucle silencieuse — et l'échec, lui, reste consigné.
        """
        with self._verrou:
            job = self._exiger(job_id)
            if job.status is RunStatus.CANCELLED:
                raise QueueRefused(f"« {job_id} » a été annulé : il ne reprend pas.")
            if job.attempt_count >= self._max:
                raise QueueRefused(
                    f"« {job_id} » a épuisé ses {self._max} tentatives. Les "
                    f"échecs restent consignés : "
                    f"{[a.get('error', '') for a in job.attempts]}. Une reprise "
                    "sans limite transformerait une panne durable en boucle "
                    "silencieuse."
                )
            job.status = RunStatus.RUNNING
            return job

    def cancel(self, job_id: str, by: str = "") -> RenderJob:
        """
        Annule un travail. L'état est **terminal**.

        Args:
            job_id: Le travail.
            by: Qui annule.

        Returns:
            Le travail annulé, avec son avancement conservé — savoir qu'un
            travail a été arrêté à 80 % est une information.
        """
        with self._verrou:
            job = self._exiger(job_id)
            job.status = RunStatus.CANCELLED
            job.attempts.append({
                "at": time.time(), "outcome": "cancelled", "by": by,
                "attempt": job.attempt_count + 1,
            })
            return job

    def reservations(self) -> Dict[str, Any]:
        """
        Ce que les travaux en cours **déclarent** avoir besoin.

        Returns:
            La somme par ressource et les travaux qui la réclament. Rien n'est
            imposé : ce module ne peut empêcher aucun autre processus de prendre
            un GPU. Une réservation existe pour qu'un exploitant voie deux
            travaux réclamant les mêmes 12 Go **avant** qu'ils échouent tous les
            deux.
        """
        with self._verrou:
            actifs = [
                job for job in self._jobs.values()
                if job.status is RunStatus.RUNNING
            ]
        totaux: Dict[str, float] = {}
        for job in actifs:
            for ressource, quantite in job.reserved.items():
                if isinstance(quantite, (int, float)):
                    totaux[ressource] = totaux.get(ressource, 0.0) + quantite
        return {
            "active_jobs": [job.job_id for job in actifs],
            "declared_totals": {r: round(v, 3) for r, v in sorted(totaux.items())},
            "enforced": False,
            "note": (
                "Déclaratif, jamais imposé : ce module ne peut empêcher aucun "
                "autre processus de prendre un GPU. Il sert à voir deux "
                "travaux réclamant la même ressource avant qu'ils échouent "
                "tous les deux."
            ),
        }

    def report(self) -> Dict[str, Any]:
        """L'état de la file, sans rien arrondir."""
        with self._verrou:
            jobs = list(self._jobs.values())
        return {
            "count": len(jobs),
            "by_status": {
                etat.value: sum(1 for job in jobs if job.status is etat)
                for etat in RunStatus
            },
            "unknown_progress": [
                job.job_id for job in jobs if job.progress is None
            ],
            "retried": [
                job.job_id for job in jobs if job.attempt_count > 1
            ],
            "reservations": self.reservations(),
            "max_attempts": self._max,
        }


def queue_report() -> Dict[str, Any]:
    """
    Ce que la file garantit, et ce qu'elle refuse.

    Returns:
        Les priorités, les états, et les règles tenues.
    """
    return {
        "priorities": list(PRIORITES),
        "statuses": [etat.value for etat in RunStatus],
        "max_attempts": TENTATIVES_MAXIMUM,
        "rules": [
            "L'avancement est **compté** en unités traitées. Un total inconnu "
            "rend `None` : une file qui calcule un pourcentage depuis le temps "
            "écoulé atteint 90 % et y reste, et ce que l'utilisateur voit "
            "n'est plus une mesure mais une animation.",
            "Chaque tentative est conservée avec son erreur : un travail qui a "
            "réussi à la troisième n'est pas un travail qui a réussi.",
            "Les tentatives sont **bornées** — une reprise sans limite "
            "transforme une panne durable en boucle silencieuse.",
            "Une annulation est **terminale** : quelqu'un a décidé d'arrêter, "
            "et une file qui redémarre en douce l'a contredit.",
            "Les états viennent de `RunStatus` : un second vocabulaire pour la "
            "même idée finirait par diverger.",
            "Une réservation est **déclarative** : elle sert à voir un conflit "
            "avant qu'il fasse échouer deux travaux.",
        ],
        "does_not": [
            "Estimer un pourcentage depuis le temps écoulé.",
            "Effacer un échec en relançant.",
            "Reprendre un travail annulé.",
            "Laisser un avancement reculer.",
            "Imposer une réservation de ressource.",
        ],
    }
