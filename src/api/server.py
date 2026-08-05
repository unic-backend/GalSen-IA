"""
API Server for GalSen IA platform.

Expose les fonctionnalités du noyau via une API RESTful.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
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
from src.tool.tool_executor import ToolExecutor

# Import du limiteur de taux
from src.api.rate_limiter import (
    rate_limit_dependency,
    set_valid_api_keys,
)

# Import du vérificateur de santé
from src.api.health import (
    init_health_checker,
    get_health_checker,
)

# Import du RBAC
from src.api.rbac import (
    RBACManager,
    Permission,
    RBACContext,
)

# Import des services
from src.services.notification.manager import NotificationManagerImpl
from src.services.notification.types import NotificationType, NotificationPriority
from src.services.search.manager import SearchManagerImpl
from src.services.search.types import SearchQuery, SearchSource, SearchSort
from src.services.file.manager import FileManagerImpl

# Horodatage de démarrage (utilisé pour le calcul de l'uptime)
APP_START_TIME = time.time()

# API Key security
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Gestionnaire RBAC — charge le mapping clé API → rôle depuis GALSEN_API_KEYS
# Format attendu : "sk-admin123:admin,sk-user456:user,sk-operator789:operator"
# Une clé sans rôle hérite du rôle "user".
rbac_manager = RBACManager()

# Enregistrer les clés API valides auprès du limiteur de taux
set_valid_api_keys(rbac_manager.get_valid_keys())


def require_auth(api_key: str = Security(api_key_header)) -> RBACContext:
    """Dépendance FastAPI : authentifie la clé API et retourne le contexte RBAC.

    Remplace l'ancienne dépendance get_api_key(). En plus de valider la clé,
    elle associe un rôle et des permissions à la requête.

    Args:
        api_key: Clé API transmise dans l'en-tête X-API-Key.

    Returns:
        Contexte RBAC (rôle + permissions) pour la requête.

    Raises:
        HTTPException 401 : clé manquante ou invalide.
    """
    try:
        return rbac_manager.authenticate(api_key)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))


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

# Initialisation de l'application FastAPI
app = FastAPI(
    title="GalSen IA API",
    description="API exposant les fonctionnalités de la plateforme GalSen IA",
    version="0.1.0",
)

# Configuration CORS (à ajuster en production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, remplacer par les origines autorisées
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialisation des moteurs (singleton pour la durée de vie de l'application)
memory_manager = MemoryManager()
model_manager = ModelManagerImpl()
knowledge_manager = KnowledgeManagerImpl()
tool_loader = ToolLoader()
tool_executor = ToolExecutor()
tool_engine = None  # sera initialisé après chargement des outils
# File d'attente d'approbation humaine : les agents qui demandent une décision
# soumettent ici leur action, et un opérateur la valide ou la refuse (ADR-006).
approval_manager = ApprovalManagerImpl()

# Services backend (VOLET 02, Phase 2)
notification_manager = NotificationManagerImpl()
search_manager = SearchManagerImpl()
file_manager = FileManagerImpl()

# Initialisation du moteur d'outils au démarrage
@app.on_event("startup")
async def startup_event():
    global tool_engine
    # Charger les outils depuis la configuration
    tools = tool_loader.load_tools()
    tool_engine = ToolEngine(tools)
    # Enregistrer l'executeur d'outils
    tool_engine.set_executor(tool_executor)
    # Mettre à jour la référence au moteur d'outils dans le vérificateur de santé
    checker = get_health_checker()
    if hasattr(checker, 'set_tool_engine'):
        checker.set_tool_engine(tool_engine)
    # Démarrer le moteur d'outils (si nécessaire)
    # Note: le moteur d'outils est généralement prêt après chargement
    print("Moteur d'outils initialisé avec", len(tools), "outils")

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

# Endpoints de santé

# Initialiser le vérificateur de santé (singleton) avec les instances des moteurs
# Le moteur d'outils sera mis à jour après le démarrage via startup_event
init_health_checker(
    start_time=APP_START_TIME,
    version=app.version,
    memory_manager=memory_manager,
    model_manager=model_manager,
    knowledge_manager=knowledge_manager,
    tool_engine=tool_engine,  # None au démarrage, mis à jour dans startup_event
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
    return report.to_dict()


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
@app.post("/memory/store", response_model=MemoryItemResponse, tags=["memory"],
           dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_WRITE))])
async def store_memory(item: MemoryItemCreate):
    """Stocker un nouvel élément de mémoire."""
    # Créer un MemoryItem à partir des données reçues
    memory_item = MemoryItem(
        content=item.content,
        memory_type=item.memory_type,
        user_id=item.user_id,
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
           dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def retrieve_memory(item_id: str):
    """Récupérer un élément de mémoire par son ID."""
    item = memory_manager.get_memory(item_id)
    if item is None:
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
async def search_memory(query: str, limit: int = 10):
    """Rechercher des éléments de mémoire par similaire."""
    results = memory_manager.search_memory(query, limit=limit)
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
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération: {str(e)}")

# Endpoints outils
@app.post("/tool/execute", response_model=ToolExecuteResponse, tags=["tool"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.TOOL_EXECUTE))])
async def execute_tool(request: ToolExecuteRequest):
    """Exécuter un outil spécifié."""
    if tool_engine is None:
        raise HTTPException(status_code=503, detail="Moteur d'outils non initialisé")

    try:
        # Exécuter l'outil via le moteur d'outils
        result = tool_engine.execute(request.tool_id, request.input, request.config or {})
        return ToolExecuteResponse(
            output=result,
            status="success",
            tool_id=request.tool_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'exécution de l'outil: {str(e)}")

# Endpoints connaissances
@app.post("/knowledge/search", response_model=KnowledgeSearchResponse, tags=["knowledge"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.KNOWLEDGE_SEARCH))])
async def search_knowledge(request: KnowledgeSearchRequest):
    """Rechercher des connaissances par similarité."""
    try:
        results = knowledge_manager.search_knowledge(request.query, limit=request.limit)
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
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche: {str(e)}")

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
           dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def list_notifications(request: NotificationListRequest):
    """Liste les notifications avec filtres."""
    notifications = notification_manager.list_notifications(
        limit=request.limit,
        offset=request.offset,
        unread_only=request.unread_only,
        notification_type=request.notification_type,
        recipient=request.recipient,
        role=request.role,
    )
    return {
        "notifications": [n.to_dict() for n in notifications],
        "total": len(notifications),
    }


@app.post("/notification/mark-read/{notification_id}", tags=["notification"],
           dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_WRITE))])
async def mark_notification_read(notification_id: str):
    """Marque une notification comme lue."""
    success = notification_manager.mark_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} introuvable")
    return {"notification_id": notification_id, "status": "read"}


@app.post("/notification/mark-all-read", tags=["notification"],
           dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_WRITE))])
async def mark_all_read(recipient: Optional[str] = None):
    """Marque toutes les notifications comme lues."""
    count = notification_manager.mark_all_read(recipient=recipient)
    return {"marked_read": count}


@app.get("/notification/stats", tags=["notification"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def notification_stats():
    """Statistiques agrégées des notifications."""
    return notification_manager.stats()


@app.delete("/notification/{notification_id}", tags=["notification"],
            dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_DELETE))])
async def delete_notification(notification_id: str):
    """Supprime une notification."""
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
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.KNOWLEDGE_SEARCH))])
async def unified_search(request: SearchRequest):
    """Recherche unifiée sur toutes les sources disponibles."""
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
    )

    # Exécuter la recherche
    try:
        response = search_manager.search(query)
        return response.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la recherche : {str(e)}")


# =========================================================================
# Endpoints — Service de Fichiers
# =========================================================================

import base64


@app.post("/file/upload", tags=["file"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_WRITE))])
async def upload_file(request: FileUploadRequest):
    """Téléverse un fichier sur la plateforme."""
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
        uploaded_by=request.uploaded_by,
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
         dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def get_file(file_id: str, include_data: bool = False):
    """Retourne les métadonnées et le contenu d'un fichier."""
    file = file_manager.get_file(file_id)
    if file is None:
        raise HTTPException(status_code=404, detail=f"Fichier {file_id} introuvable")
    return file.to_dict(include_data=include_data)


@app.post("/file/list", tags=["file"],
          dependencies=[Depends(rate_limit_dependency), Depends(require_permission(Permission.MEMORY_READ))])
async def list_files(request: FileListRequest):
    """Liste les fichiers avec filtres."""
    files = file_manager.list_files(
        limit=request.limit,
        offset=request.offset,
        category=request.category,
        content_type=request.content_type,
        uploaded_by=request.uploaded_by,
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


# Point d'entrée pour exécuter le serveur directement (pour le développement)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)