"""
Dashboard d'administration GalSen IA.

Monte une application FastAPI avec Jinja2 qui expose des pages web
pour visualiser et interagir avec les composants de la plateforme.
S'interface avec les mêmes managers que l'API REST.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from urllib.parse import parse_qs
import os
import time
import sys

# Chemin du dossier de ce module
_HERE = Path(__file__).parent

# Templates et statiques
_templates = Jinja2Templates(directory=str(_HERE / "templates"))


def _import_managers():
    """Importe les managers existants pour le dashboard.

    Retourne un dict de managers ou None si non disponibles.
    Chaque import est protégé individuellement.
    """
    managers = {}

    # Santé système
    try:
        from src.api.health import get_health_checker
        managers["health"] = get_health_checker()
    except Exception:
        managers["health"] = None

    # Mémoire
    try:
        from src.memory_engine.memory_manager import MemoryManager
        managers["memory"] = MemoryManager()
    except Exception:
        managers["memory"] = None

    # Modèles
    try:
        from src.model_engine.model_manager import ModelManagerImpl
        managers["models"] = ModelManagerImpl()
    except Exception:
        managers["models"] = None

    # Connaissances
    try:
        from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
        managers["knowledge"] = KnowledgeManagerImpl()
    except Exception:
        managers["knowledge"] = None

    # Services
    try:
        from src.services.notification.manager import NotificationManagerImpl
        managers["notifications"] = NotificationManagerImpl()
    except Exception:
        managers["notifications"] = None

    try:
        from src.services.file.manager import FileManagerImpl
        managers["files"] = FileManagerImpl()
    except Exception:
        managers["files"] = None

    try:
        from src.services.cloud.manager import CloudManagerImpl
        managers["cloud"] = CloudManagerImpl()
    except Exception:
        managers["cloud"] = None

    try:
        from src.services.calendar.manager import CalendarManagerImpl
        managers["calendar"] = CalendarManagerImpl()
    except Exception:
        managers["calendar"] = None

    try:
        from src.services.email.manager import EmailManagerImpl
        managers["email"] = EmailManagerImpl()
    except Exception:
        managers["email"] = None

    # Conseil agricole
    try:
        from src.tools.agri_advice.tool import AgriAdviceTool
        managers["agri"] = AgriAdviceTool()
    except Exception:
        managers["agri"] = None

    return managers


def _health_summary(managers: dict) -> dict:
    """Agrège un résumé santé pour la page d'accueil."""
    health = managers.get("health")
    if health is not None:
        try:
            report = health.check_health()
            return {
                "status": getattr(report, "status", "unknown"),
                "components": getattr(report, "to_dict", lambda: {})(),
            }
        except Exception:
            pass
    return {"status": "unknown", "components": {}}


def _memory_stats(managers: dict) -> dict:
    """Statistiques mémoire."""
    mem = managers.get("memory")
    if mem is None:
        return {"count": 0}
    try:
        count = len(mem.get_all_memories()) if hasattr(mem, "get_all_memories") else 0
        return {"count": count}
    except Exception:
        return {"count": 0}


def _model_stats(managers: dict) -> dict:
    """Statistiques modèles."""
    mm = managers.get("models")
    if mm is None:
        return {"total": 0, "active": 0}
    try:
        models = mm.list_models() if hasattr(mm, "list_models") else []
        active = [m for m in models if getattr(m, "status", None) == "active"]
        return {"total": len(models), "active": len(active)}
    except Exception:
        return {"total": 0, "active": 0}


def _service_stats(managers: dict) -> dict:
    """Agrège les stats de tous les services."""
    stats = {}
    for name in ["notifications", "files", "cloud", "calendar", "email"]:
        mgr = managers.get(name)
        if mgr is None:
            stats[name] = {"count": 0, "available": False}
            continue
        try:
            s = mgr.stats() if hasattr(mgr, "stats") else {}
            stats[name] = {"count": s.get("total", 0), "available": True}
        except Exception:
            stats[name] = {"count": 0, "available": False}
    return stats


