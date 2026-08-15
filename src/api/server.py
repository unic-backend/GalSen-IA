"""
API Server for GalSen IA platform.

Expose les fonctionnalités du noyau via une API RESTful.
"""

from fastapi import FastAPI, HTTPException, Depends, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
import logging
import threading
import time
import uuid

# Import des moteurs existants
from src.memory_engine.memory_manager import MemoryManager
from src.memory_engine.types import MemoryItem
from src.model_engine.model_manager import ModelManagerImpl
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.approval_engine.approval_manager import ApprovalManagerImpl
from src.tool.authorization import (
    Actor,
    authorization_report,
    authorize,
    authorized_tools,
    ceiling_for,
)
from src.tool.tool_engine import ToolEngine
from src.tool.tool_loader import ToolLoader
from src.tools.agri_advice.tool import AgriAdviceTool

# Import du limiteur de taux
from src.api.rate_limiter import (
    rate_limit_dependency,
    set_valid_api_key_digests,
    # Réutilisé plutôt que réécrit : la détection de menaces doit identifier une
    # source exactement comme le limiteur de débit, sinon les deux désignent des
    # choses différentes sous le même nom.
    _get_client_ip,
)
from src.api.threat_detection import get_shared_detector

# Import du vérificateur de santé
from src.api.health import (
    init_health_checker,
    get_health_checker,
)

# Import de l'inventaire d'état local au processus (VOLET 02 ch. 10, ADR-009)
from src.api.scaling import instance_id, scaling_report

# Le chemin d'une requête, reconstitué depuis l'audit (phase 26.4)
from src.api.tracing import build_trace

# Une seule instance par répertoire de données (ADR-013)
from src.api import instance_lock

# Import de la mesure du trafic réel (VOLET 04 ch. 09, critère C5)
from src.api.metrics import (
    RequestMetricsMiddleware,
    metrics_snapshot,
    record_authentication,
    record_search,
)

# Version de la plateforme — source unique (src/version.py)
from src.version import __version__
from src.config import log_environment_problems
from src.analytics import build_report as build_analytics_report
from src.integration.engine_registry import get_shared_registry

# Import de la posture de sécurité HTTP (VOLET 02 ch. 08)
from src.api.security_headers import (
    SecurityHeadersMiddleware,
    allowed_origins,
    docs_enabled,
)

# Versionnement et fin de vie des routes (VOLET 15 ch. 04, ADR-011)
from src.api.versioning import DeprecationHeadersMiddleware, version_report

# Import du RBAC
from src.api.rbac import (
    ANONYMOUS_SUBJECT,
    RBACManager,
    Permission,
    RBACContext,
)

# Import de l'interface web (ADR-008)
from src.web import STATIC_DIRECTORY, UI_PREFIX

# Import des connecteurs externes (ADR-007)
from src.connectors import (
    LocalDiskStorageConnector,
    SMTPEmailConnector,
    get_shared_connector_registry,
)
from src.connectors.contract import conformance
from src.connectors.lifecycle import lifecycle_report
from src.connectors.oauth import (
    FlowRefused,
    OAuthNotConfigured,
    ProviderUnknown,
    ScopeRefused,
)
from src.connectors.oauth import configuration_report as oauth_configuration_report
from src.connectors.oauth import get_provider as get_oauth_provider
from src.connectors.oauth.flow import DUREE_DE_VIE_SECONDES
from src.connectors.google import (
    CalendarConnector,
    DriveConnector,
    GmailConnector,
)
from src.connectors.oauth.session import OAuthSession
from src.routines import (
    RoutineAction,
    RoutineJournal,
    RoutineRefused,
    RoutineRegistry,
    RoutineSafety,
    RoutineScheduler,
)
from src.connectors.safety import safety_report
from src.integration.degradation import degradation_report
from src.observability import observability_report, trail
from src.router.orchestration_paths import orchestration_paths
from src.router.workflow_checkpoint import CheckpointRefused

# Import des services
from src.knowledge_engine.domains import domain_coverage
from src.agent.capabilities_reach import agent_reach
from src.document_intelligence_engine.from_connector import ingestion_report
from src.memory_engine.layers import layers_report
from src.plugins import (
    PluginExecutionRefused,
    PluginRefused,
    PluginRegistry,
    ReviewRefused,
    execution_report,
    review_plugin,
    review_report,
    run_installed,
)
from src.plugins.registry import discover as plugin_discover
from src.knowledge_engine.routing import ask, layer_comparison, routing_report
from src.knowledge_engine.freshness import (
    freshness_of_year,
    freshness_report,
    repository_freshness,
)
from src.knowledge_engine.series import answer_series, load_series, series_report
from src.knowledge_engine.world import answer_country, answer_field, world_report
from src.services.notification.channels import ChannelRegistry
from src.services.notification.events import PlatformNotifier
from src.services.notification.manager import NotificationManagerImpl
from src.services.notification.types import NotificationType, NotificationPriority
from src.services.search.manager import SearchManagerImpl
from src.document_intelligence_engine.document_manager import DocumentManagerImpl
from src.services.search.providers import (
    DocumentSearchProvider,
    KnowledgeSearchProvider,
    MemorySearchProvider,
    WorldSearchProvider,
)
from src.services.search.governance import governance_report as search_governance_report
from src.services.search.types import SearchQuery, SearchSource, SearchSort
from src.services.file.manager import FileManagerImpl

# Import des services d'intégration externe (VOLET 02, Phase 3)
from src.services.cloud.manager import CloudManagerImpl
from src.services.cloud.types import CloudProvider
from src.services.calendar.manager import CalendarManagerImpl
from src.services.calendar.types import EventStatus
from src.services.email.manager import EmailManagerImpl

logger = logging.getLogger(__name__)

# Horodatage de démarrage (utilisé pour le calcul de l'uptime)
APP_START_TIME = time.time()


def erreur_interne(message: str, erreur: Exception) -> HTTPException:
    """
    Construit un 500 qui informe l'appelant sans lui livrer l'intérieur.

    Le texte d'une exception n'est pas rédigé pour être lu par un client : il
    porte régulièrement un chemin de fichier, un nom d'hôte interne, un
    fragment de requête SQL ou une URL de service. Quatre routes le
    recopiaient tel quel dans `detail`, et c'était mesurable — une recherche en
    échec répondait « connexion refusée vers http://interne:11434 (fichier
    /home/user/.../knowledge.sqlite) » à qui savait la faire échouer.

    La cause n'est pas perdue pour autant : elle part au journal avec sa pile
    d'appels, sous un identifiant d'incident que l'appelant reçoit et peut
    citer. L'opérateur retrouve l'erreur exacte, l'appelant n'apprend rien de
    la machine.

    Args:
        message: ce que l'appelant peut savoir, sans détail interne
        erreur: l'exception à journaliser

    Returns:
        L'HTTPException 500 à lever.
    """
    incident = uuid.uuid4().hex[:12]
    logger.exception("Incident %s — %s : %s", incident, message, erreur)
    return HTTPException(status_code=500, detail=f"{message} (incident {incident})")

# API Key security
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Gestionnaire RBAC — charge le mapping clé API → rôle depuis GALSEN_API_KEYS
# Format attendu : "sk-admin123:admin,sk-user456:user,sk-operator789:operator"
# Une clé sans rôle hérite du rôle "user".
rbac_manager = RBACManager()

# Enregistrer les clés API valides auprès du limiteur de taux
set_valid_api_key_digests(rbac_manager.active_key_digests())


def require_auth(request: Request, api_key: str = Security(api_key_header)) -> RBACContext:
    """Dépendance FastAPI : authentifie la clé API et retourne le contexte RBAC.

    Remplace l'ancienne dépendance get_api_key(). En plus de valider la clé,
    elle associe un rôle et des permissions à la requête.

    Chaque issue alimente aussi la détection de menaces (VOLET 11, ch. 05) :
    compter les échecs ne suffisait pas, douze tentatives avec douze clés
    différentes ne levaient aucun signal. La **source** est l'adresse IP, jamais
    la clé ni son empreinte — un journal de menaces qui nomme des clés devient
    lui-même une cible.

    Args:
        request: Requête en cours, pour identifier la source.
        api_key: Clé API transmise dans l'en-tête X-API-Key.

    Returns:
        Contexte RBAC (rôle + permissions) pour la requête.

    Raises:
        HTTPException 401 : clé manquante ou invalide.
    """
    source = _get_client_ip(request)
    try:
        contexte = rbac_manager.authenticate(api_key)
    except PermissionError as e:
        # Compté avant de lever : sans cela, la seule catégorie qui intéresse
        # une enquête — les échecs — serait la seule absente des chiffres.
        record_authentication(reussie=False)
        get_shared_detector().record_failure(source)
        raise HTTPException(status_code=401, detail=str(e))

    record_authentication(reussie=True)
    # Une authentification réussie efface les échecs de la source : sans cela,
    # quelqu'un qui se trompe puis se connecte resterait signalé indéfiniment.
    get_shared_detector().record_success(source)
    return contexte


def require_permission(permission: Permission):
    """Fabrique une dépendance FastAPI qui vérifie une permission spécifique.

    Utilisation :
        @app.get("/memory")
        async def list_memory(ctx: RBACContext = Depends(require_permission(Permission.MEMORY_READ))):
            ...

    Args:
        permission: La permission requise pour accéder à l'endpoint.

    Returns:
        Une dépendance FastAPI qui vérifie l'authentification ET la permission.
    """
    def _check_permission(
        ctx: RBACContext = Depends(require_auth),
    ) -> RBACContext:
        if not ctx.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission.value}' requise. Rôle actuel : '{ctx.role.value}'.",
            )
        return ctx
    return _check_permission

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Construit le moteur d'outils au démarrage et le publie au vérificateur de santé.

    Le moteur lit lui-même le registre `tools/tools.yaml` : il construit son
    propre chargeur et son propre exécuteur. Un échec ici laisserait toute l'API
    hors service, donc l'erreur est journalisée et `tool_engine` reste à None —
    `/tool/execute` répond alors 503 et `/health` signale le moteur comme
    indisponible.

    Les objets utilisés ici sont définis plus bas dans le module : le corps de
    cette fonction ne s'exécute qu'au démarrage, jamais à l'import.
    """
    global tool_engine
    # Une variable présente et inexploitable est signalée ici, jamais plus tard :
    # `GALSEN_STORAGE_BACKEND=sqllite` repartait en mémoire sans rien dire
    # (VOLET 03, ch. 05). Le démarrage n'est pas interrompu pour autant.
    log_environment_problems(logger)

    # Une seule instance par répertoire de données (ADR-013). C'est la seule
    # chose que l'on refuse au démarrage : les révocations de clés et les
    # compteurs de quota vivent dans ce processus, donc une deuxième instance
    # ne dégrade pas le service — elle défait une garantie de sécurité, en
    # silence. Le refus est bruyant par nécessité.
    instance_lock.acquire()

    try:
        tool_engine = ToolEngine(tool_loader.registry_path)
        logger.info(
            "Moteur d'outils initialisé avec %d outils actifs.",
            len(tool_engine.list_enabled_tools()),
        )
    except Exception as error:
        tool_engine = None
        logger.error("Échec de l'initialisation du moteur d'outils : %s", error)

    checker = get_health_checker()
    if hasattr(checker, "set_tool_engine"):
        checker.set_tool_engine(tool_engine)

    _register_builtin_connectors()

    yield

    # Les moteurs sont en mémoire et les connexions SQLite sont ouvertes et
    # refermées par opération : seul le verrou d'instance survit au processus,
    # et il doit partir, sinon une restauration de sauvegarde se croira bloquée.
    instance_lock.release()


def _register_builtin_connectors() -> None:
    """
    Inscrit les connecteurs livrés avec la plateforme au registre partagé.

    L'inscription ne dépend d'aucune configuration : un connecteur non
    configuré doit rester **visible** dans l'inventaire, sinon un opérateur ne
    peut pas savoir ce que l'installation saurait joindre une fois branchée.
    Un identifiant déjà pris n'est pas une erreur ici : le cycle de vie peut
    être rejoué (rechargement, tests), et le registre est partagé.
    """
    registre = get_shared_connector_registry()
    for connecteur in (SMTPEmailConnector(), LocalDiskStorageConnector()):
        try:
            registre.register(connecteur)
        except ValueError:
            logger.debug("Connecteur %s déjà enregistré.", connecteur.connector_id)

    # Les connecteurs Google, inscrits même sans identifiants : un connecteur
    # non configuré doit rester **visible**, sinon personne ne peut savoir ce
    # que l'installation saurait joindre une fois branchée.
    #
    # Ils partagent la session OAuth du fournisseur, donc son magasin de jetons.
    # Sans ce partage, un consentement donné par `/oauth/google/authorize`
    # resterait invisible des connecteurs — une panne silencieuse où chaque
    # moitié fonctionne et l'ensemble non.
    try:
        session = _oauth_session("google")
    except HTTPException:
        logger.info("Fournisseur OAuth 'google' non déclaré : aucun connecteur Google.")
    else:
        for classe in (GmailConnector, DriveConnector, CalendarConnector):
            try:
                registre.register(classe(session.provider, tokens=session.tokens))
            except ValueError:
                logger.debug("Connecteur %s déjà enregistré.", classe.CONNECTOR_ID)

    logger.info("Connecteurs enregistrés : %d", registre.count())


# Initialisation de l'application FastAPI
# La documentation interactive n'est servie que si l'API est elle-même ouverte
# (aucune clé configurée), ou si GALSEN_API_DOCS le demande explicitement.
_docs_actives = docs_enabled()

app = FastAPI(
    title="GalSen IA API",
    description="API exposant les fonctionnalités de la plateforme GalSen IA",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if _docs_actives else None,
    redoc_url="/redoc" if _docs_actives else None,
    openapi_url="/openapi.json" if _docs_actives else None,
)

# En-têtes de sécurité sur toutes les réponses
app.add_middleware(SecurityHeadersMiddleware)

# Annonce de fin de vie (ADR-011). Au plus près de la route, comme les en-têtes
# de sécurité : l'annonce doit accompagner toute réponse de la route dépréciée,
# y compris ses erreurs.
app.add_middleware(DeprecationHeadersMiddleware)

# Mesure du trafic. Ajouté après la sécurité : Starlette exécute les
# intergiciels dans l'ordre inverse de leur ajout, donc celui-ci enveloppe
# l'autre et voit le code de statut réellement renvoyé.
app.add_middleware(RequestMetricsMiddleware)

# Origines croisées : aucune par défaut. `allow_origins=["*"]` avec
# `allow_credentials=True` renvoyait l'origine de l'appelant quelle qu'elle
# soit, ce qui autorisait n'importe quel site à appeler l'API avec les
# identifiants du visiteur. Les origines légitimes se déclarent dans
# GALSEN_CORS_ORIGINS.
_origines = allowed_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origines,
    allow_credentials=bool(_origines),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["X-API-Key", "Content-Type"],
)

# Interface web (ADR-008) : fichiers servis tels quels, sans étape de
# construction. `html=True` fait servir index.html à la racine du préfixe, de
# sorte que /ui affiche le tableau de bord.
# L'interface ne contient aucun secret : la clé API est saisie par l'utilisateur
# et reste dans son navigateur, elle n'est jamais écrite dans une page.
app.mount(UI_PREFIX, StaticFiles(directory=STATIC_DIRECTORY, html=True), name="ui")


@app.get("/", include_in_schema=False)
async def racine():
    """Redirige la racine vers le tableau de bord.

    Une racine qui répondait 404 laissait croire que rien n'écoutait.
    """
    return RedirectResponse(url=f"{UI_PREFIX}/")
if not _origines:
    logger.info(
        "Aucune origine croisée autorisée. Déclarez-les dans %s si un frontend en a besoin.",
        "GALSEN_CORS_ORIGINS",
    )

# Initialisation des moteurs (singleton pour la durée de vie de l'application)
#
# Les moteurs viennent du **registre partagé**, celui-là même que les agents
# utilisent à travers `AgentContext`. Ils étaient auparavant construits ici une
# seconde fois, si bien que la plateforme faisait tourner deux exemplaires de
# chaque moteur : une alerte levée par un agent n'apparaissait pas sur
# `/notification/list`, et une mémoire écrite par l'API restait invisible aux
# agents (VOLET 25, ch. 02 — « chaque moteur communique par des interfaces
# normalisées »). Le défaut ne se voyait pas avec `GALSEN_STORAGE_BACKEND=sqlite`,
# les deux exemplaires partageant alors le même fichier ; en mémoire, le défaut
# par défaut, il coupait la plateforme en deux.
_registre_moteurs = get_shared_registry()


def _moteur_partage(nom: str, secours):
    """Retourne le moteur du registre, ou un exemplaire de secours.

    Le registre construit paresseusement et peut échouer (dépendance absente).
    Dans ce cas l'API garde un exemplaire à elle plutôt que de perdre la route :
    la duplication redevient possible, mais elle est alors journalisée et non
    silencieuse.

    Args:
        nom: nom du moteur dans le registre.
        secours: fabrique appelée si le registre ne peut pas le fournir.
    """
    instance = _registre_moteurs.try_get(nom)
    if instance is not None:
        return instance
    logger.warning(
        "Moteur '%s' indisponible dans le registre : l'API en construit un "
        "exemplaire séparé, non partagé avec les agents.", nom,
    )
    return secours()


memory_manager = _moteur_partage("memory", MemoryManager)
model_manager = _moteur_partage("model", ModelManagerImpl)
knowledge_manager = _moteur_partage("knowledge", KnowledgeManagerImpl)
# Le chargeur ne sert plus qu'à localiser le registre : le ToolEngine construit
# son propre chargeur et son propre exécuteur à partir de ce chemin (lifespan).
tool_loader = ToolLoader()
tool_engine = None  # sera initialisé au démarrage, par lifespan()

# Sessions OAuth, une par fournisseur, pour la durée du processus. Les jetons
# d'une personne ne doivent pas disparaître entre deux requêtes ; ils ne
# survivent pas non plus à un redémarrage, ce qui est assumé tant que le
# magasin est en mémoire (VOLET 43.2).
_oauth_sessions: Dict[str, OAuthSession] = {}


# Routines : registre, planificateur et journal, pour la durée du processus.
#
# **Aucune boucle ne tourne d'elle-même.** Une plateforme qui se met à déclencher
# des routines au démarrage, sans que personne l'ait demandé, est exactement ce
# qu'un moteur de routines ne doit pas être. Le déclenchement est provoqué —
# `POST /routines/tick` — par un opérateur ou par une entrée cron, et le rapport
# le dit en toutes lettres.
routine_registry = RoutineRegistry()
routine_journal = RoutineJournal()

# La sûreté vit **hors** du planificateur, et survit à sa reconstruction.
#
# Le premier branchement de cette phase la laissait naître avec chaque
# planificateur : un arrêt d'urgence engagé disparaissait dès que le moteur
# d'outils changeait — exactement le défaut contre lequel `safety.py` a été
# écrit, réintroduit par son propre câblage. Un test le garde désormais.
routine_safety = RoutineSafety()
_routine_scheduler: Optional[RoutineScheduler] = None


def _scheduler() -> RoutineScheduler:
    """Retourne le planificateur, construit au premier besoin."""
    global _routine_scheduler
    if _routine_scheduler is None or _routine_scheduler._outils is not tool_engine:
        _routine_scheduler = RoutineScheduler(
            routine_registry, tool_engine=tool_engine, safety=routine_safety,
            notifier=platform_notifier,
            # L'orchestrateur du dépôt, celui de `POST /process` (VOLET 64).
            # Une routine qui déclenche un workflow emprunte le même moteur :
            # un second chemin d'exécution sans points de reprise ni historique
            # serait l'implémentation parallèle que la directive interdit.
            orchestrator=_OrchestrateurALaDemande(),
        )
    return _routine_scheduler


class _OrchestrateurALaDemande:
    """
    L'orchestrateur, ouvert seulement quand une routine en déclenche un.

    Le passer construit ferait payer à tout déploiement le chargement de trois
    registres et la validation des workflows, y compris à celui dont aucune
    routine ne déclenche de workflow — exactement ce que `get_router_engine()`
    évite déjà pour les requêtes.
    """

    def process_request(self, *args, **kwargs):
        """Transmet la demande à l'orchestrateur partagé du processus."""
        return get_router_engine().process_request(*args, **kwargs)


