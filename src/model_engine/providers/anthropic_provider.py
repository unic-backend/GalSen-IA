"""
Anthropic provider for the GalSen IA Model Engine.

Declares the Claude model catalogue. The long context windows make these models
the natural candidates for document-heavy tasks, which is how the selector uses
this information.
"""

import json
import os
from typing import List
import urllib.request
import urllib.error

from .base import ModelDescriptor
from .hosted_provider import HostedProvider, detail_avec_corps, read_error_body
from .base import GenerationRequest, GenerationResponse, ProviderStatus, UnavailabilityReason

# Langues couvertes par les modèles Claude retenus ici
_SUPPORTED_LANGUAGES = ["en", "fr", "es", "de", "it", "pt", "ja", "ko", "zh", "ar"]


class AnthropicProvider(HostedProvider):
    """Fournisseur des modèles Anthropic Claude."""

    provider_id = "anthropic"
    display_name = "Anthropic"
    credential_environment_variable = "ANTHROPIC_API_KEY"

    def list_models(self) -> List[ModelDescriptor]:
        """Retourne le catalogue des modèles Claude pris en charge."""
        return [
            ModelDescriptor(
                model_name="claude-3-opus",
                provider_id=self.provider_id,
                context_window=200000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_function_calling=True,
                supports_vision=True,
                supported_languages=_SUPPORTED_LANGUAGES,
                pricing_per_1k_tokens={"input": 0.015, "output": 0.075},
                training_data_cutoff="2023-08",
                special_features=["reasoning", "analysis", "creative_writing", "vision", "long_context"],
            ),
            ModelDescriptor(
                model_name="claude-3-sonnet",
                provider_id=self.provider_id,
                context_window=200000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_function_calling=True,
                supports_vision=True,
                supported_languages=_SUPPORTED_LANGUAGES,
                pricing_per_1k_tokens={"input": 0.003, "output": 0.015},
                training_data_cutoff="2023-08",
                special_features=["reasoning", "analysis", "vision", "long_context", "balanced_cost"],
            ),
            ModelDescriptor(
                model_name="claude-3-haiku",
                provider_id=self.provider_id,
                context_window=200000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_function_calling=True,
                supports_vision=True,
                supported_languages=_SUPPORTED_LANGUAGES,
                pricing_per_1k_tokens={"input": 0.00025, "output": 0.00125},
                training_data_cutoff="2023-08",
                special_features=["fast_response", "vision", "long_context", "low_cost"],
            ),
        ]

    def _call_api(self, request: GenerationRequest) -> GenerationResponse:
        """
        Appelle l'API Anthropic pour générer du texte.

        Args:
            request: Requête de génération

        Returns:
            Réponse de l'API Anthropic
        """
        import time

        api_key = os.environ.get(self.credential_environment_variable)
        if not api_key:
            return GenerationResponse.unavailable(
                provider_id=self.provider_id,
                model_name=request.model_name,
                reason=UnavailabilityReason.NO_CREDENTIALS,
                detail=self._credentials_detail(),
            )

        # Préparer la requête pour l'API Anthropic
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        # Convertir le format de requête générique au format Anthropic
        messages = []
        if request.system_prompt:
            # Anthropic place le system prompt dans un champ dédié
            pass  # sera mis dans le champ "system" dédié ci-dessous
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": request.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if request.system_prompt:
            payload["system"] = request.system_prompt

        if request.stop_sequences:
            payload["stop_sequences"] = request.stop_sequences

        # Appel API
        started_at = time.time()
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode('utf-8'))

            # Extraction de la réponse
            content = response_data.get('content', [{}])[0].get('text', '')

            return GenerationResponse(
                status=ProviderStatus.READY,
                text=content,
                provider_id=self.provider_id,
                model_name=request.model_name,
                prompt_tokens=response_data.get('usage', {}).get('input_tokens', 0),
                completion_tokens=response_data.get('usage', {}).get('output_tokens', 0),
                latency_seconds=time.time() - started_at,
            )
        except urllib.error.HTTPError as e:
            error_body = read_error_body(e)
            if e.code == 401:
                reason = UnavailabilityReason.UNAUTHORIZED
                detail = "Clé API Anthropic invalide ou absente"
            elif e.code == 429:
                reason = UnavailabilityReason.QUOTA_EXCEEDED
                detail = "Quota Anthropic dépassé"
            else:
                reason = UnavailabilityReason.UNREACHABLE
                detail = detail_avec_corps(f"Erreur API Anthropic: {e.code}", error_body)

            return GenerationResponse.unavailable(
                provider_id=self.provider_id,
                model_name=request.model_name,
                reason=reason,
                detail=detail,
            )
        except Exception as e:
            return GenerationResponse.unavailable(
                provider_id=self.provider_id,
                model_name=request.model_name,
                reason=UnavailabilityReason.UNREACHABLE,
                detail=f"Erreur lors de l'appel à l'API Anthropic: {str(e)}",
            )
