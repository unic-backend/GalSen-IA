"""
Platform events that nobody would otherwise see.

The notification service already existed — a manager, two stores, templates,
deduplication, retention, six routes. What it had never been given is the one
thing wave III created: **events that happen while nobody is watching.**

A routine that disables itself after three consecutive failures does it at
three in the morning. A workflow that dies at its eighth agent leaves a
resumable checkpoint that no one knows exists. Both were written to the logs,
and a log is not a notification: it is read by someone who already suspects
something.

Four rules hold here.

**Only what asks for a decision or an action.** Not every routine turn, not
every successful run. A mailbox that receives everything buries the one message
that mattered — and the platform already had a name for that failure: a routine
skipped in silence appears to run and does nothing.

**The recipient is derived, never chosen.** It comes from the owner of the
routine or the run, exactly as the isolation boundary derives ownership from a
declared scope (VOLET 40). What belongs to the platform goes to the operators
by role, because the platform is nobody's private data.

**Notifying never breaks what it observes.** The notifier is a witness, not a
link in the chain. Every call is guarded, and a failure to notify is logged and
swallowed — the routine that just stopped has troubles enough.

**The message says what happened and what to do about it.** "Routine stopped"
is a fact; "stopped after 3 consecutive failures, re-enable it once the cause
is fixed" is something someone can act on at three in the morning.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .types import NotificationPriority, NotificationType

logger = logging.getLogger(__name__)

#: Rôle destinataire de ce qui appartient à la plateforme plutôt qu'à une
#: personne. L'exploitation est l'audience d'un incident sans propriétaire.
ROLE_EXPLOITATION = "admin"


class PlatformNotifier:
    """
    Traduit les événements silencieux de la plateforme en notifications.

    Enveloppe le gestionnaire existant ; n'en remplace aucune partie. Sans
    gestionnaire, chaque méthode ne fait rien et le dit une fois — un notifieur
    absent ne doit pas empêcher ce qu'il observe.
    """

    def __init__(self, manager: Any = None) -> None:
        """
        Args:
            manager: Le gestionnaire de notifications. `None` est accepté :
                l'appelant n'a pas à savoir si le service est monté.
        """
        self._manager = manager
        self._logger = logging.getLogger(f"{__name__}.PlatformNotifier")

    @property
    def available(self) -> bool:
        """Vrai si un gestionnaire est branché."""
        return self._manager is not None

    # ------------------------------------------------------------------
    # Routines
    # ------------------------------------------------------------------

    def routine_stopped(
        self, routine_id: str, reason: str, subject: Optional[str] = None,
    ) -> Optional[str]:
        """
        Une routine s'est arrêtée d'elle-même.

        C'est l'événement pour lequel ce module existe : une routine qui cesse
        de veiller sans que personne ne l'apprenne laisse croire qu'elle veille
        encore, ce qui est pire que d'échouer bruyamment.

        Args:
            routine_id: La routine arrêtée.
            reason: Pourquoi elle s'est arrêtée, telle que le planificateur l'a
                formulée.
            subject: Son propriétaire. `None` pour une routine de plateforme.

        Returns:
            L'identifiant de la notification, ou `None`.
        """
        return self._envoyer(
            NotificationType.TASK_FAILED,
            title=f"Routine « {routine_id} » arrêtée",
            message=(
                f"{reason} Elle ne tournera plus tant qu'elle n'aura pas été "
                "réactivée. Corrigez la cause, puis réactivez-la explicitement."
            ),
            priority=NotificationPriority.HIGH,
            subject=subject,
            source="routines",
            related_id=routine_id,
        )

    def routines_halted(self, engaged_by: str, reason: str) -> Optional[str]:
        """
        L'arrêt d'urgence a été engagé : plus aucune routine ne démarre.

        Adressé à l'exploitation, jamais à une personne : l'arrêt est global,
        et il vaut pour les routines de tout le monde.

        Args:
            engaged_by: Qui l'a engagé.
            reason: Pourquoi.

        Returns:
            L'identifiant de la notification, ou `None`.
        """
        return self._envoyer(
            NotificationType.SYSTEM,
            title="Arrêt d'urgence des routines engagé",
            message=(
                f"Engagé par « {engaged_by} » : {reason} Aucune routine ne "
                "démarrera tant qu'il ne sera pas levé explicitement — il "
                "n'expire pas de lui-même."
            ),
            priority=NotificationPriority.URGENT,
            subject=None,
            source="routines",
        )

    def routines_released(self, released_by: str) -> Optional[str]:
        """
        L'arrêt d'urgence a été levé.

        La levée se notifie autant que l'engagement : savoir que les routines
        ont repris fait partie de savoir ce qui tourne.

        Args:
            released_by: Qui l'a levé.

        Returns:
            L'identifiant de la notification, ou `None`.
        """
        return self._envoyer(
            NotificationType.SYSTEM,
            title="Arrêt d'urgence des routines levé",
            message=(
                f"Levé par « {released_by} ». Les routines actives reprennent "
                "à leur prochain tour dû."
            ),
            priority=NotificationPriority.NORMAL,
            subject=None,
            source="routines",
        )

    # ------------------------------------------------------------------
    # Exécutions longues
    # ------------------------------------------------------------------

    def workflow_interrupted(
        self, run_id: str, workflow_id: str, failing_agent: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> Optional[str]:
        """
        Une exécution s'est interrompue et peut être reprise.

        Sans cette notification, le point de reprise existe et personne ne sait
        qu'il existe : la reprise resterait une possibilité théorique.

        Args:
            run_id: L'exécution interrompue.
            workflow_id: Le workflow.
            failing_agent: L'agent sur lequel elle s'est arrêtée.
            subject: Qui l'a lancée.

        Returns:
            L'identifiant de la notification, ou `None`.
        """
        ou = f" à l'étape « {failing_agent} »" if failing_agent else ""
        return self._envoyer(
            NotificationType.TASK_FAILED,
            title=f"Exécution « {workflow_id} » interrompue",
            message=(
                f"L'exécution {run_id} s'est arrêtée{ou}. Les étapes déjà "
                "abouties ne seront pas refaites : reprenez-la avec "
                f"POST /workflow/runs/{run_id}/resume."
            ),
            priority=NotificationPriority.NORMAL,
            subject=subject,
            source="workflow",
            related_id=run_id,
        )

    # ------------------------------------------------------------------
    # Envoi
    # ------------------------------------------------------------------

    def _envoyer(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority,
        subject: Optional[str],
        source: str,
        related_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Envoie, sans jamais lever.

        Le destinataire est **déduit** du propriétaire : une personne reçoit ce
        qui lui appartient, et ce qui appartient à la plateforme part vers
        l'exploitation par son rôle. L'appelant ne choisit pas de destinataire.
        """
        if self._manager is None:
            return None
        try:
            return self._manager.send_notification(
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority,
                recipient=subject,
                role=None if subject else ROLE_EXPLOITATION,
                source=source,
                related_id=related_id,
            )
        except Exception as erreur:
            # Un témoin ne fait pas tomber ce qu'il observe.
            self._logger.warning("Notification non envoyée (%s) : %s", source, erreur)
            return None