def _oauth_session(provider_id: str) -> OAuthSession:
    """Retourne la session d'un fournisseur, ou 404 s'il n'est pas déclaré."""
    session = _oauth_sessions.get(provider_id)
    if session is not None:
        return session
    try:
        fournisseur = get_oauth_provider(provider_id)
    except ProviderUnknown as inconnu:
        raise HTTPException(status_code=404, detail=str(inconnu))
    session = OAuthSession(fournisseur, list(fournisseur.allowed_scopes))
    _oauth_sessions[provider_id] = session
    return session
# File d'attente d'approbation humaine : les agents qui demandent une décision
# soumettent ici leur action, et un opérateur la valide ou la refuse (ADR-006).
approval_manager = _moteur_partage("approval", ApprovalManagerImpl)

# Services backend (VOLET 02, Phase 2)
notification_manager = _moteur_partage("notification", NotificationManagerImpl)

# Le témoin de la plateforme (VOLET 50). Le service de notification existait ;
# ce qui lui manquait, ce sont les événements de la vague III — une routine qui
# s'arrête d'elle-même, une exécution longue qui meurt en route. Tous deux
# n'existaient que dans les journaux, et un journal est lu par quelqu'un qui
# soupçonne déjà quelque chose.
platform_notifier = PlatformNotifier(notification_manager)

# Les canaux de livraison (phase 50.2). Déclarés dans
# `config/notifications/channels.yaml` ; aucun canal externe n'a d'identifiants
# dans cette installation, et il le dit plutôt que de simuler un envoi.
notification_channels_registry = ChannelRegistry()

# Les greffons (VOLET 58). Vide au démarrage : rien n'est installé sans qu'on le
# demande, et rien n'est activé sans qu'une personne le décide.
plugin_registry = PluginRegistry()

search_manager = _moteur_partage("search", SearchManagerImpl)
# Sans cet enregistrement, la recherche unifiée n'a aucune source et ne peut rien
# trouver (VOLET 14, ch. 04).
search_manager.register_provider(KnowledgeSearchProvider(knowledge_manager))
# La mémoire est la deuxième source réellement branchée. Elle est possédée :
# le fournisseur ne cherche que dans les souvenirs du sujet de la requête, et
# ne cherche pas du tout sans sujet (ADR-010, critère C2).
search_manager.register_provider(MemorySearchProvider(memory_manager))
# La troisième : le moteur documentaire indexait déjà ce qu'il charge, et seul
# le fournisseur manquait. **La vision reste sans fournisseur**, et la réponse
# de `/search` dit pourquoi — elle ne produit aucun texte indexé, donc il n'y a
# rien à y chercher.
search_manager.register_provider(
    DocumentSearchProvider(_moteur_partage("document", DocumentManagerImpl))
)
# La quatrième (phase 54.2) : la connaissance mondiale existait et **rien ne la
# cherchait** — on ne l'atteignait qu'avec un code ISO ou un nom exact. Publique
# et de plateforme : aucun filtre par propriétaire, et le dire évite qu'on
# cherche un filtre absent en croyant à un oubli.
search_manager.register_provider(WorldSearchProvider())
file_manager = _moteur_partage("file", FileManagerImpl)

# Services d'intégration externe (VOLET 02, Phase 3)
cloud_manager = _moteur_partage("cloud", CloudManagerImpl)
calendar_manager = _moteur_partage("calendar", CalendarManagerImpl)
email_manager = _moteur_partage("email", EmailManagerImpl)

# Orchestrateur d'agents. Construit à la première demande plutôt qu'au
# démarrage : il charge trois registres et valide les workflows, ce qu'un
# déploiement qui n'exécute jamais d'agent n'a pas à payer.
_router_engine = None
_router_engine_lock = threading.Lock()


def get_router_engine():
    """Retourne l'orchestrateur partagé du processus."""
    global _router_engine
    if _router_engine is None:
        with _router_engine_lock:
            if _router_engine is None:
                from src.router.router_engine import RouterEngine
                _router_engine = RouterEngine()
                # Le témoin est posé par l'intégration, pas construit par le
                # routeur : l'orchestration n'a pas à savoir monter un service.
                _router_engine.notifier = platform_notifier
    return _router_engine


# Modèles Pydantic pour les requêtes/réponses
class MemoryItemBase(BaseModel):
    content: Any = Field(..., description="Contenu de la mémoire")
    memory_type: str = Field("short_term", description="Type de mémoire")
    user_id: Optional[str] = Field(None, description="Identifiant de l'utilisateur")
    session_id: Optional[str] = Field(None, description="Identifiant de la session")
    agent_id: Optional[str] = Field(None, description="Identifiant de l'agent")
    tags: List[str] = Field(default_factory=list, description="Tags pour catégorisation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées supplémentaires")

class MemoryItemCreate(MemoryItemBase):
    pass

class MemoryItemResponse(MemoryItemBase):
    id: str = Field(..., description="Identifiant unique de la mémoire")
    created_at: float = Field(..., description="Timestamp de création")
    updated_at: float = Field(..., description="Timestamp de dernière mise à jour")
    expires_at: Optional[float] = Field(None, description="Timestamp d'expiration")
    priority: str = Field(..., description="Niveau de priorité")
    status: str = Field(..., description="Statut actuel")
    version: int = Field(..., description="Numéro de version")

class ModelGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Prompt pour la génération")
    model_id: Optional[str] = Field(None, description="ID du modèle à utiliser (optionnel)")
    max_tokens: Optional[int] = Field(None, description="Nombre maximum de tokens à générer")
    temperature: Optional[float] = Field(None, description="Température de génération")
    system_prompt: Optional[str] = Field(None, description="Prompt système")
    stop_sequences: List[str] = Field(default_factory=list, description="Séquences d'arrêt")

class ModelGenerateResponse(BaseModel):
    text: str = Field(..., description="Texte généré")
    status: str = Field(..., description="Statut de la génération")
    model_used: str = Field(..., description="Modèle utilisé")
    tokens_used: int = Field(..., description="Nombre de tokens utilisés")
    latency_seconds: float = Field(..., description="Latence en secondes")

class AgriAdviceRequest(BaseModel):
    question: str = Field(..., description="Question agricole en français ou en wolof")
    language: str = Field("fr", description="Langue de réponse : 'fr' ou 'wo'")
    model_id: Optional[str] = Field(None, description="ID du modèle à utiliser (optionnel)")
    max_tokens: Optional[int] = Field(None, description="Nombre maximum de tokens à générer")

class AgriAdviceResponse(BaseModel):
    answer: str = Field(..., description="Conseil agricole généré")
    language: str = Field(..., description="Langue de la réponse")
    model_used: str = Field(..., description="Modèle utilisé")

class WorkflowRunRequest(BaseModel):
    """Demande d'exécution d'un workflow."""
    request: str = Field(..., min_length=1, description="La demande à traiter")
    workflow_id: Optional[str] = Field(None, description="Workflow à utiliser ; le défaut sinon")
    session_id: Optional[str] = Field(None, description="Session, pour relier plusieurs demandes")


class PluginEnableRequest(BaseModel):
    """L'activation d'un greffon. Qui active vient de la clé, jamais du corps."""

    reason: str = Field(
        ...,
        description=(
            "Pourquoi ce greffon est activé. Elle sera lue par quelqu'un qui "
            "n'était pas là quand la confiance a été accordée."
        ),
    )


class WorkflowCancelRequest(BaseModel):
    """L'annulation d'une exécution. Qui annule vient de la clé, jamais du corps."""

    reason: str = Field(
        ...,
        description=(
            "Pourquoi. L'annulation est définitive : la raison est tout ce "
            "qui restera pour l'expliquer."
        ),
    )


class RoutineHaltRequest(BaseModel):
    """L'arrêt d'urgence. Qui l'engage vient de la clé, jamais du corps."""

    reason: str = Field(
        ...,
        description=(
            "Pourquoi. Elle sera lue par celui qui envisagera de lever "
            "l'arrêt, peut-être des jours plus tard."
        ),
    )


class RoutineBudgetRequest(BaseModel):
    """Le budget quotidien d'une routine."""

    runs_per_day: int = Field(
        ..., description="Tours autorisés par jour. Zéro est refusé."
    )


class RoutineActionRequest(BaseModel):
    """Une action d'une routine, telle qu'une requête la déclare."""

    tool_id: str = Field(..., description="Identifiant de l'outil appelé")
    operation: Any = Field(
        None,
        description=(
            "Premier argument de l'appel : l'opération nommée, ou la commande. "
            "C'est lui qui décide si une borne pré-approuvée couvre l'appel."
        ),
    )
    options: Optional[Dict[str, Any]] = Field(None, description="Arguments nommés")


class RoutineDeclareRequest(BaseModel):
    """Une routine à déclarer. Elle naîtra désactivée."""

    routine_id: str = Field(..., description="Identifiant de la routine")
    description: str = Field(
        ...,
        description=(
            "Ce qu'elle fait, lisible par son propriétaire au moment où il se "
            "demandera pourquoi elle tourne."
        ),
    )
    actions: List[RoutineActionRequest] = Field(..., description="Les appels d'outils")
    interval_seconds: int = Field(..., description="Temps entre deux exécutions")
    platform: bool = Field(
        False,
        description=(
            "Routine de plateforme, n'appartenant à personne. Elle ne peut "
            "alors toucher aucune donnée de personne."
        ),
    )


class ToolExecuteRequest(BaseModel):
    tool_id: str = Field(..., description="Identifiant de l'outil à exécuter")
    input: Any = Field(..., description="Entrée pour l'outil")
    config: Optional[Dict[str, Any]] = Field(None, description="Configuration supplémentaire")

class ToolExecuteResponse(BaseModel):
    output: Any = Field(..., description="Sortie de l'outil")
    status: str = Field(..., description="Statut d'exécution")
    tool_id: str = Field(..., description="Identifiant de l'outil exécuté")

class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., description="Requête de recherche")
    limit: int = Field(10, description="Nombre maximum de résultats")

class KnowledgeSearchResponse(BaseModel):
    results: List[Dict[str, Any]] = Field(..., description="Liste des connaissances trouvées")
    total: int = Field(..., description="Nombre total de résultats")

class ApprovalDecisionRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Motif de la décision (obligatoire pour un refus)")
    decided_by: Optional[str] = Field(None, description="Identifiant de l'opérateur humain qui décide")


# =========================================================================
# Modèles Pydantic — Services (Notification, Search, File)
# =========================================================================

class NotificationCreateRequest(BaseModel):
    """Requête d'envoi de notification."""
    type: str = Field("info", description="Type de notification (info, warning, error, ...)")
    title: str = Field(..., description="Titre de la notification")
    message: str = Field(..., description="Message de la notification")
    priority: str = Field("normal", description="Priorité (low, normal, high, urgent)")
    recipient: Optional[str] = Field(None, description="Destinataire (identifiant utilisateur)")
    role: Optional[str] = Field(None, description="Rôle destinataire")
    source: Optional[str] = Field(None, description="Source de la notification")
    related_id: Optional[str] = Field(None, description="Identifiant lié (requête, agent, ...)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées supplémentaires")


class NotificationListRequest(BaseModel):
    """Paramètres de filtrage des notifications."""
    limit: int = Field(50, description="Nombre maximum de résultats")
    offset: int = Field(0, description="Index de début")
    unread_only: bool = Field(False, description="Uniquement les non lues")
    notification_type: Optional[str] = Field(None, description="Filtrer par type")
    recipient: Optional[str] = Field(None, description="Filtrer par destinataire")
    role: Optional[str] = Field(None, description="Filtrer par rôle")


class SearchRequest(BaseModel):
    """Requête de recherche unifiée."""
    query: str = Field(..., description="Terme de recherche")
    sources: List[str] = Field(default_factory=lambda: ["knowledge", "memory", "document"], description="Sources à interroger")
    limit: int = Field(10, description="Nombre maximum de résultats")
    offset: int = Field(0, description="Index de début")
    sort: str = Field("relevance", description="Tri (relevance, date_desc, date_asc)")
    min_score: Optional[float] = Field(None, description="Score minimum de pertinence")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filtres supplémentaires")


