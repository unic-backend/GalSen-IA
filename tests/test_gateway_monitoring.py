"""
Métriques clés de la passerelle (VOLET 15, chapitre 06).

Le chapitre en nomme six : latence, disponibilité, débit, taux d'erreur, taux de
succès d'authentification, utilisation des ressources. Quatre étaient mesurées.
Le débit manquait — il se déduisait des compteurs mais personne ne le
calculait — et deux ne sont pas mesurables ici : elles sont désormais nommées
plutôt que laissées absentes sans explication.
"""

import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GALSEN_API_KEYS", "test-key-0123456789abcdef")

from src.api import server  # noqa: E402
from src.api.metrics import metrics_snapshot, reset_metrics  # noqa: E402
from src.api.rate_limiter import set_valid_api_key_digests  # noqa: E402

CLE = "test-key-0123456789abcdef"


@pytest.fixture
def client(monkeypatch):
    """Client administrateur, compteurs remis à zéro de part et d'autre."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin")
    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    reset_metrics()
    with TestClient(server.app) as instance:
        yield instance
    reset_metrics()


def test_le_debit_est_calcule_a_partir_des_requetes_reelles(client):
    """Le chapitre 06 demande le débit ; il n'était calculé nulle part."""
    for _ in range(4):
        client.get("/live")

    instantane = metrics_snapshot()
    assert instantane["requests_total"] == 4
    assert instantane["uptime_seconds"] > 0
    assert instantane["throughput_rps"] > 0


def test_le_debit_suit_la_fenetre_des_compteurs(client):
    """
    Remettre les compteurs à zéro sans remettre l'origine donnerait un débit
    calculé sur une durée que les compteurs ne couvrent plus — il s'effondrerait
    vers zéro sans que le trafic ait changé.
    """
    client.get("/live")
    time.sleep(0.05)
    reset_metrics()

    instantane = metrics_snapshot()
    assert instantane["requests_total"] == 0
    assert instantane["uptime_seconds"] < 0.05


def test_les_metriques_non_mesurables_sont_nommees(client):
    """
    Une disponibilité auto-déclarée vaut toujours 100 % : une instance arrêtée
    ne rapporte rien. Rendre ce chiffre serait exactement la réponse plausible
    que `.claude/rules/verification.md` interdit.
    """
    indisponibles = metrics_snapshot()["unavailable"]

    assert "availability" in indisponibles
    assert "resource_utilization" in indisponibles
    assert "sonde externe" in indisponibles["availability"]
    assert "psutil" in indisponibles["resource_utilization"]


def test_aucune_disponibilite_chiffree_n_est_rendue(client):
    """Le contre-test : personne ne doit pouvoir lire un pourcentage inventé."""
    instantane = metrics_snapshot()

    assert "availability" not in instantane
    assert "availability_percent" not in instantane


def test_la_route_metrics_sert_les_nouvelles_mesures(client):
    """Une mesure calculée mais non servie ne mesure rien pour l'opérateur."""
    corps = client.get("/metrics", headers={"X-API-Key": CLE}).json()

    assert "throughput_rps" in corps
    assert "uptime_seconds" in corps
    assert corps["unavailable"]["availability"]
