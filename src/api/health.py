"""
Module de vérification de santé pour l'API GalSen IA.

Fournit des points de terminaison de health check pour Kubernetes et le monitoring,
avec vérification de tous les composants de la plateforme.

Conçu pour une intégration future avec Prometheus/Grafana : l'interface
HealthChecker permet de remplacer ou d'étendre les vérifications sans
modifier le code appelant.

Endpoints :
    GET /health — Rapport de santé détaillé de tous les composants
    GET /ready  — Test de readiness (l'application peut-elle servir ?)
    GET /live   — Test de liveness (le processus est-il vivant ?)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import logging
import threading
import time
from src.storage.paths import declared_backend, storage_backend

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modèles de données
# ---------------------------------------------------------------------------


@dataclass
class ComponentHealth:
    """État de santé d'un composant individuel.

    Attributs :
        status: "healthy", "degraded" ou "unhealthy"
        details: Informations supplémentaires spécifiques au composant
        error: Message d'erreur en cas de problème (None si tout va bien)
    """

    status: str
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class HealthReport:
    """Rapport de santé complet de la plateforme.

    Attributs :
        status: Statut global — "healthy", "degraded" ou "unhealthy"
        timestamp: Horodatage Unix de la vérification
        version: Version de l'application
        uptime: Temps écoulé depuis le démarrage (en secondes)
        components: État de chaque composant vérifié
        storage_backend: Backend de stockage utilisé
        configured_providers: Liste des fournisseurs de modèles configurés
    """

    status: str
    timestamp: float
    version: str
    uptime: float
    components: Dict[str, ComponentHealth]
    storage_backend: str
    configured_providers: List[str]
    subsystems: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit le rapport en dictionnaire pour la réponse JSON."""
        components_dict: Dict[str, Dict[str, Any]] = {}
        for name, comp in self.components.items():
            entry: Dict[str, Any] = {"status": comp.status}
            entry.update(comp.details)
            if comp.error:
                entry["error"] = comp.error
            components_dict[name] = entry

        rendu = {
            "status": self.status,
            "timestamp": self.timestamp,
            "version": self.version,
            "uptime": self.uptime,
            "components": components_dict,
            "storage_backend": self.storage_backend,
            "configured_providers": self.configured_providers,
        }
        if self.subsystems is not None:
            # Les sous-systèmes construits après le registre des moteurs
            # (VOLETs 47 à 64). Ils vivent dans une section à part parce qu'ils
            # ne pèsent pas sur le statut global : un sous-système dégradé
            # fonctionne comme prévu, et l'ajouter aux composants ferait passer
            # la plateforme en `degraded` chaque fois qu'un canal externe n'a
            # pas d'identifiants — c'est-à-dire toujours.
            rendu["subsystems"] = self.subsystems
        return rendu


# ---------------------------------------------------------------------------
# Interface abstraite
# ---------------------------------------------------------------------------


class HealthChecker(ABC):
    """Interface abstraite pour le vérificateur de santé.

    Conçue pour permettre le remplacement par une implémentation distribuée
    (ex. Redis) ou par un collecteur Prometheus/Grafana sans modifier
    le code appelant.
    """

    @abstractmethod
    def check_health(self, include_subsystems: bool = False) -> HealthReport:
        """Exécute toutes les vérifications et retourne un rapport complet.

        Args:
            include_subsystems: Sonde aussi les sous-systèmes des VOLETs 47 à
                64. Hors du défaut parce que la supervision interroge `/health`
                sans arrêt : la sonde complète coûte ~70 ms, la cible en est 50.

        Returns:
            HealthReport avec l'état de chaque composant et le statut global.
        """
        ...

    @abstractmethod
    def check_readiness(self) -> Tuple[bool, str]:
        """Vérifie si l'application est prête à servir des requêtes.

        Returns:
            Tuple (est_prêt, raison).
        """
        ...

    @abstractmethod
    def check_liveness(self) -> bool:
        """Vérifie si l'application est vivante (test minimal).

        Returns:
            True si le processus répond.
        """
        ...


