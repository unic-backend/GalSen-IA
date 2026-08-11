"""
Tests de la détection de menaces (VOLET 11, chapitre 05).

La plateforme comptait les échecs d'authentification sans rien en conclure :
douze tentatives avec douze clés différentes — un bourrage d'identifiants
manifeste — donnaient un compteur à 12 et aucun signal. Compter n'est pas
détecter.

Le test qui compte le plus ici est celui du contournement : la première version
effaçait les échecs d'une source dès qu'elle réussissait à s'authentifier.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.api.threat_detection import (  # noqa: E402
    DEFAULT_THRESHOLD, THRESHOLD_ENV, UNAVAILABLE_METHODS, ThreatDetector,
    failure_threshold, get_shared_detector, reset_detector, severity_for,
    window_seconds,
)


@pytest.fixture
def detecteur():
    """Détecteur isolé pour un test."""
    return ThreatDetector()


@pytest.fixture
def cles(monkeypatch):
    """Clés admin et lecture seule, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin,cle-lecture:readonly")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    reset_detector()
    yield {"admin": "cle-admin", "readonly": "cle-lecture"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    reset_detector()


def test_sous_le_seuil_rien_n_est_signale(detecteur):
    """Quelques erreurs de frappe ne sont pas une attaque."""
    for _ in range(3):
        detecteur.record_failure("10.0.0.1")
    assert detecteur.active_threats(threshold=10) == []


def test_au_dela_du_seuil_la_source_est_nommee(detecteur):
    """Le signal dit qui insiste, pas seulement combien d'échecs ont eu lieu."""
    for _ in range(12):
        detecteur.record_failure("10.0.0.1")

    menaces = detecteur.active_threats(threshold=10)
    assert len(menaces) == 1
    assert menaces[0]["source"] == "10.0.0.1"
    assert menaces[0]["failures"] == 12
    assert menaces[0]["first_seen"] > 0


def test_un_succes_n_efface_pas_les_echecs(detecteur):
    """Le contournement de la première version : réussir une fois effaçait tout.

    Deux personnes différentes en pâtissaient — l'attaquant qui finit par
    trouver une clé valide effaçait sa trace, et l'opérateur qui consultait la
    route depuis la même adresse effaçait ce qu'il venait observer.
    """
    for _ in range(12):
        detecteur.record_failure("10.0.0.1")
    detecteur.record_success("10.0.0.1")

    menaces = detecteur.active_threats(threshold=10)
    assert len(menaces) == 1, "la menace a disparu après une authentification réussie"
    assert menaces[0]["succeeded_in_window"] is True


def test_sans_succes_l_insistance_est_le_signal(detecteur):
    """Des échecs sans aucun succès sont le cas le plus suspect."""
    for _ in range(12):
        detecteur.record_failure("10.0.0.2")
    assert detecteur.active_threats(threshold=10)[0]["succeeded_in_window"] is False


def test_les_echecs_sortent_de_la_fenetre(detecteur, monkeypatch):
    """Une fenêtre glissante oublie : sinon toute source finit par être signalée."""
    maintenant = 1_000_000.0
    for _ in range(12):
        detecteur.record_failure("10.0.0.1", now=maintenant)

    assert detecteur.active_threats(threshold=10, now=maintenant)
    plus_tard = maintenant + window_seconds() + 1
    assert detecteur.active_threats(threshold=10, now=plus_tard) == []


def test_les_sources_sont_distinguees(detecteur):
    """Deux adresses ne s'additionnent pas : sinon un seuil global masquerait tout."""
    for _ in range(6):
        detecteur.record_failure("10.0.0.1")
        detecteur.record_failure("10.0.0.2")
    assert detecteur.active_threats(threshold=10) == []


def test_une_source_inconnue_est_comptee(detecteur):
    """Perdre les échecs sans origine reviendrait à ne pas voir le plus discret."""
    for _ in range(12):
        detecteur.record_failure(None)
    assert detecteur.active_threats(threshold=10)[0]["source"] == "unknown"


def test_le_nombre_de_sources_suivies_est_borne():
    """Un détecteur dont la mémoire suit le trafic devient le déni de service."""
    detecteur = ThreatDetector(max_sources=5)
    for i in range(50):
        detecteur.record_failure(f"10.0.0.{i}")
    assert detecteur.summary()["tracked_sources"] <= 6


@pytest.mark.parametrize("echecs, attendu", [
    (10, "medium"), (19, "medium"), (20, "high"), (49, "high"), (50, "critical"),
])
def test_la_severite_suit_des_multiples_du_seuil(echecs, attendu):
    """Trois niveaux : une échelle plus fine prétendrait à une précision absente."""
    assert severity_for(echecs, threshold=10) == attendu


def test_le_seuil_est_configurable(monkeypatch):
    """Un seuil qui crie au loup est un seuil désactivé dans la semaine."""
    monkeypatch.delenv(THRESHOLD_ENV, raising=False)
    assert failure_threshold() == DEFAULT_THRESHOLD
    monkeypatch.setenv(THRESHOLD_ENV, "3")
    assert failure_threshold() == 3
    # Valeur illisible ou nulle : repli sur le défaut, jamais de désactivation.
    monkeypatch.setenv(THRESHOLD_ENV, "zéro")
    assert failure_threshold() == DEFAULT_THRESHOLD
    monkeypatch.setenv(THRESHOLD_ENV, "0")
    assert failure_threshold() == DEFAULT_THRESHOLD


def test_les_methodes_absentes_sont_nommees(detecteur):
    """Analyse comportementale, renseignement, modèle : nommés, jamais simulés."""
    resume = detecteur.summary()
    assert set(resume["unavailable_methods"]) == set(UNAVAILABLE_METHODS)
    assert set(resume["unavailable_methods"]) == {
        "behavioral_analytics", "threat_intelligence_correlation", "machine_assisted_analysis",
    }


def test_les_echecs_reels_alimentent_la_detection(cles):
    """De bout en bout, par de vraies requêtes refusées."""
    with TestClient(app) as client:
        for i in range(12):
            client.get("/metrics", headers={"X-API-Key": f"cle-volee-{i}"})
        reponse = client.get("/security/threats", headers={"X-API-Key": cles["admin"]})

    assert reponse.status_code == 200
    menaces = reponse.json()["threats"]
    assert menaces and menaces[0]["failures"] >= 12


def test_aucune_cle_n_apparait_dans_le_rapport(cles):
    """Un journal de menaces qui nomme des clés devient lui-même une cible."""
    import json

    with TestClient(app) as client:
        for _ in range(12):
            client.get("/metrics", headers={"X-API-Key": "zzcle-secrete-voleezz"})
        reponse = client.get("/security/threats", headers={"X-API-Key": cles["admin"]})

    assert "zzcle-secrete-voleezz" not in json.dumps(reponse.json())


def test_la_route_est_reservee_a_la_supervision(cles):
    """Savoir qui attaque la plateforme n'est pas une information publique."""
    with TestClient(app) as client:
        lecture = client.get("/security/threats", headers={"X-API-Key": cles["readonly"]})
        sans_cle = client.get("/security/threats")
    assert lecture.status_code == 403
    assert sans_cle.status_code == 401