def create_dashboard_app() -> FastAPI:
    """Crée et retourne l'application FastAPI du dashboard.

    Retourne une sous-application à monter sur `/admin` dans le serveur principal.
    """
    app = FastAPI(title="GalSen IA — Dashboard")

    # Servir les fichiers statiques
    static_dir = _HERE / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "css").mkdir(parents=True, exist_ok=True)
    app.mount("/admin/static", StaticFiles(directory=str(static_dir)), name="dashboard_static")

    # Page d'accueil — vue d'ensemble
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_home(request: Request):
        managers = _import_managers()
        health = _health_summary(managers)
        memory = _memory_stats(managers)
        models = _model_stats(managers)
        services = _service_stats(managers)

        return _templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "health": health,
                "memory": memory,
                "models": models,
                "services": services,
                "page": "accueil",
            },
        )

    # Page santé détaillée
    @app.get("/health", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_health(request: Request):
        managers = _import_managers()
        health_checker = managers.get("health")
        report = {}
        if health_checker is not None:
            try:
                report = health_checker.check_health().to_dict()
            except Exception:
                report = {"error": "Impossible de récupérer le rapport de santé"}

        return _templates.TemplateResponse(
            request,
            "health.html",
            {"request": request, "report": report, "page": "sante"},
        )

    # Page services
    @app.get("/services", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_services(request: Request):
        managers = _import_managers()
        services = _service_stats(managers)

        # Récupérer les données détaillées de chaque service
        details = {}
        for name in ["notifications", "files", "cloud", "calendar", "email"]:
            mgr = managers.get(name)
            if mgr is None:
                details[name] = {"available": False, "data": []}
                continue
            try:
                if hasattr(mgr, "stats"):
                    details[name] = {"available": True, "stats": mgr.stats()}
                else:
                    details[name] = {"available": True, "stats": {}}
            except Exception:
                details[name] = {"available": False, "data": []}

        return _templates.TemplateResponse(
            request,
            "services.html",
            {"request": request, "services": services, "details": details, "page": "services"},
        )

    # Page modèles
    @app.get("/models", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_models(request: Request):
        managers = _import_managers()
        mm = managers.get("models")
        models_list = []
        if mm is not None:
            try:
                models_list = mm.list_models() if hasattr(mm, "list_models") else []
            except Exception:
                models_list = []

        return _templates.TemplateResponse(
            request,
            "models.html",
            {"request": request, "models": models_list, "page": "modeles"},
        )

    @app.get("/memory", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_memory(request: Request):
        managers = _import_managers()
        mem = managers.get("memory")
        items = []
        if mem is not None:
            try:
                items = mem.get_all_memories() if hasattr(mem, "get_all_memories") else []
            except Exception:
                items = []

        return _templates.TemplateResponse(
            request,
            "memory.html",
            {"request": request, "items": items, "page": "memoire"},
        )

    # Page Conseil Agricole — formulaire + génération côté serveur
    @app.get("/agri-conseil", response_class=HTMLResponse, include_in_schema=False)
    @app.post("/agri-conseil", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard_agri(request: Request):
        # Les données arrivent en x-www-form-urlencoded (pas de python-multipart :
        # on parse le corps manuellement avec la stdlib)
        result = None
        error = None
        question = ""
        language = "fr"

        if request.method == "POST":
            raw = (await request.body()).decode("utf-8", errors="replace")
            data = parse_qs(raw)
            question = (data.get("question") or [""])[0].strip()
            language = (data.get("language") or ["fr"])[0]
            if not question:
                error = "Veuillez écrire votre question agricole."
            else:
                tool = _import_managers().get("agri")
                if tool is None:
                    error = "Le service Conseil Agricole est indisponible."
                else:
                    try:
                        result = tool.execute("get_advice", question,
                                              language=language)
                    except Exception as exc:
                        error = str(exc)

        return _templates.TemplateResponse(
            request,
            "agri_conseil.html",
            {"request": request, "result": result, "error": error,
             "question": question, "language": language, "page": "agri"},
        )

    return app