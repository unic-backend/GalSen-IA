"""
Tests pour la fonctionnalité « Conseil Agricole » (priorité #7).

Couvre :
- L'outil AgriAdviceTool (sélection du modèle, génération, langues, erreurs)
- L'endpoint POST /agri/advice (authentification, validation, réponse)
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# Définir la clé API avant d'importer le serveur : le RBAC la charge à l'import.
os.environ["GALSEN_API_KEYS"] = "test-key:user"
os.environ["GALSEN_RATE_LIMIT_ENABLED"] = "false"

from fastapi.testclient import TestClient

from src.api import server
from src.tools.agri_advice.tool import AgriAdviceTool

VALID_KEY = "test-key"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Client HTTP branché sur l'application réelle du serveur."""
    return TestClient(server.app)


@pytest.fixture
def headers():
    """En-têtes avec la clé API valide."""
    return {"X-API-Key": VALID_KEY}


@pytest.fixture
def mock_generation():
    """Mock de AgriAdviceTool pour une génération déterministe."""
    fake_tool = MagicMock()
    fake_tool.execute.return_value = {
        "answer": "Plantez le mil en début d'hivernage.",
        "language": "fr",
        "model_used": "qwen2.5-coder:14b",
    }
    with patch.object(server, "AgriAdviceTool", return_value=fake_tool):
        yield fake_tool


# ---------------------------------------------------------------------------
# Tests de l'outil AgriAdviceTool
# ---------------------------------------------------------------------------


class TestAgriAdviceTool:
    """Tests unitaires de l'outil de conseil agricole."""

    def test_available_operations(self):
        """Les opérations disponibles doivent contenir get_advice."""
        tool = AgriAdviceTool(config={"model_id": "fake"})
        assert tool.available_operations() == ["get_advice"]

    def test_question_vide_leve_value_error(self):
        """Une question vide doit lever ValueError."""
        tool = AgriAdviceTool(config={"model_id": "fake"})
        with pytest.raises(ValueError):
            tool.execute("get_advice", "   ")

    def test_operation_inconnue_leve_value_error(self):
        """Une opération inconnue doit lever ValueError."""
        tool = AgriAdviceTool(config={"model_id": "fake"})
        with pytest.raises(ValueError, match="inconnue"):
            tool.execute("autre_operation", "Question")

    def test_aucune_operation_leve_value_error(self):
        """L'exécution sans opération doit lever ValueError."""
        tool = AgriAdviceTool(config={"model_id": "fake"})
        with pytest.raises(ValueError):
            tool.execute()

    def test_generation_avec_modele_impose(self):
        """Un modèle imposé doit être utilisé et la réponse retournée."""
        fake_manager = MagicMock()
        fake_model = MagicMock()
        fake_model.name = "modele-test"
        fake_manager.get_model.return_value = fake_model
        fake_response = MagicMock()
        fake_response.succeeded = True
        fake_response.text = "  Un bon conseil.  "
        fake_response.detail = None
        fake_response.model_name = "modele-test"
        fake_manager.generate.return_value = fake_response

        with patch("src.tools.agri_advice.tool.ModelManagerImpl",
                   return_value=fake_manager):
            tool = AgriAdviceTool()
            result = tool.execute("get_advice", "Quand planter le mil ?",
                                  model_id="modele-test")

        assert result["answer"] == "Un bon conseil."
        assert result["language"] == "fr"
        assert result["model_used"] == "modele-test"
        fake_manager.get_model.assert_called_once_with("modele-test")
        fake_manager.generate.assert_called_once()

    def test_generation_retourne_le_nom_du_modele_reel(self):
        """Le nom du modèle doit venir de la réponse si disponible."""
        fake_manager = MagicMock()
        fake_manager.get_model.return_value = MagicMock(name="declared")
        fake_response = MagicMock()
        fake_response.succeeded = True
        fake_response.text = "Conseil"
        fake_response.model_name = "reel-modele"
        fake_manager.generate.return_value = fake_response

        with patch("src.tools.agri_advice.tool.ModelManagerImpl",
                   return_value=fake_manager):
            tool = AgriAdviceTool()
            result = tool.execute("get_advice", "Question ?")

        assert result["model_used"] == "reel-modele"

    def test_modele_inconnu_leve_erreur(self):
        """Un modèle inconnu doit lever une erreur explicite."""
        fake_manager = MagicMock()
        fake_manager.get_model.return_value = None

        with patch("src.tools.agri_advice.tool.ModelManagerImpl",
                   return_value=fake_manager):
            tool = AgriAdviceTool()
            with pytest.raises(RuntimeError, match="Modèle inconnu"):
                tool.execute("get_advice", "Question ?", model_id="nope")

    def test_aucun_modele_disponible_leve_erreur(self):
        """Sans modèle disponible, une erreur doit être levée."""
        fake_manager = MagicMock()
        fake_manager.select_model_for_task.return_value = None
        fake_manager.unavailability_reason.return_value = "Aucun fournisseur"

        with patch("src.tools.agri_advice.tool.ModelManagerImpl",
                   return_value=fake_manager):
            tool = AgriAdviceTool()
            with pytest.raises(RuntimeError, match="Aucun fournisseur"):
                tool.execute("get_advice", "Question ?")

    def test_echec_generation_leve_erreur(self):
        """Un échec de génération doit lever une erreur."""
        fake_manager = MagicMock()
        fake_manager.select_model_for_task.return_value = MagicMock()
        fake_response = MagicMock()
        fake_response.succeeded = False
        fake_response.detail = "Erreur du fournisseur"
        fake_manager.generate.return_value = fake_response

        with patch("src.tools.agri_advice.tool.ModelManagerImpl",
                   return_value=fake_manager):
            tool = AgriAdviceTool()
            with pytest.raises(RuntimeError, match="Erreur du fournisseur"):
                tool.execute("get_advice", "Question ?")

    def test_question_non_texte_leve_value_error(self):
        """Une question non textuelle doit lever ValueError."""
        tool = AgriAdviceTool(config={"model_id": "fake"})
        with pytest.raises(ValueError):
            tool.execute("get_advice", 123)


