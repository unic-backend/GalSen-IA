"""
Tests de l'interface web (VOLET 02 ch. 02, ADR-008).

Ce que ces tests couvrent : la couche de service — les fichiers sont servis, la
racine mène au tableau de bord, la page porte ses points de montage, et la
politique de sécurité du contenu autorise l'interface à charger ses propres
ressources.

Ce qu'ils ne couvrent **pas** : la logique JavaScript. L'ADR-008 assume ce
manque et en fait le signal qui justifiera d'introduire un exécuteur de tests
JS. Le rendu réel a été vérifié dans un navigateur, à la main — ce qui n'est pas
la même chose qu'un test qui reviendra tout seul.

Le test sur la CSP existe pour une raison précise : la politique de l'API
(`default-src 'none'; sandbox`) rendait l'interface muette dans un navigateur,
sans qu'aucun test HTTP ne s'en aperçoive, un client de test n'appliquant pas
les CSP.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.server import app  # noqa: E402
from src.web import STATIC_DIRECTORY, UI_PREFIX  # noqa: E402


@pytest.fixture
def client():
    """Client HTTP sur l'application réelle."""
    with TestClient(app) as instance:
        yield instance


class TestFichiersServis:
    """Vérifie que l'interface est bien servie par l'application."""

    def test_le_tableau_de_bord_repond(self, client):
        """`/ui/` doit servir la page d'accueil de l'interface."""
        reponse = client.get(f"{UI_PREFIX}/")
        assert reponse.status_code == 200
        assert "text/html" in reponse.headers["content-type"]

    def test_la_racine_mene_au_tableau_de_bord(self, client):
        """Une racine en 404 laisserait croire que rien n'écoute."""
        reponse = client.get("/", follow_redirects=False)
        assert reponse.status_code in (307, 308)
        assert reponse.headers["location"] == f"{UI_PREFIX}/"

    @pytest.mark.parametrize(
        "chemin, type_attendu",
        [
            ("/ui/js/api-client.js", "javascript"),
            ("/ui/js/chat.js", "javascript"),
            ("/ui/js/dashboard.js", "javascript"),
            ("/ui/js/studio.js", "javascript"),
            ("/ui/css/chat.css", "css"),
            ("/ui/css/dashboard.css", "css"),
            ("/ui/css/studio.css", "css"),
            ("/ui/studio.html", "html"),
        ],
    )
    def test_les_ressources_sont_servies(self, client, chemin, type_attendu):
        """Chaque ressource doit être servie avec le bon type MIME.

        Un module JavaScript servi en `text/plain` est refusé par le navigateur :
        le type compte autant que le contenu.
        """
        reponse = client.get(chemin)
        assert reponse.status_code == 200
        assert type_attendu in reponse.headers["content-type"]

    def test_ressource_inexistante(self, client):
        """Un fichier absent doit répondre 404, pas la page d'accueil."""
        assert client.get("/ui/js/inexistant.js").status_code == 404


class TestContenuDeLaPage:
    """Vérifie que la page porte ce dont le script a besoin."""

<<<<<<< HEAD
    def test_les_points_de_montage_existent(self, client):
        """La conversation, la saisie et le menu doivent exister, sinon le script écrit dans le vide."""
        page = client.get(f"{UI_PREFIX}/").text
        for identifiant in ('id="conversation"', 'id="saisie"', 'id="menu-domaines"'):
=======
    def test_le_chat_existe_a_ui(self, client):
        """Le chat doit exister à /ui/, avec conversation et composeur."""
        page = client.get(f"{UI_PREFIX}/").text
        for identifiant in ('id="conversation"', 'id="composeur"', 'id="message"'):
>>>>>>> f8b0c60f12a9156a80608b76d3a9bf2266613290
            assert identifiant in page

    def test_le_script_du_chat_est_module(self, client):
        """Le client d'API utilise `import` : sans `type="module"`, rien ne s'exécute."""
        page = client.get(f"{UI_PREFIX}/").text
        assert 'type="module"' in page
        assert "/ui/js/chat.js" in page
<<<<<<< HEAD
=======
        assert 'type="module"' in page
>>>>>>> f8b0c60f12a9156a80608b76d3a9bf2266613290

    def test_page_en_francais(self, client):
        """L'interface s'adresse à des utilisateurs francophones."""
        assert 'lang="fr"' in client.get(f"{UI_PREFIX}/").text

    def test_adaptee_au_telephone(self, client):
        """Sans `viewport`, la page est illisible sur un téléphone."""
        assert "width=device-width" in client.get(f"{UI_PREFIX}/").text

    def test_le_dashboard_a_noscript(self, client):
        """Un navigateur sans JavaScript sur le dashboard doit être orienté."""
        page = client.get(f"{UI_PREFIX}/admin/").text
        assert "<noscript>" in page
        assert "/health" in page

    def test_aucune_cle_dans_la_page(self, client):
        """La clé API est saisie par l'utilisateur : rien ne doit être écrit en dur."""
        page = client.get(f"{UI_PREFIX}/").text
        assert "X-API-Key" not in page.replace('placeholder="X-API-Key"', "")