# ---------------------------------------------------------------------------
# Implémentation concrète
# ---------------------------------------------------------------------------


class ComponentHealthChecker(HealthChecker):
    """Vérificateur de santé des composants de la plateforme.

    Vérifie chaque composant (API, moteurs, stockage, fournisseurs) de manière
    indépendante et agrège les résultats. Un composant défaillant ne bloque pas
    la vérification des autres.

    Les moteurs sont optionnels : si une référence est None, le composant
    correspondant est marqué comme "unhealthy".
    """

    # Composants considérés comme requis pour la readiness
    REQUIRED_COMPONENTS = ("api", "tool_engine")

    def __init__(
        self,
        start_time: float,
        version: str,
        memory_manager: Any = None,
        model_manager: Any = None,
        knowledge_manager: Any = None,
        tool_engine: Any = None,
    ):
        """Initialise le vérificateur de santé.

        Args:
            start_time: Horodatage de démarrage de l'application (time.time())
            version: Version de l'application
            memory_manager: Instance du gestionnaire de mémoire (optionnel)
            model_manager: Instance du gestionnaire de modèles (optionnel)
            knowledge_manager: Instance du gestionnaire de connaissances (optionnel)
            tool_engine: Instance du moteur d'outils (optionnel)
        """
        self._start_time = start_time
        self._version = version
        self._memory_manager = memory_manager
        self._model_manager = model_manager
        self._knowledge_manager = knowledge_manager
        self._tool_engine = tool_engine

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def check_health(self, include_subsystems: bool = False) -> HealthReport:
        """Vérifie la santé de tous les composants de la plateforme.

        Chaque composant est vérifié indépendamment ; une défaillance dans l'un
        n'empêche pas la vérification des autres.

        Args:
            include_subsystems: Sonde aussi les neuf sous-systèmes des VOLETs 47
                à 64. **Hors du défaut, et mesuré** : la sonde complète coûte
                environ 70 ms, pour une cible de supervision de 50 ms. Une
                supervision qui interroge `/health` toutes les cinq secondes
                paierait, chaque fois, la lecture de la connaissance mondiale et
                la validation des workflows — pour une information qui change
                quelques fois par mois.

        Returns:
            HealthReport complet avec le statut global et le détail par composant.
        """
        components = {
            "api": self._check_api(),
            "memory_engine": self._check_memory_engine(),
            "model_engine": self._check_model_engine(),
            "knowledge_engine": self._check_knowledge_engine(),
            "tool_engine": self._check_tool_engine(),
            "storage": self._check_storage(),
            "connectors": self._check_connectors(),
        }

        overall = self._compute_overall_status(components.values())

        return HealthReport(
            status=overall,
            timestamp=time.time(),
            version=self._version,
            uptime=time.time() - self._start_time,
            components=components,
            storage_backend=self._get_storage_backend(),
            configured_providers=self._get_configured_providers(),
            subsystems=self._check_subsystems() if include_subsystems else None,
        )

    @staticmethod
    def _check_subsystems() -> Optional[Dict[str, Any]]:
        """Interroge les sous-systèmes construits après le registre des moteurs.

        Ils n'entrent pas dans le statut global : « dégradé » y veut dire « il
        dit ce qui lui manque et continue », pas « en panne ». Les compter
        comme des composants ferait sonner l'alarme en permanence, et une
        alarme toujours allumée n'est plus lue.

        Returns:
            Le rapport de dégradation, ou None s'il n'a pas pu être calculé —
            `/health` ne tombe pas parce qu'une section refuse de se calculer.
        """
        try:
            from src.integration.degradation import degradation_report

            return degradation_report()
        except Exception as erreur:
            logger.warning("Rapport de dégradation indisponible : %s", erreur)
            return None

    def check_readiness(self) -> Tuple[bool, str]:
        """Vérifie si l'application est prête à servir des requêtes.

        L'application est prête si tous les composants requis
        (API et moteur d'outils) sont disponibles.

        Returns:
            Tuple (est_prêt, raison).
        """
        report = self.check_health()

        for name in self.REQUIRED_COMPONENTS:
            component = report.components.get(name)
            if component is not None and component.status == "unhealthy":
                error = component.error or "composant non disponible"
                return False, f"Composant requis '{name}' non disponible : {error}"

        return True, "Tous les composants requis sont disponibles"

    def check_liveness(self) -> bool:
        """Vérifie si l'application est vivante.

        Test minimal : si cette méthode peut s'exécuter, le processus est vivant.

        Returns:
            Toujours True.
        """
        return True

    # ------------------------------------------------------------------
    # Setter pour les références tardives (ex: tool_engine après startup)
    # ------------------------------------------------------------------

    def set_tool_engine(self, tool_engine: Any) -> None:
        """Met à jour la référence au moteur d'outils.

        Utile lorsque le moteur d'outils est initialisé après le démarrage
        de l'application (dans l'événement startup de FastAPI).

        Args:
            tool_engine: Instance du moteur d'outils initialisé.
        """
        self._tool_engine = tool_engine
        logger.info("Référence au moteur d'outils mise à jour dans le vérificateur de santé")

    # ------------------------------------------------------------------
    # Vérifications par composant
    # ------------------------------------------------------------------

    @staticmethod
    def _check_api() -> ComponentHealth:
        """Vérifie l'API (toujours saine si elle répond)."""
        return ComponentHealth(
            status="healthy",
            details={"message": "API opérationnelle"},
        )

    def _check_memory_engine(self) -> ComponentHealth:
        """Vérifie le moteur de mémoire.

        Tente d'écrire puis de lire un élément de test pour valider
        le fonctionnement complet du cycle écriture/lecture.
        """
        if self._memory_manager is None:
            return ComponentHealth(
                status="unhealthy",
                error="Gestionnaire de mémoire non initialisé",
            )

        try:
            # Import local pour éviter les dépendances circulaires
            from src.memory_engine.types import MemoryItem  # noqa: E402

            test_item = MemoryItem(
                content="health_check_test",
                memory_type="short_term",
                tags=["health_check"],
            )
            item_id = self._memory_manager.save_memory(test_item)
            retrieved = self._memory_manager.get_memory(item_id)

            if retrieved is not None and retrieved.content == "health_check_test":
                # Nettoyer l'élément de test
                try:
                    self._memory_manager.delete_memory(item_id)
                except Exception:
                    pass  # Le nettoyage n'est pas critique

                return ComponentHealth(
                    status="healthy",
                    details={"message": "Moteur de mémoire opérationnel"},
                )
            else:
                return ComponentHealth(
                    status="degraded",
                    details={"message": "Moteur de mémoire partiellement fonctionnel"},
                    error="La lecture de l'élément de test a retourné des données inattendues",
                )
        except Exception as e:
            logger.warning("Échec de la vérification du moteur de mémoire : %s", e)
            return ComponentHealth(
                status="unhealthy",
                error=f"Échec de la vérification : {str(e)}",
            )

    def _check_model_engine(self) -> ComponentHealth:
        """Vérifie le moteur de modèles.

        Consulte l'état des fournisseurs pour déterminer si le moteur
        peut fonctionner.
        """
        if self._model_manager is None:
            return ComponentHealth(
                status="unhealthy",
                error="Gestionnaire de modèles non initialisé",
            )

        try:
            provider_status = self._model_manager.get_provider_status()
            available_providers = sum(
                1 for info in provider_status.values()
                if info.get("available", False)
            )
            total_providers = len(provider_status)

            details = {
                "message": "Moteur de modèles opérationnel",
                "total_providers": total_providers,
                "available_providers": available_providers,
            }

            if total_providers == 0:
                return ComponentHealth(
                    status="degraded",
                    details=details,
                    error="Aucun fournisseur de modèles configuré",
                )
            elif available_providers == 0:
                return ComponentHealth(
                    status="degraded",
                    details=details,
                    error="Aucun fournisseur de modèles disponible",
                )
            else:
                return ComponentHealth(
                    status="healthy",
                    details=details,
                )
        except Exception as e:
            logger.warning("Échec de la vérification du moteur de modèles : %s", e)
            return ComponentHealth(
                status="unhealthy",
                error=f"Échec de la vérification : {str(e)}",
            )

    def _check_knowledge_engine(self) -> ComponentHealth:
        """Vérifie le moteur de connaissances.

        Utilise la méthode get_stats() pour vérifier que le moteur répond.
        """
        if self._knowledge_manager is None:
            return ComponentHealth(
                status="unhealthy",
                error="Gestionnaire de connaissances non initialisé",
            )

        try:
            stats = self._knowledge_manager.get_stats()

            store_count = 0
            if isinstance(stats, dict) and "store" in stats:
                store_count = stats["store"].get("total_items", 0)

            return ComponentHealth(
                status="healthy",
                details={
                    "message": "Moteur de connaissances opérationnel",
                    "total_items": store_count,
                },
            )
        except Exception as e:
            logger.warning("Échec de la vérification du moteur de connaissances : %s", e)
            return ComponentHealth(
                status="unhealthy",
                error=f"Échec de la vérification : {str(e)}",
            )

    def _check_tool_engine(self) -> ComponentHealth:
        """Vérifie le moteur d'outils.

        Vérifie que le moteur est initialisé et capable de lister les outils.
        """
        if self._tool_engine is None:
            return ComponentHealth(
                status="unhealthy",
                error="Moteur d'outils non initialisé (démarrage en cours ou échec)",
            )

        try:
            tools = self._tool_engine.list_tools()
            tools_count = len(tools) if tools else 0
            return ComponentHealth(
                status="healthy",
                details={
                    "message": "Moteur d'outils opérationnel",
                    "tools_count": tools_count,
                },
            )
        except Exception as e:
            logger.warning("Échec de la vérification du moteur d'outils : %s", e)
            return ComponentHealth(
                status="unhealthy",
                error=f"Échec de la vérification : {str(e)}",
            )

    @staticmethod
    def _check_storage() -> ComponentHealth:
        """Vérifie la configuration du backend de stockage."""
        declare = declared_backend()
        backend = storage_backend()

        if declare == backend:
            return ComponentHealth(
                status="healthy",
                details={
                    "message": f"Stockage configuré : {backend}",
                    "backend": backend,
                },
            )
        else:
            # La valeur déclarée n'est pas appliquée. Le rapport nomme les deux :
            # savoir ce qui s'applique **à la place** est ce qui permet d'agir.
            return ComponentHealth(
                status="degraded",
                details={"backend": declare, "effective_backend": backend},
                error=f"Backend de stockage inconnu : {backend}",
            )

    # ------------------------------------------------------------------
    # Méthodes privées
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_overall_status(components) -> str:
        """Détermine le statut global à partir des statuts de chaque composant.

        Règles :
            - Si au moins un composant est "unhealthy" → "unhealthy"
            - Sinon, si au moins un composant est "degraded" → "degraded"
            - Sinon → "healthy"
        """
        statuses = [c.status for c in components]
        if "unhealthy" in statuses:
            return "unhealthy"
        if "degraded" in statuses:
            return "degraded"
        return "healthy"

    def _check_connectors(self) -> ComponentHealth:
        """Rapporte l'état des connecteurs externes (VOLET 10, chapitre 06).

        Règle qui décide de tout ici : **un connecteur non configuré ne rend pas
        la plateforme malsaine.** La plupart des déploiements n'en configurent
        aucun, et faire passer `/health` en `degraded` pour un SMTP absent
        rendrait l'indicateur inutilisable — il serait rouge en permanence, donc
        ignoré. Seul un connecteur configuré *et* en erreur dégrade la santé.

        Cette vérification ne contacte personne : elle lit la configuration.
        `/connectors/status` est la route qui sollicite les services distants.
        """
        try:
            from src.connectors import get_shared_connector_registry

            registre = get_shared_connector_registry()
            resume = registre.check_all()
        except Exception as error:  # pragma: no cover - chemin de secours
            return ComponentHealth(
                status="degraded",
                details={"reason": "registre de connecteurs illisible"},
                error=str(error),
            )

        par_statut = resume.get("by_status", {})
        en_erreur = par_statut.get("error", 0) + par_statut.get("unreachable", 0)

        return ComponentHealth(
            status="degraded" if en_erreur else "healthy",
            details={
                "total": resume.get("total", 0),
                "ready": resume.get("ready", 0),
                "by_status": par_statut,
                # Dit explicitement pourquoi « non configuré » ne dégrade rien,
                # pour qu'un opérateur ne cherche pas une panne inexistante.
                "note": (
                    "un connecteur non configuré est normal et ne dégrade pas la "
                    "santé ; seul un connecteur configuré et en erreur le fait"
                ),
            },
        )

    @staticmethod
    def _get_storage_backend() -> str:
        """Détecte le backend de stockage utilisé."""
        return storage_backend()

    def _get_configured_providers(self) -> List[str]:
        """Retourne la liste des fournisseurs de modèles configurés."""
        if self._model_manager is None:
            return []
        try:
            provider_status = self._model_manager.get_provider_status()
            return sorted(provider_status.keys())
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Factory (singleton, pattern identique au limiteur de taux)
# ---------------------------------------------------------------------------