# ---------------------------------------------------------------------------
# Tests de l'endpoint /agri/advice
# ---------------------------------------------------------------------------


class TestAgriAdviceEndpoint:
    """Tests d'intégration de l'endpoint POST /agri/advice."""

    def test_question_vide_retourne_422(self, client, headers):
        """Une question vide doit retourner 422."""
        r = client.post("/agri/advice", json={"question": "   "}, headers=headers)
        assert r.status_code == 422
        assert "vide" in r.json()["detail"]

    def test_langue_invalide_retourne_422(self, client, headers):
        """Une langue inconnue doit retourner 422."""
        r = client.post("/agri/advice", json={"question": "Salut", "language": "xx"},
                        headers=headers)
        assert r.status_code == 422
        assert "Langue invalide" in r.json()["detail"]

    def test_sans_cle_api_retourne_401(self, client):
        """Une requête sans clé API doit retourner 401."""
        r = client.post("/agri/advice", json={"question": "Salut"})
        assert r.status_code == 401

    def test_cle_api_invalide_retourne_401(self, client):
        """Une clé API invalide doit retourner 401."""
        r = client.post("/agri/advice", json={"question": "Salut"},
                        headers={"X-API-Key": "mauvaise-cle"})
        assert r.status_code == 401

    def test_generation_reussie_retourne_200(self, client, headers, mock_generation):
        """Une génération réussie doit retourner 200 avec la réponse."""
        r = client.post("/agri/advice", json={"question": "Quand planter ?"},
                        headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["answer"] == "Plantez le mil en début d'hivernage."
        assert data["language"] == "fr"
        assert data["model_used"] == "qwen2.5-coder:14b"

    def test_parametres_transmis_au_tool(self, client, headers, mock_generation):
        """language, model_id et max_tokens doivent être transmis au tool."""
        r = client.post("/agri/advice",
                        json={"question": "Quand planter ?", "language": "wo",
                              "model_id": "m-test", "max_tokens": 200},
                        headers=headers)
        assert r.status_code == 200
        args, kwargs = mock_generation.execute.call_args
        assert args[0] == "get_advice"
        assert args[1] == "Quand planter ?"
        assert kwargs["language"] == "wo"
        assert kwargs["model_id"] == "m-test"
        assert kwargs["max_tokens"] == 200

    def test_erreur_tool_retourne_503(self, client, headers):
        """Une erreur interne du tool doit retourner 503."""
        fake_tool = MagicMock()
        fake_tool.execute.side_effect = RuntimeError("Ollama indisponible")
        with patch.object(server, "AgriAdviceTool", return_value=fake_tool):
            r = client.post("/agri/advice", json={"question": "Quand planter ?"},
                            headers=headers)
        assert r.status_code == 503
        assert "indisponible" in r.json()["detail"]
