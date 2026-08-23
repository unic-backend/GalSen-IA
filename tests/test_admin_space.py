"""
Tests de l'espace administrateur (VOLET chat-first, ch. 06).

Le tableau de bord passe de /ui/ à /ui/admin/. Le chat prend /ui/.
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


class TestChat:
    """Le chat est à /ui/ maintenant."""

    def test_ui_root_est_le_chat(self, client):
        page = client.get("/ui/").text
        assert 'id="conversation"' in page
        assert 'id="composeur"' in page
        assert 'Pose ta question' in page

    def test_le_chat_charge_son_script(self, client):
        page = client.get("/ui/").text
        assert '/ui/js/chat.js' in page


class TestAdmin:
    """Le tableau de bord est à /ui/admin/."""

    def test_admin_est_le_tableau_de_bord(self, client):
        page = client.get("/ui/admin/").text
        assert 'Tableau de bord' in page
        assert '/admin/' not in page or '../css/dashboard.css' in page

    def test_les_chemins_dans_admin_sont_relatifs(self, client):
        page = client.get("/ui/admin/").text
        assert '../css/dashboard.css' in page
        assert '../js/dashboard.js' in page

    def test_admin_charge_son_script(self, client):
        page = client.get("/ui/admin/").text
        assert '../js/dashboard.js' in page


class TestAncienChemin:
    """L'ancien chemin du tableau de bord n'existe plus à /ui/index.html."""

    def test_ui_avec_index_html_specifique_est_le_chat(self, client):
        # /ui/index.html doit être le chat maintenant
        page = client.get("/ui/index.html").text
        assert 'id="conversation"' in page
        assert 'Tableau de bord' not in page
