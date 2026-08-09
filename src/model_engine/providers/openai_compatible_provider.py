"""
Fournisseur pour toute API parlant le protocole OpenAI (ADR-003).

Un seul fournisseur ouvre la plupart des chemins possibles vers un modèle,
parce que le protocole d'OpenAI est devenu le dénominateur commun :

| Où          | Exemples                                            | Clé |
|-------------|-----------------------------------------------------|-----|
| Local       | vLLM, LM Studio, llama.cpp `--server`, LocalAI       | non |
| Serveur loué| vLLM ou TGI sur une machine à GPU                    | selon |
| Hébergé     | OpenRouter, Groq, Together, DeepInfra                | oui |

C'est ce qui rend le passage « mon portable → mon serveur → un hébergeur »
possible sans écrire une ligne de code : seule l'URL change.

Deux différences avec `OpenAIProvider`, et elles justifient un fournisseur
distinct plutôt qu'un paramètre :

- **La clé est facultative.** Un serveur local n'en demande pas, et
  `HostedProvider` refuse de fonctionner sans identifiants.
- **Le catalogue est découvert**, pas déclaré. `GET /v1/models` dit ce que le
  serveur sert réellement ; une liste écrite en dur mentirait dès qu'on change
  de modèle.

Configuration :

    GALSEN_OPENAI_COMPATIBLE_URL      http://localhost:8000/v1  (obligatoire)
    GALSEN_OPENAI_COMPATIBLE_KEY      clé, si le service en exige une
    GALSEN_OPENAI_COMPATIBLE_CONTEXT  fenêtre de contexte annoncée (défaut 8192)
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import List, Optional

from src.model_engine.providers.base import (
    GenerationRequest,
    GenerationResponse,
    ModelDescriptor,
    ModelProvider,
    ProviderInfo,
    ProviderStatus,
    UnavailabilityReason,
)

logger = logging.getLogger(__name__)

URL_VARIABLE = "GALSEN_OPENAI_COMPATIBLE_URL"
KEY_VARIABLE = "GALSEN_OPENAI_COMPATIBLE_KEY"
CONTEXT_VARIABLE = "GALSEN_OPENAI_COMPATIBLE_CONTEXT"

# `/v1/models` ne dit pas quelle fenêtre de contexte un modèle accepte. 8192 est
# le seuil que le sélecteur exige par défaut : annoncer moins écarterait
# silencieusement tous les modèles de ce fournisseur, annoncer beaucoup plus
# ferait accepter des requêtes que le serveur refuserait. La valeur est donc
# réglable, et sa valeur par défaut est celle qui rend le fournisseur utilisable.
CONTEXTE_PAR_DEFAUT = 8192

_LANGUES = ["fr", "en", "wo", "ar", "es", "pt"]


class OpenAICompatibleProvider(ModelProvider):
    """
    Parle à n'importe quel service exposant `/v1/models` et `/v1/chat/completions`.

    Le fournisseur est **inactif tant qu'aucune URL n'est déclarée** : il ne
    devine pas d'adresse et ne se rabat sur rien. Un fournisseur qui pointerait
    silencieusement ailleurs serait pire qu'un fournisseur absent.
    """

    provider_id = "openai_compatible"
    display_name = "API compatible OpenAI"

    DELAI_SONDE_SECONDES = 3
    DELAI_GENERATION_SECONDES = 120

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialise le fournisseur.

        Args:
            base_url: Racine de l'API, `.../v1`. Lue dans l'environnement si absente.
            api_key: Clé éventuelle. Lue dans l'environnement si absente.
        """
        self._base_url = (base_url or os.environ.get(URL_VARIABLE, "")).strip().rstrip("/")
        self._api_key = api_key if api_key is not None else os.environ.get(KEY_VARIABLE)

    # ------------------------------------------------------------------
    # Contrat ModelProvider
    # ------------------------------------------------------------------

    @property
    def requires_credentials(self) -> bool:
        """Une clé n'est requise que si le service en réclame une."""
        return False

    def check_availability(self) -> ProviderInfo:
        """
        Vérifie qu'un service répond à l'URL déclarée.

        Returns:
            L'état du fournisseur, avec le motif exact s'il est indisponible.
        """
        if not self._base_url:
            return self._indisponible(
                UnavailabilityReason.DISABLED,
                f"Aucune URL déclarée. Renseignez {URL_VARIABLE}, par exemple "
                f"http://localhost:8000/v1 pour un serveur vLLM local.",
            )

        modeles = self.list_models()
        if not modeles:
            return self._indisponible(
                UnavailabilityReason.UNREACHABLE,
                f"Aucun modèle servi par {self._base_url}. Le service répond-il, "
                f"et sert-il bien /v1/models ?",
            )

        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            status=ProviderStatus.READY,
            model_count=len(modeles),
            requires_credentials=False,
        )

    def list_models(self) -> List[ModelDescriptor]:
        """
        Retourne les modèles que le service déclare servir.

        Le catalogue est **découvert**, jamais écrit en dur : c'est la seule
        façon de rester juste quand l'exploitant change de modèle.
        """
        if not self._base_url:
            return []

        try:
            corps = self._get("/models", self.DELAI_SONDE_SECONDES)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as erreur:
            logger.debug("Catalogue compatible OpenAI illisible : %s", erreur)
            return []

        contexte = self._contexte_annonce()
        descripteurs = []
        for entree in corps.get("data", []):
            nom = entree.get("id")
            if not nom:
                continue
            descripteurs.append(
                ModelDescriptor(
                    model_name=nom,
                    provider_id=self.provider_id,
                    context_window=contexte,
                    max_output_tokens=4096,
                    supports_streaming=True,
                    supports_function_calling=False,
                    supports_vision=False,
                    supported_languages=_LANGUES,
                    # Aucun prix : un service auto-hébergé n'en a pas, et en
                    # inventer un fausserait la sélection par coût.
                    pricing_per_1k_tokens=None,
                )
            )
        return descripteurs

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        """
        Génère du texte via `/v1/chat/completions`.

        Args:
            request: La requête de génération.

        Returns:
            La réponse, ou une indisponibilité portant son motif — jamais un
            texte de remplacement.
        """
        if not self._base_url:
            return GenerationResponse.unavailable(
                provider_id=self.provider_id,
                model_name=request.model_name,
                reason=UnavailabilityReason.DISABLED,
                detail=f"Aucune URL déclarée ({URL_VARIABLE}).",
            )

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        charge = {
            "model": request.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        if request.stop_sequences:
            charge["stop"] = list(request.stop_sequences)

        debut = time.time()
        try:
            corps = self._post("/chat/completions", charge, self.DELAI_GENERATION_SECONDES)
        except urllib.error.HTTPError as erreur:
            return self._echec_http(erreur, request)
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as erreur:
            return GenerationResponse.unavailable(
                provider_id=self.provider_id,
                model_name=request.model_name,
                reason=UnavailabilityReason.UNREACHABLE,
                detail=f"{self._base_url} n'a pas répondu : {erreur}",
            )

        choix = (corps.get("choices") or [{}])[0]
        texte = (choix.get("message") or {}).get("content", "")
        usage = corps.get("usage") or {}

        return GenerationResponse(
            status=ProviderStatus.READY,
            text=texte,
            provider_id=self.provider_id,
            model_name=corps.get("model") or request.model_name,
            prompt_tokens=usage.get("prompt_tokens", self.estimate_tokens(request.prompt)),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_seconds=time.time() - debut,
        )

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------

    def _contexte_annonce(self) -> int:
        """Retourne la fenêtre de contexte annoncée, réglable par l'environnement."""
        try:
            valeur = int(os.environ.get(CONTEXT_VARIABLE, "").strip())
        except (TypeError, ValueError):
            return CONTEXTE_PAR_DEFAUT
        return valeur if valeur > 0 else CONTEXTE_PAR_DEFAUT

    def _entetes(self) -> dict:
        """Construit les en-têtes, avec la clé seulement si elle existe."""
        entetes = {"Content-Type": "application/json"}
        if self._api_key:
            entetes["Authorization"] = f"Bearer {self._api_key}"
        return entetes

    def _get(self, chemin: str, delai: int) -> dict:
        """Exécute un GET et retourne le corps JSON."""
        requete = urllib.request.Request(
            f"{self._base_url}{chemin}", headers=self._entetes(), method="GET"
        )
        with urllib.request.urlopen(requete, timeout=delai) as reponse:
            return json.loads(reponse.read().decode("utf-8"))

    def _post(self, chemin: str, charge: dict, delai: int) -> dict:
        """Exécute un POST JSON et retourne le corps JSON."""
        requete = urllib.request.Request(
            f"{self._base_url}{chemin}",
            data=json.dumps(charge).encode("utf-8"),
            headers=self._entetes(),
            method="POST",
        )
        with urllib.request.urlopen(requete, timeout=delai) as reponse:
            return json.loads(reponse.read().decode("utf-8"))

    def _echec_http(self, erreur, request: GenerationRequest) -> GenerationResponse:
        """
        Traduit un code HTTP en motif exploitable.

        Un 401 et un 429 appellent des gestes différents : le premier demande
        une clé, le second demande d'attendre. Les confondre laisserait
        l'exploitant sans piste.
        """
        motifs = {
            401: (UnavailabilityReason.UNAUTHORIZED, f"Clé refusée. Vérifiez {KEY_VARIABLE}."),
            403: (UnavailabilityReason.UNAUTHORIZED, "Accès refusé par le service."),
            404: (
                UnavailabilityReason.DISABLED,
                f"Modèle '{request.model_name}' inconnu de {self._base_url}.",
            ),
            429: (UnavailabilityReason.QUOTA_EXCEEDED, "Quota atteint : réessayez plus tard."),
        }
        motif, detail = motifs.get(
            erreur.code,
            (UnavailabilityReason.UNREACHABLE, f"HTTP {erreur.code} depuis {self._base_url}."),
        )
        return GenerationResponse.unavailable(
            provider_id=self.provider_id,
            model_name=request.model_name,
            reason=motif,
            detail=detail,
        )

    def _indisponible(self, motif, detail: str) -> ProviderInfo:
        """Construit un état indisponible portant son motif."""
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            status=ProviderStatus.UNAVAILABLE,
            model_count=0,
            requires_credentials=False,
            reason=motif,
            detail=detail,
        )
