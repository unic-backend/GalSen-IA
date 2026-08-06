"""
Tests de la posture de sécurité HTTP (VOLET 02 ch. 08, phase 8.2).

Trois réglages sont vérifiés ici, chacun correspondant à un trou constaté avant
correction : aucune réponse ne portait d'en-tête de sécurité, la politique
d'origines croisées acceptait n'importe quel site **avec les identifiants du
visiteur**, et la documentation interactive était publique quel que soit le
déploiement.

Les trois dépendent de l'environnement au moment de la construction de
l'application : les tests qui changent la configuration reconstruisent donc
l'application plutôt que de modifier celle déjà en place.
"""

import importlib
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.security_headers import (  # noqa: E402
    SecurityHeadersMiddleware,
    allowed_origins,
    docs_enabled,
)


def _application(origines=None):
    """Construit une application minimale portant la même posture que l'API."""
    application = FastAPI()
    application.add_middleware(SecurityHeadersMiddleware)
    if origines is not None:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origines,
            allow_credentials=bool(origines),
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["X-API-Key", "Content-Type"],
        )

    @application.get("/essai")
    async def essai():
        return {"ok": True}

    return application


class TestEnTetesDeSecurite:
    """Vérifie que chaque réponse porte les en-têtes attendus."""

    @pytest.fixture
    def client(self):
        """Client sur une application portant l'intergiciel de sécurité."""
        return TestClient(_application())

    @pytest.mark.parametrize(
        "entete, valeur",
        [
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "no-referrer"),
            ("Cache-Control", "no-store"),
        ],
    )
    def test_entete_present(self, client, entete, valeur):
        """Les en-têtes de base doivent être posés sur toute réponse."""
        assert client.get("/essai").headers[entete] == valeur

    def test_politique_de_contenu_verrouillee(self, client):
        """Une API JSON n'a rien à charger ni à laisser encadrer."""
        politique = client.get("/essai").headers["Content-Security-Policy"]
        assert "default-src 'none'" in politique
        assert "frame-ancestors 'none'" in politique

    def test_pas_de_hsts_en_clair(self, client):
        """En HTTP, l'en-tête HSTS ne protège rien et casserait l'accès local."""
        assert "Strict-Transport-Security" not in client.get("/essai").headers

    def test_hsts_derriere_un_repartiteur_https(self, client):
        """Derrière un répartiteur, `X-Forwarded-Proto` porte le vrai schéma."""
        reponse = client.get("/essai", headers={"X-Forwarded-Proto": "https"})
        assert "max-age=63072000" in reponse.headers["Strict-Transport-Security"]

    def test_les_erreurs_portent_aussi_les_entetes(self, client):
        """Une réponse d'erreur ne doit pas échapper à la posture."""
        assert client.get("/inexistant").headers["X-Content-Type-Options"] == "nosniff"


class TestOriginesCroisees:
    """Vérifie la politique CORS, dont le réglage précédent était dangereux."""

    def test_aucune_origine_par_defaut(self, monkeypatch):
        """Sans déclaration, aucune origine croisée n'est autorisée."""
        monkeypatch.delenv("GALSEN_CORS_ORIGINS", raising=False)
        assert allowed_origins() == []

    def test_origines_declarees(self, monkeypatch):
        """Les origines déclarées sont lues et nettoyées."""
        monkeypatch.setenv(
            "GALSEN_CORS_ORIGINS", "https://galsen.sn, https://app.galsen.sn "
        )
        assert allowed_origins() == ["https://galsen.sn", "https://app.galsen.sn"]

    def test_une_origine_quelconque_est_refusee(self):
        """Un site tiers ne doit recevoir aucune autorisation d'appel."""
        client = TestClient(_application(origines=["https://galsen.sn"]))
        reponse = client.get(
            "/essai", headers={"Origin": "https://site-malveillant.example"}
        )
        assert "access-control-allow-origin" not in reponse.headers

    def test_l_origine_declaree_est_acceptee(self):
        """Une origine légitime reste autorisée, avec les identifiants."""
        client = TestClient(_application(origines=["https://galsen.sn"]))
        reponse = client.get("/essai", headers={"Origin": "https://galsen.sn"})
        assert reponse.headers["access-control-allow-origin"] == "https://galsen.sn"
        assert reponse.headers["access-control-allow-credentials"] == "true"

    def test_sans_origine_declaree_rien_n_est_reflete(self):
        """Liste vide : aucune origine n'obtient d'autorisation, pas même la sienne."""
        client = TestClient(_application(origines=[]))
        reponse = client.get("/essai", headers={"Origin": "https://galsen.sn"})
        assert "access-control-allow-origin" not in reponse.headers


