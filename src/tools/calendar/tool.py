"""
Outil de calendrier pour GalSen IA.

Cet outil n'a aujourd'hui **aucun calendrier** derrière lui : aucun service
externe n'est raccordé. Il le dit, plutôt que d'inventer.

Auparavant, `get_events` retournait deux rendez-vous fabriqués (« Réunion
d'équipe », « Déjeuner avec client ») et `add_event` répondait `success` sans
rien créer. Un agent interrogeant l'agenda d'un utilisateur recevait donc des
rendez-vous imaginaires présentés comme réels — ce que le VOLET 01 chapitre 04
(*Truth and Knowledge Rules*) interdit, et qui est plus dangereux qu'une panne :
une panne se voit, une invention se croit.

Chaque opération retourne désormais `status: "unavailable"` avec sa raison, sur
le modèle de `context.generate()` quand aucun modèle n'est enregistré. La
validation des entrées, elle, est réelle et reste appliquée : une demande mal
formée est refusée avant même la question de la disponibilité.

Le raccordement à un vrai service passera par un connecteur calendrier
(`src/connectors/`, ADR-007), comme la messagerie.
"""

from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

logger = __import__('logging').getLogger(__name__)


class CalendarTool(BaseTool):
    """
    Outil de gestion de calendrier, sans service raccordé à ce jour.

    Opérations disponibles :
    - `get_events` (liste les événements)
    - `add_event` (ajoute un événement)
    - `delete_event` (supprime un événement par son identifiant)

    Tant qu'aucun connecteur calendrier n'est configuré, chaque opération
    retourne `status: "unavailable"` : l'appelant doit pouvoir constater
    l'absence de calendrier et se rabattre sur autre chose.

    Exemple:
        tool.execute("get_events")
        # {'status': 'unavailable', 'detail': "Aucun calendrier...", 'events': []}
    """

    UNAVAILABLE_DETAIL = (
        "Aucun calendrier n'est raccordé à cette installation. Un connecteur "
        "calendrier (src/connectors/, ADR-007) doit être configuré avant que les "
        "événements puissent être lus ou modifiés."
    )

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil de calendrier.

        Args:
            config: Configuration ; aucune clé n'est utilisée tant qu'aucun
                connecteur calendrier n'existe.
        """
        super().__init__(config)
        logger.debug("CalendarTool initialisé : aucun calendrier raccordé.")

    def _unavailable(self, **extra: Any) -> Dict[str, Any]:
        """Construit la réponse d'une opération impossible faute de calendrier."""
        response: Dict[str, Any] = {
            "status": "unavailable",
            "detail": self.UNAVAILABLE_DETAIL,
        }
        response.update(extra)
        return response

    def _op_get_events(self, **kwargs) -> Dict[str, Any]:
        """
        Liste les événements du calendrier.

        Args:
            **kwargs: Options de filtrage, sans effet tant qu'aucun calendrier
                n'est raccordé.

        Returns:
            Un dictionnaire portant `status`, une liste `events` vide et la
            raison. Jamais d'événement inventé.
        """
        logger.info("Lecture d'agenda demandée sans calendrier raccordé.")
        return self._unavailable(events=[])

    def _op_add_event(self, title: str, start: str, end: str, **kwargs) -> Dict[str, Any]:
        """
        Ajoute un événement au calendrier.

        La validation des entrées est réelle : une demande mal formée est refusée
        avant la question de la disponibilité, pour que l'appelant corrige
        d'abord ce qui dépend de lui.

        Args:
            title: Titre de l'événement.
            start: Date et heure de début (format ISO 8601).
            end: Date et heure de fin (format ISO 8601).
            **kwargs: Options supplémentaires (description, lieu).

        Returns:
            Un dictionnaire portant `status: "unavailable"` et la raison.

        Raises:
            ValueError: Si le titre, le début ou la fin sont invalides.
        """
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Le titre de l'événement doit être une chaîne non vide")
        if not isinstance(start, str) or not start:
            raise ValueError("La date de début doit être une chaîne non vide")
        if not isinstance(end, str) or not end:
            raise ValueError("La date de fin doit être une chaîne non vide")

        logger.info("Création d'événement demandée sans calendrier raccordé : %s", title)
        return self._unavailable(event_id=None)

    def _op_delete_event(self, event_id: str, **kwargs) -> Dict[str, Any]:
        """
        Supprime un événement du calendrier.

        Args:
            event_id: Identifiant de l'événement à supprimer.
            **kwargs: Options supplémentaires.

        Returns:
            Un dictionnaire portant `status: "unavailable"` et la raison.

        Raises:
            ValueError: Si l'identifiant est invalide.
        """
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("L'identifiant de l'événement doit être une chaîne non vide")

        logger.info("Suppression d'événement demandée sans calendrier raccordé : %s", event_id)
        return self._unavailable(deleted=False)

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur l'outil de calendrier.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération.

        Raises:
            ValueError: Opération inconnue ou absente.
        """
        if not args:
            raise ValueError("Une opération est requise (get_events, add_event, delete_event)")

        operation = str(args[0]).lower()
        operation_args = args[1:]

        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. "
                f"Opérations disponibles: {', '.join(self.available_operations())}"
            )

        return handler(*operation_args, **kwargs)

    def available_operations(self) -> List[str]:
        """Retourne la liste des opérations prises en charge."""
        return ["get_events", "add_event", "delete_event"]
