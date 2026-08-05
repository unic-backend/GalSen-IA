"""
Local provider for the GalSen IA Model Engine.

Talks to an Ollama server running on the machine. This provider needs no
credentials, so it is the one path that can actually generate text today: if a
server is running, generation works; if not, the provider reports `UNREACHABLE`
and the engine moves on.

A local model also matters for the project beyond convenience: it removes the
per-token cost and the dependency on a connection, which is what makes the
platform usable where bandwidth is expensive or unreliable.
"""

import json
import logging
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .base import (
    GenerationRequest,
    GenerationResponse,
    ModelDescriptor,
    ModelProvider,
    ProviderInfo,
    ProviderStatus,
    UnavailabilityReason,
)

logger = logging.getLogger(__name__)


class LocalProvider(ModelProvider):
    """
    Fournisseur de modèles locaux servis par Ollama.

    Le catalogue est découvert auprès du serveur quand il répond, et retombe sur
    une liste déclarative sinon : la sélection de modèle reste ainsi possible
    même serveur éteint.
    """

    provider_id = "local"
    display_name = "Local (Ollama)"
    requires_credentials = False

    DEFAULT_BASE_URL = "http://localhost:11434"

    # Délai court : sonder un serveur absent ne doit pas retarder le moteur
    PROBE_TIMEOUT_SECONDS = 1.0

    # Délai de génération, plus large car un modèle local peut être lent
    GENERATION_TIMEOUT_SECONDS = 120

    # Durée de validité du résultat de la sonde, pour ne pas la refaire à chaque appel
    AVAILABILITY_CACHE_SECONDS = 30.0

    # Modèles courants, annoncés quand le serveur ne répond pas
    _FALLBACK_CATALOGUE = (
        ("llama3", 8192, 4096),
        ("mistral", 32768, 4096),
        ("phi3", 4096, 4096),
    )

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialise le fournisseur.

        Args:
            base_url: URL du serveur Ollama, `http://localhost:11434` par défaut
        """
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._cached_availability: Optional[ProviderInfo] = None
        self._availability_checked_at: float = 0.0

    def list_models(self) -> List[ModelDescriptor]:
        """
        Retourne les modèles disponibles localement.

        Returns:
            Les modèles réellement installés si le serveur répond, sinon le
            catalogue déclaratif
        """
        installed = self._fetch_installed_models()
        if installed:
            return installed

        return [
            self._build_descriptor(name, context_window, max_output)
            for name, context_window, max_output in self._FALLBACK_CATALOGUE
        ]

    def check_availability(self) -> ProviderInfo:
        """
        Vérifie qu'un serveur Ollama répond.

        Returns:
            L'état du fournisseur, avec le motif exact s'il est indisponible
        """
        now = time.time()
        if (
            self._cached_availability is not None
            and now - self._availability_checked_at < self.AVAILABILITY_CACHE_SECONDS
        ):
            return self._cached_availability

        info = self._probe_server()
        self._cached_availability = info
        self._availability_checked_at = now
        return info

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """
        Génère du texte avec un modèle local.

        Args:
            request: Requête de génération

        Returns:
            La réponse du modèle, ou une réponse `UNAVAILABLE` si le serveur ne
            répond pas
        """
        availability = self.check_availability()
        if availability.status != ProviderStatus.READY:
            return GenerationResponse.unavailable(
                provider_id=self.provider_id,
                model_name=request.model_name,
                reason=availability.reason or UnavailabilityReason.UNREACHABLE,
                detail=availability.detail or "Serveur local injoignable",
            )

        payload: Dict[str, Any] = {
            "model": request.model_name,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        if request.stop_sequences:
            payload["options"]["stop"] = list(request.stop_sequences)

        started_at = time.time()
        try:
            body = self._post("/api/generate", payload, self.GENERATION_TIMEOUT_SECONDS)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as error:
            # Le serveur a disparu entre la sonde et l'appel : la sonde est invalidée
            self._cached_availability = None
            logger.warning(f"Génération locale impossible: {error}")
            return GenerationResponse.unavailable(
                provider_id=self.provider_id,
                model_name=request.model_name,
                reason=UnavailabilityReason.UNREACHABLE,
                detail=f"Le serveur local a échoué pendant la génération: {error}",
            )

        return GenerationResponse(
            status=ProviderStatus.READY,
            text=body.get("response", ""),
            provider_id=self.provider_id,
            model_name=request.model_name,
            prompt_tokens=body.get("prompt_eval_count", self.estimate_tokens(request.prompt)),
            completion_tokens=body.get("eval_count", 0),
            latency_seconds=time.time() - started_at,
        )

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _probe_server(self) -> ProviderInfo:
        """Sonde le serveur local et en déduit l'état du fournisseur."""
        host, port = self._host_and_port()

        try:
            with socket.create_connection((host, port), timeout=self.PROBE_TIMEOUT_SECONDS):
                pass
        except OSError:
            return ProviderInfo(
                provider_id=self.provider_id,
                display_name=self.display_name,
                status=ProviderStatus.UNAVAILABLE,
                model_count=len(self._FALLBACK_CATALOGUE),
                requires_credentials=False,
                reason=UnavailabilityReason.UNREACHABLE,
                detail=(
                    f"Aucun serveur Ollama sur {self.base_url}. "
                    "Démarrez-le avec 'ollama serve' pour activer la génération locale."
                ),
            )

        installed = self._fetch_installed_models()
        if not installed:
            return ProviderInfo(
                provider_id=self.provider_id,
                display_name=self.display_name,
                status=ProviderStatus.UNAVAILABLE,
                model_count=0,
                requires_credentials=False,
                reason=UnavailabilityReason.MISSING_DEPENDENCY,
                detail=(
                    "Le serveur Ollama répond mais aucun modèle n'est installé. "
                    "Installez-en un avec 'ollama pull llama3'."
                ),
            )

        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            status=ProviderStatus.READY,
            model_count=len(installed),
            requires_credentials=False,
        )

    def _fetch_installed_models(self) -> List[ModelDescriptor]:
        """Interroge le serveur sur les modèles réellement installés."""
        try:
            body = self._get("/api/tags", self.PROBE_TIMEOUT_SECONDS)
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            return []

        descriptors: List[ModelDescriptor] = []
        for entry in body.get("models", []):
            name = entry.get("name")
            if not name:
                continue

            details = entry.get("details") or {}
            descriptors.append(self._build_descriptor(
                name,
                context_window=int(details.get("context_length", 8192)),
                max_output_tokens=4096,
            ))

        return descriptors

    def _build_descriptor(
        self, name: str, context_window: int, max_output_tokens: int
    ) -> ModelDescriptor:
        """Construit le descripteur d'un modèle local."""
        return ModelDescriptor(
            model_name=name,
            provider_id=self.provider_id,
            context_window=context_window,
            max_output_tokens=max_output_tokens,
            supports_streaming=True,
            supports_function_calling=False,
            supports_vision=False,
            supported_languages=["en", "fr"],
            # Un modèle local ne coûte rien par jeton : c'est son intérêt principal
            pricing_per_1k_tokens={"input": 0.0, "output": 0.0},
            special_features=["local", "no_cost", "offline"],
        )

    def _host_and_port(self) -> tuple:
        """Extrait l'hôte et le port de l'URL du serveur."""
        parsed = urlparse(self.base_url)
        return parsed.hostname or "localhost", parsed.port or 11434

    def _get(self, path: str, timeout: float) -> Dict[str, Any]:
        """Effectue une requête GET sur le serveur local."""
        request = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post(self, path: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        """Effectue une requête POST sur le serveur local."""
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
