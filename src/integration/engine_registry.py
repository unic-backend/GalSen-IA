"""
Engine Registry for GalSen IA.

The registry is the single place where every engine is instantiated. Agents and
orchestrators ask the registry for an engine instead of building one, which
guarantees that the whole platform shares the same memory, the same knowledge
base and the same document store during a request.

Two rules drive the design:

- **Lazy**: an engine is built the first time it is asked for. Starting the
  platform therefore costs nothing, and an engine whose optional dependencies
  are missing only fails if something actually needs it.
- **Isolated failures**: an engine that cannot be built never propagates its
  exception to unrelated code. The registry records the reason and reports the
  engine as unavailable, so one broken component cannot take the platform down.
"""

import logging
import os
import threading
from typing import Any, Callable, Dict, List, Optional

# Identifiers of every engine reachable through the registry
ENGINE_NAMES = (
    "memory",
    "model",
    "knowledge",
    "document",
    "vision",
    "tool",
    "audit",
    "approval",
    "notification",
    "search",
    "file",
    "cloud",
    "calendar",
    "email",
)


class EngineUnavailableError(RuntimeError):
    """Raised when an engine is requested but cannot be provided."""

    def __init__(self, engine_name: str, reason: str):
        """
        Initialise l'erreur.

        Args:
            engine_name: Nom du moteur demandé
            reason: Raison pour laquelle il est indisponible
        """
        super().__init__(f"Moteur '{engine_name}' indisponible: {reason}")
        self.engine_name = engine_name
        self.reason = reason