class FileUploadRequest(BaseModel):
    """Requête de téléversement de fichier."""
    name: str = Field(..., description="Nom du fichier")
    content_type: str = Field(..., description="Type MIME du fichier")
    data: str = Field(..., description="Contenu du fichier en base64")
    description: Optional[str] = Field(None, description="Description du fichier")
    tags: Dict[str, str] = Field(default_factory=dict, description="Tags du fichier")
    uploaded_by: Optional[str] = Field(None, description="Identifiant de l'utilisateur")
    source: Optional[str] = Field(None, description="Source du fichier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées supplémentaires")


class FileListRequest(BaseModel):
    """Paramètres de filtrage des fichiers."""
    limit: int = Field(50, description="Nombre maximum de résultats")
    offset: int = Field(0, description="Index de début")
    category: Optional[str] = Field(None, description="Filtrer par catégorie")
    content_type: Optional[str] = Field(None, description="Filtrer par type MIME")
    uploaded_by: Optional[str] = Field(None, description="Filtrer par utilisateur")


# =========================================================================
# Modèles Pydantic — Cloud Service
# =========================================================================

class CloudUploadRequest(BaseModel):
    """Requête de téléversement cloud."""
    name: str = Field(..., description="Nom du fichier")
    content_type: str = Field(..., description="Type MIME")
    data: str = Field(..., description="Contenu du fichier en base64")
    provider: str = Field("local", description="Fournisseur cloud (local, s3, gcs, azure)")
    uploaded_by: Optional[str] = Field(None, description="Identifiant utilisateur")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées")


class CloudListRequest(BaseModel):
    """Paramètres de filtrage cloud."""
    limit: int = Field(50, description="Nombre maximum de résultats")
    offset: int = Field(0, description="Index de début")
    provider: Optional[str] = Field(None, description="Filtrer par fournisseur")
    category: Optional[str] = Field(None, description="Filtrer par catégorie")
    uploaded_by: Optional[str] = Field(None, description="Filtrer par utilisateur")


# =========================================================================
# Modèles Pydantic — Calendar Service
# =========================================================================

class CalendarCreateRequest(BaseModel):
    """Requête de création d'événement."""
    title: str = Field(..., description="Titre de l'événement")
    start_time: str = Field(..., description="Début (ISO 8601)")
    end_time: str = Field(..., description="Fin (ISO 8601)")
    description: Optional[str] = Field(None, description="Description")
    location: Optional[str] = Field(None, description="Lieu")
    organizer: Optional[str] = Field(None, description="Organisateur")
    attendees: List[str] = Field(default_factory=list, description="Participants")
    status: str = Field("confirmed", description="Statut (confirmed, tentative, cancelled)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées")


class CalendarListRequest(BaseModel):
    """Paramètres de filtrage des événements."""
    limit: int = Field(50, description="Nombre maximum de résultats")
    offset: int = Field(0, description="Index de début")
    status: Optional[str] = Field(None, description="Filtrer par statut")
    organizer: Optional[str] = Field(None, description="Filtrer par organisateur")
    start_after: Optional[str] = Field(None, description="Début après cette date (ISO 8601)")
    start_before: Optional[str] = Field(None, description="Début avant cette date (ISO 8601)")


class CalendarUpdateRequest(BaseModel):
    """Requête de mise à jour d'événement."""
    title: Optional[str] = Field(None, description="Titre")
    start_time: Optional[str] = Field(None, description="Début (ISO 8601)")
    end_time: Optional[str] = Field(None, description="Fin (ISO 8601)")
    description: Optional[str] = Field(None, description="Description")
    location: Optional[str] = Field(None, description="Lieu")
    status: Optional[str] = Field(None, description="Statut")


# =========================================================================
# Modèles Pydantic — Email Service
# =========================================================================

class EmailSendRequest(BaseModel):
    """Requête d'envoi d'email."""
    subject: str = Field(..., description="Sujet de l'email")
    body: str = Field(..., description="Corps du message")
    sender: str = Field(..., description="Adresse expéditeur")
    recipients: List[str] = Field(..., description="Destinataires")
    cc: List[str] = Field(default_factory=list, description="Copie carbone")
    bcc: List[str] = Field(default_factory=list, description="Copie carbone invisible")
    is_html: bool = Field(False, description="Corps en HTML")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées")


class EmailListRequest(BaseModel):
    """Paramètres de filtrage des emails."""
    limit: int = Field(50, description="Nombre maximum de résultats")
    offset: int = Field(0, description="Index de début")
    status: Optional[str] = Field(None, description="Filtrer par statut")
    sender: Optional[str] = Field(None, description="Filtrer par expéditeur")
    recipient: Optional[str] = Field(None, description="Filtrer par destinataire")

# Endpoints de santé

# Initialiser le vérificateur de santé (singleton) avec les instances des moteurs
# Le moteur d'outils sera mis à jour au démarrage, par lifespan()
init_health_checker(
    start_time=APP_START_TIME,
    version=app.version,
    memory_manager=memory_manager,
    model_manager=model_manager,
    knowledge_manager=knowledge_manager,
    tool_engine=tool_engine,  # None à l'import, mis à jour par lifespan()
)


@app.get("/health", tags=["health"], dependencies=[Depends(rate_limit_dependency)])
async def health_check(subsystems: bool = False):
    """Rapport de santé détaillé de la plateforme.

    Retourne l'état de tous les composants (API, moteurs, stockage, fournisseurs)
    avec les métadonnées (version, uptime, backend de stockage).

    Code HTTP toujours 200 — le statut global est dans le corps de la réponse
    (champ ``status`` : ``healthy``, ``degraded`` ou ``unhealthy``).

    `?subsystems=true` ajoute l'état des dix sous-systèmes des VOLETs 47 à 64.
    **Hors du défaut, et mesuré** : les sonder coûte environ 70 ms pour une cible
    de supervision de 50 ms, et une supervision qui interroge `/health` toutes
    les cinq secondes paierait ce prix sans arrêt pour une information qui change
    quelques fois par mois. Le rapport complet vit sur `/system/degradation`.
    """
    checker = get_health_checker()
    report = checker.check_health(include_subsystems=subsystems)
    donnees = report.to_dict()
    # La plateforme ne tourne aujourd'hui qu'en une seule instance (ADR-009).
    # La contrainte est exposée ici plutôt que laissée à la documentation :
    # c'est le seul endroit qu'un opérateur consulte avant de dupliquer un
    # service.
    donnees["scaling"] = scaling_report()
    # La souveraineté se constate, elle ne se lit pas seulement dans un ADR :
    # un opérateur doit pouvoir vérifier qu'aucun fournisseur tiers n'est
    # inscrit, sans avoir à ouvrir le code (ADR-014).
    try:
        donnees["sovereignty"] = model_manager.sovereignty_report()
    except Exception as erreur:
        # `/health` ne tombe pas parce qu'une section refuse de se calculer.
        logger.warning("Rapport de souveraineté indisponible : %s", erreur)
    return donnees


@app.get("/system/degradation", tags=["health"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.TOOL_EXECUTE))])
async def system_degradation():
    """Ce qui fonctionne encore, et ce qui manque à chacun.

    Exige une clé : ce rapport nomme les dépendances internes et la cause exacte
    de chaque manque. C'est ce qu'un exploitant doit lire, et ce qu'un inconnu
    n'a pas à connaître — `/health` reste la porte publique.

    Les dix sous-systèmes construits après le registre des moteurs (VOLETs 47 à
    64) n'apparaissaient dans aucun rapport : un exploitant pouvait lire une
    plateforme saine pendant que la moitié récente était inutilisable.

    **Dégradé n'est pas en panne** : un sous-système qui dit ce qui lui manque
    fonctionne comme prévu. Chaque état porte donc *ce qui fonctionne encore
    sans lui* — sans quoi personne ne sait s'il faut agir ce soir ou lundi.
    """
    return degradation_report()


@app.get("/ready", tags=["health"], dependencies=[Depends(rate_limit_dependency)])
async def readiness_check():
    """Test de readiness pour Kubernetes.

    Vérifie que les composants requis (API, moteur d'outils) sont disponibles.
    Retourne 200 si l'application peut servir des requêtes, 503 sinon.
    """
    checker = get_health_checker()
    ready, reason = checker.check_readiness()
    if ready:
        return {"status": "ready", "reason": reason}
    else:
        raise HTTPException(status_code=503, detail=reason)


@app.get("/metrics", tags=["health"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def metrics():
    """Ce que la plateforme a réellement fait : requêtes, erreurs, latences.

    `/health` répond « qu'est-ce qui est configuré ». Cette route répond
    « qu'est-ce qui se passe » — sans quoi la seule façon de le savoir est
    d'ouvrir les journaux, ce que le chapitre 09 exclut.

    Contrairement à `/health`, elle demande une clé : les volumes de trafic et
    les taux d'erreur décrivent l'usage d'un déploiement, pas son architecture.
    """
    return metrics_snapshot()


@app.get("/api/versions", tags=["health"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def api_versions():
    """Version servie et routes annoncées en fin de vie (ADR-011).

    Le chapitre 04 demande un contrôle de version et le retrait sûr des API
    obsolètes. La réponse dit explicitement qu'il n'existe **pas** de
    versionnage d'URL : un appelant qui suppose un `/v1` implicite, donc une
    stabilité que rien ne garantit, construit sur du sable.

    La liste des dépréciations est vide tant qu'aucune route ne l'est.
    """
    return version_report()


@app.get("/security/posture", tags=["health"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_AUDIT))])
async def security_posture():
    """Ce que la plateforme peut réellement faire à cette machine (VOLET 34, ch. 13).

    Les protections vivent dans six modules et cinq ADR ; cette route les
    **mesure** et les rassemble : racines inscriptibles, liste blanche
    d'exécutables, bac à sable, exposition MCP, portillon, audit, souveraineté,
    et ce qui reste annulable.

    Chaque section porte ses `gaps` — ce qu'elle ne garantit pas. Une posture
    qui ne montrerait que les protections présentes rassurerait à tort, ce qui
    est pire que de ne rien montrer.

    Elle demande une clé d'administration : la liste des trous d'une
    installation est exactement ce qu'un attaquant voudrait lire.
    """
    from src.security.posture import posture

    return posture()


@app.get("/security/checkpoints", tags=["health"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_AUDIT))])
async def security_checkpoints(limit: int = 100):
    """Ce qu'un agent a fait, et ce qu'on peut encore défaire (VOLET 34, ch. 13).

    Rassemble les opérations de fichiers annulables, les décisions du portillon
    et les sauvegardes présentes. **Il n'y a pas d'annulation globale** : le
    champ `reversible` dit, ligne par ligne, ce qui se défait.
    """
    from src.security.checkpoints import list_checkpoints

    return list_checkpoints(limit=limit)


@app.get("/proactive/suggestions", tags=["health"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def proactive_suggestions():
    """Ce que la plateforme remarque sans qu'on lui demande.

    Sept détecteurs lisent l'état réel — modèle disponible, décisions en
    attente, cycles d'imports, code sans test, qualité en baisse, fichiers en
    vrac, failles de posture. Chaque observation porte **ses preuves mesurées**
    et nomme qui doit décider.

    **Rien n'est exécuté** : c'est une liste de propositions, pas un journal
    d'actions. Un détecteur qui ne peut pas mesurer se tait ; un détecteur en
    panne est rapporté comme tel, jamais confondu avec un détecteur muet.
    """
    from src.proactive import scan

    return scan()


@app.post("/proactive/{observation_id}/dismiss", tags=["health"],
          dependencies=[Depends(rate_limit_dependency),
                        Depends(require_permission(Permission.HEALTH_VIEW))])
async def proactive_dismiss(observation_id: str, fingerprint: str,
                            reason: str = "",
                            ctx: RBACContext = Depends(require_permission(Permission.HEALTH_VIEW))):
    """Écarte une suggestion : elle ne reviendra pas tant que rien n'aura changé.

    L'empreinte est exigée pour que l'écart porte sur **cette situation** et non
    sur le sujet en général : écarter « 3 fichiers sans test » ne doit pas
    masquer « 300 fichiers sans test » six mois plus tard.
    """
    from src.proactive import dismiss

    return dismiss(observation_id, fingerprint, by=ctx.subject, reason=reason)


@app.get("/live", tags=["health"], dependencies=[Depends(rate_limit_dependency)])
async def liveness_check():
    """Test de liveness pour Kubernetes.

    Vérification minimale que le processus est vivant et répond.
    Retourne toujours 200 tant que l'application fonctionne.
    """
    checker = get_health_checker()
    alive = checker.check_liveness()
    return {"status": "alive" if alive else "dead"}

# Endpoints mémoire
def _proprietaire_effectif(ctx: RBACContext, demande: Optional[str]) -> str:
    """
    Détermine à qui appartient une donnée écrite (ADR-010).

    Args:
        ctx: Contexte de la requête, porteur du sujet authentifié.
        demande: Propriétaire réclamé dans le corps de la requête, s'il y en a un.

    Returns:
        Le sujet authentifié, sauf pour un administrateur qui peut en désigner
        un autre explicitement.
    """
    if demande and ctx.has_permission(Permission.ADMIN_MANAGE):
        return demande
    return ctx.subject


def _appartient_au_sujet(ctx: RBACContext, proprietaire: Optional[str]) -> bool:
    """
    Indique si l'appelant a le droit de voir une donnée.

    Un administrateur voit tout : c'est ce qui rend l'exploitation possible.
    Une donnée sans propriétaire est visible du sujet anonyme, ce qui préserve
    le comportement des déploiements dont les clés ne nomment personne.
    """
    if ctx.has_permission(Permission.ADMIN_MANAGE):
        return True
    return (proprietaire or ANONYMOUS_SUBJECT) == ctx.subject


@app.post("/memory/store", response_model=MemoryItemResponse, tags=["memory"],
           dependencies=[Depends(rate_limit_dependency)])
async def store_memory(
    item: MemoryItemCreate,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_WRITE)),
):
    """Stocker un nouvel élément de mémoire, au nom de l'appelant.

    Le propriétaire est **le sujet authentifié**, pas un champ du corps de la
    requête : sans cela, n'importe quel porteur de clé pouvait écrire dans la
    mémoire d'un autre en déclarant son identifiant (ADR-010, critère C2).

    Un administrateur peut désigner un autre propriétaire — c'est ce qui permet
    d'amorcer des données ou d'en reprendre pour quelqu'un.
    """
    proprietaire = _proprietaire_effectif(ctx, item.user_id)

    # Créer un MemoryItem à partir des données reçues
    memory_item = MemoryItem(
        content=item.content,
        memory_type=item.memory_type,
        user_id=proprietaire,
        session_id=item.session_id,
        agent_id=item.agent_id,
        tags=item.tags,
        metadata=item.metadata,
    )
    # Sauvegarder via le gestionnaire de mémoire
    item_id = memory_manager.save_memory(memory_item)
    # Récupérer l'élément sauvegardé pour retourner les données complètes
    stored_item = memory_manager.get_memory(item_id)
    if stored_item is None:
        raise HTTPException(status_code=500, detail="Échec de la récupération de l'élément stocké")
    # Convertir en dictionnaire pour la réponse
    return {
        "id": stored_item.id,
        "content": stored_item.content,
        "memory_type": stored_item.memory_type.value if hasattr(stored_item.memory_type, 'value') else str(stored_item.memory_type),
        "user_id": stored_item.user_id,
        "session_id": stored_item.session_id,
        "agent_id": stored_item.agent_id,
        "tags": stored_item.tags,
        "created_at": stored_item.created_at,
        "updated_at": stored_item.updated_at,
        "expires_at": stored_item.expires_at,
        "priority": stored_item.priority.name if hasattr(stored_item.priority, 'name') else str(stored_item.priority),
        "status": stored_item.status.value if hasattr(stored_item.status, 'value') else str(stored_item.status),
        "metadata": stored_item.metadata,
        "version": stored_item.version,
    }

@app.get("/memory/retrieve/{item_id}", response_model=MemoryItemResponse, tags=["memory"],
           dependencies=[Depends(rate_limit_dependency)])
