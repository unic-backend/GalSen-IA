"""
API Server for GalSen IA platform.

Expose les fonctionnalités du noyau via une API RESTful.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
import logging
import time
import uuid
import os

# Import des moteurs existants
from src.memory_engine.memory_manager import MemoryManager
from src.memory_engine.types import MemoryItem
from src.model_engine.model_manager import ModelManagerImpl
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.approval_engine.approval_manager import ApprovalManagerImpl
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

# Import des services
from src.services.notification.manager import NotificationManagerImpl
from src.services.notification.types import NotificationType, NotificationPriority
from src.services.search.manager import SearchManagerImpl
from src.services.search.providers import KnowledgeSearchProvider
from src.services.search.governance import governance_report as search_governance_report
from src.services.search.types import SearchQuery, SearchSource, SearchSort
from src.services.file.manager import FileManagerImpl

# Import des services d'intégration externe (VOLET 02, Phase 3)
from src.services.cloud.manager import CloudManagerImpl
from src.services.cloud.types import CloudProvider
from src.services.calendar.manager import CalendarManagerImpl
from src.services.calendar.types import EventStatus, EventVisibility
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

    # Rien à libérer aujourd'hui : les moteurs sont en mémoire et les connexions
    # SQLite sont ouvertes et refermées par opération.


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
memory_manager = MemoryManager()
model_manager = ModelManagerImpl()
knowledge_manager = KnowledgeManagerImpl()
# Le chargeur ne sert plus qu'à localiser le registre : le ToolEngine construit
# son propre chargeur et son propre exécuteur à partir de ce chemin (lifespan).
tool_loader = ToolLoader()
tool_engine = None  # sera initialisé au démarrage, par lifespan()
# File d'attente d'approbation humaine : les agents qui demandent une décision
# soumettent ici leur action, et un opérateur la valide ou la refuse (ADR-006).
approval_manager = ApprovalManagerImpl()

# Services backend (VOLET 02, Phase 2)
notification_manager = NotificationManagerImpl()
search_manager = SearchManagerImpl()
# Sans cet enregistrement, la recherche unifiée n'a aucune source et ne peut rien
# trouver (VOLET 14, ch. 04). La connaissance est la seule source réellement
# indexée à ce jour ; mémoire, document et vision restent déclarées, non branchées.
search_manager.register_provider(KnowledgeSearchProvider(knowledge_manager))
file_manager = FileManagerImpl()

# Services d'intégration externe (VOLET 02, Phase 3)
cloud_manager = CloudManagerImpl()
calendar_manager = CalendarManagerImpl()
email_manager = EmailManagerImpl()

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
async def health_check():
    """Rapport de santé détaillé de la plateforme.

    Retourne l'état de tous les composants (API, moteurs, stockage, fournisseurs)
    avec les métadonnées (version, uptime, backend de stockage).

    Code HTTP toujours 200 — le statut global est dans le corps de la réponse
    (champ ``status`` : ``healthy``, ``degraded`` ou ``unhealthy``).
    """
    checker = get_health_checker()
    report = checker.check_health()
    donnees = report.to_dict()
    # La plateforme ne tourne aujourd'hui qu'en une seule instance (ADR-009).
    # La contrainte est exposée ici plutôt que laissée à la documentation :
    # c'est le seul endroit qu'un opérateur consulte avant de dupliquer un
    # service.
    donnees["scaling"] = scaling_report()
    return donnees


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
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.TOOL_EXECUTE))])
async def execute_tool(request: ToolExecuteRequest):
    """Exécuter un outil spécifié."""
    if tool_engine is None:
        raise HTTPException(status_code=503, detail="Moteur d'outils non initialisé")

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


@app.get("/notification/stats", tags=["notification"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def notification_stats():
    """Statistiques agrégées des notifications."""
    return notification_manager.stats()


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
        "files": [f.to_dict(include_data=False) for f in files],
        "total": len(files),
    }


@app.get("/file/stats", tags=["file"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def file_stats():
    """Statistiques agrégées des fichiers."""
    return file_manager.stats()


@app.delete("/file/{file_id}", tags=["file"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_DELETE))])
async def delete_file(file_id: str):
    """Supprime un fichier."""
    success = file_manager.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Fichier {file_id} introuvable")
    return {"file_id": file_id, "status": "deleted"}


# =========================================================================
# Endpoints — Cloud Service
# =========================================================================

@app.post("/cloud/upload", tags=["cloud"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_WRITE))])
async def cloud_upload(request: CloudUploadRequest):
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
        uploaded_by=request.uploaded_by,
        metadata=request.metadata,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"file_id": result.file_id, "status": "uploaded"}


@app.post("/cloud/list", tags=["cloud"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def cloud_list_files(request: CloudListRequest):
    """Liste les fichiers cloud avec filtres."""
    files = cloud_manager.list_files(
        limit=request.limit,
        offset=request.offset,
        provider=request.provider,
        category=request.category,
        uploaded_by=request.uploaded_by,
    )
    return {
        "files": [f.to_dict() for f in files],
        "total": len(files),
    }


@app.get("/cloud/{file_id}", tags=["cloud"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def cloud_get_file(file_id: str):
    """Retourne les métadonnées d'un fichier cloud."""
    file = cloud_manager.get_file(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail=f"Fichier cloud {file_id} introuvable")
    return file.to_dict()


@app.get("/cloud/{file_id}/download", tags=["cloud"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def cloud_download(file_id: str):
    """Télécharge un fichier cloud."""
    data = cloud_manager.download(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Fichier cloud {file_id} introuvable")
    from fastapi.responses import Response
    return Response(content=data, media_type="application/octet-stream")


@app.get("/cloud/stats", tags=["cloud"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def cloud_stats():
    """Statistiques agrégées du stockage cloud."""
    return cloud_manager.stats()


@app.delete("/cloud/{file_id}", tags=["cloud"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_DELETE))])
async def cloud_delete(file_id: str):
    """Supprime un fichier cloud."""
    success = cloud_manager.delete(file_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Fichier cloud {file_id} introuvable")
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


@app.get("/calendar/stats", tags=["calendar"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def calendar_stats():
    """Statistiques agrégées du calendrier."""
    return calendar_manager.stats()


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


@app.get("/email/stats", tags=["email"],
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def email_stats():
    """Statistiques agrégées des emails."""
    return email_manager.stats()


# L'interface web est servie sous `/ui` (ADR-008), montée plus haut. Un second
# tableau de bord Jinja2 avait été monté ici sur `/admin` : deux interfaces
# concurrentes pour la même plateforme, c'est une de trop à maintenir et à
# documenter. `/ui` est la décision retenue ; `src/frontend/` a été retiré.

# Point d'entrée pour exécuter le serveur directement (pour le développement)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)