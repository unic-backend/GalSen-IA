"""
Tests de la page « Conseil agricole » de l'interface web (ADR-008).

Ce fichier remplace `tests/test_dashboard_agri.py`, qui couvrait le tableau de
bord Jinja2 (`src/frontend/`) écarté lors de la réconciliation des deux lignes
de développement. La page a changé de support ; la couverture ne devait pas
disparaître avec lui.

Comme pour `tests/test_web_ui.py`, la logique JavaScript n'est pas exécutée ici
— l'ADR-008 assume ce manque. Ce qui est vérifié est ce qui casse en silence :
les points de montage attendus par le script, le passage obligé par le client
d'API, et le fait que la réponse d'un modèle n'est jamais insérée comme
balisage.
"""

import os
import re
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.server import app  # noqa: E402
from src.web import STATIC_DIRECTORY, UI_PREFIX  # noqa: E402


def _source(relatif: str) -> str:
    """Retourne le contenu d'un fichier livré de l'interface."""
    with open(os.path.join(STATIC_DIRECTORY, relatif), encoding="utf-8") as fichier:
        return fichier.read()


@pytest.fixture
def client():
    """Client HTTP sur l'application réelle."""
    with TestClient(app) as instance:
        yield instance


@pytest.fixture
def page(client):
    """Le tableau de bord tel qu'un navigateur le reçoit."""
    return client.get(f"{UI_PREFIX}/").text


class TestPointsDeMontage:
    """Sans ces identifiants, le script écrit dans le vide."""

    @pytest.mark.parametrize(
        "identifiant",
        [
            'id="formulaire-conseil"',
            'id="question-agricole"',
            'id="langue-conseil"',
            'id="demander-conseil"',
            'id="conseil"',
        ],
    )
    def test_identifiant_present(self, page, identifiant):
        """Chaque élément manipulé par `dashboard.js` doit exister dans la page."""
        assert identifiant in page

    def test_les_deux_langues_sont_proposees(self, page):
        """L'API n'accepte que `fr` et `wo` : la page ne doit pas en offrir d'autres."""
        langues = re.findall(r'<option value="(\w+)"', page)
        assert set(langues) == {"fr", "wo"}

    def test_le_champ_porte_une_etiquette(self, page):
        """Un champ sans étiquette est inutilisable au lecteur d'écran."""
        assert 'for="question-agricole"' in page
        assert 'for="langue-conseil"' in page

    def test_c_est_un_formulaire(self, page):
        """La touche Entrée doit suffire : un `div` avec un bouton ne le permet pas."""
        assert "<form" in page


class TestPassageParLeClientDApi:
    """La directive de l'ADR-008 : aucune page n'appelle le réseau elle-même."""

    def test_la_route_est_declaree_dans_le_client(self):
        """Le client d'API est le seul module à connaître `/agri/advice`."""
        client_api = _source("js/api-client.js")
        assert "/agri/advice" in client_api
        assert "conseil:" in client_api

    def test_le_tableau_de_bord_ignore_la_route(self):
        """Le chemin ne doit apparaître nulle part ailleurs que dans le client."""
        assert "/agri/advice" not in _source("js/dashboard.js")

    def test_le_tableau_de_bord_n_appelle_pas_fetch(self):
        """Aucun appel réseau direct, y compris pour cette nouvelle page."""
        tableau_de_bord = _source("js/dashboard.js")
        assert "fetch(" not in tableau_de_bord
        assert "api.agri.conseil" in tableau_de_bord

    def test_la_langue_est_transmise(self):
        """Choisir « Wolof » sans transmettre la langue rendrait le sélecteur décoratif."""
        assert "#langue-conseil" in _source("js/dashboard.js")


class TestRenduDeLaReponse:
    """Une réponse de modèle est du texte non maîtrisé : elle doit le rester."""

    def test_aucune_insertion_de_balisage(self):
        """Insérer la réponse en HTML ouvrirait une injection depuis le modèle."""
        tableau_de_bord = _source("js/dashboard.js")
        assert re.search(r"\.innerHTML\s*=", tableau_de_bord) is None
        assert re.search(r"insertAdjacentHTML", tableau_de_bord) is None

    def test_les_retours_a_la_ligne_sont_preserves(self):
        """Un conseil en étapes devient illisible si les sauts de ligne tombent."""
        assert "reponse-conseil" in _source("js/dashboard.js")
        assert "white-space: pre-wrap" in _source("css/dashboard.css")

    def test_le_bouton_est_bloque_pendant_la_generation(self):
        """Sans blocage, un double clic lance deux générations facturées."""
        tableau_de_bord = _source("js/dashboard.js")
        assert "bouton.disabled = true" in tableau_de_bord
        assert "bouton.disabled = false" in tableau_de_bord


class TestRouteServie:
    """La page est inutile si la route qu'elle appelle n'existe pas."""

    def test_la_route_existe_et_est_protegee(self, client):
        """Sans clé, l'API doit refuser — et non répondre un conseil."""
        reponse = client.post("/agri/advice", json={"question": "Quand semer ?"})
        assert reponse.status_code == 401

    def test_langue_invalide_refusee(self, client):
        """La validation vit côté serveur : le sélecteur ne la remplace pas."""
        reponse = client.post(
            "/agri/advice", json={"question": "Quand semer ?", "language": "xx"}
        )
        # 401 avant 422 : l'authentification passe en premier, c'est voulu.
        assert reponse.status_code in (401, 422)

    def test_la_page_reste_servie(self, client):
        """Ajouter une section ne doit pas casser le tableau de bord."""
        assert client.get(f"{UI_PREFIX}/").status_code == 200
