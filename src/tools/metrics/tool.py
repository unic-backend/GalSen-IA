"""
Outil de métriques pour GalSen IA.

Fournit une interface simple pour collecter et récupérer des métriques
(compteurs, jauges, histogrammes) en mémoire.
"""

from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool

logger = __import__('logging').getLogger(__name__)


class MetricsTool(BaseTool):
    """Outil de collecte de métriques en mémoire."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialise l'outil de métriques.

        Args:
            config: Configuration avec les clés optionnelles :
                    Aucune configuration spécifique pour l'instant.
        """
        super().__init__(config)
        # Stockage en mémoire des métriques
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        logger.debug("MetricsTool initialisé.")

    def _op_increment(self, name: str, value: int = 1, **kwargs) -> Dict[str, Any]:
        """
        Incrémente un compteur.

        Args:
            name: Nom du compteur.
            value: Valeur à ajouter (défaut: 1).
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Dictionnaire avec le statut et la nouvelle valeur du compteur.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Le nom du compteur doit être une chaîne non vide")
        if not isinstance(value, int):
            raise ValueError("La valeur d'incrément doit être un entier")

        self._counters[name] = self._counters.get(name, 0) + value
        return {
            "status": "success",
            "metric": "counter",
            "name": name,
            "value": self._counters[name],
        }

    def _op_set_gauge(self, name: str, value: float, **kwargs) -> Dict[str, Any]:
        """
        Définit la valeur d'une jauge.

        Args:
            name: Nom de la jauge.
            value: Valeur à définir.
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Dictionnaire avec le statut et la nouvelle valeur de la jauge.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Le nom de la jauge doit être une chaîne non vide")
        if not isinstance(value, (int, float)):
            raise ValueError("La valeur de la jauge doit être un nombre")

        self._gauges[name] = float(value)
        return {
            "status": "success",
            "metric": "gauge",
            "name": name,
            "value": self._gauges[name],
        }

    def _op_record_histogram(self, name: str, value: float, **kwargs) -> Dict[str, Any]:
        """
        Enregistre une valeur dans un histogramme.

        Args:
            name: Nom de l'histogramme.
            value: Valeur à enregistrer.
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Dictionnaire avec le statut et le nombre d'échantillons enregistrés.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Le nom de l'histogramme doit être une chaîne non vide")
        if not isinstance(value, (int, float)):
            raise ValueError("La valeur de l'histogramme doit être un nombre")

        self._histograms.setdefault(name, []).append(float(value))
        return {
            "status": "success",
            "metric": "histogram",
            "name": name,
            "sample_count": len(self._histograms[name]),
        }

    def _op_get_metrics(self, **kwargs) -> Dict[str, Any]:
        """
        Récupère toutes les métriques collectées.

        Args:
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Dictionnaire contenant les compteurs, jauges et histogrammes.
        """
        # Calculer quelques statistiques pour les histogrammes
        histogram_stats: Dict[str, Dict[str, float]] = {}
        for name, values in self._histograms.items():
            if values:
                histogram_stats[name] = {
                    "count": len(values),
                    "sum": sum(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                }
            else:
                histogram_stats[name] = {"count": 0}

        return {
            "status": "success",
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "histograms": histogram_stats,
        }

    def _op_reset(self, **kwargs) -> Dict[str, Any]:
        """
        Réinitialise toutes les métriques.

        Args:
            **kwargs: Options supplémentaires (non utilisées actuellement).

        Returns:
            Dictionnaire avec le statut de la réinitialisation.
        """
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        return {
            "status": "success",
            "message": "Toutes les métriques ont été remises à zéro.",
        }

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur l'outil de métriques.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération.

        Raises:
            ValueError: Opération inconnue.
        """
        if not args:
            raise ValueError(
                "Une opération est requise (increment, set_gauge, record_histogram, "
                "get_metrics, reset)"
            )

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
        return ["increment", "set_gauge", "record_histogram", "get_metrics", "reset"]