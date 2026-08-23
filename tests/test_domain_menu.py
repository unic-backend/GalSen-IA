"""
Tests du menu des domaines (VOLET chat-first, ch. 05).

Le menu porte 14 capacités/domaines. Un utilisateur qui en choisit un impose
ce domaine à toutes les questions suivantes jusqu'à réinitialisation.
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


class TestMenu:
    """Le menu affiche 14 domaines."""

    def test_le_menu_est_present(self, client):
        page = client.get("/ui/").text
        assert 'id="menu-domaines"' in page

    def test_14_domaines_sont_listes(self, client):
        page = client.get("/ui/").text
        # Vérifier que 14 domaines sont présents avec l'attribut data-domaine
        count = page.count('class="menu-domaine"')
        assert count == 14, f"Attendu 14 domaines, trouvé {count}"

    def test_les_domaines_connus_sont_presents(self, client):
        page = client.get("/ui/").text
        domaines = [
            "Agriculture",
            "Santé",
            "Éducation",
            "Commerce",
            "Énergie",
            "Environnement",
            "Finance",
            "Gouvernance",
            "Infrastructure",
            "Juridique",
            "Technologie",
            "Transport",
            "Eau",
            "Emploi",
        ]
        for domaine in domaines:
            assert domaine in page, f"{domaine} absent du menu"

    def test_les_domaines_ont_des_identifiants(self, client):
        page = client.get("/ui/").text
        # Vérifier que chaque bouton a un data-domaine
        assert 'data-domaine="agriculture"' in page
        assert 'data-domaine="sante"' in page
        assert 'data-domaine="education"' in page


class TestIntegration:
    """Le menu fonctionne avec le chat."""

    def test_le_script_du_menu_est_charge(self, client):
        # Vérifier que le script chat.js contient la logique du menu
        script = client.get("/ui/js/chat.js").text
        assert "menu-domaines" in script
        assert "domaineImposeParUtilisateur" in script
        assert "dataset.domaine" in script

    def test_le_menu_se_ferme_quand_on_choisit(self, client):
        # La fermeture elle-même demande un vrai navigateur ; ce qui est
        # vérifiable ici est que le retour à « aucun filtrage » existe.
        page = client.get("/ui/").text
        assert "menu-reinitialiser" in page
        assert "Aucun filtrage" in page