async def retrieve_memory(
    item_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_READ)),
):
    """Récupérer un élément de mémoire appartenant à l'appelant.

    La mémoire d'autrui répond **404 et non 403** : distinguer « cela existe
    mais ne vous appartient pas » de « cela n'existe pas » permettrait
    d'énumérer les identifiants d'autres sujets. Même raisonnement que pour une
    clé révoquée, qui reçoit le message d'une clé inconnue.
    """
    item = memory_manager.get_memory(item_id)
    if item is None or not _appartient_au_sujet(ctx, item.user_id):
        raise HTTPException(status_code=404, detail="Élément de mémoire non trouvé")
    return {
        "id": item.id,
        "content": item.content,
        "memory_type": item.memory_type.value if hasattr(item.memory_type, 'value') else str(item.memory_type),
        "user_id": item.user_id,
        "session_id": item.session_id,
        "agent_id": item.agent_id,
        "tags": item.tags,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "expires_at": item.expires_at,
        "priority": item.priority.name if hasattr(item.priority, 'name') else str(item.priority),
        "status": item.status.value if hasattr(item.status, 'value') else str(item.status),
        "metadata": item.metadata,
        "version": item.version,
    }

@app.post("/memory/search", response_model=List[MemoryItemResponse], tags=["memory"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def search_memory(
    query: str,
    limit: int = 10,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_READ)),
):
    """Rechercher dans la mémoire de l'appelant.

    Le filtrage est appliqué **après** la recherche : le moteur de mémoire ne
    connaît pas les sujets, et lui apprendre l'autorisation mélangerait deux
    responsabilités. La conséquence est assumée : la limite porte sur les
    résultats bruts, donc une recherche peut rendre moins d'éléments que
    demandé.
    """
    results = memory_manager.search_memory(query, limit=limit)
    results = [
        (item, score) for item, score in results if _appartient_au_sujet(ctx, item.user_id)
    ]
    # Convertir les tuples (item, score) en objets de réponse
    response_items = []
    for item, score in results:
        response_items.append({
            "id": item.id,
            "content": item.content,
            "memory_type": item.memory_type.value if hasattr(item.memory_type, 'value') else str(item.memory_type),
            "user_id": item.user_id,
            "session_id": item.session_id,
            "agent_id": item.agent_id,
            "tags": item.tags,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "expires_at": item.expires_at,
            "priority": item.priority.name if hasattr(item.priority, 'name') else str(item.priority),
            "status": item.status.value if hasattr(item.status, 'value') else str(item.status),
            "metadata": item.metadata,
            "version": item.version,
            # Optionnel: inclure le score de similarité
            "_score": score,
        })
    return response_items

# Endpoints modèle
@app.post("/model/generate", response_model=ModelGenerateResponse, tags=["model"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MODEL_GENERATE))])
async def generate_text(request: ModelGenerateRequest):
    """Générer du texte à l'aide d'un modèle de langage."""
    # Sélection du modèle
    if request.model_id:
        model_item = model_manager.get_model(request.model_id)
        if model_item is None:
            raise HTTPException(status_code=404, detail=f"Modèle {request.model_id} non trouvé")
    else:
        # Sélection automatique basée sur le prompt (peut être améliorée)
        # Pour simplifier, on utilise le premier modèle actif disponible
        models = model_manager.list_models(status="active")
        if not models:
            raise HTTPException(status_code=503, detail="Aucun modèle actif disponible")
        model_item = models[0]  # À améliorer avec une vraie sélection

    # Préparer les paramètres de génération
    gen_params = {}
    if request.max_tokens is not None:
        gen_params["max_tokens"] = request.max_tokens
    if request.temperature is not None:
        gen_params["temperature"] = request.temperature
    if request.system_prompt is not None:
        gen_params["system_prompt"] = request.system_prompt
    if request.stop_sequences:
        gen_params["stop_sequences"] = request.stop_sequences

    # Génération de texte (méthode asynchrone)
    try:
        # Utiliser la méthode asynchrone du gestionnaire de modèles
        text = await model_manager.generate_text_with_fallback(
            prompt=request.prompt,
            task_requirements={},  # À enrichir selon les besoins
            **gen_params
        )
        # Pour obtenir des métadonnées supplémentaires, on pourrait appeler la méthode synchrone
        # Mais pour simplifier, on retourne juste le texte
        # Dans une version plus complète, on récupérerait les métadonnées de la réponse
        return ModelGenerateResponse(
            text=text,
            status="completed",
            model_used=model_item.name,
            tokens_used=0,  # À implémenter réellement
            latency_seconds=0.0,  # À implémenter réellement
        )
    except Exception as e:
        raise erreur_interne("Erreur lors de la génération", e)

# Endpoint conseil agricole (première feature pour les utilisateurs sénégalais)
@app.post("/agri/advice", response_model=AgriAdviceResponse, tags=["agri"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MODEL_GENERATE))])
async def agri_advice(request: AgriAdviceRequest):
    """Obtenir un conseil agricole adapté au contexte sénégalais, en français ou en wolof."""
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="La question ne peut pas être vide")
    if request.language not in ("fr", "wo"):
        raise HTTPException(status_code=422, detail="Langue invalide : 'fr' ou 'wo' uniquement")

    tool = AgriAdviceTool()
    gen_params = {"language": request.language}
    if request.model_id is not None:
        gen_params["model_id"] = request.model_id
    if request.max_tokens is not None:
        gen_params["max_tokens"] = request.max_tokens

    try:
        result = tool.execute("get_advice", request.question, **gen_params)
        # L'outil ne lève pas quand aucun modèle ne peut répondre : il retourne
        # un statut, pour qu'un agent puisse se rabattre ailleurs. En HTTP, ce
        # statut doit devenir un 503 — répondre 200 avec un conseil vide ferait
        # passer une indisponibilité pour une réponse.
        if result.get("status") not in (None, "ready"):
            raise HTTPException(
                status_code=503,
                detail=result.get("detail") or "Aucun modèle disponible pour le conseil agricole",
            )
        return AgriAdviceResponse(
            answer=result["answer"],
            language=result["language"],
            model_used=result["model_used"],
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Génération du conseil impossible : {e}")

# Endpoints outils
@app.post("/tool/execute", response_model=ToolExecuteResponse, tags=["tool"],
            dependencies=[Depends(rate_limit_dependency)])
async def execute_tool(
    request: ToolExecuteRequest,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Exécuter un outil spécifié.

    `TOOL_EXECUTE` ouvre la porte ; **elle ne dit pas quel outil**. Le plafond du
    rôle est appliqué ici (phase 39.1) : un rôle `user` n'atteint pas l'état de
    la plateforme, un rôle `operator` n'atteint pas les données privées d'une
    personne, et **personne ne saute une approbation** — pas même
    l'administration, parce qu'une approbation qualifie l'acte et non l'acteur.

    Un refus porte son motif dans `detail.reason`, et `detail.decision` distingue
    « jamais » de « il faut un humain » : les deux sont des 403, mais seul le
    second se lève en ouvrant une demande d'approbation.
    """
    if tool_engine is None:
        raise HTTPException(status_code=503, detail="Moteur d'outils non initialisé")

    verdict = authorize(request.tool_id, Actor.from_rbac(ctx), tool_engine.capabilities)
    if not verdict.allowed:
        raise HTTPException(status_code=403, detail={
            "decision": verdict.decision.value,
            "tool_id": verdict.tool_id,
            "reason": verdict.reason,
        })

    try:
        # Exécuter l'outil via le moteur d'outils
        # `input` porte l'opération, `config` ses options : les outils attendent
        # les options en arguments nommés, pas en dictionnaire positionnel.
        result = tool_engine.execute_tool(request.tool_id, request.input, **(request.config or {}))
        return ToolExecuteResponse(
            output=result,
            status="success",
            tool_id=request.tool_id,
        )
    except Exception as e:
        raise erreur_interne("Erreur lors de l'exécution de l'outil", e)


# Capacités des outils.
#
# Le registre disait comment charger un outil, jamais ce que l'exécuter coûte.
# Trois chantiers en dépendent — le modèle de permissions, les connecteurs et le
# moteur de routines — et aucun ne doit relire le YAML pour le savoir.
@app.get("/tools/capabilities", tags=["tool"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.TOOL_EXECUTE))])
async def list_tool_capabilities():
    """Ce que le registre d'outils déclare, et ce qu'il laisse en blanc.

    Le rapport **nomme ses propres lacunes** : un outil sans déclaration
    apparaît dans `undeclared` au lieu de passer pour sûr par omission.
    `coverage` est mesurée, pas promise.
    """
    if tool_engine is None:
        raise HTTPException(status_code=503, detail="Moteur d'outils non initialisé")
    return tool_engine.get_capability_report()


@app.get("/tools/{tool_id}/capability", tags=["tool"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.TOOL_EXECUTE))])
async def get_tool_capability(tool_id: str):
    """Ce qu'un outil touche, ce qu'il change, et s'il peut tourner sans humain.

    Un outil inconnu **n'est pas un 404** : la réponse porte `declared: false`
    et le refus qui va avec. Répondre « introuvable » laisserait croire qu'il
    n'y a rien à savoir, alors que la réponse utile est « je ne sais pas, donc
    non ».
    """
    if tool_engine is None:
        raise HTTPException(status_code=503, detail="Moteur d'outils non initialisé")

    autorise, raison = tool_engine.may_run_unattended(tool_id)
    return {
        **tool_engine.get_tool_capability(tool_id).as_dict(),
        "known_to_registry": tool_engine.get_tool_info(tool_id) is not None,
        "may_run_unattended": autorise,
        "unattended_reason": raison,
    }


@app.get("/tools/authorization", tags=["tool"],
         dependencies=[Depends(rate_limit_dependency)])
async def get_tool_authorization(
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Ce que l'appelant peut lancer, doit faire approuver, ou ne peut pas.

    **Les trois verdicts sont rendus séparément.** Une interface qui n'afficherait
    que `allowed` cacherait à l'utilisateur les outils qu'il a le droit de
    *demander* — et « il faut un humain » n'est ni un oui ni un non.

    L'identité vient de la clé API (ADR-010), jamais du corps de la requête :
    un appelant ne choisit pas le rôle sous lequel il est évalué.
    """
    if tool_engine is None:
        raise HTTPException(status_code=503, detail="Moteur d'outils non initialisé")

    acteur = Actor.from_rbac(ctx)
    plafond = ceiling_for(acteur.role)
    return {
        "subject": acteur.subject,
        "role": acteur.role,
        "ceiling": {
            "scopes": sorted(portee.value for portee in plafond.scopes),
            "effects": sorted(effet.value for effet in plafond.effects),
            "rationale": plafond.rationale,
        },
        "tools": authorized_tools(acteur, tool_engine.capabilities),
    }


@app.get("/tools/{tool_id}/authorization", tags=["tool"],
         dependencies=[Depends(rate_limit_dependency)])
async def get_tool_authorization_for(
    tool_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Le verdict pour l'appelant et un outil précis, avec sa raison.

    Un refus **porte toujours son motif** : un « non » sans cause est
    indébogable pour celui qui le reçoit comme pour celui qui l'exploite.
    """
    if tool_engine is None:
        raise HTTPException(status_code=503, detail="Moteur d'outils non initialisé")

    verdict = authorize(tool_id, Actor.from_rbac(ctx), tool_engine.capabilities)
    return verdict.as_dict()


@app.get("/tools/authorization/matrix", tags=["tool"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_MANAGE))])
async def get_tool_authorization_matrix():
    """La matrice rôle × verdict, **calculée** et non recopiée.

    Une politique décrite dans un document et une politique appliquée par le
    code divergent au premier changement. Celle-ci vient du code.
    """
    if tool_engine is None:
        raise HTTPException(status_code=503, detail="Moteur d'outils non initialisé")
    return authorization_report(tool_engine.capabilities)


# Routines (VOLET 47).
#
# Une routine tourne sans personne devant : tout ce qui coûte cher est vérifié à
# la **déclaration**, et l'exécution n'a plus rien à décider. Les routines d'une
# personne ne sont visibles que d'elle — la liste de ce que quelqu'un surveille
# dit quelque chose de lui.
@app.get("/routines", tags=["routines"],
         dependencies=[Depends(rate_limit_dependency)])
async def list_routines(
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Les routines visibles par l'appelant, et celles de la plateforme."""
    return {
        "routines": [
            routine.as_dict()
            for routine in routine_registry.list_routines(subject=ctx.subject)
        ],
        "registry": routine_registry.registry_report(),
    }


@app.post("/routines", tags=["routines"], status_code=201,
          dependencies=[Depends(rate_limit_dependency)])
async def declare_routine(
    request: RoutineDeclareRequest,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Déclare une routine — **désactivée**.

    Écrire une routine et la faire tourner sont deux décisions, à deux moments.
    Un refus nomme sa cause : une routine refusée sans motif est une routine que
    son auteur réécrira à l'identique.

    Le propriétaire est **l'appelant**, jamais un champ du corps : déclarer une
    routine au nom de quelqu'un d'autre ne doit pas être une requête formulable.
    """
    try:
        routine = routine_registry.declare(
            request.routine_id, request.description,
            [RoutineAction(a.tool_id, a.operation, a.options or {})
             for a in request.actions],
            request.interval_seconds,
            subject=None if request.platform else ctx.subject,
        )
    except RoutineRefused as refus:
        raise HTTPException(status_code=400, detail=str(refus))
    return routine.as_dict()


@app.post("/routines/{routine_id}/enable", tags=["routines"],
          dependencies=[Depends(rate_limit_dependency)])
async def enable_routine(
    routine_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Active une routine déclarée."""
    return _routine_de(routine_id, ctx, activer=True).as_dict()


@app.post("/routines/{routine_id}/disable", tags=["routines"],
          dependencies=[Depends(rate_limit_dependency)])
async def disable_routine(
    routine_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Arrête une routine.

    **Réussit toujours** pour son propriétaire : une routine qu'on ne peut pas
    arrêter est pire qu'une routine absente.
    """
    return _routine_de(routine_id, ctx, activer=False).as_dict()


@app.get("/routines/status", tags=["routines"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.TOOL_EXECUTE))])
async def routines_status():
    """Ce qui est dû maintenant, sans rien déclencher.

    **Aucune boucle ne tourne d'elle-même** : le déclenchement est provoqué par
    `POST /routines/tick`. Une plateforme qui se met à exécuter des routines au
    démarrage sans que personne l'ait demandé est ce qu'un moteur de routines ne
    doit pas être.
    """
    return _scheduler().scheduler_report()


@app.get("/observability/trail/{correlation_id}", tags=["health"],
         dependencies=[Depends(rate_limit_dependency)])
async def observability_trail(
    correlation_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Ce qu'un même travail a laissé dans chaque source.

    Un tour de routine, le workflow qu'il déclenche et les événements d'audit de
    celui-ci portent désormais **le même identifiant** : c'est ce qui permet de
    relire un travail de bout en bout au lieu de trois fragments qui se
    ressemblent.

    Une source **vide** et une source **illisible** ne sont pas confondues :
    « aucun événement ne porte cet identifiant » et « le moteur d'audit est
    indisponible » mènent à des conclusions opposées. Et rien n'est rapproché
    par l'heure — c'est ainsi qu'une piste devient confiante et fausse.

    Chaque source garde sa règle d'audience : suivre une piste n'est pas une
    façon de lire le journal de quelqu'un d'autre.
    """
    try:
        return trail(
            correlation_id,
            audit_manager=get_shared_registry().try_get("audit"),
            journal=routine_journal,
            checkpoints=get_router_engine().checkpoints,
            subject=ctx.subject,
        )
    except ValueError as refus:
        raise HTTPException(status_code=400, detail=str(refus))


@app.get("/observability/report", tags=["health"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.TOOL_EXECUTE))])
async def observability_coverage():
    """Ce qui est traçable de bout en bout, et ce qui ne l'est pas.

    Nommer ce qui n'est **pas** corrélé vaut mieux que de laisser un exploitant
    le découvrir en cherchant une piste qui n'existe pas.
    """
    return observability_report()


@app.get("/orchestrator/paths", tags=["router"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.TOOL_EXECUTE))])
async def orchestrator_paths():
    """Les deux chemins par lesquels un travail atteint l'orchestrateur.

    Une personne qui demande, et une routine qui se déclenche sans personne
    devant. **Le même moteur** pour les deux — mêmes points de reprise, même
    historique, même audit : un second chemin d'exécution sans ces garanties
    serait une implémentation parallèle. Ce qui diffère n'est pas la mécanique,
    c'est ce qui peut être **décidé** : une approbation n'est jamais accordée
    par l'absence de quelqu'un pour la refuser.
    """
    return orchestration_paths(
        workflow_loader=get_router_engine().workflow_loader,
        routine_registry=routine_registry,
    )


@app.post("/routines/tick", tags=["routines"],
          dependencies=[Depends(rate_limit_dependency),
                        Depends(require_permission(Permission.ADMIN_MANAGE))])
async def tick_routines():
    """Exécute ce qui est dû, une fois.

    Réservé à l'administration : déclencher toutes les routines dues est un acte
    d'exploitation, pas une consultation.
    """
    import time as _temps

    tours = []
    for tour in _scheduler().tick(_temps.time()):
        routine = routine_registry.get(tour.routine_id)
        routine_journal.record(tour, subject=routine.subject if routine else None)
        tours.append(tour.as_dict())
    return {"runs": tours, "count": len(tours)}


@app.get("/routines/{routine_id}/journal", tags=["routines"],
         dependencies=[Depends(rate_limit_dependency)])
async def routine_journal_entries(
    routine_id: str, limit: int = 20,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Les derniers tours d'une routine, et ses compteurs.

    Les compteurs **survivent à l'oubli des entrées** : sans eux, une routine
    cassée lundi et rétablie jeudi paraîtrait n'avoir jamais échoué.
    """
    compteurs = routine_journal.stats(routine_id, subject=ctx.subject)
    if compteurs is None:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun journal pour la routine '{routine_id}'.",
        )
    return {
        "routine_id": routine_id,
        "stats": compteurs,
        "runs": routine_journal.runs(routine_id, subject=ctx.subject, limit=limit),
    }


def _routine_de(routine_id: str, ctx: RBACContext, activer: bool):
    """Retrouve une routine visible par l'appelant, puis l'active ou l'arrête."""
    visibles = {
        routine.routine_id
        for routine in routine_registry.list_routines(subject=ctx.subject)
    }
    if routine_id not in visibles:
        # Le même message qu'une routine inexistante : dire « elle existe mais
        # elle n'est pas à vous » renseignerait sur ce qu'une autre personne
        # surveille.
        raise HTTPException(
            status_code=404, detail=f"Routine '{routine_id}' inconnue."
        )
    try:
        return (routine_registry.enable if activer else routine_registry.disable)(
            routine_id
        )
    except RoutineRefused as refus:
        raise HTTPException(status_code=404, detail=str(refus))


# Sûreté des routines (VOLET 48).
@app.get("/routines/safety", tags=["routines"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.TOOL_EXECUTE))])
async def routines_safety():
    """L'état de l'arrêt d'urgence et des budgets."""
    return routine_safety.safety_report()


