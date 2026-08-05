"""
Outil de calendrier pour GalSen IA.

Fournit une interface pour gérer des événements de calendrier (liste, ajout, suppression).
"""

from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

logger = __import__('logging').getLogger(__name__)


class CalendarTool(BaseTool):
    """
    Outil de gestion de calendrier.

    Opérations disponibles :
    - `get_events` (liste les événements)
    - `add_event` (ajoute un événement)
    - `delete_event` (supprime un événement par son identifiant)

    Exemple:
        tool.execute("get_events")
        tool.execute("add_event", title="Réunion", start="2026-08-01T10:00:00", end="2026-08-01T11:00:00")
        tool.execute("delete_event", event_id="123")
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil de calendrier.

        Args:
            config: Configuration avec les clés optionnelles :
                    Aucune configuration spécifique pour l'instant.
        """
        super().__init__(config)
        # En une implémentation réelle, nous initialiserions la connexion au service de calendrier ici.
        logger.debug("CalendrierTool initialisé.")

    def _op_get_events(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Liste les événements du calendrier.

        Args:
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Liste d'événements sous forme de dictionnaires.
        """
        # En une implémentation réelle, nous interrogerions le service de calendrier.
        # Pour cet exemple, nous retournons des données factices.
        return [
            {
                "id": "1",
                "title": "Réunion d'équipe",
                "start": "2026-08-01T09:00:00",
                "end": "2026-08-01T10:00:00",
            },
            {
                "id": "2",
                "title": "Déjeuner avec client",
                "start": "2026-08-01T12:00:00",
                "end": "2026-08-01T13:00:00",
            },
        ]

    def _op_add_event(self, title: str, start: str, end: str, **kwargs) -> Dict[str, Any]:
        """
        Ajoute un événement au calendrier.

        Args:
            title: Titre de l'événement.
            start: Date et heure de début (format ISO 8601).
            end: Date et heure de fin (format ISO 8601).
            **kwargs: Options supplémentaires (ex: description, location).

        Returns:
            Dictionnaire contenant le statut et l'ID de l'événement créé.
        """
        # Validation des entrées
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Le titre de l'événement doit être une chaîne non vide")
        if not isinstance(start, str) or not start:
            raise ValueError("La date de début doit être une chaîne non vide")
        if not isinstance(end, str) or not end:
            raise ValueError("La date de fin doit être une chaîne non vide")

        # En une implémentation réelle, nous envoie la requête au service de calendrier.
        # Pour cet exemple, nous générons un ID factice.
        event_id = "evt_" + str(hash(title + start + end))[-6:]

        return {
            "status": "success",
            "message": f"Événement '{title}' ajouté avec succès.",
            "event_id": event_id,
        }

    def _op_delete_event(self, event_id: str, **kwargs) -> Dict[str, Any]:
        """
        Supprime un événement du calendrier.

        Args:
            event_id: Identifiant de l'événement à supprimer.
            **kwargs: Options supplémentaires.

        Returns:
            Dictionnaire contenant le statut de la suppression.
        """
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("L'identifiant de l'événement doit être une chaîne non vide")

        # En une implémentation réelle, nous supprimerions l'événement du service de calendrier.
        return {
            "status": "success",
            "message": f"Événement '{event_id}' supprimé avec succès.",
        }

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur l'outil de calendrier.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération.

        Raises:
            ValueError: Opération inconnue.
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