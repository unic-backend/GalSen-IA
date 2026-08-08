"""
Tests unitaires pour les fournisseurs de modèles hébergés.

Ces tests mockent les appels HTTP sortants (urllib) pour éviter toute
dépendance réseau. Les clés API ne sont jamais lues ni définies dans
ce fichier.
"""

import json
import os
import sys
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model_engine.providers.base import (
    GenerationRequest,
    ProviderStatus,
    UnavailabilityReason,
)
from src.model_engine.providers.openai_provider import OpenAIProvider
from src.model_engine.providers.anthropic_provider import AnthropicProvider
from src.model_engine.providers.google_provider import GoogleProvider


# ── Helpers de mock HTTP ──────────────────────────────────────────────────────

def _raise_http_error(error_obj):
    """Crée une fonction qui lève une HTTPError (pour side_effect de patch)."""
    def _raise(*args, **kwargs):
        raise error_obj
    return _raise


def _make_http_error(url: str, code: int, body: str) -> HTTPError:
    """Crée une HTTPError avec le body en bytes (comme une vraie réponse HTTP)."""
    msg = "Too Many Requests" if code == 429 else "Error"
    return HTTPError(url, code, msg, {}, BytesIO(body.encode("utf-8")))


# ── Tests du comportement commun ──────────────────────────────────────────────

class TestHostedProviderBase(unittest.TestCase):

    def setUp(self):
        self.provider = OpenAIProvider()

    def tearDown(self):
        os.environ.pop("OPENAI_API_KEY", None)

    def test_check_availability_no_credentials(self):
        os.environ.pop("OPENAI_API_KEY", None)
        info = self.provider.check_availability()
        self.assertEqual(info.status, ProviderStatus.UNAVAILABLE)
        self.assertEqual(info.reason, UnavailabilityReason.NO_CREDENTIALS)
        self.assertIsNotNone(info.detail)

    def test_check_availability_with_credentials(self):
        os.environ["OPENAI_API_KEY"] = "sk-test-key"
        info = self.provider.check_availability()
        self.assertEqual(info.status, ProviderStatus.READY)

    def test_check_availability_empty_key_is_no_credentials(self):
        os.environ["OPENAI_API_KEY"] = ""
        info = self.provider.check_availability()
        self.assertEqual(info.status, ProviderStatus.UNAVAILABLE)
        self.assertEqual(info.reason, UnavailabilityReason.NO_CREDENTIALS)

    def test_generate_no_credentials_returns_unavailable(self):
        os.environ.pop("OPENAI_API_KEY", None)
        request = GenerationRequest(prompt="Test", model_name="gpt-4")
        response = self.provider.generate(request)
        self.assertEqual(response.status, ProviderStatus.UNAVAILABLE)
        self.assertEqual(response.reason, UnavailabilityReason.NO_CREDENTIALS)


class TestHostedProviderCredentialVar(unittest.TestCase):

    def test_openai_credential_var(self):
        self.assertEqual(OpenAIProvider().credential_environment_variable, "OPENAI_API_KEY")

    def test_anthropic_credential_var(self):
        self.assertEqual(AnthropicProvider().credential_environment_variable, "ANTHROPIC_API_KEY")

    def test_google_credential_var(self):
        self.assertEqual(GoogleProvider().credential_environment_variable, "GOOGLE_API_KEY")


class TestHostedProviderRequiresCredentials(unittest.TestCase):

    def test_openai_requires_credentials(self):
        self.assertTrue(OpenAIProvider().requires_credentials)

    def test_anthropic_requires_credentials(self):
        self.assertTrue(AnthropicProvider().requires_credentials)

    def test_google_requires_credentials(self):
        self.assertTrue(GoogleProvider().requires_credentials)


# ── Tests OpenAI ──────────────────────────────────────────────────────────────

