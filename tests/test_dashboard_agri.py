"""
Tests pour la page « Conseil Agricole » du dashboard web.

Couvre :
- Le chargement de la page (formulaire, langue, bouton)
- La génération d'un conseil via POST (tool appelé, réponse affichée)
- Les cas d'erreur (question vide, service indisponible, échec du tool)
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.frontend.dashboard import create_dashboard_app


@pytest.fixture
def client():
    """Client HTTP branché sur l'application du dashboard."""
    return TestClient(create_dashboard_app())


@pytest.fixture
def fake_agri():
    """Fausse instance AgriAdviceTool avec une réponse déterministe."""
    fake_tool = MagicMock()
    fake_tool.execute.return_value = {
        "answer": "Plantez le mil en début d'hivernage.",
        "language": "fr",
        "model_used": "qwen2.5-coder:14b",
    }
    return fake_tool


class TestPageConseilAgricole:
    """Tests du chargement de la page."""

    def test_get_retourne_200(self, client):
        """La page doit se charger avec le formulaire."""
        r = client.get("/agri-conseil")
        assert r.status_code == 200
        assert "Conseil Agricole" in r.text
        assert 'name="question"' in r.text
        assert 'name="language"' in r.text

    def test_langues_disponibles(self, client):
        """Le formulaire doit proposer le français et le wolof."""
        r = client.get("/agri-conseil")
        assert 'value="fr"' in r.text
        assert 'value="wo"' in r.text

    def test_bouton_present(self, client):
        """Le bouton de soumission doit être présent."""
        r = client.get("/agri-conseil")
        assert "Obtenir un conseil" in r.text


class TestGenerationConseil:
    """Tests de la génération d'un conseil via POST."""

    def test_post_generer_conseil(self, client, fake_agri):
        """Une question valide doit appeler le tool et afficher la réponse."""
        with patch("src.frontend.dashboard._import_managers",
                   return_value={"agri": fake_agri}):
            r = client.post("/agri-conseil",
                            data={"question": "Quand planter le mil ?",
                                  "language": "fr"})
        assert r.status_code == 200
        fake_agri.execute.assert_called_once_with(
            "get_advice", "Quand planter le mil ?", language="fr"
        )
        # Jinja2 échappe l'apostrophe en &#39; (auto-escape HTML)
        assert "Plantez le mil en début d&#39;hivernage." in r.text
        assert "qwen2.5-coder:14b" in r.text

    def test_post_langue_wolof_transmise(self, client, fake_agri):
        """La langue choisie doit être transmise au tool."""
        with patch("src.frontend.dashboard._import_managers",
                   return_value={"agri": fake_agri}):
            client.post("/agri-conseil",
                        data={"question": "Naka fey gindi mil ?",
                              "language": "wo"})
        _, kwargs = fake_agri.execute.call_args
        assert kwargs["language"] == "wo"

    def test_question_vide_affiche_erreur(self, client):
        """Une question vide doit afficher un message d'erreur."""
        with patch("src.frontend.dashboard._import_managers",
                   return_value={"agri": MagicMock()}):
            r = client.post("/agri-conseil", data={"question": "   "})
        assert r.status_code == 200
        assert "Veuillez écrire votre question agricole." in r.text

    def test_service_indisponible_affiche_erreur(self, client):
        """Un tool indisponible doit afficher une erreur."""
        with patch("src.frontend.dashboard._import_managers",
                   return_value={"agri": None}):
            r = client.post("/agri-conseil",
                            data={"question": "Quand planter le mil ?"})
        assert r.status_code == 200
        assert "indisponible" in r.text

    def test_echec_generation_affiche_erreur(self, client):
        """Un échec du tool doit afficher l'erreur, pas planter le serveur."""
        fake_tool = MagicMock()
        fake_tool.execute.side_effect = RuntimeError("Ollama indisponible")
        with patch("src.frontend.dashboard._import_managers",
                   return_value={"agri": fake_tool}):
            r = client.post("/agri-conseil",
                            data={"question": "Quand planter le mil ?"})
        assert r.status_code == 200
        assert "Ollama indisponible" in r.text
