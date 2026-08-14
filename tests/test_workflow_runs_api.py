"""
Les routes des exécutions longues (phase 49.3).

Le point de reprise existait (49.1) et le routeur passait par lui (49.2), mais
rien ne l'atteignait depuis l'extérieur : une exécution morte au huitième agent
était visible dans les journaux et irrattrapable. Ces routes lui donnent prise.

Ce que ces tests gardent :

1. **La reprise ne demande rien.** Le workflow et la demande d'origine viennent
   du point de reprise. Les redemander à l'appelant permettrait d'en changer
   sans que rien ne le dise, et la moitié déjà faite répondrait alors à une
   autre question.
2. **L'exécution d'autrui est un 404**, mot pour mot celui d'une exécution
   inexistante.
3. **Une reprise refusée n'est pas une erreur du serveur** : 404 si elle est
   invisible, 409 si son état s'y oppose — et rien n'a démarré.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402

WORKFLOW = "revue"
ETAPES = ["reviewer", "security"]


@pytest.fixture
def cles(monkeypatch):
    """Deux clés nommées : deux personnes distinctes."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa,cle-fatou:user:fatou")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield {"awa": "cle-awa", "fatou": "cle-fatou"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def moteur(monkeypatch):
    """
    Le routeur du serveur, avec un répartiteur contrôlé.

    Les agents réels appelleraient un modèle : ce qui est éprouvé ici est le
    chemin HTTP jusqu'au point de reprise, pas ce que les agents produisent.
    """
    routeur = server_module.get_router_engine()
    monkeypatch.setattr(routeur.retry_manager, "max_attempts", 1)
    monkeypatch.setattr(routeur.retry_manager, "delay_seconds", 0)
    from src.router.workflow_checkpoint import WorkflowCheckpoints
    monkeypatch.setattr(routeur, "checkpoints", WorkflowCheckpoints())
    return routeur


@pytest.fixture
def client():
    """Client HTTP sur l'application réelle."""
    with TestClient(app) as essai:
        yield essai


def _repartiteur(lances, echec_sur=None):
    """Un répartiteur qui note ce qu'on lui demande et échoue où on le dit."""

    def repartir(agent_config, input_data, context=None):
        agent_id = agent_config.get("id")
        lances.append((agent_id, input_data))
        if agent_id == echec_sur:
            return {"agent": agent_id, "status": "error", "error": "panne simulée"}
        return {"agent": agent_id, "status": "success", "result": f"sortie de {agent_id}"}

    return repartir


def _lancer_et_echouer(client, moteur, cle, demande="Relire le code"):
    """Lance une exécution qui meurt au second agent, et rend son identifiant."""
    moteur._dispatch_agent = _repartiteur([], echec_sur="security")
    reponse = client.post(
        "/workflow/run", headers={"X-API-Key": cle},
        json={"request": demande, "workflow_id": WORKFLOW},
    )
    return reponse.json()["run_id"]


# ----------------------------------------------------------------------
# 1. Lister et lire
# ----------------------------------------------------------------------

def test_une_execution_lancee_par_l_api_apparait_dans_la_liste(client, cles, moteur):
    """Sans cela, reprendre supposerait d'avoir gardé l'identifiant."""
    run_id = _lancer_et_echouer(client, moteur, cles["awa"])

    listee = client.get("/workflow/runs", headers={"X-API-Key": cles["awa"]}).json()

    assert [e["run_id"] for e in listee["runs"]] == [run_id]
    assert listee["runs"][0]["next_step"] == "security"


def test_l_etat_d_une_execution_dit_ce_qui_reste(client, cles, moteur):
    """Ce qui est fait, ce qui reste, et où elle en est."""
    run_id = _lancer_et_echouer(client, moteur, cles["awa"])

    etat = client.get(
        f"/workflow/runs/{run_id}", headers={"X-API-Key": cles["awa"]}
    ).json()

    assert etat["status"] == "failed"
    assert etat["progress"] == "1/2"
    assert etat["next_step"] == "security"


def test_l_execution_d_une_autre_personne_est_un_404(client, cles, moteur):
    """Le même que pour une exécution inexistante."""
    run_id = _lancer_et_echouer(client, moteur, cles["awa"])

    autrui = client.get(
        f"/workflow/runs/{run_id}", headers={"X-API-Key": cles["fatou"]}
    )
    inexistante = client.get(
        "/workflow/runs/run_nexistepas", headers={"X-API-Key": cles["fatou"]}
    )

    assert autrui.status_code == 404
    assert autrui.json()["detail"].replace(run_id, "X") == (
        inexistante.json()["detail"].replace("run_nexistepas", "X")
    )


def test_la_liste_d_une_autre_personne_est_vide(client, cles, moteur):
    """Compter les exécutions d'autrui serait déjà en dire trop."""
    _lancer_et_echouer(client, moteur, cles["awa"])

    listee = client.get("/workflow/runs", headers={"X-API-Key": cles["fatou"]}).json()

    assert listee["runs"] == []


def test_les_routes_d_execution_exigent_une_cle(client):
    """Aucune n'est publique."""
    assert client.get("/workflow/runs").status_code in (401, 403)
    assert client.post("/workflow/runs/x/resume").status_code in (401, 403)


# ----------------------------------------------------------------------
# 2. Reprendre
# ----------------------------------------------------------------------

def test_la_reprise_ne_refait_pas_ce_qui_a_abouti(client, cles, moteur):
    """De bout en bout par HTTP : on compte les agents réellement lancés."""
    run_id = _lancer_et_echouer(client, moteur, cles["awa"])

    lances = []
    moteur._dispatch_agent = _repartiteur(lances)
    reprise = client.post(
        f"/workflow/runs/{run_id}/resume", headers={"X-API-Key": cles["awa"]}
    )

    assert reprise.status_code == 200
    assert [agent for agent, _ in lances] == ["security"]
    assert reprise.json()["metadata"]["run_status"] == "completed"


def test_la_reprise_repose_la_demande_d_origine(client, cles, moteur):
    """
    Elle ne se redemande pas : la redemander permettrait d'en changer sans que
    rien ne le dise, et la moitié déjà faite répondrait à une autre question.
    """
    run_id = _lancer_et_echouer(client, moteur, cles["awa"], demande="Auditer le module X")

    lances = []
    moteur._dispatch_agent = _repartiteur(lances)
    client.post(f"/workflow/runs/{run_id}/resume", headers={"X-API-Key": cles["awa"]})

    assert lances[0][1] == "Auditer le module X"


def test_reprendre_l_execution_d_un_autre_est_un_404_sans_rien_lancer(
    client, cles, moteur
):
    """Reprendre le workflow d'autrui, ce serait lancer des agents sur ses données."""
    run_id = _lancer_et_echouer(client, moteur, cles["awa"])

    lances = []
    moteur._dispatch_agent = _repartiteur(lances)
    refus = client.post(
        f"/workflow/runs/{run_id}/resume", headers={"X-API-Key": cles["fatou"]}
    )

    assert refus.status_code == 404
    assert lances == []


def test_reprendre_une_execution_terminee_est_un_409(client, cles, moteur):
    """Son état s'oppose à la reprise ; ce n'est pas une panne du serveur."""
    moteur._dispatch_agent = _repartiteur([])
    lancee = client.post(
        "/workflow/run", headers={"X-API-Key": cles["awa"]},
        json={"request": "Relire le code", "workflow_id": WORKFLOW},
    ).json()

    refus = client.post(
        f"/workflow/runs/{lancee['run_id']}/resume", headers={"X-API-Key": cles["awa"]}
    )

    assert refus.status_code == 409
    assert "travail déjà fait" in refus.json()["detail"]


# ----------------------------------------------------------------------
# 3. Annuler
# ----------------------------------------------------------------------

def test_une_execution_annulee_ne_reprend_plus(client, cles, moteur):
    """Sinon « annuler » voudrait dire « suspendre »."""
    run_id = _lancer_et_echouer(client, moteur, cles["awa"])

    annulation = client.post(
        f"/workflow/runs/{run_id}/cancel", headers={"X-API-Key": cles["awa"]},
        json={"reason": "le client a changé d'avis"},
    )
    lances = []
    moteur._dispatch_agent = _repartiteur(lances)
    reprise = client.post(
        f"/workflow/runs/{run_id}/resume", headers={"X-API-Key": cles["awa"]}
    )

    assert annulation.json()["status"] == "cancelled"
    assert reprise.status_code == 409
    assert lances == []


def test_une_annulation_sans_raison_est_refusee(client, cles, moteur):
    """Elle est définitive : la raison est tout ce qui restera pour l'expliquer."""
    run_id = _lancer_et_echouer(client, moteur, cles["awa"])

    refus = client.post(
        f"/workflow/runs/{run_id}/cancel", headers={"X-API-Key": cles["awa"]},
        json={"reason": "   "},
    )

    assert refus.status_code == 400
    assert "dit pourquoi" in refus.json()["detail"]


def test_l_annulation_dit_ce_qu_elle_ne_fait_pas(client, cles, moteur):
    """Une étape déjà commencée finit : le dire vaut mieux que le laisser croire."""
    run_id = _lancer_et_echouer(client, moteur, cles["awa"])

    annulation = client.post(
        f"/workflow/runs/{run_id}/cancel", headers={"X-API-Key": cles["awa"]},
        json={"reason": "incident"},
    ).json()

    assert any("déjà commencée" in ligne for ligne in annulation["does_not"])


def test_annuler_l_execution_d_un_autre_est_un_404(client, cles, moteur):
    """La même frontière que pour lire et reprendre."""
    run_id = _lancer_et_echouer(client, moteur, cles["awa"])

    refus = client.post(
        f"/workflow/runs/{run_id}/cancel", headers={"X-API-Key": cles["fatou"]},
        json={"reason": "x"},
    )

    assert refus.status_code == 404
    # Rien n'a bougé pour son propriétaire : un refus n'annule pas à moitié.
    assert moteur.checkpoints.get(run_id, subject="awa").status.value == "failed"