_health_checker: Optional[HealthChecker] = None
_lock = threading.RLock()


def get_health_checker() -> HealthChecker:
    """Retourne le vérificateur de santé (singleton).

    Le vérificateur doit d'abord être initialisé via ``init_health_checker()``.
    Lève ``RuntimeError`` si le vérificateur n'a pas encore été configuré.

    Returns:
        L'instance unique du vérificateur de santé.

    Raises:
        RuntimeError: Si ``init_health_checker()`` n'a pas été appelé au préalable.
    """
    with _lock:
        if _health_checker is None:
            raise RuntimeError(
                "Le vérificateur de santé n'a pas été initialisé. "
                "Appelez init_health_checker() au démarrage de l'application."
            )
        return _health_checker


def init_health_checker(
    start_time: float,
    version: str,
    memory_manager: Any = None,
    model_manager: Any = None,
    knowledge_manager: Any = None,
    tool_engine: Any = None,
) -> HealthChecker:
    """Initialise le vérificateur de santé avec les instances des moteurs.

    Doit être appelé une seule fois au démarrage de l'application.
    Les appels suivants retournent l'instance existante (idempotent).

    Pattern singleton avec double-checked locking, identique au limiteur de taux.

    Args:
        start_time: Horodatage de démarrage (time.time())
        version: Version de l'application
        memory_manager: Instance du gestionnaire de mémoire
        model_manager: Instance du gestionnaire de modèles
        knowledge_manager: Instance du gestionnaire de connaissances
        tool_engine: Instance du moteur d'outils

    Returns:
        L'instance unique du vérificateur de santé.
    """
    global _health_checker
    with _lock:
        if _health_checker is not None:
            return _health_checker

        _health_checker = ComponentHealthChecker(
            start_time=start_time,
            version=version,
            memory_manager=memory_manager,
            model_manager=model_manager,
            knowledge_manager=knowledge_manager,
            tool_engine=tool_engine,
        )
        logger.info("Vérificateur de santé initialisé")
        return _health_checker
