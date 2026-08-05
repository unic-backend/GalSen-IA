"""
Moniteur de santé pour le moteur de modèles GalSen IA.
"""

from typing import Dict, Any, Optional
from .types import ModelItem
from .interfaces import HealthMonitor
import time
import threading
from collections import deque, defaultdict


class RollingWindowHealthMonitor(HealthMonitor):
    """
    Moniteur de santé qui utilise une fenêtre glissante pour suivre les métriques
    de santé des modèles (latence, taux d'erreur, etc.).
    """

    def __init__(self, window_size: int = 100):
        """
        Initialise le moniteur de santé.

        Args:
            window_size: Taille de la fenêtre glissante pour le stockage des métriques
        """
        self._window_size = window_size
        # Structure: {model_id: {"latencies": deque, "successes": deque, "timestamps": deque}}
        self._metrics: dict = defaultdict(lambda: {
            "latencies": deque(maxlen=window_size),
            "successes": deque(maxlen=window_size),
            "timestamps": deque(maxlen=window_size)
        })
        self._lock = threading.RLock()

        # Seuils de santé (configurable via metadata dans une implémentation réelle)
        self._latency_threshold_ms = 5000  # 5 secondes
        self._error_rate_threshold = 0.5   # 50% d'erreurs

    def update_health(self, model_item: ModelItem, latency: float,
                     success: bool, error: Optional[str] = None) -> None:
        """
        Met à jour les métriques de santé d'un modèle.

        Args:
            model_item: Modèle dont mettre à jour la santé
            latency: Latence de la dernière sollicitation (en secondes)
            success: True si la sollicitation a réussi, False sinon
            error: Message d'erreur optionnel si la sollicitation a échoué
        """
        model_id = model_item.model_id
        timestamp = time.time()

        with self._lock:
            metrics = self._metrics[model_id]
            metrics["latencies"].append(latency)
            metrics["successes"].append(success)
            metrics["timestamps"].append(timestamp)

            # Mettre à jour le modèle lui-même si accessible
            # model_item.avg_latency = self._calculate_average_latency(model_id)
            # model_item.error_rate = self._calculate_error_rate(model_id)

    def get_health_status(self, model_item: ModelItem) -> Dict[str, Any]:
        """
        Récupère l'état de santé d'un modèle.

        Args:
            model_item: Modèle pour lequel obtenir l'état de santé

        Returns:
            Dictionnaire contenant les métriques de santé
        """
        model_id = model_item.model_id

        with self._lock:
            metrics = self._metrics.get(model_id, {
                "latencies": deque(),
                "successes": deque(),
                "timestamps": deque()
            })

            if not metrics["latencies"]:
                return {
                    "status": "unknown",
                    "sample_size": 0,
                    "average_latency_ms": 0.0,
                    "error_rate": 0.0,
                    "last_updated": None
                }

            avg_latency = self._calculate_average_latency(model_id)
            error_rate = self._calculate_error_rate(model_id)
            latest_timestamp = max(metrics["timestamps"]) if metrics["timestamps"] else None

            # Déterminer le statut global de santé
            status = self._determine_health_status(avg_latency, error_rate)

            return {
                "status": status,
                "sample_size": len(metrics["latencies"]),
                "average_latency_ms": avg_latency * 1000,  # Convertir en millisecondes
                "error_rate": error_rate,
                "last_updated": latest_timestamp,
                "is_healthy": status == "healthy"
            }

    def is_healthy(self, model_item: ModelItem) -> bool:
        """
        Vérifie si un modèle est en bonne santé.

        Args:
            model_item: Modèle à vérifier

        Returns:
            True si le modèle est en bonne santé, False sinon
        """
        health_status = self.get_health_status(model_item)
        return health_status.get("is_healthy", False)

    def _calculate_average_latency(self, model_id: str) -> float:
        """Calcule la latence moyenne pour un modèle."""
        with self._lock:
            latencies = self._metrics[model_id]["latencies"]
            if not latencies:
                return 0.0
            return sum(latencies) / len(latencies)

    def _calculate_error_rate(self, model_id: str) -> float:
        """Calcule le taux d'erreur pour un modèle."""
        with self._lock:
            successes = self._metrics[model_id]["successes"]
            if not successes:
                return 0.0
            failures = len([s for s in successes if not s])
            return failures / len(successes)

    def _determine_health_status(self, avg_latency: float, error_rate: float) -> str:
        """
        Détermine le statut de santé basé sur la latence et le taux d'erreur.

        Args:
            avg_latency: Latence moyenne en secondes
            error_rate: Taux d'erreur (0.0 à 1.0)

        Returns:
            Statut de santé: "healthy", "degraded" ou "unhealthy"
        """
        # Vérifier les seuils
        latency_exceeded = avg_latency > self._latency_threshold_ms / 1000.0
        error_exceeded = error_rate > self._error_rate_threshold

        if not latency_exceeded and not error_exceeded:
            return "healthy"
        elif latency_exceeded and error_exceeded:
            return "unhealthy"
        else:
            return "degraded"

    def reset_health(self, model_item: ModelItem) -> None:
        """
        Réinitialise les métriques de santé pour un modèle.

        Args:
            model_item: Modèle pour lequel réinitialiser les métriques
        """
        model_id = model_item.model_id
        with self._lock:
            if model_id in self._metrics:
                self._metrics[model_id] = {
                    "latencies": deque(maxlen=self._window_size),
                    "successes": deque(maxlen=self._window_size),
                    "timestamps": deque(maxlen=self._window_size)
                }

    def set_health_thresholds(self, latency_threshold_ms: float,
                             error_rate_threshold: float) -> None:
        """
        Définit les seuils de santé.

        Args:
            latency_threshold_ms: Seuil de latence en millisecondes
            error_rate_threshold: Seuil de taux d'erreur (0.0 à 1.0)
        """
        self._latency_threshold_ms = latency_threshold_ms
        self._error_rate_threshold = error_rate_threshold