@app.post("/routines/halt", tags=["routines"],
          dependencies=[Depends(rate_limit_dependency)])
async def halt_routines(
    request: RoutineHaltRequest,
    ctx: RBACContext = Depends(require_permission(Permission.ADMIN_MANAGE)),
):
    """Engage l'arrêt d'urgence : plus aucune routine ne démarre.

    Global à dessein : **au moment où l'on en a besoin, on n'a pas la liste des
    routines.** Il ne se lève jamais tout seul, et il nomme qui l'a engagé —
    sinon personne ne sait s'il a le droit de le lever.

    Il n'interrompt pas un tour déjà commencé : celui-là finit, et aucun autre
    ne démarre.
    """
    try:
        etat = routine_safety.halt(ctx.subject, request.reason)
    except ValueError as refus:
        raise HTTPException(status_code=400, detail=str(refus))
    # L'exploitation l'apprend sans avoir à lire les journaux : un arrêt
    # global engagé par quelqu'un d'autre est exactement ce qu'on découvre
    # trop tard.
    platform_notifier.routines_halted(ctx.subject, request.reason)
    return etat


@app.delete("/routines/halt", tags=["routines"],
            dependencies=[Depends(rate_limit_dependency)])
async def release_routines_halt(
    ctx: RBACContext = Depends(require_permission(Permission.ADMIN_MANAGE)),
):
    """Lève l'arrêt d'urgence.

    La levée se notifie autant que l'engagement : savoir que les routines ont
    repris fait partie de savoir ce qui tourne.
    """
    leve = routine_safety.release()
    if leve:
        platform_notifier.routines_released(ctx.subject)
    return {"released": leve, "halted": routine_safety.halted}


@app.put("/routines/{routine_id}/budget", tags=["routines"],
         dependencies=[Depends(rate_limit_dependency)])
async def set_routine_budget(
    routine_id: str,
    request: RoutineBudgetRequest,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Fixe le nombre de tours autorisés par jour pour une routine.

    Une limite nulle est refusée : ce serait une désactivation déguisée, qui
    laisserait la routine paraître active sans jamais tourner. Arrêter une
    routine se fait explicitement.
    """
    visibles = {
        routine.routine_id
        for routine in routine_registry.list_routines(subject=ctx.subject)
    }
    if routine_id not in visibles:
        raise HTTPException(
            status_code=404, detail=f"Routine '{routine_id}' inconnue."
        )
    try:
        limite = routine_safety.set_limit(routine_id, request.runs_per_day)
    except ValueError as refus:
        raise HTTPException(status_code=400, detail=str(refus))
    return {"routine_id": routine_id, "runs_per_day": limite}


# Endpoints workflows
#
# L'orchestration existait, était testée, et **aucune route ne l'atteignait** :
# `RouterEngine` n'était instancié que par les tests. Même défaut que les
# magasins cloud du VOLET 24 — une capacité qui fonctionne et que personne ne
# peut allumer.
@app.post("/workflow/run", tags=["workflow"],
          dependencies=[Depends(rate_limit_dependency)])
async def run_workflow(
    request: WorkflowRunRequest,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Exécute un workflow d'agents sur une demande.

    `TOOL_EXECUTE` est la permission requise, et c'est la bonne : un workflow
    n'est qu'une suite d'agents qui appellent des outils, donc il ne peut rien
    faire de plus que `POST /tool/execute`.

    **L'exécution est synchrone et peut être longue** — le pipeline `standard`
    mobilise jusqu'à dix agents, dont un qui exécute la suite de tests du
    projet. La durée réelle est dans `execution_time_seconds`, et
    `metadata.decision` dit quels agents ont été retenus et pourquoi.

    Le sujet vient de la clé API (ADR-010), jamais du corps de la requête :
    un appelant ne choisit pas l'identité au nom de laquelle il agit.
    """
    try:
        moteur = get_router_engine()
    except Exception as e:
        raise erreur_interne("Orchestrateur indisponible", e)

    if request.workflow_id and request.workflow_id not in moteur.workflow_loader.get_all_workflows():
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{request.workflow_id}' introuvable",
        )

    try:
        return moteur.process_request(
            request.request,
            user_id=ctx.subject,
            session_id=request.session_id,
            workflow_id=request.workflow_id,
        )
    except ValueError as e:
        # Workflow inexécutable : la cause est dans la déclaration, pas dans la
        # plateforme. L'appelant peut la corriger, donc il la reçoit.
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise erreur_interne("Erreur lors de l'exécution du workflow", e)


@app.get("/workflow/list", tags=["workflow"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def list_workflows():
    """Workflows déclarés, avec leur version et leur exécutabilité.

    Un workflow qui ne peut pas s'exécuter est annoncé comme tel, avec ses
    défauts : le découvrir au moment de l'appel coûte une requête pour rien.
    """
    moteur = get_router_engine()
    declares = moteur.workflow_loader.get_all_workflows()
    return {
        "default": moteur.workflow_loader.get_default_workflow(),
        "workflows": [
            {
                "id": nom,
                "description": definition.get("description"),
                "version": moteur.workflow_loader.get_version(nom),
                "owner": definition.get("owner"),
                "pipeline": definition.get("pipeline", []),
                "agent_selection": (definition.get("execution") or {}).get("agent_selection"),
                "executable": moteur.workflow_loader.is_executable(nom),
                "problems": [p.to_dict() for p in moteur.workflow_loader.get_problems(nom)],
            }
            for nom, definition in declares.items()
        ],
    }


@app.get("/workflow/history", tags=["workflow"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def workflow_history(workflow_id: Optional[str] = None, limit: int = 20):
    """Exécutions récentes et ce qu'elles apprennent.

    Taux de succès ventilé par version du workflow, temps passé par agent et
    agents en échec — les trois mesures que les VOLETs 18 et 19 ont ajoutées et
    qu'aucune route ne servait.
    """
    moteur = get_router_engine()
    return {
        "stats": moteur.history.stats(workflow_id),
        "recent": moteur.history.recent(limit=limit, workflow_id=workflow_id),
    }


# Points de reprise des exécutions (VOLET 49)
#
# L'historique dit ce qu'une exécution a fait une fois finie ; ces routes
# donnent prise sur celles qui ne le sont pas. Sans elles, une exécution morte
# au huitième agent était visible dans les logs et irrattrapable depuis
# l'extérieur.
@app.get("/workflow/runs", tags=["workflow"],
         dependencies=[Depends(rate_limit_dependency)])
async def list_workflow_runs(
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Les exécutions visibles par l'appelant, de la plus récente à la plus ancienne.

    Un point de reprise porte le travail déjà produit : il appartient à qui a
    lancé l'exécution. Celles des autres ne sont pas listées.
    """
    moteur = get_router_engine()
    return {
        "runs": moteur.checkpoints.list_runs(subject=ctx.subject),
        "checkpoints": moteur.checkpoints.checkpoint_report(subject=ctx.subject),
    }


@app.get("/workflow/runs/{run_id}", tags=["workflow"],
         dependencies=[Depends(rate_limit_dependency)])
async def get_workflow_run(
    run_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """L'état d'une exécution : ce qui est fait, ce qui reste, ce qui a été sauté."""
    moteur = get_router_engine()
    execution = moteur.checkpoints.get(run_id, subject=ctx.subject)
    if execution is None:
        # Le même 404 qu'une exécution inexistante : dire « elle existe mais
        # elle n'est pas à vous » renseignerait sur ce que quelqu'un d'autre
        # fait tourner.
        raise HTTPException(status_code=404, detail=f"Exécution '{run_id}' inconnue.")
    return execution.as_dict()


@app.post("/workflow/runs/{run_id}/resume", tags=["workflow"],
          dependencies=[Depends(rate_limit_dependency)])
async def resume_workflow_run(
    run_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Reprend une exécution interrompue, sans refaire ce qui a abouti.

    **Rien n'est demandé dans le corps.** Le workflow et la demande d'origine
    viennent du point de reprise : les redemander à l'appelant permettrait d'en
    changer sans que rien ne le dise, et les étapes déjà faites répondraient
    alors à une autre question que celles qui restent.

    L'exécution est synchrone comme `POST /workflow/run`, et peut être longue.
    """
    moteur = get_router_engine()
    try:
        return moteur.process_request("", user_id=ctx.subject, resume_run_id=run_id)
    except CheckpointRefused as refus:
        if "inconnue" in str(refus):
            raise HTTPException(status_code=404, detail=str(refus))
        # 409 : l'état de l'exécution s'oppose à la reprise — annulée, déjà
        # terminée, ou hors quota. Rien n'a été lancé.
        raise HTTPException(status_code=409, detail=str(refus))
    except Exception as e:
        raise erreur_interne("Erreur lors de la reprise du workflow", e)


@app.post("/workflow/runs/{run_id}/cancel", tags=["workflow"],
          dependencies=[Depends(rate_limit_dependency)])
async def cancel_workflow_run(
    run_id: str,
    request: WorkflowCancelRequest,
    ctx: RBACContext = Depends(require_permission(Permission.TOOL_EXECUTE)),
):
    """Annule une exécution. **Définitif** : elle ne reprendra pas.

    Ce que cela ne fait pas, et qu'il vaut mieux dire : cela n'interrompt pas
    un agent en train de tourner. L'exécution en cours va au bout de son étape ;
    ce que l'annulation garantit, c'est qu'aucune reprise ne suivra.
    """
    moteur = get_router_engine()
    try:
        execution = moteur.checkpoints.cancel(
            run_id, reason=request.reason, subject=ctx.subject,
        )
    except CheckpointRefused as refus:
        if "inconnue" in str(refus):
            raise HTTPException(status_code=404, detail=str(refus))
        raise HTTPException(status_code=400, detail=str(refus))
    return {
        "run_id": execution.run_id,
        "status": execution.status.value,
        "cancelled_reason": execution.cancelled_reason,
        "does_not": [
            "Interrompre une étape déjà commencée : elle finit, et aucune "
            "autre ne démarre.",
        ],
    }


@app.get("/agents/reach", tags=["agents"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def agents_reach():
    """Ce que les agents peuvent réellement appeler — et ce qui leur manque.

    Le mode de panne que cette route existe pour rendre visible est silencieux :
    une capacité arrive dans `src/`, reçoit une route et des tests, et
    n'apparaît jamais dans `AgentContext`. Elle marche alors pour tout le monde
    **sauf** pour les agents dont la plateforme est faite, et rien n'échoue.

    Ce qui est volontairement hors de portée est nommé aussi : une capacité
    manquante et une capacité écartée se ressemblent, et seule la seconde est
    une décision.
    """
    return agent_reach()


@app.get("/documents/from-connector", tags=["documents"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def documents_from_connector(connector_id: Optional[str] = None):
    """Ce que la jonction connecteur → documents garantit, et pour quel connecteur.

    Un document tiré du disque ou de la boîte de quelqu'un appartient à une
    personne, et **rien dans son contenu ne le dit** : c'est le connecteur qui
    le sait. Cette jonction porte cette propriété, ou refuse l'entrée.
    """
    connecteur = None
    if connector_id:
        connecteur = get_shared_connector_registry().get(connector_id)
        if connecteur is None:
            raise HTTPException(
                status_code=404, detail=f"Connecteur '{connector_id}' inconnu.",
            )
    return ingestion_report(connecteur)


@app.get("/memory/layers", tags=["memory"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def memory_layers():
    """Les couches de mémoire : ce que chacune garde, et combien de temps.

    Une couche **est** une durée de vie. `lifetime_seconds: null` veut dire
    « ne périme pas » — écrit, donc décidé, jamais oublié.

    `capped_expirations` compte les expirations demandées plus longues que leur
    couche et ramenées à elle : rallonger une durée de vie est une promotion, et
    une promotion se décide avec un auteur et une raison — pas en passant un
    nombre plus grand.
    """
    return {
        **layers_report(),
        "capped_expirations": getattr(memory_manager, "capped_expirations", 0),
    }


# Greffons (VOLET 58)
#
# Un greffon est du code que ce dépôt n'a pas écrit. Installer l'inscrit
# **désactivé** ; activer est une décision d'exploitation, tracée.
@app.get("/plugins", tags=["plugins"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def list_plugins():
    """Les greffons installés, lesquels sont activés, et par qui."""
    return {
        **plugin_registry.registry_report(),
        "execution": execution_report(plugin_registry),
    }


@app.post("/plugins/discover", tags=["plugins"],
          dependencies=[Depends(rate_limit_dependency),
                        Depends(require_permission(Permission.ADMIN_MANAGE))])
async def discover_plugins():
    """Installe les greffons présents dans `plugins/`, **désactivés**.

    Un répertoire qui échoue n'arrête pas les autres, et sa raison est rendue :
    un greffon mal écrit ne doit pas empêcher les greffons corrects d'exister.
    """
    return plugin_discover(plugin_registry)


@app.post("/plugins/{plugin_id}/enable", tags=["plugins"],
          dependencies=[Depends(rate_limit_dependency)])
async def enable_plugin(
    plugin_id: str,
    request: PluginEnableRequest,
    ctx: RBACContext = Depends(require_permission(Permission.ADMIN_MANAGE)),
):
    """Active un greffon. **Qui décide vient de la clé, jamais du corps.**

    La raison sera lue par quelqu'un qui n'était pas là quand la confiance a été
    accordée à du code écrit ailleurs.
    """
    try:
        manifeste = plugin_registry.enable(plugin_id, ctx.subject, request.reason)
    except PluginRefused as refus:
        code = 404 if "inconnu" in str(refus) else 400
        raise HTTPException(status_code=code, detail=str(refus))
    return {
        **manifeste.as_dict(),
        "activation": plugin_registry.activation_of(plugin_id),
    }


@app.post("/plugins/{plugin_id}/disable", tags=["plugins"],
          dependencies=[Depends(rate_limit_dependency),
                        Depends(require_permission(Permission.ADMIN_MANAGE))])
async def disable_plugin(plugin_id: str):
    """Désactive un greffon. **Aucune raison demandée** : arrêter doit être gratuit."""
    try:
        return plugin_registry.disable(plugin_id).as_dict()
    except PluginRefused as refus:
        raise HTTPException(status_code=404, detail=str(refus))


@app.get("/plugins/{plugin_id}/review", tags=["plugins"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_MANAGE))])
async def review_plugin_route(plugin_id: str):
    """Compare ce qu'un greffon **déclare** à ce que son code **montre**.

    Un écart est un fait sur deux documents — le manifeste et le code — jamais
    un jugement sur l'auteur. Et **« aucun écart » ne veut pas dire « sûr »** :
    la liste des modules connus est incomplète par construction, et un greffon
    peut atteindre le réseau par un nom construit à l'exécution.
    """
    try:
        return {**review_plugin(plugin_id, plugin_registry), **review_report()}
    except ReviewRefused as refus:
        code = 404 if "inconnu" in str(refus) else 409
        raise HTTPException(status_code=code, detail=str(refus))


@app.post("/plugins/{plugin_id}/run", tags=["plugins"],
          dependencies=[Depends(rate_limit_dependency),
                        Depends(require_permission(Permission.ADMIN_MANAGE))])
async def run_plugin_route(plugin_id: str):
    """Exécute le **point d'entrée déclaré** d'un greffon, dans le bac à sable.

    Aucun code n'est accepté dans la requête : il vient du fichier que le
    manifeste désigne, et de nulle part ailleurs. Sans cela, l'autorisation
    porterait sur un manifeste et l'exécution sur autre chose.

    La sortie revient enveloppée comme **donnée externe** — jamais comme une
    instruction — et ce que le bac à sable ne garantit pas voyage avec elle.
    """
    try:
        resultat = run_installed(plugin_id, plugin_registry)
    except PluginExecutionRefused as refus:
        code = 404 if "inconnu" in str(refus) else 409
        raise HTTPException(status_code=code, detail=str(refus))
    return {**resultat, "output": resultat["output"].to_dict()}


# Connaissance mondiale (VOLET 52)
#
# Dérivée de jeux acquis, jamais écrite de mémoire. Ces routes servent ce que le
# dépôt contient réellement : une donnée que rien ne lit n'est pas une
# connaissance.
@app.get("/knowledge/world", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.KNOWLEDGE_SEARCH))])
async def world_knowledge_state():
    """Ce que la connaissance mondiale contient, et ce qu'elle ne fait pas.

    `built: false` **n'est pas** un monde vide : c'est un fichier jamais
    construit, et la distinction doit se voir avant la première question.
    """
    return world_report()


@app.get("/knowledge/world/country/{query}", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.KNOWLEDGE_SEARCH))])
async def world_country(query: str, field: Optional[str] = None):
    """Un pays, par code ISO ou par nom officiel — ou `UNKNOWN`.

    **Aucune approximation.** Un nom qui ne correspond exactement à aucun pays
    ne rend pas le plus proche : « Niger » et « Nigeria » sont deux pays, et
    rendre l'un pour l'autre serait la pire réponse possible — plausible et
    fausse.

    Avec `field`, la réponse porte la valeur, sa provenance, et les désaccords
    entre sources qui la concernent : les taire donnerait une réponse plus nette
    et moins vraie.
    """
    reponse = (
        answer_field(query, field) if field else answer_country(query)
    )
    # 200 même pour un `UNKNOWN` : « je ne sais pas » est une réponse, et elle
    # porte ce qui trancherait. Un 404 laisserait croire à une panne de route.
    return reponse


@app.get("/knowledge/world/country/{query}/series/{indicator}", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.KNOWLEDGE_SEARCH))])
async def world_country_series(query: str, indicator: str, year: Optional[str] = None):
    """Une mesure — population, PIB — avec **l'année où elle a été mesurée**.

    Sans `year`, la dernière année mesurée est rendue. Ce n'est pas l'année en
    cours : rien n'est extrapolé, et une année absente le reste. Un chiffre sans
    son année est une phrase sur aucun moment en particulier.

    Un pays absent de la série rend `UNKNOWN` — jamais zéro, qui serait une
    mesure.
    """
    pays = answer_country(query)
    if pays["status"] != "FOUND":
        return pays

    reponse = answer_series(
        pays["country"]["iso3"], indicator, load_series(), year=year,
    )
    if reponse["status"] == "FOUND":
        # La portée appartient au pays, pas à la série : elle est jointe ici.
        reponse["scope"] = pays["country"]["scope"]
        reponse["freshness"] = freshness_of_year(reponse["year"], indicator)
    return reponse


@app.get("/knowledge/ask", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.KNOWLEDGE_SEARCH))])
async def knowledge_ask(q: str, scope: Optional[str] = None,
                        subject: Optional[str] = None):
    """Pose une question à la couche qui doit y répondre — et dit **laquelle**.

    Deux corps de connaissance peuvent parler du Sénégal : la référence
    mondiale (largeur, 249 pays) et la couche sénégalaise (profondeur, un
    pays). Deux moteurs qui répondent à la même question ne sont pas une
    fonctionnalité : le jour où ils divergent, le désaccord serait invisible.

    Un sujet national — droit, administration, langues — **ne quitte pas son
    pays** : la référence mondiale n'en est pas un repli, elle est hors sujet.
    """
    try:
        return ask(q, scope=scope, subject=subject)
    except ValueError as refus:
        raise HTTPException(status_code=400, detail=str(refus))


