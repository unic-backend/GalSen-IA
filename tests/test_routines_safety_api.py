"""
Les routes de sûreté des routines (phase 48.2).

Un défaut a été trouvé en écrivant ce fichier, et il vaut d'être nommé : le
câblage de la phase 48.1 laissait la couche de sûreté **naître avec chaque
planificateur**. Le serveur reconstruit son planificateur dès que le moteur
d'outils change, si bien qu'un arrêt d'urgence engagé disparaissait à ce
moment-là — exactement le défaut contre lequel `safety.py` a été écrit
(« un arrêt logé dans le moteur qu'il arrête est un arrêt qu'une panne de ce
moteur emporte »), réintroduit par son propre branchement.

La sûreté vit désormais au niveau du module, et un test conduit la
reconstruction pour le vérifier.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402
from src.routines import RoutineJournal, RoutineRegistry, RoutineSafety  # noqa: E402

HEURE = 3600


@pytest.fixture
def cles(monkeypatch):
    """Une clé admin et une clé utilisateur, nommées."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv(
        "GALSEN_API_KEYS", "cle-awa:admin:awa,cle-fatou:user:fatou"
    )
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield {"admin": "cle-awa", "user": "cle-fatou"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


@pytest.fixture
def routines_neuves(monkeypatch):
    """Registre, journal et sûreté propres pour ce test."""
    monkeypatch.setattr(server_module, "routine_registry", RoutineRegistry())
    monkeypatch.setattr(server_module, "routine_journal", RoutineJournal())
    monkeypatch.setattr(server_module, "routine_safety", RoutineSafety())
    monkeypatch.setattr(server_module, "_routine_scheduler", None)


@pytest.fixture
def client():
    """Client HTTP sur l'application réelle."""
    with TestClient(app) as essai:
        yield essai


def _declarer(client, cle, identifiant="veille"):
    """Déclare puis active une routine par l'API."""
    client.post("/routines", headers={"X-API-Key": cle}, json={
        "routine_id": identifiant,
        "description": "Surveiller les métriques chaque heure",
        "actions": [{"tool_id": "metrics", "operation": "get_metrics"}],
        "interval_seconds": HEURE,
    })
    return client.post(
        f"/routines/{identifiant}/enable", headers={"X-API-Key": cle}
    )


# ----------------------------------------------------------------------
# 1. Le défaut de câblage, et sa correction
# ----------------------------------------------------------------------

def test_un_arret_survit_a_la_reconstruction_du_planificateur(
    client, cles, routines_neuves, monkeypatch
):
    """
    **Le test qui a trouvé le défaut.** Le serveur reconstruit son
    planificateur dès que le moteur d'outils change ; un arrêt engagé ne doit
    pas disparaître à ce moment-là.
    """
    client.post("/routines/halt", headers={"X-API-Key": cles["admin"]},
                json={"reason": "incident chez le fournisseur"})
    premier = server_module._scheduler()

    # Le moteur d'outils change : le planificateur est reconstruit.
    monkeypatch.setattr(server_module, "tool_engine", object())
    second = server_module._scheduler()

    assert second is not premier, "Le planificateur devrait avoir été reconstruit"
    assert second.safety.halted is True
    assert second.due_at(0) == []


def test_la_surete_est_le_meme_objet_pour_tous_les_planificateurs(
    client, cles, routines_neuves, monkeypatch
):
    """Une sûreté par instance n'arrêterait qu'une instance."""
    premier = server_module._scheduler()
    monkeypatch.setattr(server_module, "tool_engine", object())
    second = server_module._scheduler()

    assert premier.safety is second.safety is server_module.routine_safety


# ----------------------------------------------------------------------
# 2. L'arrêt d'urgence par l'API
# ----------------------------------------------------------------------

def test_l_arret_nomme_l_appelant_pas_un_champ_du_corps(client, cles, routines_neuves):
    """Un arrêt anonyme ne se lève pas : personne ne sait s'il peut."""
    reponse = client.post(
        "/routines/halt", headers={"X-API-Key": cles["admin"]},
        json={"reason": "incident", "engaged_by": "quelqu-un-d-autre"},
    )

    assert reponse.status_code == 200
    assert reponse.json()["engaged_by"] == "awa"


def test_un_arret_sans_raison_est_refuse(client, cles, routines_neuves):
    """Elle sera lue par celui qui envisagera de lever, des jours plus tard."""
    reponse = client.post(
        "/routines/halt", headers={"X-API-Key": cles["admin"]}, json={"reason": "  "}
    )

    assert reponse.status_code == 400
    assert "dit pourquoi" in reponse.json()["detail"]


def test_l_arret_empeche_tout_declenchement(client, cles, routines_neuves):
    """C'est ce qu'on attend d'un arrêt d'urgence."""
    _declarer(client, cles["admin"])
    client.post("/routines/halt", headers={"X-API-Key": cles["admin"]},
                json={"reason": "incident"})

    tick = client.post("/routines/tick", headers={"X-API-Key": cles["admin"]})

    assert tick.json()["count"] == 0


def test_l_etat_publie_dit_qui_a_arrete_et_pourquoi(client, cles, routines_neuves):
    """Sans cela, la levée serait une décision prise à l'aveugle."""
    client.post("/routines/halt", headers={"X-API-Key": cles["admin"]},
                json={"reason": "quota du fournisseur dépassé"})

    etat = client.get(
        "/routines/safety", headers={"X-API-Key": cles["admin"]}
    ).json()

    assert etat["halted"] is True
    assert etat["halt"]["engaged_by"] == "awa"
    assert "quota" in etat["halt"]["reason"]


def test_la_levee_est_explicite_et_reversible(client, cles, routines_neuves):
    """Un arrêt qui se lèverait tout seul serait un délai."""
    _declarer(client, cles["admin"])
    client.post("/routines/halt", headers={"X-API-Key": cles["admin"]},
                json={"reason": "incident"})

    levee = client.delete("/routines/halt", headers={"X-API-Key": cles["admin"]})

    assert levee.json() == {"released": True, "halted": False}
    assert client.post(
        "/routines/tick", headers={"X-API-Key": cles["admin"]}
    ).json()["count"] == 1


def test_l_arret_est_reserve_a_l_administration(client, cles, routines_neuves):
    """Arrêter toutes les routines de l'installation est un acte d'exploitation."""
    assert client.post(
        "/routines/halt", headers={"X-API-Key": cles["user"]}, json={"reason": "x"}
    ).status_code == 403
    assert client.delete(
        "/routines/halt", headers={"X-API-Key": cles["user"]}
    ).status_code == 403


# ----------------------------------------------------------------------
# 3. Le budget par l'API
# ----------------------------------------------------------------------

def test_le_budget_pose_par_l_api_est_celui_qui_s_applique(client, cles, routines_neuves):
    """
    La route **fixe** la limite ; son application dans le temps est vérifiée
    par les tests unitaires, qui contrôlent l'horloge. La route `tick` lit
    l'heure réelle — deux appels dans la même seconde ne prouveraient rien,
    et un test qui attendrait une heure serait un test supprimé.

    Ce que ce test vérifie est donc la jonction : la limite posée par l'API est
    celle que la couche de sûreté applique.
    """
    _declarer(client, cles["admin"])

    pose = client.put(
        "/routines/veille/budget", headers={"X-API-Key": cles["admin"]},
        json={"runs_per_day": 1},
    )

    # Depuis le VOLET 67 la route rend aussi le plafond de **travail** : un tour
    # n'est plus une unité de coût depuis qu'il peut déclencher un workflow.
    assert pose.json()["routine_id"] == "veille"
    assert pose.json()["runs_per_day"] == 1
    assert pose.json()["agents_per_day"] > 0
    server_module.routine_safety.consume("veille", now=0)
    autorise, motif = server_module.routine_safety.check("veille", now=1)
    assert autorise is False
    assert "Budget épuisé" in motif


def test_un_tour_declenche_par_l_api_consomme_le_budget(client, cles, routines_neuves):
    """La consommation passe bien par la route, pas seulement par l'objet."""
    _declarer(client, cles["admin"])

    client.post("/routines/tick", headers={"X-API-Key": cles["admin"]})

    etat = client.get(
        "/routines/safety", headers={"X-API-Key": cles["admin"]}
    ).json()
    assert etat["budgets"]["veille"]["runs"] == 1


def test_un_budget_nul_est_refuse(client, cles, routines_neuves):
    """Ce serait une désactivation déguisée."""
    _declarer(client, cles["admin"])

    reponse = client.put(
        "/routines/veille/budget", headers={"X-API-Key": cles["admin"]},
        json={"runs_per_day": 0},
    )

    assert reponse.status_code == 400
    assert "désactivation déguisée" in reponse.json()["detail"]


def test_le_budget_d_une_routine_d_une_autre_personne_est_invisible(
    client, cles, routines_neuves
):
    """Le même 404 qu'une routine inexistante."""
    _declarer(client, cles["admin"], identifiant="a-awa")

    reponse = client.put(
        "/routines/a-awa/budget", headers={"X-API-Key": cles["user"]},
        json={"runs_per_day": 5},
    )

    assert reponse.status_code == 404


def test_les_routes_de_surete_exigent_une_cle(client, routines_neuves):
    """Aucune n'est publique."""
    assert client.get("/routines/safety").status_code in (401, 403)
    assert client.post(
        "/routines/halt", json={"reason": "x"}
    ).status_code in (401, 403)


def test_l_etat_de_surete_nomme_ce_qu_il_ne_fait_pas(client, cles, routines_neuves):
    """Le dire vaut mieux que le laisser croire."""
    etat = client.get(
        "/routines/safety", headers={"X-API-Key": cles["admin"]}
    ).json()

    ne_fait_pas = " ".join(etat["does_not"])
    assert "déjà commencé" in ne_fait_pas
    assert "fournisseur" in ne_fait_pas