class TestOpenAIProviderAPI(unittest.TestCase):

    def setUp(self):
        self.provider = OpenAIProvider()
        os.environ["OPENAI_API_KEY"] = "sk-test-key"

    def tearDown(self):
        os.environ.pop("OPENAI_API_KEY", None)

    def _mock_response(self, text="Hello!", prompt_tokens=10, completion_tokens=5):
        data = {
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }
        mock = MagicMock()
        mock.read.return_value = json.dumps(data).encode("utf-8")
        mock.__enter__.return_value = mock
        return mock

    def test_successful_generation(self):
        request = GenerationRequest(prompt="Bonjour", model_name="gpt-4")
        with patch("urllib.request.urlopen", return_value=self._mock_response("Bonjour")):
            response = self.provider.generate(request)
        self.assertEqual(response.status, ProviderStatus.READY)
        self.assertIn("Bonjour", response.text)
        self.assertEqual(response.prompt_tokens, 10)
        self.assertEqual(response.completion_tokens, 5)
        self.assertGreater(response.latency_seconds, 0)

    def test_generation_with_system_prompt(self):
        request = GenerationRequest(prompt="Dis bonjour", model_name="gpt-4", system_prompt="Sois poli")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response("Bonjour!")
            self.provider.generate(request)
            call_args = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
            self.assertEqual(call_args["messages"][0]["role"], "system")
            self.assertEqual(call_args["messages"][0]["content"], "Sois poli")

    def test_generation_with_stop_sequences(self):
        request = GenerationRequest(prompt="Test", model_name="gpt-4", stop_sequences=["\n", "STOP"])
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response("OK")
            self.provider.generate(request)
            call_args = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
            self.assertEqual(call_args["stop"], ["\n", "STOP"])

    def test_generation_with_temperature(self):
        request = GenerationRequest(prompt="Test", model_name="gpt-4", temperature=0.2)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response("OK")
            self.provider.generate(request)
            call_args = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
            self.assertEqual(call_args["temperature"], 0.2)

    def test_http_401_returns_unauthorized(self):
        request = GenerationRequest(prompt="Test", model_name="gpt-4")
        error = _make_http_error("https://api.openai.com/", 401, '{"error": "Unauthorized"}')
        with patch("urllib.request.urlopen", _raise_http_error(error)):
            response = self.provider.generate(request)
        self.assertEqual(response.status, ProviderStatus.UNAVAILABLE)
        self.assertEqual(response.reason, UnavailabilityReason.UNAUTHORIZED)

    def test_http_429_returns_quota_exceeded(self):
        request = GenerationRequest(prompt="Test", model_name="gpt-4")
        error = _make_http_error("https://api.openai.com/", 429, '{"error": "Rate limit"}')
        with patch("urllib.request.urlopen", _raise_http_error(error)):
            response = self.provider.generate(request)
        self.assertEqual(response.status, ProviderStatus.UNAVAILABLE)
        self.assertEqual(response.reason, UnavailabilityReason.QUOTA_EXCEEDED)


# ── Tests Anthropic ───────────────────────────────────────────────────────────