class TestPolitiqueDeSecurite:
    """Vérifie que la posture de sécurité n'étouffe pas l'interface."""

    def test_l_interface_peut_charger_ses_ressources(self, client):
        """La CSP de l'interface doit autoriser ses propres styles et scripts."""
        politique = client.get(f"{UI_PREFIX}/").headers["content-security-policy"]
        assert "style-src 'self'" in politique
        assert "script-src 'self'" in politique
        assert "connect-src 'self'" in politique

    def test_l_interface_n_est_pas_mise_en_bac_a_sable(self, client):
        """`sandbox` sans valeur interdit toute exécution de script."""
        assert "sandbox" not in client.get(f"{UI_PREFIX}/").headers["content-security-policy"]

    def test_aucune_ressource_tierce_autorisee(self, client):
        """Rien d'externe : ni police distante, ni script tiers, ni `unsafe-inline`."""
        politique = client.get(f"{UI_PREFIX}/").headers["content-security-policy"]
        assert "unsafe-inline" not in politique
        assert "unsafe-eval" not in politique
        assert "https://" not in politique

    def test_l_api_garde_sa_politique_stricte(self, client):
        """Assouplir pour l'interface ne doit rien assouplir pour l'API."""
        politique = client.get("/health").headers["content-security-policy"]
        assert "sandbox" in politique
        assert "script-src" not in politique

    def test_l_interface_reste_non_encadrable(self, client):
        """Le tableau de bord ne doit pas pouvoir être placé dans une iframe."""
        entetes = client.get(f"{UI_PREFIX}/").headers
        assert entetes["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in entetes["content-security-policy"]


class TestSourcesLivrees:
    """Vérifie l'arborescence livrée, indépendamment du serveur."""

    def test_les_fichiers_existent(self):
        """Les fichiers annoncés par l'ADR-008 doivent être présents."""
        for relatif in (
            "index.html", "js/api-client.js", "js/chat.js", "js/dashboard.js",
            "css/chat.css", "css/dashboard.css", "studio.html", "js/studio.js",
            "css/studio.css",
        ):
            assert os.path.isfile(os.path.join(STATIC_DIRECTORY, relatif)), relatif

    @pytest.mark.parametrize("page", ["index.html", "studio.html"])
    def test_aucune_dependance_distante(self, page):
        """Rien n'est chargé depuis un CDN : le premier affichage ne doit pas
        dépendre d'une connexion sortante.

        La vérification porte sur les attributs qui déclenchent un
        téléchargement. L'espace de noms SVG (`xmlns`) est une URL qui n'est
        jamais requêtée : l'interdire reviendrait à confondre un identifiant
        avec une ressource.

        Elle porte sur **chaque** page livrée : une garantie vérifiée sur une
        seule page cesse d'en être une le jour où une deuxième est ajoutée.
        """
        import re

        with open(os.path.join(STATIC_DIRECTORY, page), encoding="utf-8") as fichier:
            contenu = fichier.read()

        telechargements = re.findall(r'(?:src|href)\s*=\s*"(https?://[^"]+)"', contenu)
        assert telechargements == []

    @pytest.mark.parametrize("script", ["js/dashboard.js", "js/studio.js"])
    def test_seul_le_client_d_api_appelle_le_reseau(self, script):
        """Aucune page ne doit appeler `fetch` directement (ADR-008)."""
        with open(os.path.join(STATIC_DIRECTORY, script), encoding="utf-8") as fichier:
            source = fichier.read()
        assert "fetch(" not in source

    @pytest.mark.parametrize("script", ["js/dashboard.js", "js/studio.js"])
    def test_le_rendu_n_interprete_pas_de_balisage(self, script):
        """Une donnée d'API insérée en HTML ouvrirait une injection de balisage.

        C'est l'**écriture** dans `innerHTML` qui est interdite, pas le mot :
        le fichier l'évoque en commentaire pour expliquer pourquoi il utilise
        `textContent`.
        """
        import re

        with open(os.path.join(STATIC_DIRECTORY, script), encoding="utf-8") as fichier:
            source = fichier.read()

        assert re.search(r"\.innerHTML\s*=", source) is None
        assert re.search(r"insertAdjacentHTML", source) is None
        assert "textContent" in source
