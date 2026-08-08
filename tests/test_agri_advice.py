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
from src.api.rate_limiter import set_valid_api_key_digests
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
def headers(monkeypatch):
    """En-têtes avec la clé API valide, garantie active pendant le test.

    Poser la variable d'environnement à l'import ne suffit pas : le
    gestionnaire RBAC est construit au premier import de `src.api.server`, qui
    peut avoir eu lieu dans un autre fichier de tests avec d'autres clés. On
    recharge donc explicitement, et on rend son état d'origine ensuite — sans
    quoi ce fichier casserait les suites exécutées après lui.
    """
    ancien_mapping = dict(server.rbac_manager._key_role_map)
    anciennes_revocations = set(server.rbac_manager._revoked_digests)

    monkeypatch.setenv("GALSEN_API_KEYS", f"{VALID_KEY}:user")
    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())

    yield {"X-API-Key": VALID_KEY}

    server.rbac_manager._key_role_map = ancien_mapping
    server.rbac_manager._revoked_digests = anciennes_revocations
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())


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
# Aides
# ---------------------------------------------------------------------------


def _outil_avec(gestionnaire):
    """Retourne un outil branché sur un gestionnaire de modèles donné.

    L'outil résout son gestionnaire par le registre partagé de la plateforme :
    on injecte donc directement, plutôt que de remplacer une classe que le
    module n'importe pas.
    """
    tool = AgriAdviceTool()
    tool._model_manager = gestionnaire
    return tool


def _reponse(status="ready", text="Conseil", detail=None):
    """Construit une réponse de génération telle que le moteur en produit."""
    reponse = MagicMock()
    reponse.to_dict.return_value = {"status": status, "text": text, "detail": detail}
    return reponse


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
        faux_gestionnaire = MagicMock()
        faux_modele = MagicMock()
        faux_modele.name = "modele-test"
        faux_gestionnaire.get_model.return_value = faux_modele
        faux_gestionnaire.generate.return_value = _reponse(text="  Un bon conseil.  ")

        tool = _outil_avec(faux_gestionnaire)
        result = tool.execute("get_advice", "Quand planter le mil ?",
                              model_id="modele-test")

        assert result["status"] == "ready"
        assert result["answer"] == "Un bon conseil."
        assert result["language"] == "fr"
        assert result["model_used"] == "modele-test"
        faux_gestionnaire.get_model.assert_called_once_with("modele-test")
        faux_gestionnaire.generate.assert_called_once()

    def test_selection_automatique_du_modele(self):
        """Sans modèle imposé, la sélection par tâche doit être utilisée."""
        faux_gestionnaire = MagicMock()
        faux_modele = MagicMock()
        faux_modele.name = "modele-choisi"
        faux_gestionnaire.select_model_for_task.return_value = faux_modele
        faux_gestionnaire.generate.return_value = _reponse(text="Conseil")

        tool = _outil_avec(faux_gestionnaire)
        result = tool.execute("get_advice", "Question ?")

        assert result["model_used"] == "modele-choisi"
        exigences = faux_gestionnaire.select_model_for_task.call_args[0][0]
        assert exigences["domain"] == "agriculture"
        assert exigences["region"] == "Senegal"

    def test_modele_inconnu_signale_une_indisponibilite(self):
        """Un modèle inconnu est une indisponibilité, pas une exception.

        L'outil est appelé par des agents : une exception les arrêterait, là où
        un statut leur laisse la possibilité de se rabattre ailleurs
        (`docs/architecture/overview.md`). C'est l'endpoint HTTP qui traduit ce
        statut en 503.
        """
        faux_gestionnaire = MagicMock()
        faux_gestionnaire.get_model.return_value = None
        faux_gestionnaire._model_registry.to_model_item.return_value = None
        faux_gestionnaire.unavailability_reason.return_value = "Modèle inconnu"

        tool = _outil_avec(faux_gestionnaire)
        result = tool.execute("get_advice", "Question ?", model_id="nope")

        assert result["status"] == "unavailable"
        assert result["answer"] == ""
        assert result["model_used"] is None
        assert "Modèle inconnu" in result["detail"]

    def test_aucun_modele_disponible_signale_la_raison(self):
        """Sans modèle disponible, la raison doit être rapportée telle quelle."""
        faux_gestionnaire = MagicMock()
        faux_gestionnaire.select_model_for_task.return_value = None
        faux_gestionnaire.unavailability_reason.return_value = "Aucun fournisseur"

        tool = _outil_avec(faux_gestionnaire)
        result = tool.execute("get_advice", "Question ?")

        assert result["status"] == "unavailable"
        assert result["detail"] == "Aucun fournisseur"
        # Jamais de texte inventé quand personne n'a généré.
        assert result["answer"] == ""

    def test_echec_generation_remonte_le_statut_du_fournisseur(self):
        """Un échec de génération doit porter le statut et le détail du moteur."""
        faux_gestionnaire = MagicMock()
        faux_gestionnaire.select_model_for_task.return_value = MagicMock()
        faux_gestionnaire.generate.return_value = _reponse(
            status="error", text="", detail="Erreur du fournisseur"
        )

        tool = _outil_avec(faux_gestionnaire)
        result = tool.execute("get_advice", "Question ?")

        assert result["status"] == "error"
        assert result["answer"] == ""
        assert result["detail"] == "Erreur du fournisseur"

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

    def test_indisponibilite_retourne_503(self, client, headers):
        """Un statut d'indisponibilité doit devenir un 503, jamais un 200 vide.

        L'outil ne lève pas quand aucun modèle ne répond : il retourne un
        statut. Sans traduction ici, l'API répondrait 200 avec un conseil vide
        — une indisponibilité déguisée en réponse.
        """
        faux_outil = MagicMock()
        faux_outil.execute.return_value = {
            "status": "unavailable",
            "answer": "",
            "language": "fr",
            "model_used": None,
            "detail": "Aucun fournisseur configuré",
        }
        with patch.object(server, "AgriAdviceTool", return_value=faux_outil):
            r = client.post("/agri/advice", json={"question": "Quand planter ?"},
                            headers=headers)
        assert r.status_code == 503
        assert r.json()["detail"] == "Aucun fournisseur configuré"

    def test_erreur_tool_retourne_503(self, client, headers):
        """Une erreur interne du tool doit retourner 503."""
        fake_tool = MagicMock()
        fake_tool.execute.side_effect = RuntimeError("Ollama indisponible")
        with patch.object(server, "AgriAdviceTool", return_value=fake_tool):
            r = client.post("/agri/advice", json={"question": "Quand planter ?"},
                            headers=headers)
        assert r.status_code == 503
        assert "indisponible" in r.json()["detail"]