class TestAnthropicProviderAPI(unittest.TestCase):

    def setUp(self):
        self.provider = AnthropicProvider()
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-key"

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def _mock_response(self, text="Hello!"):
        data = {
            "content": [{"text": text}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        mock = MagicMock()
        mock.read.return_value = json.dumps(data).encode("utf-8")
        mock.__enter__.return_value = mock
        return mock

    def test_successful_generation(self):
        request = GenerationRequest(prompt="Bonjour", model_name="claude-3-sonnet")
        with patch("urllib.request.urlopen", return_value=self._mock_response("Bonjour!")):
            response = self.provider.generate(request)
        self.assertEqual(response.status, ProviderStatus.READY)
        self.assertEqual(response.text, "Bonjour!")
        self.assertEqual(response.prompt_tokens, 10)
        self.assertEqual(response.completion_tokens, 5)

    def test_system_prompt_in_separate_field(self):
        request = GenerationRequest(prompt="Parle", model_name="claude-3-sonnet", system_prompt="Sois bref")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response("OK")
            self.provider.generate(request)
            call_args = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
            self.assertEqual(call_args["system"], "Sois bref")
            self.assertEqual(len(call_args["messages"]), 1)

    def test_http_401_returns_unauthorized(self):
        request = GenerationRequest(prompt="Test", model_name="claude-3-sonnet")
        error = _make_http_error("https://api.anthropic.com/", 401, '{"error": "Unauthorized"}')
        with patch("urllib.request.urlopen", _raise_http_error(error)):
            response = self.provider.generate(request)
        self.assertEqual(response.status, ProviderStatus.UNAVAILABLE)
        self.assertEqual(response.reason, UnavailabilityReason.UNAUTHORIZED)

    def test_http_429_returns_quota_exceeded(self):
        request = GenerationRequest(prompt="Test", model_name="claude-3-sonnet")
        error = _make_http_error("https://api.anthropic.com/", 429, '{"error": "Rate limit"}')
        with patch("urllib.request.urlopen", _raise_http_error(error)):
            response = self.provider.generate(request)
        self.assertEqual(response.status, ProviderStatus.UNAVAILABLE)
        self.assertEqual(response.reason, UnavailabilityReason.QUOTA_EXCEEDED)


# ── Tests Google ──────────────────────────────────────────────────────────────

class TestGoogleProviderAPI(unittest.TestCase):

    def setUp(self):
        self.provider = GoogleProvider()
        os.environ["GOOGLE_API_KEY"] = "google-test-key"

    def tearDown(self):
        os.environ.pop("GOOGLE_API_KEY", None)

    def _mock_response(self, text="Hello!"):
        data = {
            "candidates": [
                {"content": {"parts": [{"text": text}]}}
            ]
        }
        mock = MagicMock()
        mock.read.return_value = json.dumps(data).encode("utf-8")
        mock.__enter__.return_value = mock
        return mock

    def test_successful_generation(self):
        request = GenerationRequest(prompt="Bonjour", model_name="gemini-1.5-pro")
        with patch("urllib.request.urlopen", return_value=self._mock_response("Bonjour!")):
            response = self.provider.generate(request)
        self.assertEqual(response.status, ProviderStatus.READY)
        self.assertEqual(response.text, "Bonjour!")

    def test_http_400_api_key_invalid_returns_unauthorized(self):
        request = GenerationRequest(prompt="Test", model_name="gemini-1.5-pro")
        error = _make_http_error(
            "https://generativelanguage.googleapis.com/",
            400,
            '{"error": {"message": "API_KEY_INVALID"}}',
        )
        with patch("urllib.request.urlopen", _raise_http_error(error)):
            response = self.provider.generate(request)
        self.assertEqual(response.status, ProviderStatus.UNAVAILABLE)
        self.assertEqual(response.reason, UnavailabilityReason.UNAUTHORIZED)

    def test_http_429_returns_quota_exceeded(self):
        request = GenerationRequest(prompt="Test", model_name="gemini-1.5-pro")
        error = _make_http_error("https://generativelanguage.googleapis.com/", 429, '{"error": "Rate limit"}')
        with patch("urllib.request.urlopen", _raise_http_error(error)):
            response = self.provider.generate(request)
        self.assertEqual(response.status, ProviderStatus.UNAVAILABLE)
        self.assertEqual(response.reason, UnavailabilityReason.QUOTA_EXCEEDED)

    def test_system_prompt_included(self):
        request = GenerationRequest(prompt="Test", model_name="gemini-1.5-pro", system_prompt="Sois utile")
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = self._mock_response("OK")
            self.provider.generate(request)
            call_args = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
            parts = call_args["contents"][0]["parts"]
            texts = [p["text"] for p in parts]
            self.assertIn("Sois utile", texts)
            self.assertIn("Test", texts)


if __name__ == "__main__":
    unittest.main()