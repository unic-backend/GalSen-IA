"""
Outil de journalisation pour GalSen IA.

Fournit une interface pour gérer les journaux de l'application (liste, ajout, suppression).
"""

from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

logger = __import__('logging').getLogger(__name__)


class LoggingTool(BaseTool):
    """Outil de gestion des journaux."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil de journalisation.

        Args:
            config: Configuration avec les clés optionnelles :
                    Aucune configuration spécifique pour l'instant.
        """
        super().__init__(config)
        # En mémoire, on stocke les journaux sous forme de liste de dictionnaires
        self._logs: List[Dict[str, Any]] = []
        logger.debug("LoggingTool initialisé.")

    def _op_list_logs(self, level: Optional[str] = None, limit: int = 100, **kwargs) -> List[Dict[str, Any]]:
        """
        Liste les journaux.

        Args:
            level: Filtrer par niveau (ex: "INFO", "ERROR") (optionnel).
            limit: Nombre maximum de journaux à retourner (défaut: 100).
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Liste de dictionnaires représentant les journaux.
        """
        filtered = self._logs
        if level:
            filtered = [log for log in self._logs if log.get("level") == level]
        # Retourner les plus récents en premier (comme dans les journaux)
        result = list(reversed(filtered))[:limit]
        return result

    def _op_add_log(self, message: str, level: str = "INFO", **kwargs) -> Dict[str, Any]:
        """
        Ajoute une entrée de journal.

        Args:
            message: Message du journal.
            level: Niveau du journal (ex: "INFO", "WARNING", "ERROR") (défaut: "INFO").
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Dictionnaire contenant le statut et l'ID de l'entrée ajoutée.
        """
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Le message du journal doit être une chaîne non vide")
        if not isinstance(level, str) or not level.strip():
            raise ValueError("Le niveau du journal doit être une chaîne non vide")

        log_entry = {
            "id": len(self._logs) + 1,  # simple ID incrémental
            "message": message.strip(),
            "level": level.upper(),
            "timestamp": __import__('datetime').datetime.now().isoformat(),
        }
        self._logs.append(log_entry)
        logger.debug(f"Journal ajouté: {log_entry}")
        return {
            "status": "success",
            "message": "Entrée de journal ajoutée avec succès.",
            "log_id": log_entry["id"],
        }

    def _op_clear_logs(self, **kwargs) -> Dict[str, Any]:
        """
        Efface tous les journaux.

        Args:
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Dictionnaire contenant le statut de l'effacement.
        """
        self._logs.clear()
        return {
            "status": "success",
            "message": "Tous les journaux ont été effacés.",
        }

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur l'outil de journalisation.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération.

        Raises:
            ValueError: Opération inconnue.
        """
        if not args:
            raise ValueError("Une opération est requise (list_logs, add_log, clear_logs)")

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
        return ["list_logs", "add_log", "clear_logs"]