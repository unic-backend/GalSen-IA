"""
Limiteur de taux pour le moteur de modèles GalSen IA.
"""

from typing import Dict, Any, Optional
from .types import ModelItem
from .interfaces import RateLimiter
import time
import threading
from collections import defaultdict


class TokenBucketRateLimiter(RateLimiter):
    """
    Limiteur de taux basé sur l'algorithme du seau à jetons (token bucket).
    """

    def __init__(self):
        """Initialise le limiteur de taux."""
        # Structure: {model_id: {"tokens": float, "last_update": float, "capacity": float, "fill_rate": float}}
        self._buckets: Dict[str, Dict[str, float]] = {}
        self._lock = threading.RLock()

        # Limites de taux par défaut (requêtes par minute)
        # Dans une implémentation réelle, ces valeurs viendraient de la configuration du modèle ou des limites API
        self._default_rpm = {
            # OpenAI (valeurs estimées, varient selon le niveau)
            "openai_gpt4": 500,
            "openai_gpt35": 3500,
            # Anthropic
            "anthropic_claude3_opus": 50,
            "anthropic_claude3_sonnet": 1000,
            "anthropic_claude3_haiku": 1000,
            # Google
            "google_gemini_pro": 300,
            "google_gemini_ultra": 100,
            # Valeur par défaut
            "default": 60
        }

    def _get_rpm_limit(self, model_item: ModelItem) -> int:
        """
        Obtient la limite de requêtes par minute pour un modèle.

        Args:
            model_item: Modèle pour lequel obtenir la limite

        Returns:
            Limite de requêtes par minute
        """
        # Essayer d'obtenir la limite depuis les métadonnées du modèle
        custom_rpm = model_item.metadata.get("rpm_limit")
        if isinstance(custom_rpm, int) and custom_rpm > 0:
            return custom_rpm

        # Essayer de déduire à partir du type de modèle
        model_key = f"{model_item.provider}_{model_item.model_type.value}".lower()
        if model_key in self._default_rpm:
            return self._default_rpm[model_key]

        # Retourner la limite par défaut
        return self._default_rpm["default"]

    def _get_bucket(self, model_id: str) -> Dict[str, float]:
        """
        Obtient ou crée le seau à jetons pour un modèle.

        Args:
            model_id: Identifiant du modèle

        Returns:
            Dictionnaire représentant le seau à jetons
        """
        if model_id not in self._buckets:
            # Initialiser le seau avec sa capacité maximale
            # Nous aurions besoin du modèle pour déterminer la limite RPM,
            # mais ici nous utilisons une valeur par défaut et mettrons à jour lors du premier appel
            self._buckets[model_id] = {
                "tokens": 1.0,  # Commencer avec un jeton disponible
                "last_update": time.time(),
                "capacity": 1.0,  # Sera mis à jour lors du premier appel à can_execute
                "fill_rate": 1.0  # Sera mis à jour lors du premier appel à can_execute
            }
        return self._buckets[model_id]

    def can_execute(self, model_item: ModelItem) -> bool:
        """
        Vérifie si une exécution est autorisée selon les limites de taux.

        Args:
            model_item: Modèle pour lequel vérifier la limite

        Returns:
            True si l'exécution est autorisée, False sinon
        """
        model_id = model_item.model_id

        with self._lock:
            bucket = self._get_bucket(model_id)
            now = time.time()

            # Mettre à jour le taux de remplissage basé sur la limite RPM
            rpm_limit = self._get_rpm_limit(model_item)
            # Convertir RPM en remplissage par seconde
            fill_rate = rpm_limit / 60.0  # requêtes par seconde

            # Mettre à jour la capacité et le taux de remplissage du seau
            bucket["capacity"] = float(rpm_limit)  # Capacité maximale = RPM
            bucket["fill_rate"] = fill_rate

            # Calculer le temps écoulé depuis la dernière mise à jour
            time_passed = now - bucket["last_update"]
            # Ajouter de nouveaux jetons basés sur le temps écoulé
            new_tokens = time_passed * bucket["fill_rate"]
            # Limiter le nombre de jetons à la capacité du seau
            bucket["tokens"] = min(bucket["capacity"], bucket["tokens"] + new_tokens)
            bucket["last_update"] = now

            # Vérifier s'il y a suffisamment de jetons pour une requête (coût de 1 jeton par requête)
            if bucket["tokens"] >= 1.0:
                # Consommer un jeton
                bucket["tokens"] -= 1.0
                return True
            else:
                return False

    def wait_if_needed(self, model_item: ModelItem) -> float:
        """
        Attend si nécessaire pour respecter les limites de taux.

        Args:
            model_item: Modèle pour lequel vérifier l'attente

        Returns:
            Temps d'attente en secondes (0 si pas d'attente nécessaire)
        """
        if self.can_execute(model_item):
            return 0.0

        # Calculer combien de temps attendre pour obtenir suffisamment de jetons
        model_id = model_item.model_id
        with self._lock:
            bucket = self._get_bucket(model_id)
            # Nous avons besoin d'au moins 1 jeton
            needed_tokens = 1.0 - bucket["tokens"]
            if needed_tokens <= 0:
                return 0.0

            # Temps nécessaire pour accumuler les jetons manquants
            wait_time = needed_tokens / bucket["fill_rate"]
            return max(0.0, wait_time)

    def reset_limits(self, model_item: ModelItem) -> None:
        """
        Réinitialise les limites de taux pour un modèle.

        Args:
            model_item: Modèle pour lequel réinitialiser les limites
        """
        model_id = model_item.model_id
        with self._lock:
            if model_id in self._buckets:
                # Réinitialiser le seau à son état initial
                self._buckets[model_id] = {
                    "tokens": 1.0,
                    "last_update": time.time(),
                    "capacity": 1.0,  # Sera mis à jour lors du prochain appel
                    "fill_rate": 1.0   # Sera mis à jour lors du prochain appel
                }

    def get_current_rate(self, model_item: ModelItem) -> float:
        """
        Obtient le taux d'utilisation actuel pour un modèle.

        Args:
            model_item: Modèle pour lequel obtenir le taux d'utilisation

        Returns:
            Taux d'utilisation actuel (requêtes par minute)
        """
        model_id = model_item.model_id
        with self._lock:
            bucket = self._get_bucket(model_id)
            now = time.time()
            time_passed = max(now - bucket["last_update"], 0.001)  # Éviter division par zéro

            # Estimer le taux d'utilisation basé sur la consommation de jetons
            # Ceci est une approximation - dans une implémentation réelle, nous suivrions explicitement les requêtes
            used_tokens = (bucket["capacity"] - bucket["tokens"]) if bucket["tokens"] < bucket["capacity"] else 0
            # Convertir les jetons utilisés en taux RPM approximatif
            # Cette estimation est très approximative et devrait être remplacée par un suivi réel
            estimated_rpm = (used_tokens / time_passed) * 60 if time_passed > 0 else 0
            return min(estimated_rpm, self._get_rpm_limit(model_item) * 2)  # Plafonner à 2x la limite