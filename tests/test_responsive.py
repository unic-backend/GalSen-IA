"""
Tests du responsive design (VOLET chat-first, ch. 07).

Mobile-first : la page fonctionne d'abord sur petit écran, puis s'améliore
sur grand écran. Pas de scrolling horizontal.
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


def _lire(chemin: str) -> str:
    with open(chemin, encoding="utf-8") as f:
        return f.read()


class TestMobileFirst:
    """La page annonce son support du responsive."""

    def test_viewport_est_declare(self, client):
        page = client.get("/ui/").text
        assert 'viewport' in page
        assert 'width=device-width' in page
        assert 'initial-scale=1' in page

    def test_color_scheme_est_support(self, client):
        """La page s'adapte au thème clair ou sombre du système."""
        page = client.get("/ui/").text
        assert 'color-scheme' in page

    def test_100dvh_au_lieu_de_100vh(self):
        """100dvh sur mobile, pas 100vh, pour que le clavier virtuel ne pousse pas l'UI."""
        css = _lire("src/web/static/css/chat.css")
        assert '100dvh' in css, "100dvh manquant (mobile avec clavier virtuel)"


class TestTouchability:
    """Les touches sont assez grandes pour être cliquées confortablement."""

    def test_boutons_au_moins_48px(self):
        """3rem (48px) est le minimum pour une touche confortable en mobile."""
        css = _lire("src/web/static/css/chat.css")
        # Vérifier qu'on a des boutons de taille 3rem
        assert '3rem' in css, "Pas de bouton à 3rem trouvé"

    def test_pas_de_scrolling_horizontal(self):
        """La page ne défile jamais horizontalement."""
        css = _lire("src/web/static/css/chat.css")
        # Vérifier qu'on utilise min() et pas de widths fixes
        assert 'min(' in css, "Widths flexibles (min) manquantes"
        # Vérifier que les textes peuvent se casser
        assert 'overflow-wrap: anywhere' in css or 'word-break' in css


class TestLightweightContent:
    """La page charge vite même sur connexion lente."""

    def test_pas_de_police_distante(self, client):
        """Aucune police n'est téléchargée d'un serveur externe."""
        page = client.get("/ui/").text
        css = client.get("/ui/css/chat.css").text
        assert 'https://' not in page, "Ressource HTTPS dans la page"
        assert 'https://' not in css, "Police/ressource HTTPS dans le CSS"

    def test_css_raisonnable(self, client):
        """chat.css < 15 Ko (chat.html + tous les CSS = <50 Ko)."""
        css_size = len(client.get("/ui/css/chat.css").content)
        html_size = len(client.get("/ui/").content)
        total = css_size + html_size
        assert css_size < 15000, f"chat.css trop gros : {css_size} octets"
        assert total < 50000, f"Page + CSS trop gros : {total} octets"


class TestAccessible:
    """L'accessibilité fonctionne sur mobile et desktop."""

    def test_aucun_element_invisible_au_clavier(self, client):
        """Les boutons et champs sont accessibles au clavier."""
        page = client.get("/ui/").text
        # Vérifier qu'on n'a pas caché d'éléments interactifs
        assert 'aria-label' in page, "Quelques boutons n'ont pas de label"


class TestDarkMode:
    """Le mode sombre fonctionne."""

    def test_couleurs_dark_mode_declarees(self):
        css = _lire("src/web/static/css/chat.css")
        assert '@media (prefers-color-scheme: dark)' in css
        assert 'color:' in css.split('@media (prefers-color-scheme: dark)')[1]
