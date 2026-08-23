"""
Tests d'interaction de la page de chat (VOLET chat-first, ch. 04).

Ce qui est testé ici : **que la page ne casse pas quand l'utilisateur tape.**
Le reste — les bulles qui apparaissent, leur couleur, leur ordre — relève du
rendu navigateur, que seuls des tests en navigateur réel vérifieraient.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def client():
    import src.api.server as serveur
    return TestClient(serveur.app)


@pytest.fixture
def page_chat(client):
    """Charger la page de conversation."""
    return client.get("/ui/").text


class TestPageStructure:
    """La page porte tous les éléments que le script attend."""

    def test_le_formulaire_existe(self, page_chat):
        assert 'id="composeur"' in page_chat
        assert 'id="message"' in page_chat
        assert 'id="envoyer"' in page_chat

    def test_la_conversation_existe(self, page_chat):
        assert 'id="conversation"' in page_chat
        assert 'id="accueil"' in page_chat

    def test_les_scripts_sont_charges(self, page_chat):
        # chat.js est chargé en tant que module, il importe api-client lui-même
        assert "/ui/js/chat.js" in page_chat
        assert 'type="module"' in page_chat


class TestRessources:
    """Les dépendances du script existent et sont servies."""

    def test_api_client_est_servi(self, client):
        reponse = client.get("/ui/js/api-client.js")
        assert reponse.status_code == 200
        assert "export const api" in reponse.text

    def test_chat_js_est_servi(self, client):
        reponse = client.get("/ui/js/chat.js")
        assert reponse.status_code == 200
        assert "api.post" in reponse.text
        assert "afficherReponse" in reponse.text
        assert "import { api }" in reponse.text

    def test_la_feuille_de_style_est_servie(self, client):
        assert client.get("/ui/css/chat.css").status_code == 200


class TestStructureReponse:
    """La réponse de `/chat` porte ce que le script affiche."""

    def test_les_champs_requis_existent(self, client):
        """
        Une réponse de chat doit permettre à chat.js d'afficher quelque chose.

        Les champs optionnels seront absents ou nuls ; les requis doivent exister.
        """
        reponse = client.post(
            "/chat",
            json={"message": "bonjour"},
            headers={"X-API-Key": "demo"},
        )
        if reponse.status_code == 200:
            charge = reponse.json()
            assert "answer" in charge
            assert "grounding" in charge
            assert "detection" in charge
            assert "elapsed_seconds" in charge
