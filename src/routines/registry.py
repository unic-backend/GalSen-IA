"""
The routine registry: where a routine is checked, and where it is refused.

Everything expensive happens here, at declaration. Once a routine is in this
registry it is known to be composed only of tools that may run with nobody
watching — so the engine that fires it (phase 47.2) has nothing left to decide
and cannot decide it wrongly.

The check that matters reuses `may_run_unattended` from phase 38.1, and passes
it the **operation**, not just the tool name. That is what makes the refusal
precise rather than blunt: a routine running `python -m pytest` every night is
allowed, one running `python -c` is not, and both name the same tool.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from ..security.isolation import Audience, Owner, may_read
from ..tool.capabilities import (
    CapabilityRegistry,
    DataScope,
    load_capabilities,
    may_run_unattended,
)
from .types import (
    ACTIONS_MAXIMUM,
    INTERVALLE_MINIMAL_SECONDES,
    Routine,
    RoutineAction,
    RoutineRefused,
)
from .workflow_action import WorkflowAction, workflow_runnable_unattended


class RoutineRegistry:
    """
    Les routines déclarées, et les refus qui les ont filtrées.

    Thread-safe, en mémoire. La persistance suivra le même contrat ; ce qui
    compte ici est que rien n'entre sans avoir été vérifié.
    """

    def __init__(
        self,
        capabilities: Optional[CapabilityRegistry] = None,
        workflow_loader: Optional[Any] = None,
    ) -> None:
        """
        Args:
            capabilities: Le registre des capacités d'outils. Relu par défaut.
            workflow_loader: Le chargeur de workflows, pour les routines qui en
                déclenchent un (VOLET 64). Celui du dépôt par défaut, ouvert
                seulement si une telle action est déclarée.
        """
        self._verrou = threading.RLock()
        self._routines: Dict[str, Routine] = {}
        self._capacites = capabilities if capabilities is not None else load_capabilities()
        self._workflows = workflow_loader

    def _verifier_workflow(self, workflow_id: str) -> Tuple[bool, str]:
        """Dit si un workflow peut être déclenché sans témoin."""
        return workflow_runnable_unattended(workflow_id, self._workflows)

    # ------------------------------------------------------------------
    # Déclaration
    # ------------------------------------------------------------------

    def declare(
        self,
        routine_id: str,
        description: str,
        actions: List[RoutineAction],
        interval_seconds: int,
        subject: Optional[str] = None,
    ) -> Routine:
        """
        Déclare une routine, ou refuse en disant pourquoi.

        Args:
            routine_id: Son identifiant.
            description: Ce qu'elle fait, lisible par son propriétaire.
            actions: Les appels d'outils.
            interval_seconds: Le temps entre deux exécutions.
            subject: À qui elle appartient ; `None` pour la plateforme.

        Returns:
            La routine, **désactivée**. Déclarer n'est pas activer.

        Raises:
            RoutineRefused: Si quoi que ce soit ne va pas. Le message nomme la
                cause : une routine refusée sans motif est une routine que son
                auteur réécrira à l'identique.
        """
        identifiant = (routine_id or "").strip()
        if not identifiant:
            raise RoutineRefused("Une routine doit avoir un identifiant non vide.")
        if not (description or "").strip():
            raise RoutineRefused(
                f"Routine '{identifiant}' : une description est exigée. Elle "
                "sera lue par la personne à qui la routine appartient, au "
                "moment où elle se demandera pourquoi elle tourne."
            )
        if not actions:
            raise RoutineRefused(
                f"Routine '{identifiant}' : aucune action. Une routine qui ne "
                "fait rien consomme un créneau et ne se remarque jamais."
            )
        if len(actions) > ACTIONS_MAXIMUM:
            raise RoutineRefused(
                f"Routine '{identifiant}' : {len(actions)} actions, au-delà de "
                f"{ACTIONS_MAXIMUM}. Ce n'est plus une routine mais un "
                "workflow, qui a son propre moteur avec reprise et points de "
                "contrôle — choses qu'une routine n'a pas."
            )
        if int(interval_seconds) < INTERVALLE_MINIMAL_SECONDES:
            raise RoutineRefused(
                f"Routine '{identifiant}' : intervalle de {interval_seconds} s, "
                f"sous le plancher de {INTERVALLE_MINIMAL_SECONDES} s. Une "
                "routine trop fréquente est une attaque contre sa propre "
                "plateforme et contre ce qu'elle appelle."
            )

        self._verifier_actions(identifiant, actions, subject)

        with self._verrou:
            if identifiant in self._routines:
                raise RoutineRefused(
                    f"Routine '{identifiant}' déjà déclarée. Un doublon "
                    "silencieux ferait disparaître l'une des deux sans trace."
                )
            routine = Routine(
                routine_id=identifiant,
                description=description.strip(),
                actions=list(actions),
                interval_seconds=int(interval_seconds),
                subject=(subject or "").strip() or None,
                enabled=False,
                created_at=time.time(),
            )
            self._routines[identifiant] = routine
        return routine

    def _verifier_actions(
        self, routine_id: str, actions: List[RoutineAction], subject: Optional[str]
    ) -> None:
        """
        Vérifie que chaque action peut tourner sans témoin, et pour qui.

        Deux contrôles, dans cet ordre :

        1. **L'outil peut-il tourner sans personne devant ?** La question de la
           phase 38.1, posée avec l'**opération** : `python -m pytest` est
           pré-approuvé, `python -c` ne l'est pas, et les deux nomment le même
           outil.
        2. **Une routine de plateforme ne touche aucune donnée de personne.** À
           trois heures du matin il n'y a pas de session dont déduire un sujet,
           et lire la boîte de « personne en particulier » n'a pas de sens.

        Raises:
            RoutineRefused: Au premier problème, en le nommant.
        """
        audience = Audience.user(subject) if subject else Audience.platform()

        for position, action in enumerate(actions):
            if isinstance(action, WorkflowAction):
                # Un workflow ne se juge pas comme un outil : ce qui est
                # vérifiable à la déclaration est qu'il existe et que le
                # chargeur accepte de l'exécuter. Ce que le workflow fera au
                # moment venu relève de l'orchestrateur, qui a ses propres
                # gardes — les redoubler ici les ferait diverger.
                autorise, motif = self._verifier_workflow(action.workflow_id)
                if not autorise:
                    raise RoutineRefused(
                        f"Routine '{routine_id}', action {position + 1} "
                        f"(workflow) : {motif} Refuser à la déclaration vaut "
                        "mieux qu'échouer chaque nuit sans témoin."
                    )
                continue

            autorise, motif = may_run_unattended(
                action.tool_id, self._capacites, arguments=action.operation
            )
            if not autorise:
                raise RoutineRefused(
                    f"Routine '{routine_id}', action {position + 1} "
                    f"('{action.tool_id}') : {motif} Une routine tourne sans "
                    "personne devant ; refuser à la déclaration vaut mieux "
                    "qu'échouer chaque nuit sans témoin."
                )

            capacite = self._capacites.get(action.tool_id)
            if capacite.data_scope is DataScope.USER_PRIVATE:
                lisible, raison = may_read(audience, Owner.user(subject or "—")) \
                    if subject else (False, "")
                if not subject or not lisible:
                    raise RoutineRefused(
                        f"Routine '{routine_id}', action {position + 1} "
                        f"('{action.tool_id}') : cet outil atteint la donnée "
                        "d'une personne, et la routine n'en nomme aucune. À "
                        "trois heures du matin, il n'y a pas de session dont "
                        "déduire un propriétaire."
                    )

    # ------------------------------------------------------------------
    # Activation et lecture
    # ------------------------------------------------------------------

    def enable(self, routine_id: str) -> Routine:
        """
        Active une routine déclarée.

        Args:
            routine_id: Son identifiant.

        Returns:
            La routine active.

        Raises:
            RoutineRefused: Si elle est inconnue.
        """
        routine = self._exiger(routine_id)
        routine.enabled = True
        return routine

    def disable(self, routine_id: str) -> Routine:
        """
        Désactive une routine.

        Comme le retrait d'un consentement, cela doit toujours réussir : une
        routine qu'on ne peut pas arrêter est pire qu'une routine absente.
        """
        routine = self._exiger(routine_id)
        routine.enabled = False
        return routine

    def remove(self, routine_id: str) -> bool:
        """Retire une routine ; retourne False si elle était absente."""
        with self._verrou:
            return self._routines.pop((routine_id or "").strip(), None) is not None

    def get(self, routine_id: str) -> Optional[Routine]:
        """Retourne une routine, ou `None`."""
        with self._verrou:
            return self._routines.get((routine_id or "").strip())

    def _exiger(self, routine_id: str) -> Routine:
        """Retourne une routine ou refuse."""
        routine = self.get(routine_id)
        if routine is None:
            raise RoutineRefused(f"Routine '{routine_id}' inconnue.")
        return routine

    def counts(self) -> Dict[str, int]:
        """
        Combien de routines existent, sans dire lesquelles ni à qui.

        `list_routines()` filtre par audience, et c'est ce qu'il doit faire : la
        liste des routines de quelqu'un dit ce qu'il surveille. Un rapport
        d'orchestration a pourtant besoin de savoir *combien* il en existe.
        Les deux besoins sont séparés ici — des nombres, jamais des
        identifiants ni des propriétaires.

        Returns:
            Le nombre de routines déclarées, actives, et déclenchant un
            workflow.
        """
        with self._verrou:
            toutes = list(self._routines.values())

        return {
            "declared": len(toutes),
            "enabled": sum(1 for routine in toutes if routine.enabled),
            "running_a_workflow": sum(
                1 for routine in toutes
                if any(isinstance(action, WorkflowAction) for action in routine.actions)
            ),
        }

    def list_routines(self, subject: Optional[str] = None) -> List[Routine]:
        """
        Les routines, filtrées pour une audience.

        Une personne voit les siennes et celles de la plateforme, jamais celles
        d'une autre : la liste des routines de quelqu'un dit ce qu'il surveille.

        Args:
            subject: La personne ; `None` pour ne voir que celles de la
                plateforme.

        Returns:
            Les routines visibles, triées par identifiant.
        """
        audience = Audience.user(subject) if subject else Audience.platform()
        with self._verrou:
            toutes = list(self._routines.values())

        visibles = [
            routine for routine in toutes
            if routine.belongs_to_platform
            or may_read(audience, Owner.user(routine.subject))[0]
        ]
        return sorted(visibles, key=lambda routine: routine.routine_id)

    def enabled_routines(self) -> List[Routine]:
        """Les routines actives, triées. C'est ce que le moteur exécutera."""
        with self._verrou:
            actives = [r for r in self._routines.values() if r.enabled]
        return sorted(actives, key=lambda routine: routine.routine_id)

    def registry_report(self) -> Dict[str, Any]:
        """
        Ce que le registre contient, et ce qu'il refuse.

        Returns:
            Le décompte et les règles appliquées à la déclaration.
        """
        with self._verrou:
            toutes = list(self._routines.values())

        return {
            "declared": len(toutes),
            "enabled": sum(1 for routine in toutes if routine.enabled),
            "platform_routines": sum(1 for r in toutes if r.belongs_to_platform),
            "minimum_interval_seconds": INTERVALLE_MINIMAL_SECONDES,
            "maximum_actions": ACTIONS_MAXIMUM,
            "refuses_at_declaration": [
                "Un outil qui ne peut pas tourner sans témoin (phase 38.1).",
                "Un outil atteignant la donnée d'une personne, sans personne "
                "nommée.",
                "Un intervalle sous le plancher.",
                "Plus d'actions qu'une routine n'en porte — c'est un workflow.",
                "Une description vide : elle sera lue par son propriétaire.",
            ],
            "note": (
                "Déclarer n'est pas activer : une routine naît désactivée, "
                "comme une source au registre d'acquisition."
            ),
        }
