"""
Tests for the creative API surface (C17 phase 17.1, directive V4 §70, §72).

The property under test is a refusal. §70 proposes fifteen prefixes; four are
mounted, because four are the ones a real function serves. Mounting the other
eleven would give an API that looks complete and answers empty objects — worse
than a small API, because callers build on it.

So the tests check two things that are easy to lose later: that no route was
added without something behind it, and that the eleven absent prefixes are
*documented* rather than silently missing. A caller must be able to read what
the platform does not do yet, not have to infer it.
"""

import os

import pytest
from fastapi.testclient import TestClient

from src.creative.api_surface import (
    DEJA_SERVI_AILLEURS,
    PAS_ENCORE,
    PREFIXES_DIRECTIVE,
    SERVI,
    readiness,
    surface_map,
)

CLE = "cle-de-test-creative"
ENTETE = {"X-API-Key": CLE}


@pytest.fixture
def client(monkeypatch):
    """Client API avec une clé d'administration, sans recharger de module."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin:testeur")
    import src.api.server as serveur
    serveur.rbac_manager.reload()
    serveur.set_valid_api_key_digests(serveur.rbac_manager.active_key_digests())
    try:
        with TestClient(serveur.app) as client:
            yield client
    finally:
        monkeypatch.delenv("GALSEN_API_KEYS", raising=False)
        serveur.rbac_manager.reload()
        serveur.set_valid_api_key_digests(serveur.rbac_manager.active_key_digests())


class TestSurface:
    """Ce qui n'est pas monté est dit, pas tu."""

    def test_les_quinze_prefixes_de_la_directive_sont_tous_traites(self):
        traites = {entree["prefix"] for entree in surface_map()}
        assert traites == set(PREFIXES_DIRECTIVE), (
            "Un préfixe proposé par la directive et absent de la carte serait "
            "un trou que personne ne verrait."
        )

    def test_un_prefixe_non_servi_dit_ce_qui_manque(self):
        for entree in surface_map():
            if entree["state"] == PAS_ENCORE:
                assert entree["missing"], (
                    f"{entree['prefix']} est absent sans dire pourquoi."
                )

    def test_un_prefixe_deja_servi_nomme_la_route_existante(self):
        """Deux chemins pour un même geste dérivent."""
        for entree in surface_map():
            if entree["state"] == DEJA_SERVI_AILLEURS:
                assert entree["route"]

    def test_les_references_ne_sont_pas_exposees_sans_persistance(self):
        """Téléverser un visage dans un magasin qui disparaît au redémarrage."""
        par_prefixe = {e["prefix"]: e for e in surface_map()}
        assert par_prefixe["/references"]["state"] == PAS_ENCORE
        assert "redémarrage" in par_prefixe["/references"]["missing"]

    def test_la_verification_n_est_pas_exposee_sans_mesure(self):
        """Une route rendrait un score qu'aucune mesure ne soutient."""
        par_prefixe = {e["prefix"]: e for e in surface_map()}
        assert par_prefixe["/verification"]["state"] == PAS_ENCORE

    def test_aucune_route_ne_pretend_generer(self):
        for entree in surface_map():
            assert "generate" not in (entree.get("route") or "")


class TestAptitude:
    """L'état est calculé, jamais écrit."""

    def test_l_etat_suit_les_fournisseurs_et_le_materiel(self):
        etat = readiness()
        assert etat["providers_declared"] > 0
        if not etat["resources"]["gpu_available"]:
            assert "GENERATION BLOCKED" in etat["state"]

    def test_aucune_architecture_n_est_recommandee(self):
        assert readiness()["recommended_pipeline"] is None

    def test_chaque_architecture_dit_ou_elle_bute(self):
        for plan in readiness()["pipelines"].values():
            if plan["state"] == "BLOCKED":
                assert plan["first_block"]

    def test_orchestration_prete_n_est_pas_plateforme_qui_genere(self):
        assert "n'est pas une plateforme qui génère" in readiness()["note"]


class TestRoutes:
    """Quatre routes, chacune servie par du code réel."""

    CHEMINS = ("/creative/readiness", "/creative/surface",
               "/creative/languages", "/creative/pipelines")

    @pytest.mark.parametrize("chemin", CHEMINS)
    def test_la_cle_est_exigee(self, client, chemin):
        assert client.get(chemin).status_code == 401

    @pytest.mark.parametrize("chemin", CHEMINS)
    def test_la_route_repond_du_contenu(self, client, chemin):
        reponse = client.get(chemin, headers=ENTETE)
        assert reponse.status_code == 200
        assert reponse.json(), f"{chemin} répond un objet vide."

    def test_les_langues_rendent_les_cinq_capacites(self, client):
        matrice = client.get("/creative/languages",
                             headers=ENTETE).json()["matrix"]
        assert matrice["speakable"] == []
        assert matrice["declared"] > 10

    def test_les_architectures_ne_designent_pas_de_gagnante(self, client):
        charge = client.get("/creative/pipelines", headers=ENTETE).json()
        assert charge["recommended"] is None

    def test_seules_quatre_routes_creatives_existent(self):
        """§72 : un flux qui marche vaut mieux que cent abstractions vides."""
        from src.api.server import app
        creatives = {route.path for route in app.routes
                     if getattr(route, "path", "").startswith("/creative")}
        assert creatives == set(self.CHEMINS)

    def test_le_nombre_de_prefixes_servis_correspond_aux_routes(self):
        servis = [e for e in surface_map() if e["state"] == SERVI]
        assert len(servis) == len(self.CHEMINS)


def test_le_module_ne_sonde_rien_a_l_import():
    """Sonder le GPU à l'import ferait payer la mesure à chaque démarrage."""
    chemin = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))),
        "src", "creative", "api_surface.py")
    with open(chemin, encoding="utf-8") as fichier:
        source = fichier.read()
    entete = source.split("def readiness")[0]
    assert "from .resources import" not in entete
    assert "from .research import" not in entete
