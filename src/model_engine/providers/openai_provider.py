"""
OpenAI provider for the GalSen IA Model Engine.

Declares the OpenAI model catalogue. The figures below are the published
characteristics of each model and are used for selection and cost estimation
before any call is made.
"""

import json
import os
from typing import List
import urllib.request
import urllib.error

from .base import GenerationRequest, GenerationResponse, ProviderStatus, UnavailabilityReason
from .hosted_provider import HostedProvider, detail_avec_corps, read_error_body
from .base import ModelDescriptor

# Langues couvertes par les modèles OpenAI retenus ici
_SUPPORTED_LANGUAGES = ["en", "fr", "es", "de", "it", "pt", "ja", "ko", "zh", "ar"]


class OpenAIProvider(HostedProvider):
    """Fournisseur des modèles OpenAI."""

    provider_id = "openai"
    display_name = "OpenAI"
    credential_environment_variable = "OPENAI_API_KEY"

    def list_models(self) -> List[ModelDescriptor]:
        """Retourne le catalogue des modèles OpenAI pris en charge."""
        return [
            ModelDescriptor(
                model_name="gpt-4",
                provider_id=self.provider_id,
                context_window=8192,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_function_calling=True,
                supports_vision=False,
                supported_languages=_SUPPORTED_LANGUAGES,
                pricing_per_1k_tokens={"input": 0.03, "output": 0.06},
                training_data_cutoff="2023-09",
                special_features=["reasoning", "creative_writing", "code_generation"],
            ),
            ModelDescriptor(
                model_name="gpt-4-turbo",
                provider_id=self.provider_id,
                context_window=128000,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_function_calling=True,
                supports_vision=True,
                supported_languages=_SUPPORTED_LANGUAGES,
                pricing_per_1k_tokens={"input": 0.01, "output": 0.03},
                training_data_cutoff="2023-12",
                special_features=["reasoning", "vision", "code_generation", "long_context"],
            ),
            ModelDescriptor(
                model_name="gpt-3.5-turbo",
                provider_id=self.provider_id,
                context_window=4096,
                max_output_tokens=4096,
                supports_streaming=True,
                supports_function_calling=True,
                supports_vision=False,
                supported_languages=_SUPPORTED_LANGUAGES,
                pricing_per_1k_tokens={"input": 0.0015, "output": 0.002},
                training_data_cutoff="2021-09",
                special_features=["general_conversation", "basic_reasoning", "low_cost"],
            ),
        ]

    def _call_api(self, request: GenerationRequest) -> GenerationResponse:
        """
        Appelle l'API OpenAI pour générer du texte.

        Args:
            request: Requête de génération

        Returns:
            Réponse de l'API OpenAI
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

        # Préparer la requête pour l'API OpenAI
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Convertir le format de requête générique au format OpenAI
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": request.model_name,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False
        }

        if request.stop_sequences:
            payload["stop"] = request.stop_sequences

        # Faire l'appel API
        started_at = time.time()
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode('utf-8'))

            # Extraire la réponse
            content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')

            return GenerationResponse(
                status=ProviderStatus.READY,
                text=content,
                provider_id=self.provider_id,
                model_name=request.model_name,
                prompt_tokens=response_data.get('usage', {}).get('prompt_tokens', 0),
                completion_tokens=response_data.get('usage', {}).get('completion_tokens', 0),
                latency_seconds=time.time() - started_at,
            )
        except urllib.error.HTTPError as e:
            error_body = read_error_body(e)
            if e.code == 401:
                reason = UnavailabilityReason.UNAUTHORIZED
                detail = "Clé API OpenAI invalide ou absente"
            elif e.code == 429:
                reason = UnavailabilityReason.QUOTA_EXCEEDED
                detail = "Quota OpenAI dépassé"
            else:
                reason = UnavailabilityReason.UNREACHABLE
                detail = detail_avec_corps(f"Erreur API OpenAI: {e.code}", error_body)

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
                detail=f"Erreur lors de l'appel à l'API OpenAI: {str(e)}",
            )
