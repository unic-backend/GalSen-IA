"""
Google provider for the GalSen IA Model Engine.

Declares the Gemini model catalogue.
"""

import json
import os
import urllib.error
import urllib.request
from typing import List

from .base import ModelDescriptor, GenerationRequest, GenerationResponse, ProviderStatus, UnavailabilityReason
from .hosted_provider import HostedProvider, detail_avec_corps, read_error_body

# Langues couvertes par les modèles Gemini retenus ici
_SUPPORTED_LANGUAGES = ["en", "fr", "es", "de", "it", "pt", "ja", "ko", "zh", "ar", "sw"]


class GoogleProvider(HostedProvider):
    """Fournisseur des modèles Google Gemini."""

    provider_id = "google"
    display_name = "Google Gemini"
    credential_environment_variable = "GOOGLE_API_KEY"

    def list_models(self) -> List[ModelDescriptor]:
        """Retourne le catalogue des modèles Gemini pris en charge."""
        return [
            ModelDescriptor(
                model_name="gemini-1.5-pro",
                provider_id=self.provider_id,
                context_window=1000000,
                max_output_tokens=8192,
                supports_streaming=True,
                supports_function_calling=True,
                supports_vision=True,
                supported_languages=_SUPPORTED_LANGUAGES,
                pricing_per_1k_tokens={"input": 0.00125, "output": 0.005},
                training_data_cutoff="2023-11",
                special_features=["reasoning", "vision", "long_context", "multimodal"],
            ),
            ModelDescriptor(
                model_name="gemini-1.5-flash",
                provider_id=self.provider_id,
                context_window=1000000,
                max_output_tokens=8192,
                supports_streaming=True,
                supports_function_calling=True,
                supports_vision=True,
                supported_languages=_SUPPORTED_LANGUAGES,
                pricing_per_1k_tokens={"input": 0.000075, "output": 0.0003},
                training_data_cutoff="2023-11",
                special_features=["fast_response", "vision", "long_context", "low_cost"],
            ),
        ]

    def _call_api(self, request: GenerationRequest) -> GenerationResponse:
        """
        Appelle l'API Google Gemini pour générer du texte.

        Args:
            request: Requête de génération

        Returns:
            Réponse de l'API Google Gemini
        """
        import time

        api_key = os.environ.get(self.credential_environment_variable)
        if not api_key:
            return self._make_unavailable_response(
                request.model_name,
                UnavailabilityReason.NO_CREDENTIALS,
                self._credentials_detail()
            )

        # Construire l'URL de l'API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{request.model_name}:generateContent?key={api_key}"
        headers = {
            "Content-Type": "application/json"
        }

        # Convertir le format de requête générique au format Google Gemini
        contents = []
        parts = []

        # Ajouter le prompt système s'il existe
        if request.system_prompt:
            parts.append({"text": request.system_prompt})

        # Ajouter le prompt utilisateur
        parts.append({"text": request.prompt})

        contents.append({"role": "user", "parts": parts})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
                "stopSequences": request.stop_sequences if request.stop_sequences else None,
            }
        }

        # Nettoyer les valeurs None
        if payload["generationConfig"]["stopSequences"] is None:
            del payload["generationConfig"]["stopSequences"]

        # Faire l'appel API
        started_at = time.time()
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode('utf-8'))

            # Extraire la réponse
            candidates = response_data.get('candidates', [])
            if candidates:
                content_parts = candidates[0].get('content', {}).get('parts', [])
                text_parts = [part.get('text', '') for part in content_parts if 'text' in part]
                content = ''.join(text_parts)
            else:
                content = ""

            return GenerationResponse(
                status=ProviderStatus.READY,
                text=content,
                provider_id=self.provider_id,
                model_name=request.model_name,
                prompt_tokens=self._estimate_tokens(request.prompt),  # Estimation approximative
                completion_tokens=self._estimate_tokens(content),     # Estimation approximative
                latency_seconds=time.time() - started_at,
            )
        except urllib.error.HTTPError as e:
            error_body = read_error_body(e)
            if e.code == 400 and "API_KEY_INVALID" in error_body:
                reason = UnavailabilityReason.UNAUTHORIZED
                detail = "Clé API Google invalide ou absente"
            elif e.code == 429:
                reason = UnavailabilityReason.QUOTA_EXCEEDED
                detail = "Quota Google AI épuisé"
            else:
                reason = UnavailabilityReason.UNREACHABLE
                detail = detail_avec_corps(f"Erreur API Google: {e.code}", error_body)

            return self._make_unavailable_response(
                request.model_name,
                reason,
                detail
            )
        except Exception as e:
            return self._make_unavailable_response(
                request.model_name,
                UnavailabilityReason.UNREACHABLE,
                f"Erreur lors de l'appel à l'API Google: {str(e)}"
            )

    def _make_unavailable_response(self, model_name: str, reason: UnavailabilityReason, detail: str) -> GenerationResponse:
        """Créer une réponse d'indisponibilité."""
        return GenerationResponse.unavailable(
            provider_id=self.provider_id,
            model_name=model_name,
            reason=reason,
            detail=detail,
        )

    def _estimate_tokens(self, text: str) -> int:
        """Estimer le nombre de tokens (approximation simple)."""
        if not text:
            return 0
        # Approximation grossière : environ 4 caractères par token
        return max(1, len(text) // 4)
