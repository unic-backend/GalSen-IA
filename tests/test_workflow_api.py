"""
Exécution d'un workflow par l'API.

L'orchestration existait, était testée, et **aucune route ne l'atteignait** :
`RouterEngine` n'était instancié que par les tests. Même défaut que les magasins
cloud du VOLET 24 — une capacité qui fonctionne et que personne ne peut allumer.
"""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GALSEN_API_KEYS", "test-key-0123456789abcdef")

from src.api import server  # noqa: E402
from src.api.rate_limiter import set_valid_api_key_digests  # noqa: E402

CLE = "test-key-0123456789abcdef"
CLE_LECTURE = "test-key-lecture-0123456789"


@pytest.fixture
def client(monkeypatch):
    """Client administrateur, plus une clé en lecture seule."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin,{CLE_LECTURE}:readonly")
    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    with TestClient(server.app) as instance:
        yield instance


def test_un_workflow_s_execute_par_l_api(client):
    """La capacité devient atteignable — c'est tout l'objet de ces routes.

    `revue` est choisi parce qu'il ne mobilise que deux agents d'analyse
    statique : le test vérifie le chemin, pas la patience de qui le lance.
    """
    reponse = client.post("/workflow/run",
                          json={"request": "Relire le module de recherche", "workflow_id": "revue"},
                          headers={"X-API-Key": CLE})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["status"] in ("success", "partial_success")
    assert corps["workflow_used"] == "revue"
    assert [r["agent"] for r in corps["agent_results"]] == ["reviewer", "security"]


def test_la_reponse_porte_la_trace_de_decision(client):
    """Ce que le VOLET 22 a mesuré doit rester visible depuis l'extérieur."""
    corps = client.post("/workflow/run",
                        json={"request": "Relire le module", "workflow_id": "revue"},
                        headers={"X-API-Key": CLE}).json()

    decision = corps["metadata"]["decision"]
    assert "applied" in decision
    assert decision["executed_agents"] == ["reviewer", "security"]


def test_un_workflow_inconnu_repond_404(client):
    """
    404 et non 500 : la faute est dans la demande, pas dans la plateforme, et
    l'appelant peut la corriger.
    """
    reponse = client.post("/workflow/run",
                          json={"request": "test", "workflow_id": "inexistant"},
                          headers={"X-API-Key": CLE})

    assert reponse.status_code == 404
    assert "inexistant" in reponse.json()["detail"]


def test_une_demande_vide_est_refusee(client):
    """Exécuter dix agents sur une chaîne vide serait dix agents pour rien."""
    reponse = client.post("/workflow/run", json={"request": ""},
                          headers={"X-API-Key": CLE})

    assert reponse.status_code == 422


def test_une_cle_en_lecture_seule_ne_peut_pas_executer(client):
    """
    Un workflow exécute des agents qui appellent des outils : il ne doit pas
    ouvrir plus que `POST /tool/execute`.
    """
    reponse = client.post("/workflow/run", json={"request": "test"},
                          headers={"X-API-Key": CLE_LECTURE})

    assert reponse.status_code == 403


def test_l_appelant_ne_choisit_pas_son_identite(client):
    """
    Le sujet vient de la clé (ADR-010), jamais du corps. Un champ `user_id`
    accepté ici permettrait d'agir au nom de quelqu'un d'autre.
    """
    assert "user_id" not in server.WorkflowRunRequest.model_fields


def test_la_liste_annonce_l_executabilite(client):
    """Découvrir un workflow inexécutable à l'appel coûte une requête pour rien."""
    corps = client.get("/workflow/list", headers={"X-API-Key": CLE}).json()

    assert corps["default"] == "standard"
    par_id = {w["id"]: w for w in corps["workflows"]}
    assert par_id["revue"]["executable"] is True
    assert par_id["standard"]["agent_selection"] == "planner"
    assert par_id["revue"]["version"] == "1.0"


def test_l_historique_sert_les_trois_mesures(client):
    """Les VOLETs 18 et 19 les ont ajoutées et aucune route ne les servait."""
    client.post("/workflow/run", json={"request": "Relire", "workflow_id": "revue"},
                headers={"X-API-Key": CLE})

    stats = client.get("/workflow/history", headers={"X-API-Key": CLE}).json()["stats"]

    assert stats["executions"] >= 1
    assert "by_version" in stats
    assert "agent_time" in stats
    assert "failing_agents" in stats


def test_l_historique_est_reserve_a_qui_peut_voir_l_etat(client):
    """Les durées et les taux d'échec décrivent l'usage d'un déploiement."""
    reponse = client.get("/workflow/history")

    assert reponse.status_code == 401
