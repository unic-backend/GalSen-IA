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

from ..local_catalogue import DEFAUT, CatalogueLocal, ProfilLocal, profil_mesure
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

    def __init__(self, base_url: Optional[str] = None, catalogue: Optional[CatalogueLocal] = None):
        """
        Initialise le fournisseur.

        Args:
            base_url: URL du serveur Ollama, `http://localhost:11434` par défaut
            catalogue: Profils déclarés des modèles locaux ; celui de
                `config/model_routing.yaml` par défaut
        """
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._cached_availability: Optional[ProviderInfo] = None
        self._availability_checked_at: float = 0.0
        self._catalogue = catalogue or CatalogueLocal()
        # Les capacités d'un modèle ne changent pas en cours d'exécution :
        # interroger `/api/show` à chaque construction de descripteur coûterait
        # un aller-retour par modèle et par sélection.
        self._profils_mesures: Dict[str, ProfilLocal] = {}

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

            # `/api/tags` ne porte **pas** de `context_length` : son bloc
            # `details` annonce `family`, `parameter_size` et
            # `quantization_level`. La valeur lue ici était donc toujours le
            # défaut, pour tous les modèles — ce qui rendait `summarization`
            # (32k) et `document_analysis` (100k) impossibles à router. Le
            # contexte réel se demande à `/api/show`.
            descriptors.append(self._build_descriptor(
                name,
                context_window=8192,
                max_output_tokens=4096,
                mesure=self._mesurer(name),
            ))

        return descriptors

    def _build_descriptor(
        self,
        name: str,
        context_window: int,
        max_output_tokens: int,
        mesure: Optional[ProfilLocal] = None,
    ) -> ModelDescriptor:
        """
        Construit le descripteur d'un modèle local.

        Trois sources se superposent, de la plus faible à la plus forte : le
        défaut (ce que `/api/tags` a donné, sans atout), la déclaration
        (`config/model_routing.yaml`), puis la mesure (`/api/show`). Chaque
        champ retenu garde l'origine qui l'a fixé.

        Args:
            name: Nom du modèle tel qu'Ollama l'annonce
            context_window: Contexte connu à défaut de mieux
            max_output_tokens: Sortie maximale
            mesure: Profil constaté sur le serveur, s'il a répondu

        Returns:
            Le descripteur, avec `capability_sources` renseigné
        """
        profil = ProfilLocal(
            context_window=context_window,
            origines={"context_window": DEFAUT},
        )
        profil = profil.fusionner(self._catalogue.profil(name))
        if mesure is not None:
            profil = profil.fusionner(mesure)

        # `local`, `no_cost` et `offline` restent : ils décrivent le mode de
        # service, pas la compétence, et d'autres composants les lisent. Les
        # atouts du profil s'y ajoutent — ce sont eux que le routage compare.
        atouts = ["local", "no_cost", "offline"] + [
            f for f in profil.features if f not in ("local", "no_cost", "offline")
        ]

        return ModelDescriptor(
            model_name=name,
            provider_id=self.provider_id,
            context_window=profil.context_window or context_window,
            max_output_tokens=max_output_tokens,
            supports_streaming=True,
            # Une capacité non constatée vaut « non » pour un appelant qui doit
            # décider maintenant — mais l'origine dit qu'elle n'a pas été vue,
            # ce qui n'est pas la même information.
            supports_function_calling=bool(profil.supports_tools),
            supports_vision=bool(profil.supports_vision),
            supported_languages=["en", "fr"],
            # Un modèle local ne coûte rien par jeton : c'est son intérêt principal
            pricing_per_1k_tokens={"input": 0.0, "output": 0.0},
            special_features=atouts,
            capability_sources=dict(profil.origines),
        )

    def _mesurer(self, name: str) -> Optional[ProfilLocal]:
        """
        Interroge `/api/show` sur ce que le modèle sait faire.

        Returns:
            Le profil mesuré, ou `None` si le serveur n'a pas répondu — auquel
            cas rien n'est supposé à sa place.
        """
        if name in self._profils_mesures:
            return self._profils_mesures[name]
        try:
            corps = self._post("/api/show", {"model": name}, self.PROBE_TIMEOUT_SECONDS)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as erreur:
            # Un serveur plus ancien ne connaît pas `capabilities` ; ce n'est pas
            # une panne, c'est une absence de mesure, et le profil déclaré tient.
            logger.debug("Capacités non mesurées pour %s : %s", name, erreur)
            return None
        profil = profil_mesure(corps)
        self._profils_mesures[name] = profil
        return profil

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