@app.get("/knowledge/layers", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def knowledge_layers():
    """Ce que chaque couche porte, mesuré, et le routage qui les sépare."""
    return {**layer_comparison(), "routing": routing_report()}


@app.get("/knowledge/domains", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.KNOWLEDGE_SEARCH))])
async def knowledge_domains(scope: str = "global"):
    """Ce que la plateforme couvre pour une portée — et ce qu'elle ne couvre pas.

    Trois absences se ressemblent et appellent trois gestes différents :
    **aucune source inscrite** (personne n'a dit qui ferait autorité),
    **inscrite mais non activée** (le domaine n'a jamais eu le droit d'essayer),
    **active et vide** (une acquisition a tourné et n'a rien rapporté). Les
    confondre ferait chercher au mauvais endroit.

    Sans compteur branché, le nombre d'éléments vaut `null` — jamais zéro : un
    comptage absent ne devient pas une base vide.
    """
    try:
        return domain_coverage(scope)
    except ValueError as refus:
        raise HTTPException(status_code=400, detail=str(refus))


@app.get("/knowledge/freshness", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def knowledge_freshness():
    """L'âge de **tout** ce que ce dépôt a dérivé.

    La question qu'un opérateur pose une fois par an et à laquelle personne ne
    pouvait répondre : « qu'est-ce qui, ici, est vieux ? »

    Deux âges sont distingués. `built_at` date la **dérivation**, pas les faits :
    relancer un script rajeunit l'un sans toucher l'autre, et les confondre
    ferait passer une base périmée pour fraîche. Le verdict retenu est le pire
    des deux, et il dit lequel le porte.
    """
    return repository_freshness()


@app.get("/knowledge/world/series", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.KNOWLEDGE_SEARCH))])
async def world_series_state():
    """Ce que les séries couvrent, leur fraîcheur, et ce qu'elles ne font pas."""
    series = load_series()
    return {**series_report(series), "freshness": freshness_report(series)}


# Endpoints connaissances
@app.post("/knowledge/search", response_model=KnowledgeSearchResponse, tags=["knowledge"],
            dependencies=[Depends(rate_limit_dependency)])
async def search_knowledge(request: KnowledgeSearchRequest,
                           ctx: RBACContext = Depends(require_permission(Permission.KNOWLEDGE_SEARCH))):
    """Rechercher des connaissances par similarité.

    Le rôle de l'appelant filtre les résultats par sensibilité (VOLET 05,
    chapitre 07) : une connaissance confidentielle n'apparaît pas à un rôle qui
    n'a pas le droit de la lire, et rien ne signale son existence.
    """
    try:
        results = knowledge_manager.search_knowledge(request.query, limit=request.limit,
                                                     role=ctx.role.value)
        # Convertir les KnowledgeItem en dictionnaires
        result_dicts = []
        for item in results:
            result_dict = {
                "id": item.id,
                "content": item.content,
                "source": item.source.value if hasattr(item.source, 'value') else str(item.source),
                "confidence": item.confidence,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "metadata": item.metadata,
            }
            result_dicts.append(result_dict)
        return KnowledgeSearchResponse(
            results=result_dicts,
            total=len(result_dicts),
        )
    except Exception as e:
        raise erreur_interne("Erreur lors de la recherche", e)

@app.get("/security/threats", tags=["health"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_AUDIT))])
async def security_threats():
    """Les sources dont les échecs d'authentification dépassent le seuil.

    La plateforme comptait les échecs sans rien en conclure : douze tentatives
    avec douze clés différentes donnaient un compteur à 12 et aucun signal
    (VOLET 11, ch. 05). Cette route dit **qui** insiste, depuis quand, et à
    quelle sévérité.

    Ce qu'elle ne fait pas est nommé dans `unavailable_methods` : ni analyse
    comportementale, ni corrélation de renseignement, ni analyse assistée par
    modèle. Une fenêtre glissante d'échecs est une détection honnête ; l'appeler
    autrement ne le serait pas.

    Aucune clé ni empreinte de clé n'apparaît ici — une source est une adresse.
    """
    return get_shared_detector().summary()


@app.get("/analytics", tags=["health"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_AUDIT))])
async def analytics():
    """Ce que la plateforme a fait, agrégé à partir de ce qu'elle mesure déjà.

    `/metrics` répond « combien de requêtes » ; cette route répond « qu'ont fait
    les agents, quels workflows ont réussi, quelles sources alimentent
    réellement l'analytique » (VOLET 09, ch. 02 et 06).

    Elle ne collecte rien : elle agrège l'audit, l'historique des workflows et
    les compteurs. Une source absente rend `null`, jamais zéro — un zéro se
    lirait comme une mesure. Ce que la plateforme ne sait pas produire — les
    tendances, la détection d'anomalies, les tableaux de bord — est nommé dans
    `unavailable` avec sa raison.
    """
    registre = get_shared_registry()
    return build_analytics_report(
        audit_manager=registre.try_get("audit"),
        metrics=metrics_snapshot(),
    )


@app.get("/trace/{request_id}", tags=["health"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_AUDIT))])
async def request_trace(request_id: str):
    """Le chemin d'une requête : ce qui a tourné, et où est passé le temps.

    `/metrics` répond « combien », `/analytics` répond « qu'ont fait les agents
    en général ». Aucune route ne répondait « qu'est-il arrivé à **cette**
    requête », alors que l'audit portait déjà l'information : un `request_id` sur
    chaque événement et une durée sur les appels d'outils et de modèles.
    `POST /workflow/run` rend ce `request_id` — c'est lui qui s'utilise ici.

    Rien n'est collecté en plus : la trace est une lecture de l'audit.
    """
    registre = get_shared_registry()
    return build_trace(registre.try_get("audit"), request_id)


@app.get("/knowledge/governance", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_AUDIT))])
async def knowledge_governance():
    """Qui possède quel domaine, et ce que personne ne possède (VOLET 05, ch. 06 et 10).

    Le chapitre 10 demande de publier les métriques de gouvernance : sans cette
    route, l'attribution des domaines n'est lisible que dans une variable
    d'environnement, et les domaines orphelins ne se voient nulle part.
    """
    return knowledge_manager.governance_report()


@app.get("/knowledge/quality", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_AUDIT))])
async def knowledge_quality():
    """Complétude, fraîcheur, doublons et couverture de validation (VOLET 05, ch. 09 et 10).

    Les deux métriques que la plateforme ne sait pas calculer — exactitude et
    retour utilisateur — sont nommées dans `unavailable` avec leur raison, et ne
    portent aucun chiffre.
    """
    return knowledge_manager.quality_report()


@app.get("/knowledge/languages", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def knowledge_languages():
    """Ce que la plateforme sait réellement faire par langue (VOLET 36, ch. B).

    Le wolof, le pulaar et le sérère sont désormais étiquetables — un document
    peut être stocké, filtré et retrouvé lexicalement dans sa langue. **Cela ne
    veut pas dire que la plateforme les comprend**, et cette route existe pour
    que la distinction soit lisible : neuf capacités, un verdict chacune, et
    `unknown` là où rien n'a jamais été mesuré ici plutôt qu'un « non » qui
    refermerait la question.
    """
    from src.knowledge_engine.languages import languages_report

    return languages_report()


@app.get("/knowledge/factual-benchmark", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def knowledge_factual_benchmark():
    """L'état réel du jeu de référence factuel sénégalais (VOLET 36, ch. C).

    **Il ne porte aucune entrée vérifiée**, et la route le publie plutôt que de
    le taire : une entrée de référence exige un document que le projet détient,
    et le dépôt n'en détient encore aucun. Les entrées `to_source` nomment la
    question et l'institution qui la trancherait — elles ne notent rien, et
    `score_entry()` refuse de les utiliser.

    Une entrée écrite de mémoire ferait de chaque mesure future une mesure de
    cette mémoire.
    """
    from src.knowledge_engine.factual_evaluation import benchmark_report

    return benchmark_report()


@app.get("/knowledge/health-policy", tags=["knowledge"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def knowledge_health_policy():
    """Ce que la plateforme refuse de dire en santé (VOLET 35, ch. 10).

    Trois règles : un **plancher de sources** plus haut que le seuil général,
    un avertissement sur chaque réponse, et le refus de toute forme d'acte
    médical — posologie, diagnostic, prescription — **quoi que disent les
    sources**.

    Ce refus est du code appliqué après la génération, pas une consigne
    d'invite : un modèle qui a lu la bonne notice peut quand même écrire
    « 500 mg toutes les six heures ». Ce que le filtre ne détecte pas est nommé.
    """
    from src.knowledge_engine.health_policy import health_policy_report

    return health_policy_report()


# Endpoints d'approbation humaine (ADR-006)
# Un agent peut suspendre une action dans l'état `requires_approval` ; un
# opérateur humain consulte la file d'attente et approuve ou refuse chaque
# demande. Toute décision est tracée dans le système d'audit.

def _serialize_approval_request(request) -> Dict[str, Any]:
    """Sérialise une demande d'approbation en dictionnaire."""
    return request.to_dict() if hasattr(request, 'to_dict') else dict(request)


@app.get("/approval/pending", tags=["approval"],
           dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.APPROVAL_VIEW))])
async def list_pending_approvals(limit: int = 100):
    """Liste les demandes d'approbation en attente (de la plus ancienne à la plus récente)."""
    requests = approval_manager.list_pending(limit=limit)
    return {
        "requests": [_serialize_approval_request(req) for req in requests],
        "total": len(requests),
    }


@app.get("/approval/stats", tags=["approval"],
           dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.APPROVAL_VIEW))])
async def approval_stats():
    """Statistiques agrégées de la file d'approbation."""
    return approval_manager.stats()


@app.get("/approval/{request_id}", tags=["approval"],
           dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.APPROVAL_VIEW))])
async def get_approval(request_id: str):
    """Retourne une demande d'approbation par son identifiant."""
    request = approval_manager.get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail=f"Demande d'approbation {request_id} introuvable")
    return _serialize_approval_request(request)


@app.post("/approval/{request_id}/approve", tags=["approval"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.APPROVAL_DECIDE))])
async def approve_request(request_id: str, decision: ApprovalDecisionRequest):
    """Approuve une demande d'approbation en attente.

    L'action de l'agent peut alors être considérée comme validée par un humain.
    """
    decided = approval_manager.approve(
        request_id,
        reason=decision.reason,
        decided_by=decision.decided_by,
    )
    if not decided:
        raise HTTPException(
            status_code=409,
            detail=f"Demande {request_id} introuvable ou déjà décidée",
        )
    return {"request_id": request_id, "status": "approved"}


@app.post("/approval/{request_id}/reject", tags=["approval"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.APPROVAL_DECIDE))])
async def reject_request(request_id: str, decision: ApprovalDecisionRequest):
    """Refuse une demande d'approbation en attente.

    Un motif est recommandé pour que l'agent et l'audit gardent la trace du
    pourquoi de la décision.
    """
    decided = approval_manager.reject(
        request_id,
        reason=decision.reason,
        decided_by=decision.decided_by,
    )
    if not decided:
        raise HTTPException(
            status_code=409,
            detail=f"Demande {request_id} introuvable ou déjà décidée",
        )
    return {"request_id": request_id, "status": "rejected"}


