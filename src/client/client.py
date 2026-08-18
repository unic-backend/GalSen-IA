"""
Client API REST GalSen IA.

Wrapper Python typé pour l'API REST de la plateforme.
Toutes les méthodes retournent des objets Pydantic.
Pattern best-effort : pas d'exception levée, résultats partiels avec
``success`` et ``error`` en cas d'échec.

Utilisation ::

    from src.client import GalSenClient

    client = GalSenClient(base_url="http://localhost:8000", api_key="sk-...")

    # Santé
    health = client.health()

    # Mémoire
    mem_id = client.store_memory({"text": "Bonjour"})
    items = client.search_memory("test")

    # Génération
    result = client.generate("Explique le Sénégal en une phrase")

    # Notifications
    notifs = client.list_notifications()
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import base64

from .models import (
    ApiResponse,
    CalendarEvent,
    CloudFileItem,
    CloudStats,
    ComponentStatus,
    EmailMessage,
    FileItem,
    HealthReport,
    MemoryItem,
    MemorySearchResult,
    ModelGenerateResult,
    ModelInfo,
    NotificationItem,
    NotificationStats,
)


class GalSenClient:
    """Client API GalSen IA.

    Args:
        base_url: URL racine de l'API (ex: http://localhost:8000).
        api_key: Clé API pour l'authentification.
        timeout: Délai d'attente max par requête (secondes).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._api_key = api_key

    # =========================================================================
    #  Internes
    # =========================================================================

    def _url(self, path: str) -> str:
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _request(
        self,
        method: str,
        path: str,
        data: Any = None,
    ) -> "ApiResponse":
        """Exécute une requête HTTP.

        Retourne une ApiResponse avec le body parsé ou l'erreur.
        """
        body = json.dumps(data).encode() if data is not None else None
        req = Request(self._url(path), data=body, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        if self._api_key:
            req.add_header("X-API-Key", self._api_key)

        try:
            with urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                raw = resp.read()
                parsed = json.loads(raw) if raw else {}
                return ApiResponse(success=200 <= status < 300, data=parsed)
        except HTTPError as e:
            detail = ""
            try:
                detail = json.loads(e.read()).get("detail", str(e))
            except Exception:
                detail = str(e)
            return ApiResponse(success=False, error=detail)
        except (URLError, OSError) as e:
            return ApiResponse(success=False, error=str(e))

    def _get_json(self, path: str, params: Optional[Dict] = None) -> Any:
        """GET et retourne le JSON parsé, ou None en cas d'erreur."""
        url = self._url(path)
        if params:
            from urllib.parse import urlencode
            url += "?" + urlencode(params)
        req = Request(url, method="GET")
        req.add_header("Accept", "application/json")
        if self._api_key:
            req.add_header("X-API-Key", self._api_key)
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except (HTTPError, URLError, OSError):
            return None

    def _get_bytes(self, path: str) -> Optional[bytes]:
        """GET et retourne les bytes bruts, ou None en cas d'erreur."""
        req = Request(self._url(path), method="GET")
        if self._api_key:
            req.add_header("X-API-Key", self._api_key)
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                return resp.read()
        except (HTTPError, URLError, OSError):
            return None

    # =========================================================================
    #  Santé
    # =========================================================================

    def health(self) -> HealthReport:
        """Rapport de santé de la plateforme."""
        data = self._get_json("/health")
        if not data:
            return HealthReport(status="error")
        return HealthReport(
            status=data.get("status", "unknown"),
            version=data.get("version", ""),
            uptime=data.get("uptime", ""),
            components=[
                ComponentStatus(**c)
                for c in data.get("components", data.get("details", []))
            ],
        )

    def ready(self) -> bool:
        """Vérifie si la plateforme est prête (readiness)."""
        data = self._get_json("/ready")
        if data is None:
            return False
        return data.get("status") == "ready" if isinstance(data, dict) else True

    # =========================================================================
    #  Mémoire
    # =========================================================================

    def store_memory(
        self,
        content: Any,
        memory_type: str = "short_term",
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ApiResponse:
        """Stocke un élément en mémoire."""
        payload = {
            "content": content,
            "memory_type": memory_type,
            "user_id": user_id,
            "tags": tags or [],
            "metadata": metadata or {},
        }
        return self._request("POST", "/memory/store", data=payload)

    def retrieve_memory(self, item_id: str) -> Optional[MemoryItem]:
        """Récupère un élément mémoire par son ID."""
        data = self._get_json(f"/memory/retrieve/{item_id}")
        if not data:
            return None
        return MemoryItem(**data)

    def search_memory(
        self, query: str, limit: int = 10
    ) -> MemorySearchResult:
        """Recherche dans la mémoire."""
        data = self._get_json("/memory/search", params={"query": query, "limit": limit})
        if not data:
            return MemorySearchResult()
        items = data if isinstance(data, list) else []
        return MemorySearchResult(
            items=[MemoryItem(**it) for it in items],
            total=len(items),
        )

    # =========================================================================
    #  Modèles
    # =========================================================================

    def generate(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
    ) -> ModelGenerateResult:
        """Génère du texte via un modèle."""
        payload: Dict[str, Any] = {"prompt": prompt}
        if model_id:
            payload["model_id"] = model_id
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if system_prompt:
            payload["system_prompt"] = system_prompt

        resp = self._request("POST", "/model/generate", data=payload)
        if not resp.success:
            return ModelGenerateResult(
                status="error", text=resp.error or "Erreur"
            )
        d = resp.data or {}
        return ModelGenerateResult(
            text=d.get("text", ""),
            status=d.get("status", ""),
            model_used=d.get("model_used", ""),
            tokens_used=d.get("tokens_used", 0),
            latency_seconds=d.get("latency_seconds", 0.0),
        )

    def list_models(self) -> List[ModelInfo]:
        """Liste les modèles disponibles."""
        data = self._get_json("/models")
        if not data:
            return []
        models = data.get("models", data if isinstance(data, list) else [])
        return [ModelInfo(**m) for m in models]

    # =========================================================================
    #  Notifications
    # =========================================================================

    def send_notification(
        self,
        title: str,
        message: str,
        type: str = "info",
        priority: str = "normal",
        recipient: Optional[str] = None,
    ) -> ApiResponse:
        """Envoie une notification."""
        payload = {
            "title": title,
            "message": message,
            "type": type,
            "priority": priority,
            "recipient": recipient,
        }
        return self._request("POST", "/notification/send", data=payload)

    def list_notifications(
        self,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
    ) -> List[NotificationItem]:
        """Liste les notifications."""
        payload = {"limit": limit, "offset": offset, "unread_only": unread_only}
        resp = self._request("POST", "/notification/list", data=payload)
        if not resp.success or not resp.data:
            return []
        return [NotificationItem(**n) for n in resp.data.get("notifications", [])]

    def mark_read(self, notification_id: str) -> bool:
        """Marque une notification comme lue."""
        resp = self._request("POST", f"/notification/mark-read/{notification_id}")
        return resp.success

    def notification_stats(self) -> NotificationStats:
        """Statistiques des notifications."""
        data = self._get_json("/notification/stats")
        if not data:
            return NotificationStats()
        return NotificationStats(**data)

    # =========================================================================
    #  Fichiers
    # =========================================================================

    def upload_file(
        self,
        name: str,
        content_type: str,
        data: bytes,
        description: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> ApiResponse:
        """Téléverse un fichier."""
        payload = {
            "name": name,
            "content_type": content_type,
            "data": base64.b64encode(data).decode(),
            "description": description,
            "uploaded_by": uploaded_by,
        }
        return self._request("POST", "/file/upload", data=payload)

    def list_files(
        self,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
    ) -> List[FileItem]:
        """Liste les fichiers."""
        payload: Dict[str, Any] = {"limit": limit, "offset": offset, "category": category}
        resp = self._request("POST", "/file/list", data=payload)
        if not resp.success or not resp.data:
            return []
        return [FileItem(**f) for f in resp.data.get("files", [])]

    def get_file(self, file_id: str) -> Optional[FileItem]:
        """Récupère un fichier."""
        data = self._get_json(f"/file/{file_id}")
        if not data:
            return None
        return FileItem(**data)

    def delete_file(self, file_id: str) -> bool:
        """Supprime un fichier."""
        resp = self._request("DELETE", f"/file/{file_id}")
        return resp.success

    # =========================================================================
    #  Cloud
    # =========================================================================

    def cloud_upload(
        self,
        name: str,
        content_type: str,
        data: bytes,
        provider: str = "local",
        uploaded_by: Optional[str] = None,
    ) -> ApiResponse:
        """Téléverse un fichier vers le cloud."""
        payload = {
            "name": name,
            "content_type": content_type,
            "data": base64.b64encode(data).decode(),
            "provider": provider,
            "uploaded_by": uploaded_by,
        }
        return self._request("POST", "/cloud/upload", data=payload)

    def cloud_list(
        self,
        limit: int = 50,
        offset: int = 0,
        provider: Optional[str] = None,
    ) -> List[CloudFileItem]:
        """Liste les fichiers cloud."""
        payload: Dict[str, Any] = {"limit": limit, "offset": offset, "provider": provider}
        resp = self._request("POST", "/cloud/list", data=payload)
        if not resp.success or not resp.data:
            return []
        return [CloudFileItem(**f) for f in resp.data.get("files", [])]

    def cloud_get(self, file_id: str) -> Optional[CloudFileItem]:
        """Récupère un fichier cloud."""
        data = self._get_json(f"/cloud/{file_id}")
        if not data:
            return None
        return CloudFileItem(**data)

    def cloud_download(self, file_id: str) -> Optional[bytes]:
        """Télécharge le contenu d'un fichier cloud."""
        return self._get_bytes(f"/cloud/{file_id}/download")

    def cloud_delete(self, file_id: str) -> bool:
        """Supprime un fichier cloud."""
        resp = self._request("DELETE", f"/cloud/{file_id}")
        return resp.success

    def cloud_stats(self) -> CloudStats:
        """Statistiques cloud."""
        data = self._get_json("/cloud/stats")
        if not data:
            return CloudStats()
        return CloudStats(**data)

    # =========================================================================
    #  Calendrier
    # =========================================================================

    def calendar_create(
        self,
        title: str,
        start_time: str,
        end_time: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        organizer: Optional[str] = None,
        attendees: Optional[List[str]] = None,
    ) -> ApiResponse:
        """Crée un événement calendrier."""
        payload = {
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "description": description,
            "location": location,
            "organizer": organizer,
            "attendees": attendees or [],
        }
        return self._request("POST", "/calendar/create", data=payload)

    def calendar_list(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[CalendarEvent]:
        """Liste les événements."""
        payload: Dict[str, Any] = {"limit": limit, "offset": offset, "status": status}
        resp = self._request("POST", "/calendar/list", data=payload)
        if not resp.success or not resp.data:
            return []
        return [CalendarEvent(**e) for e in resp.data.get("events", [])]

    def calendar_get(self, event_id: str) -> Optional[CalendarEvent]:
        """Récupère un événement."""
        data = self._get_json(f"/calendar/{event_id}")
        if not data:
            return None
        return CalendarEvent(**data)

    def calendar_cancel(self, event_id: str) -> bool:
        """Annule un événement."""
        resp = self._request("POST", f"/calendar/{event_id}/cancel")
        return resp.success

    def calendar_delete(self, event_id: str) -> bool:
        """Supprime un événement."""
        resp = self._request("DELETE", f"/calendar/{event_id}")
        return resp.success

    # =========================================================================
    #  Email
    # =========================================================================

    def send_email(
        self,
        subject: str,
        body: str,
        sender: str,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        is_html: bool = False,
    ) -> ApiResponse:
        """Envoie un email."""
        payload = {
            "subject": subject,
            "body": body,
            "sender": sender,
            "recipients": recipients,
            "cc": cc or [],
            "bcc": bcc or [],
            "is_html": is_html,
        }
        return self._request("POST", "/email/send", data=payload)

    def list_emails(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[EmailMessage]:
        """Liste les emails."""
        payload: Dict[str, Any] = {"limit": limit, "offset": offset, "status": status}
        resp = self._request("POST", "/email/list", data=payload)
        if not resp.success or not resp.data:
            return []
        return [EmailMessage(**e) for e in resp.data.get("emails", [])]

    def get_email(self, email_id: str) -> Optional[EmailMessage]:
        """Récupère un email."""
        data = self._get_json(f"/email/{email_id}")
        if not data:
            return None
        return EmailMessage(**data)

    def delete_email(self, email_id: str) -> bool:
        """Supprime un email."""
        resp = self._request("DELETE", f"/email/{email_id}")
        return resp.success