class EngineRegistry:
    """
    Fournit un accès unique et partagé à tous les moteurs de GalSen IA.

    Exemple:
        registry = EngineRegistry()
        registry.memory.save_memory(item)
        if registry.is_available("vision"):
            registry.vision.load_image(path)
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialise le registre.

        Args:
            project_root: Racine du projet, déduite de l'emplacement de ce
                fichier si elle n'est pas fournie. Sert à localiser les
                fichiers de configuration (registre des outils, etc.).
        """
        self._logger = logging.getLogger(__name__)
        self._project_root = project_root or self._detect_project_root()

        # Instances déjà construites, et raisons d'échec des autres
        self._engines: Dict[str, Any] = {}
        self._failures: Dict[str, str] = {}
        # Les agents parallèles partagent le registre : la construction doit être atomique
        self._lock = threading.RLock()

        self._builders: Dict[str, Callable[[], Any]] = {
            "memory": self._build_memory_engine,
            "model": self._build_model_engine,
            "knowledge": self._build_knowledge_engine,
            "document": self._build_document_engine,
            "vision": self._build_vision_engine,
            "tool": self._build_tool_engine,
            "audit": self._build_audit_engine,
            "approval": self._build_approval_engine,
            "notification": self._build_notification_service,
            "search": self._build_search_service,
            "file": self._build_file_service,
            "cloud": self._build_cloud_service,
            "calendar": self._build_calendar_service,
            "email": self._build_email_service,
        }

    # ------------------------------------------------------------------
    # Accès aux moteurs
    # ------------------------------------------------------------------
    def get(self, engine_name: str) -> Any:
        """
        Retourne un moteur, en le construisant au premier appel.

        Args:
            engine_name: Nom du moteur, parmi `ENGINE_NAMES`

        Returns:
            L'instance du moteur demandé

        Raises:
            EngineUnavailableError: Si le moteur est inconnu ou n'a pas pu être construit
        """
        if engine_name not in self._builders:
            raise EngineUnavailableError(engine_name, "moteur inconnu")

        with self._lock:
            if engine_name in self._engines:
                return self._engines[engine_name]

            # Un moteur qui a déjà échoué n'est pas reconstruit à chaque appel
            if engine_name in self._failures:
                raise EngineUnavailableError(engine_name, self._failures[engine_name])

            try:
                engine = self._builders[engine_name]()
            except Exception as error:
                reason = f"{type(error).__name__}: {error}"
                self._failures[engine_name] = reason
                self._logger.warning(f"Moteur '{engine_name}' non initialisable: {reason}")
                raise EngineUnavailableError(engine_name, reason) from error

            self._engines[engine_name] = engine
            self._logger.info(f"Moteur '{engine_name}' initialisé")
            return engine

    def try_get(self, engine_name: str) -> Optional[Any]:
        """
        Retourne un moteur, ou None s'il est indisponible.

        À utiliser quand l'appelant sait se passer du moteur.

        Args:
            engine_name: Nom du moteur

        Returns:
            L'instance du moteur, ou None
        """
        try:
            return self.get(engine_name)
        except EngineUnavailableError:
            return None

    def is_available(self, engine_name: str) -> bool:
        """
        Indique si un moteur peut être utilisé.

        Attention : cette vérification construit le moteur si ce n'est pas
        encore fait.

        Args:
            engine_name: Nom du moteur

        Returns:
            True si le moteur est utilisable
        """
        return self.try_get(engine_name) is not None

    def availability(self) -> Dict[str, Dict[str, Any]]:
        """
        Retourne l'état de tous les moteurs, pour le diagnostic.

        Returns:
            Pour chaque moteur : sa disponibilité et, en cas d'échec, la raison
        """
        report: Dict[str, Dict[str, Any]] = {}
        for name in ENGINE_NAMES:
            available = self.is_available(name)
            report[name] = {
                "available": available,
                "reason": None if available else self._failures.get(name, "inconnue"),
            }
        return report

    def available_engines(self) -> List[str]:
        """Retourne la liste des moteurs actuellement utilisables."""
        return [name for name in ENGINE_NAMES if self.is_available(name)]

    def reset(self) -> None:
        """
        Oublie toutes les instances et tous les échecs.

        Le prochain accès reconstruira chaque moteur. Utile après un changement
        de configuration ou entre deux tests.
        """
        with self._lock:
            self._engines.clear()
            self._failures.clear()
            self._logger.info("Registre des moteurs réinitialisé")

    # ------------------------------------------------------------------
    # Raccourcis de lecture
    # ------------------------------------------------------------------
    @property
    def memory(self):
        """Moteur de mémoire (MemoryManager)."""
        return self.get("memory")

    @property
    def model(self):
        """Moteur de modèles IA (ModelManagerImpl)."""
        return self.get("model")

    @property
    def knowledge(self):
        """Moteur de connaissances (KnowledgeManagerImpl)."""
        return self.get("knowledge")

    @property
    def document(self):
        """Moteur d'intelligence documentaire (DocumentManagerImpl)."""
        return self.get("document")

    @property
    def vision(self):
        """Moteur d'intelligence visuelle (VisionManagerImpl)."""
        return self.get("vision")

    @property
    def tool(self):
        """Moteur d'outils (ToolEngine)."""
        return self.get("tool")

    @property
    def audit(self):
        """Moteur d'audit (AuditManagerImpl)."""
        return self.get("audit")

    @property
    def approval(self):
        """Moteur d'approbation humaine (ApprovalManagerImpl)."""
        return self.get("approval")

    @property
    def notification(self):
        """Service de notification (NotificationManagerImpl)."""
        return self.get("notification")

    @property
    def search(self):
        """Service de recherche unifiée (SearchManagerImpl)."""
        return self.get("search")

    @property
    def file(self):
        """Service de fichiers (FileManagerImpl)."""
        return self.get("file")

    @property
    def cloud(self):
        """Service cloud (CloudManagerImpl)."""
        return self.get("cloud")

    @property
    def calendar(self):
        """Service de calendrier (CalendarManagerImpl)."""
        return self.get("calendar")

    @property
    def email(self):
        """Service email (EmailManagerImpl)."""
        return self.get("email")

    @property
    def project_root(self) -> str:
        """Racine du projet utilisée pour localiser les fichiers de configuration."""
        return self._project_root

    # ------------------------------------------------------------------
    # Constructeurs des moteurs
    # ------------------------------------------------------------------
    def _build_memory_engine(self):
        """Construit le moteur de mémoire."""
        from ..memory_engine.memory_manager import MemoryManager
        return MemoryManager()

    def _build_model_engine(self):
        """
        Construit le moteur de modèles.

        Le moteur de mémoire lui est passé pour qu'il y consigne l'historique
        des générations. La mémoire est optionnelle : si elle n'est pas
        disponible, le moteur de modèles fonctionne sans historique plutôt que
        d'échouer.
        """
        from ..model_engine.model_manager import ModelManagerImpl
        return ModelManagerImpl(memory_manager=self.try_get("memory"))

    def _build_knowledge_engine(self):
        """Construit le moteur de connaissances."""
        from ..knowledge_engine.knowledge_manager import KnowledgeManagerImpl
        return KnowledgeManagerImpl()

    def _build_document_engine(self):
        """Construit le moteur d'intelligence documentaire."""
        from ..document_intelligence_engine.document_manager import DocumentManagerImpl
        return DocumentManagerImpl()

    def _build_vision_engine(self):
        """Construit le moteur d'intelligence visuelle."""
        from ..vision_intelligence_engine.vision_manager import VisionManagerImpl
        return VisionManagerImpl()

    def _build_tool_engine(self):
        """Construit le moteur d'outils à partir du registre des outils."""
        from ..tool.tool_engine import ToolEngine

        registry_path = os.path.join(self._project_root, 'tools', 'tools.yaml')
        if not os.path.isfile(registry_path):
            raise FileNotFoundError(f"Registre des outils introuvable: {registry_path}")
        return ToolEngine(registry_path)

    def _build_audit_engine(self):
        """Construit le moteur d'audit (pur en mémoire, toujours disponible)."""
        from ..audit_engine.audit_manager import AuditManagerImpl
        return AuditManagerImpl()

    def _build_approval_engine(self):
        """Construit le moteur d'approbation (pur en mémoire, toujours disponible)."""
        from ..approval_engine.approval_manager import ApprovalManagerImpl
        return ApprovalManagerImpl()

    # ------------------------------------------------------------------
    # Constructeurs des services
    # ------------------------------------------------------------------
    def _build_notification_service(self):
        """Construit le service de notification (pur en mémoire, toujours disponible)."""
        from ..services.notification.manager import NotificationManagerImpl
        return NotificationManagerImpl()

    def _build_search_service(self):
        """Construit le service de recherche unifiée (pur en mémoire, toujours disponible)."""
        from ..services.search.manager import SearchManagerImpl
        return SearchManagerImpl()

    def _build_file_service(self):
        """Construit le service de fichiers (pur en mémoire, toujours disponible)."""
        from ..services.file.manager import FileManagerImpl
        return FileManagerImpl()

    def _build_cloud_service(self):
        """Construit le service cloud (pur en mémoire, toujours disponible)."""
        from ..services.cloud.manager import CloudManagerImpl
        return CloudManagerImpl()

    def _build_calendar_service(self):
        """Construit le service de calendrier (pur en mémoire, toujours disponible)."""
        from ..services.calendar.manager import CalendarManagerImpl
        return CalendarManagerImpl()

    def _build_email_service(self):
        """Construit le service email (pur en mémoire, toujours disponible)."""
        from ..services.email.manager import EmailManagerImpl
        return EmailManagerImpl()

    @staticmethod
    def _detect_project_root() -> str:
        """Déduit la racine du projet depuis l'emplacement de ce fichier."""
        # Ce fichier est dans <racine>/src/integration/, la racine est deux niveaux au-dessus
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(os.path.dirname(current_dir))


# Registre partagé par défaut : le Router Engine, l'Agent Runtime et les agents
# doivent voir la même mémoire et la même base de connaissances pendant une requête.
_shared_registry: Optional[EngineRegistry] = None
_shared_registry_lock = threading.Lock()


def get_shared_registry() -> EngineRegistry:
    """
    Retourne le registre partagé par toute la plateforme.

    Returns:
        L'instance unique de `EngineRegistry`
    """
    global _shared_registry

    if _shared_registry is None:
        with _shared_registry_lock:
            # Nouvelle vérification sous verrou : deux threads peuvent arriver ici ensemble
            if _shared_registry is None:
                _shared_registry = EngineRegistry()

    return _shared_registry