# Endpoints RBAC
@app.get("/auth/me", tags=["auth"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_auth)])
async def auth_me(ctx: RBACContext = Depends(require_auth)):
    """Retourne les informations d'authentification et le rôle de l'utilisateur.

    Utile pour qu'un client vérifie son rôle et ses permissions sans effectuer
    d'opération.
    """
    return {
        "authenticated": True,
        "role": ctx.role.value,
        "permissions": sorted(p.value for p in ctx.permissions),
    }


@app.get("/auth/roles", tags=["auth"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.ADMIN_MANAGE))])
async def list_roles():
    """Liste tous les rôles et leurs permissions (réservé aux administrateurs)."""
    from src.api.rbac import Role, get_permissions_for_role
    return {
        role.value: sorted(p.value for p in get_permissions_for_role(role))
        for role in Role
    }


def _sync_rate_limiter() -> None:
    """Réaligne le limiteur de taux sur les clés actuellement actives.

    Sans cet appel après un rechargement ou une révocation, le limiteur
    continuerait de traiter une clé coupée comme un client authentifié, avec
    le quota élevé qui va avec.
    """
    set_valid_api_key_digests(rbac_manager.active_key_digests())


@app.get("/auth/whoami", tags=["auth"],
         dependencies=[Depends(rate_limit_dependency)])
async def whoami(ctx: RBACContext = Depends(require_auth)):
    """Dit qui appelle : sujet, rôle et permissions (ADR-010).

    Aucune permission particulière n'est exigée — la route ne révèle que ce que
    l'appelant possède déjà. Elle existe parce qu'une clé mal attribuée est
    invisible autrement : on découvre son identité en lisant les traces d'audit,
    trop tard.
    """
    return {
        "subject": ctx.subject,
        "role": ctx.role.value,
        "fingerprint": ctx.key_fingerprint,
        "permissions": sorted(p.value for p in ctx.permissions),
    }


@app.get("/auth/keys", tags=["auth"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_MANAGE))])
async def list_api_keys():
    """Inventorie les clés API : empreinte, rôle, état de révocation.

    Aucune clé n'y figure. Un opérateur doit pouvoir voir combien de clés
    existent et avec quels droits, sans obtenir de quoi s'en servir.
    """
    cles = rbac_manager.list_keys()
    return {
        "total": len(cles),
        "revoked": sum(1 for cle in cles if cle["revoked"]),
        # L'état de révocation décrit *cette* instance et aucune autre (ADR-009).
        # Sans cette précision, un inventaire sans clé révoquée se lit comme
        # « aucune clé n'est coupée sur la plateforme ».
        "scope": "instance",
        "instance": instance_id(),
        "keys": cles,
    }


@app.post("/auth/keys/{fingerprint}/revoke", tags=["auth"],
          dependencies=[Depends(rate_limit_dependency),
                        Depends(require_permission(Permission.ADMIN_MANAGE))])
async def revoke_api_key(fingerprint: str):
    """Coupe immédiatement une clé, désignée par son empreinte.

    La révocation a deux limites, et toutes deux figurent dans la réponse :

    - elle **ne survit pas au redémarrage** : la source durable des clés reste
      l'environnement du déploiement (ADR-004) ;
    - elle **ne vaut que pour cette instance** : la liste de révocation vit
      dans la mémoire du processus (ADR-009), donc la clé continue d'ouvrir
      toute autre instance de la plateforme.

    Un opérateur qui ne connaît pas la seconde limite croit avoir coupé une clé
    compromise alors qu'elle reste valide ailleurs. C'est la raison pour
    laquelle elle est écrite dans la réponse plutôt que dans un document.
    """
    if not rbac_manager.revoke(fingerprint):
        raise HTTPException(status_code=404, detail=f"Empreinte '{fingerprint}' inconnue.")

    _sync_rate_limiter()
    return {
        "fingerprint": fingerprint,
        "revoked": True,
        "persistent": False,
        "scope": "instance",
        "instance": instance_id(),
        "detail": (
            "Révocation immédiate, limitée à cette instance et non persistante. "
            "Retirez la clé de GALSEN_API_KEYS et redémarrez chaque instance "
            "pour la couper partout et définitivement."
        ),
    }


@app.post("/auth/keys/{fingerprint}/restore", tags=["auth"],
          dependencies=[Depends(rate_limit_dependency),
                        Depends(require_permission(Permission.ADMIN_MANAGE))])
async def restore_api_key(fingerprint: str):
    """Lève une révocation posée par erreur."""
    if not rbac_manager.restore(fingerprint):
        raise HTTPException(
            status_code=404, detail=f"Aucune révocation pour l'empreinte '{fingerprint}'."
        )

    _sync_rate_limiter()
    return {
        "fingerprint": fingerprint,
        "revoked": False,
        "scope": "instance",
        "instance": instance_id(),
    }


@app.post("/auth/keys/reload", tags=["auth"],
          dependencies=[Depends(rate_limit_dependency),
                        Depends(require_permission(Permission.ADMIN_MANAGE))])
async def reload_api_keys():
    """Relit `GALSEN_API_KEYS` et resynchronise le limiteur de taux.

    Utile après une rotation : la nouvelle clé devient valide et l'ancienne
    cesse de l'être sans interrompre le service. Le résumé retourné ne contient
    que des empreintes.
    """
    resume = rbac_manager.reload()
    _sync_rate_limiter()
    return resume


# =========================================================================
# Endpoints — Connecteurs externes (ADR-007)
# =========================================================================

@app.get("/connectors", tags=["connectors"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.CONNECTOR_VIEW))])
async def list_connectors():
    """Décrit les intégrations externes de cette installation.

    Aucun appel sortant : cet inventaire répond depuis la configuration seule,
    de sorte qu'un déploiement s'audite sans solliciter les services distants.
    """
    registre = get_shared_connector_registry()
    return {
        "total": registre.count(),
        "kinds": [kind.value for kind in registre.kinds()],
        "connectors": registre.describe_all(),
    }


@app.get("/connectors/status", tags=["connectors"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.CONNECTOR_CHECK))])
async def check_connectors():
    """Vérifie chaque connecteur et retourne un rapport agrégé.

    Contrairement à `/connectors`, cette route **contacte les services
    externes** : elle demande donc une permission distincte.
    """
    return get_shared_connector_registry().check_all()


@app.get("/connectors/{connector_id}", tags=["connectors"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.CONNECTOR_VIEW))])
async def describe_connector(connector_id: str):
    """Décrit un connecteur précis, sans le contacter."""
    connecteur = get_shared_connector_registry().get(connector_id)
    if connecteur is None:
        raise HTTPException(status_code=404, detail=f"Connecteur '{connector_id}' inconnu.")

    description = connecteur.describe().to_dict()
    description["configured"] = connecteur.is_configured()
    return description


@app.get("/connectors/{connector_id}/contract", tags=["connectors"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.CONNECTOR_VIEW))])
async def get_connector_contract(
    connector_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.CONNECTOR_VIEW)),
):
    """Ce qu'un connecteur touche, pour le compte de qui, et ce qu'il conserve.

    Le rapport de conformité **nomme les manques** : un connecteur incomplet y
    apparaît au lieu de passer pour conforme.

    Pour un connecteur par sujet, l'état d'autorisation est celui de
    **l'appelant** — l'identité vient de la clé API (ADR-010). Aucun jeton n'est
    publié, ici ni ailleurs.
    """
    connecteur = get_shared_connector_registry().get(connector_id)
    if connecteur is None:
        raise HTTPException(status_code=404, detail=f"Connecteur '{connector_id}' inconnu.")

    return {
        **conformance(connecteur),
        "lifecycle": lifecycle_report(connecteur, ctx.subject),
        # Ce que le connecteur demande, et ce qu'aucune déclaration ne lui
        # ouvrira jamais. C'est ce qu'une personne doit lire avant de consentir.
        "safety": safety_report(connecteur),
    }


# OAuth 2.0 (VOLET 43).
#
# **Aucun fournisseur n'est configuré dans cet environnement**, et ces routes le
# disent : elles répondent 503 en nommant les variables manquantes plutôt que de
# renvoyer une adresse de consentement qui ne mènerait nulle part.
#
# Aucun jeton ne sort par ces routes, et aucune n'accepte un sujet dans son
# corps : l'identité vient de la clé API (ADR-010).
@app.get("/oauth/providers", tags=["oauth"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.CONNECTOR_VIEW))])
async def list_oauth_providers():
    """Les fournisseurs déclarés, et ce qui manque pour s'en servir.

    Les points d'accès publiés ici sont une **copie** de ce que le fournisseur
    publie à son `discovery_url` ; les confronter appartient à qui détient les
    identifiants. Aucun appel réseau n'est fait.
    """
    return oauth_configuration_report()


@app.post("/oauth/{provider_id}/authorize", tags=["oauth"],
          dependencies=[Depends(rate_limit_dependency)])
async def begin_oauth_authorization(
    provider_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.CONNECTOR_VIEW)),
):
    """Prépare l'envoi de l'appelant vers l'écran de consentement.

    Le consentement est demandé **pour l'appelant**, jamais pour un sujet nommé
    dans le corps : demander l'accès au courrier de quelqu'un d'autre ne doit
    pas être une requête que l'on peut formuler.
    """
    session = _oauth_session(provider_id)
    try:
        depart = session.begin(ctx.subject)
    except OAuthNotConfigured as absent:
        raise HTTPException(status_code=503, detail=str(absent))
    except (ScopeRefused, FlowRefused) as refus:
        raise HTTPException(status_code=400, detail=str(refus))

    return {
        "authorization_url": depart.url,
        "state": depart.pending.state,
        "expires_in": DUREE_DE_VIE_SECONDES,
        "scopes": list(depart.pending.scopes),
        "subject": depart.pending.subject,
    }


@app.delete("/oauth/{provider_id}/authorization", tags=["oauth"],
            dependencies=[Depends(rate_limit_dependency)])
async def revoke_oauth_authorization(
    provider_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.CONNECTOR_VIEW)),
):
    """Retire l'accès de l'appelant.

    **Réussit toujours de ce côté**, y compris sans identifiants configurés,
    sans clé de chiffrement, ou si l'accès était déjà périmé : reprendre son
    accès n'est pas une faveur qu'on demande à la plateforme.

    `provider_notified` reste `false` tant que personne n'a envoyé la requête de
    révocation au fournisseur — cet environnement ne peut pas l'envoyer. Le
    champ existe pour que « nous avons oublié » ne se lise jamais comme « le
    fournisseur a oublié ».
    """
    session = _oauth_session(provider_id)
    return session.revoke_detailed(ctx.subject).as_dict()


@app.get("/connectors/{connector_id}/check", tags=["connectors"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.CONNECTOR_CHECK))])
async def check_connector(connector_id: str):
    """Vérifie un connecteur précis en contactant le service externe."""
    resultat = get_shared_connector_registry().check(connector_id)
    if resultat is None:
        raise HTTPException(status_code=404, detail=f"Connecteur '{connector_id}' inconnu.")
    return resultat.to_dict()


# =========================================================================
# Endpoints — Service de Notification
# =========================================================================

def _resolve_notification_type(raw: str) -> NotificationType:
    """Résout un nom de type de notification."""
    try:
        return NotificationType(raw)
    except ValueError:
        return NotificationType.INFO


def _resolve_notification_priority(raw: str) -> NotificationPriority:
    """Résout un nom de priorité de notification."""
    try:
        return NotificationPriority(raw)
    except ValueError:
        return NotificationPriority.NORMAL


@app.post("/notification/send", tags=["notification"],
           dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_WRITE))])
async def send_notification(request: NotificationCreateRequest):
    """Envoie une notification dans la plateforme."""
    notif_id = notification_manager.send_notification(
        notification_type=_resolve_notification_type(request.type),
        title=request.title,
        message=request.message,
        priority=_resolve_notification_priority(request.priority),
        recipient=request.recipient,
        role=request.role,
        source=request.source,
        related_id=request.related_id,
        metadata=request.metadata,
    )
    if notif_id is None:
        raise HTTPException(status_code=500, detail="Échec de l'envoi de la notification")
    return {"notification_id": notif_id, "status": "sent"}


@app.post("/notification/list", tags=["notification"],
           dependencies=[Depends(rate_limit_dependency)])
async def list_notifications(
    request: NotificationListRequest,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_READ)),
):
    """Liste les notifications adressées à l'appelant (ADR-010, critère C2).

    Pour les notifications, la contrainte porte sur la **lecture** et non sur
    l'écriture : `recipient` désigne le destinataire, pas l'auteur. Envoyer à
    quelqu'un d'autre reste légitime — c'est ce que fait le moteur d'approbation
    quand il sollicite un opérateur ; lire le courrier d'autrui ne l'est pas.
    """
    notifications = notification_manager.list_notifications(
        limit=request.limit,
        offset=request.offset,
        unread_only=request.unread_only,
        notification_type=request.notification_type,
        recipient=_proprietaire_effectif(ctx, request.recipient),
        role=request.role,
    )
    return {
        "notifications": [n.to_dict() for n in notifications],
        "total": len(notifications),
    }


@app.post("/notification/mark-read/{notification_id}", tags=["notification"],
           dependencies=[Depends(rate_limit_dependency)])
async def mark_notification_read(
    notification_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_WRITE)),
):
    """Marque comme lue une notification adressée à l'appelant."""
    notification = notification_manager.get(notification_id)
    if notification is not None and not _appartient_au_sujet(ctx, notification.recipient):
        # 404 et non 403 : le refus doit être indiscernable d'une absence.
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} introuvable")

    success = notification_manager.mark_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} introuvable")
    return {"notification_id": notification_id, "status": "read"}


@app.post("/notification/mark-all-read", tags=["notification"],
           dependencies=[Depends(rate_limit_dependency)])
async def mark_all_read(
    recipient: Optional[str] = None,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_WRITE)),
):
    """Marque comme lues les notifications de l'appelant.

    Sans cette liaison, un porteur de clé pouvait vider la boîte de n'importe
    qui en nommant son destinataire.
    """
    count = notification_manager.mark_all_read(recipient=_proprietaire_effectif(ctx, recipient))
    return {"marked_read": count}


@app.get("/notification/channels", tags=["notification"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.HEALTH_VIEW))])
async def notification_channels():
    """Les canaux de livraison déclarés, et lesquels peuvent réellement partir.

    Un canal sans identifiants rapporte `NOT_CONFIGURED` et nomme les variables
    qui lui manquent — **jamais leurs valeurs**. Il ne prétend pas avoir
    envoyé : croire que quelqu'un a été prévenu alors que rien n'est parti
    serait le pire résultat possible.
    """
    return notification_channels_registry.channels_report()


@app.get("/notification/channels/plan", tags=["notification"],
         dependencies=[Depends(rate_limit_dependency)])
async def notification_delivery_plan(
    ctx: RBACContext = Depends(require_permission(Permission.HEALTH_VIEW)),
):
    """Ce qui partirait pour une notification adressée à l'appelant.

    Une destination partagée — salon d'équipe, supervision — ne porte pas la
    notification de quelqu'un : elle est lue par plus de monde que son
    destinataire.
    """
    return {
        "personal": notification_channels_registry.delivery_plan(ctx.subject),
        "platform": notification_channels_registry.delivery_plan(None),
    }


@app.get("/notification/stats", tags=["notification"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def notification_stats():
    """Statistiques agrégées des notifications, et ce qu'elles deviennent.

    Le comptage par type et par priorité dit ce qui a été créé ; le rapport de
    livraison (VOLET 17, ch. 06 et 09) dit ce qui a été **vu**. Une notification
    créée mais jamais lue n'a rien accompli, et c'était la seule chose que la
    route ne disait pas.
    """
    statistiques = notification_manager.stats()
    statistiques["delivery"] = notification_manager.delivery_report()
    return statistiques


@app.delete("/notification/{notification_id}", tags=["notification"],
            dependencies=[Depends(rate_limit_dependency)])
async def delete_notification(
    notification_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_DELETE)),
):
    """Supprime une notification adressée à l'appelant."""
    notification = notification_manager.get(notification_id)
    if notification is not None and not _appartient_au_sujet(ctx, notification.recipient):
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} introuvable")

    success = notification_manager.delete(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} introuvable")
    return {"notification_id": notification_id, "status": "deleted"}