class TestDocumentationInteractive:
    """Vérifie la règle : la documentation n'est publique que si l'API l'est."""

    def test_ouverte_sans_cle_configuree(self, monkeypatch):
        """Sans clé, la plateforme est ouverte : cacher son schéma ne protège rien."""
        monkeypatch.delenv("GALSEN_API_DOCS", raising=False)
        monkeypatch.delenv("GALSEN_API_KEYS", raising=False)
        assert docs_enabled() is True

    def test_fermee_des_qu_une_cle_existe(self, monkeypatch):
        """Une clé configurée signale un déploiement réel : le schéma se ferme."""
        monkeypatch.delenv("GALSEN_API_DOCS", raising=False)
        monkeypatch.setenv("GALSEN_API_KEYS", "une-cle:admin")
        assert docs_enabled() is False

    @pytest.mark.parametrize("valeur", ["enabled", "true", "1", "yes"])
    def test_activation_explicite(self, monkeypatch, valeur):
        """Le choix explicite doit primer sur la règle automatique."""
        monkeypatch.setenv("GALSEN_API_KEYS", "une-cle:admin")
        monkeypatch.setenv("GALSEN_API_DOCS", valeur)
        assert docs_enabled() is True

    @pytest.mark.parametrize("valeur", ["disabled", "false", "0", "no"])
    def test_desactivation_explicite(self, monkeypatch, valeur):
        """La désactivation explicite doit fonctionner même sans clé."""
        monkeypatch.delenv("GALSEN_API_KEYS", raising=False)
        monkeypatch.setenv("GALSEN_API_DOCS", valeur)
        assert docs_enabled() is False


class TestPostureDeLApiReelle:
    """Vérifie l'application réelle, reconstruite avec des clés configurées."""

    @pytest.fixture
    def api_avec_cles(self, monkeypatch):
        """Recharge `src.api.server` avec une clé configurée."""
        monkeypatch.setenv("GALSEN_API_KEYS", "cle-test:admin")
        monkeypatch.delenv("GALSEN_API_DOCS", raising=False)
        monkeypatch.delenv("GALSEN_CORS_ORIGINS", raising=False)
        import src.api.server as serveur

        rechargé = importlib.reload(serveur)
        yield rechargé
        # Rendre au processus le module tel qu'il était, sinon les autres
        # fichiers de tests hériteraient de cette configuration.
        monkeypatch.undo()
        importlib.reload(serveur)

    def test_documentation_fermee_en_presence_de_cles(self, api_avec_cles):
        """`/docs` et `/openapi.json` ne doivent plus être servis."""
        with TestClient(api_avec_cles.app) as client:
            assert client.get("/docs").status_code == 404
            assert client.get("/openapi.json").status_code == 404

    def test_entetes_sur_la_route_de_sante(self, api_avec_cles):
        """La route publique doit elle aussi porter la posture."""
        with TestClient(api_avec_cles.app) as client:
            entetes = client.get("/health").headers
        assert entetes["X-Content-Type-Options"] == "nosniff"
        assert entetes["Cache-Control"] == "no-store"

    def test_aucune_origine_croisee_autorisee(self, api_avec_cles):
        """Sans déclaration, l'API ne s'ouvre à aucun site tiers."""
        with TestClient(api_avec_cles.app) as client:
            reponse = client.get(
                "/health", headers={"Origin": "https://site-malveillant.example"}
            )
        assert "access-control-allow-origin" not in reponse.headers