# =========================================================================
# Endpoints — Service de Recherche Unifiée
# =========================================================================

def _resolve_search_source(raw: str) -> Optional[SearchSource]:
    """Résout un nom de source de recherche."""
    try:
        return SearchSource(raw)
    except ValueError:
        return None


@app.post("/search", tags=["search"],
          dependencies=[Depends(rate_limit_dependency)])
async def unified_search(request: SearchRequest,
                         ctx: RBACContext = Depends(require_permission(Permission.KNOWLEDGE_SEARCH))):
    """Recherche unifiée sur toutes les sources disponibles.

    Répond 503 tant qu'aucune source n'est branchée. Sans cela, la route rendait
    `total: 0` pour toute requête — indiscernable d'une base vide, alors que
    c'est le service qui n'a aucun fournisseur (VOLET 14, ch. 02 : une capacité
    inachevée rapporte son état).
    """
    sources_branchees = search_manager.registered_sources()
    if not sources_branchees:
        raise HTTPException(
            status_code=503,
            detail=("Aucune source de recherche n'est branchée : le service ne peut "
                    "rien trouver. Utilisez /knowledge/search en attendant."),
        )

    # Résoudre les sources
    sources = []
    for raw in request.sources:
        source = _resolve_search_source(raw)
        if source is not None:
            sources.append(source)

    # Construire la requête
    query = SearchQuery(
        query=request.query,
        sources=sources,
        limit=request.limit,
        offset=request.offset,
        sort=SearchSort.RELEVANCE if request.sort == "relevance"
              else SearchSort.DATE_DESC if request.sort == "date_desc"
              else SearchSort.DATE_ASC,
        min_score=request.min_score,
        filters=request.filters,
        # Chercher n'autorise pas à lire : le rôle suit la requête jusqu'aux
        # fournisseurs, sinon la recherche unifiée contournerait le contrôle
        # d'accès appliqué à `/knowledge/search`.
        role=ctx.role.value,
        # Le rôle dit ce que l'appelant peut lire, le sujet dit de qui sont les
        # données. La mémoire a besoin des deux.
        subject=ctx.subject,
    )

    # Exécuter la recherche
    try:
        response = search_manager.search(query)
        # Étape 6 du flux du VOLET 14 : enregistrer l'usage. Le contenu de la
        # requête n'est pas mesuré, seulement le comportement de la recherche.
        record_search(response.sources_used, response.total, response.execution_time_ms)
        return response.to_dict()
    except Exception as e:
        raise erreur_interne("Erreur lors de la recherche", e)


@app.get("/search/status", tags=["search"],
         dependencies=[Depends(rate_limit_dependency),
                       Depends(require_permission(Permission.ADMIN_AUDIT))])
async def search_status():
    """Sur quoi la plateforme cherche, qui en répond, et si ça marche.

    Réunit ce que les chapitres 08 et 09 du VOLET 14 demandent : les sources
    déclarées et réellement branchées avec leur responsable, l'intégrité de
    l'index, les compteurs de recherche — et la liste de ce qui n'est pas
    mesurable ici, précision et rappel en tête, faute de jugements de référence.
    """
    return search_governance_report(
        search_manager,
        indexer=getattr(knowledge_manager, "_indexer", None),
        metrics=metrics_snapshot(),
    )


# =========================================================================
# Endpoints — Service de Fichiers
# =========================================================================

import base64


@app.post("/file/upload", tags=["file"],
          dependencies=[Depends(rate_limit_dependency)])
async def upload_file(
    request: FileUploadRequest,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_WRITE)),
):
    """Téléverse un fichier, au nom de l'appelant (ADR-010, critère C2)."""
    try:
        data = base64.b64decode(request.data)
    except Exception:
        raise HTTPException(status_code=400, detail="Données base64 invalides")

    result = file_manager.upload_file(
        name=request.name,
        content_type=request.content_type,
        data=data,
        description=request.description,
        tags=request.tags,
        uploaded_by=_proprietaire_effectif(ctx, request.uploaded_by),
        source=request.source,
        metadata=request.metadata,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Échec du téléversement")

    return {
        "file_id": result.file_id,
        "name": result.file.name if result.file else request.name,
        "size": len(data),
        "status": "uploaded",
    }


# Les chemins littéraux sont déclarés **avant** les chemins paramétrés : FastAPI
# retient la première route qui correspond, donc `/file/{file_id}` captait
# `/file/stats` et rendait « Fichier stats introuvable ». La route existait,
# était documentée, et personne ne pouvait l'appeler.
@app.get("/file/stats", tags=["file"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def file_stats():
    """Statistiques agrégées des fichiers."""
    return file_manager.stats()


@app.get("/file/{file_id}", tags=["file"],
         dependencies=[Depends(rate_limit_dependency)])
async def get_file(
    file_id: str,
    include_data: bool = False,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_READ)),
):
    """Retourne un fichier appartenant à l'appelant.

    Le fichier d'autrui répond 404 : distinguer « existe mais pas à vous » de
    « n'existe pas » permettrait d'énumérer les fichiers des autres sujets.
    """
    file = file_manager.get_file(file_id)
    if file is None or not _appartient_au_sujet(ctx, file.uploaded_by):
        raise HTTPException(status_code=404, detail=f"Fichier {file_id} introuvable")
    return file.to_dict(include_data=include_data)


@app.post("/file/list", tags=["file"],
          dependencies=[Depends(rate_limit_dependency)])
async def list_files(
    request: FileListRequest,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_READ)),
):
    """Liste les fichiers de l'appelant.

    Le filtre `uploaded_by` demandé n'est honoré que pour un administrateur :
    sinon il permettrait de lister les fichiers de n'importe qui.
    """
    files = file_manager.list_files(
        limit=request.limit,
        offset=request.offset,
        category=request.category,
        content_type=request.content_type,
        uploaded_by=_proprietaire_effectif(ctx, request.uploaded_by),
    )
    return {
        # Des résumés, sans contenu (ADR-016) : la sérialisation était déjà
        # sans les octets, mais le magasin les lisait quand même.
        "files": [f.to_dict() for f in files],
        "total": len(files),
    }


@app.delete("/file/{file_id}", tags=["file"],
            dependencies=[Depends(rate_limit_dependency)])
async def delete_file(
    file_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_DELETE)),
):
    """Supprime un fichier appartenant à l'appelant.

    La permission seule ne suffit pas : elle dit qu'un sujet peut supprimer
    *ses* fichiers, pas ceux d'autrui (ADR-010). Le fichier d'un autre répond
    404, comme à la lecture.
    """
    file = file_manager.get_file(file_id)
    if file is None or not _appartient_au_sujet(ctx, file.uploaded_by):
        raise HTTPException(status_code=404, detail=f"Fichier {file_id} introuvable")
    file_manager.delete_file(file_id)
    return {"file_id": file_id, "status": "deleted"}


# =========================================================================
# Endpoints — Cloud Service
# =========================================================================

@app.post("/cloud/upload", tags=["cloud"], deprecated=True,
          dependencies=[Depends(rate_limit_dependency)])
async def cloud_upload(
    request: CloudUploadRequest,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_WRITE)),
):
    """Téléverse un fichier vers le cloud."""
    import base64
    try:
        data = base64.b64decode(request.data)
    except Exception:
        raise HTTPException(status_code=400, detail="Données base64 invalides")

    result = cloud_manager.upload(
        name=request.name,
        content_type=request.content_type,
        data=data,
        provider=CloudProvider.LOCAL if request.provider == "local"
                else CloudProvider.S3 if request.provider == "s3"
                else CloudProvider.GCS if request.provider == "gcs"
                else CloudProvider.AZURE,
        # Le fichier appartient à l'appelant (ADR-010). Les routes `/cloud/*`
        # ne l'attribuaient à personne : partageant désormais le stockage du
        # service de fichiers, elles auraient déposé des fichiers sans
        # propriétaire au milieu de ceux des autres.
        uploaded_by=_proprietaire_effectif(ctx, request.uploaded_by),
        metadata=request.metadata,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"file_id": result.file_id, "status": "uploaded"}


@app.post("/cloud/list", tags=["cloud"], deprecated=True,
          dependencies=[Depends(rate_limit_dependency)])
async def cloud_list_files(
    request: CloudListRequest,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_READ)),
):
    """Liste les fichiers de l'appelant.

    Le filtre `uploaded_by` demandé n'est honoré que pour un administrateur,
    comme sur `/file/list`. Sans cela, la route dépréciée rendait les fichiers
    de tout le monde — et depuis qu'elle partage le stockage du service de
    fichiers, elle aurait contourné le contrôle de la route qui la remplace.
    """
    files = cloud_manager.list_files(
        limit=request.limit,
        offset=request.offset,
        provider=request.provider,
        category=request.category,
        uploaded_by=_proprietaire_effectif(ctx, request.uploaded_by),
    )
    return {
        "files": [f.to_dict() for f in files],
        "total": len(files),
    }


# Même raison que pour `/file/stats` ci-dessus.
@app.get("/cloud/stats", tags=["cloud"], deprecated=True,
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def cloud_stats():
    """Statistiques agrégées du stockage cloud."""
    return cloud_manager.stats()


@app.get("/cloud/{file_id}", tags=["cloud"], deprecated=True,
         dependencies=[Depends(rate_limit_dependency)])
async def cloud_get_file(
    file_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_READ)),
):
    """Retourne les métadonnées d'un fichier appartenant à l'appelant."""
    file = cloud_manager.get_file(file_id)
    if file is None or not _appartient_au_sujet(ctx, file.uploaded_by):
        raise HTTPException(status_code=404, detail=f"Fichier cloud {file_id} introuvable")
    return file.to_dict()


@app.get("/cloud/{file_id}/download", tags=["cloud"], deprecated=True,
         dependencies=[Depends(rate_limit_dependency)])
async def cloud_download(
    file_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_READ)),
):
    """Télécharge un fichier appartenant à l'appelant.

    C'est la route qui rend le **contenu** : la laisser sans contrôle de
    propriété donnait les octets d'autrui, pas seulement ses métadonnées.
    """
    fichier = cloud_manager.get_file(file_id)
    if fichier is None or not _appartient_au_sujet(ctx, fichier.uploaded_by):
        raise HTTPException(status_code=404, detail=f"Fichier cloud {file_id} introuvable")
    data = cloud_manager.download(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Fichier cloud {file_id} introuvable")
    from fastapi.responses import Response
    return Response(content=data, media_type="application/octet-stream")


@app.delete("/cloud/{file_id}", tags=["cloud"], deprecated=True,
            dependencies=[Depends(rate_limit_dependency)])
async def cloud_delete(
    file_id: str,
    ctx: RBACContext = Depends(require_permission(Permission.MEMORY_DELETE)),
):
    """Supprime un fichier appartenant à l'appelant."""
    fichier = cloud_manager.get_file(file_id)
    if fichier is None or not _appartient_au_sujet(ctx, fichier.uploaded_by):
        raise HTTPException(status_code=404, detail=f"Fichier cloud {file_id} introuvable")
    cloud_manager.delete(file_id)
    return {"file_id": file_id, "status": "deleted"}


# =========================================================================
# Endpoints — Calendar Service
# =========================================================================

def _resolve_event_status(raw: str) -> EventStatus:
    """Résout un nom de statut d'événement."""
    try:
        return EventStatus(raw)
    except ValueError:
        return EventStatus.CONFIRMED


@app.post("/calendar/create", tags=["calendar"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_WRITE))])
async def calendar_create(request: CalendarCreateRequest):
    """Crée un nouvel événement de calendrier."""
    result = calendar_manager.create_event(
        title=request.title,
        start_time=request.start_time,
        end_time=request.end_time,
        description=request.description,
        location=request.location,
        organizer=request.organizer,
        attendees=request.attendees,
        status=_resolve_event_status(request.status),
        metadata=request.metadata,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {
        "event_id": result.event_id,
        "event": result.event.to_dict() if result.event else None,
        "status": "created",
    }


@app.post("/calendar/list", tags=["calendar"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def calendar_list(request: CalendarListRequest):
    """Liste les événements avec filtres."""
    events = calendar_manager.list_events(
        limit=request.limit,
        offset=request.offset,
        status=request.status,
        organizer=request.organizer,
        start_after=request.start_after,
        start_before=request.start_before,
    )
    return {
        "events": [e.to_dict() for e in events],
        "total": len(events),
    }


# Même raison que pour `/file/stats` ci-dessus.
@app.get("/calendar/stats", tags=["calendar"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def calendar_stats():
    """Statistiques agrégées du calendrier."""
    return calendar_manager.stats()


@app.get("/calendar/{event_id}", tags=["calendar"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def calendar_get(event_id: str):
    """Retourne un événement par son identifiant."""
    event = calendar_manager.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Événement {event_id} introuvable")
    return event.to_dict()


@app.put("/calendar/{event_id}", tags=["calendar"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_WRITE))])
async def calendar_update(event_id: str, request: CalendarUpdateRequest):
    """Met à jour un événement."""
    updates = {k: v for k, v in request.model_dump(exclude_none=True).items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Aucune mise à jour fournie")
    success = calendar_manager.update_event(event_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail=f"Événement {event_id} introuvable")
    return {"event_id": event_id, "status": "updated"}


@app.post("/calendar/{event_id}/cancel", tags=["calendar"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_WRITE))])
async def calendar_cancel(event_id: str):
    """Annule un événement."""
    success = calendar_manager.cancel_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Événement {event_id} introuvable")
    return {"event_id": event_id, "status": "cancelled"}


@app.delete("/calendar/{event_id}", tags=["calendar"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_DELETE))])
async def calendar_delete(event_id: str):
    """Supprime un événement."""
    success = calendar_manager.delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Événement {event_id} introuvable")
    return {"event_id": event_id, "status": "deleted"}


# =========================================================================
# Endpoints — Email Service
# =========================================================================

@app.post("/email/send", tags=["email"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_WRITE))])
async def email_send(request: EmailSendRequest):
    """Envoie un email."""
    result = email_manager.send_email(
        subject=request.subject,
        body=request.body,
        sender=request.sender,
        recipients=request.recipients,
        cc=request.cc or None,
        bcc=request.bcc or None,
        is_html=request.is_html,
        metadata=request.metadata,
    )
    if not result.success:
        # 503 quand c'est le déploiement qui n'est pas configuré, 400 quand la
        # requête est fautive : répondre 400 à un SMTP absent accuse l'appelant
        # d'une erreur qu'il n'a pas commise (VOLET 12, ch. 02).
        stocke = (result.details or {}).get("stored") is True
        raise HTTPException(status_code=503 if stocke else 400, detail=result.message)
    return {
        "email_id": result.email_id,
        "status": "sent",
        "details": result.details,
    }


@app.post("/email/list", tags=["email"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def email_list(request: EmailListRequest):
    """Liste les emails avec filtres."""
    emails = email_manager.list_emails(
        limit=request.limit,
        offset=request.offset,
        status=request.status,
        sender=request.sender,
        recipient=request.recipient,
    )
    return {
        "emails": [e.to_dict() for e in emails],
        "total": len(emails),
    }


# Même raison que pour `/file/stats` ci-dessus.
@app.get("/email/stats", tags=["email"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def email_stats():
    """Statistiques agrégées des emails."""
    return email_manager.stats()


@app.get("/email/{email_id}", tags=["email"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def email_get(email_id: str):
    """Retourne un email par son identifiant."""
    email = email_manager.get_email(email_id)
    if email is None:
        raise HTTPException(status_code=404, detail=f"Email {email_id} introuvable")
    return email.to_dict()


@app.delete("/email/{email_id}", tags=["email"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_DELETE))])
async def email_delete(email_id: str):
    """Supprime un email."""
    success = email_manager.delete_email(email_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Email {email_id} introuvable")
    return {"email_id": email_id, "status": "deleted"}


# L'interface web est servie sous `/ui` (ADR-008), montée plus haut. Un second
# tableau de bord Jinja2 avait été monté ici sur `/admin` : deux interfaces
# concurrentes pour la même plateforme, c'est une de trop à maintenir et à
# documenter. `/ui` est la décision retenue ; `src/frontend/` a été retiré.

# Point d'entrée pour exécuter le serveur directement (pour le développement)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)