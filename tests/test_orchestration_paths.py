"""
Deux chemins, un seul moteur (phase 64.2).

Après le VOLET 64 il existe exactement deux façons d'atteindre l'orchestrateur :
quelqu'un qui demande (`POST /process`) et une routine qui se déclenche sans
personne devant (`POST /routines/tick`). Ils empruntent **le même moteur** — même
plan, mêmes points de reprise, même historique, même audit. C'est tout l'objet du
volet : un second chemin sans ces garanties serait l'implémentation parallèle que
la directive interdit.

Ce que ces tests gardent :

1. **L'exécution ne change pas selon qui regarde** — seul le marquage change,
   et il atteint l'audit.
2. **Le rapport compte ce qu'il peut compter**, et nomme non mesuré ce qu'il ne
   peut pas — jamais `0` faute de registre.
3. **Les nombres ne trahissent personne** : un compte de routines ne dit ni
   lesquelles ni à qui.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.router.orchestration_paths import (  # noqa: E402
    CHEMIN_DEMANDE,
    CHEMIN_ROUTINE,
    orchestration_paths,
)
from src.routines import RoutineAction, RoutineRegistry, WorkflowAction  # noqa: E402


@pytest.fixture
def registre():
    """Un registre neuf."""
    return RoutineRegistry()


# ----------------------------------------------------------------------
# 1. Les deux chemins, et ce que le second ne peut pas décider
# ----------------------------------------------------------------------

def test_les_deux_chemins_sont_nommes_avec_leur_entree():
    """Un lecteur doit savoir par où le travail arrive."""
    rapport = orchestration_paths()

    assert rapport["paths"][CHEMIN_DEMANDE]["entry_point"] == "POST /process"
    assert rapport["paths"][CHEMIN_ROUTINE]["entry_point"] == "POST /routines/tick"


def test_seul_le_chemin_avec_temoin_peut_demander_a_un_humain():
    """C'est la seule différence de fond entre les deux."""
    rapport = orchestration_paths()

    assert rapport["paths"][CHEMIN_DEMANDE]["may_ask_a_human"] is True
    assert rapport["paths"][CHEMIN_ROUTINE]["may_ask_a_human"] is False


def test_le_rapport_dit_ce_que_les_deux_chemins_partagent():
    """Sans quoi rien ne prouverait qu'il n'y a pas deux moteurs."""
    partage = " ".join(orchestration_paths()["shared"])

    assert "points de reprise" in partage
    assert "historique" in partage
    assert "audit" in partage


def test_l_absence_de_quelqu_un_pour_refuser_n_est_pas_un_accord():
    """La règle propre à l'exécution sans témoin, écrite noir sur blanc."""
    interdits = " ".join(orchestration_paths()["unattended_cannot"])

    assert "Accorder une approbation" in interdits
    assert "suspended" in interdits
    assert "propriétaire" in interdits


# ----------------------------------------------------------------------
# 2. Mesuré, ou dit non mesuré
# ----------------------------------------------------------------------

def test_sans_registre_le_rapport_dit_non_mesure():
    """Rendre `0` ferait passer « personne n'a regardé » pour « aucune »."""
    mesures = orchestration_paths()["measured"]

    assert "NOT_MEASURED" in mesures["workflows"]
    assert "NOT_MEASURED" in mesures["routines"]


def test_les_workflows_du_depot_sont_comptes():
    """Comptés au chargeur réel, pas écrits de mémoire."""
    from src.router.workflow_loader import WorkflowLoader

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chargeur = WorkflowLoader(os.path.join(racine, "workflows", "workflows.yaml"))

    mesures = orchestration_paths(workflow_loader=chargeur)["measured"]

    assert mesures["workflows_declared"] >= 8
    assert mesures["workflows_executable"] <= mesures["workflows_declared"]


def test_les_routines_de_workflow_sont_comptees_a_part(registre):
    """C'est la capacité que ce volet ajoute : il faut la voir arriver."""
    registre.declare(
        "outil", "Un appel d'outil.", [RoutineAction("metrics", "read")],
        interval_seconds=3600, subject="awa",
    )
    registre.declare(
        "flux", "Un workflow.", [WorkflowAction(workflow_id="standard")],
        interval_seconds=3600, subject="awa",
    )

    mesures = orchestration_paths(routine_registry=registre)["measured"]

    assert mesures["routines_declared"] == 2
    assert mesures["routines_running_a_workflow"] == 1
    assert mesures["routines_enabled"] == 0


def test_les_comptes_ne_disent_ni_lesquelles_ni_a_qui(registre):
    """La liste des routines de quelqu'un dit ce qu'il surveille."""
    registre.declare(
        "privee", "La routine d'awa.", [RoutineAction("metrics", "read")],
        interval_seconds=3600, subject="awa",
    )

    rendu = str(orchestration_paths(routine_registry=registre)["measured"])

    assert "awa" not in rendu
    assert "privee" not in rendu


# ----------------------------------------------------------------------
# 3. Le marquage atteint l'audit
# ----------------------------------------------------------------------

def test_une_execution_ordinaire_n_est_pas_marquee_sans_temoin():
    """Le défaut est « quelqu'un demandait »."""
    from src.router.router_engine import RouterEngine

    moteur = RouterEngine()
    reponse = moteur.process_request("Bonjour", workflow_id="standard")

    assert reponse["metadata"]["unattended"] is False


def test_une_execution_de_routine_est_marquee_sans_temoin():
    """Sinon une approbation restée sans réponse toute la nuit se lirait
    comme un utilisateur qui a changé d'avis."""
    from src.router.router_engine import RouterEngine

    moteur = RouterEngine()
    reponse = moteur.process_request("Bonjour", workflow_id="standard", unattended=True)

    assert reponse["metadata"]["unattended"] is True


# ----------------------------------------------------------------------
# 4. La route
# ----------------------------------------------------------------------

@pytest.fixture
def client_orchestration(monkeypatch):
    """Client HTTP et clé nommée."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    with TestClient(server_module.app) as essai:
        yield essai, {"X-API-Key": "cle-awa"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def test_la_route_publie_les_deux_chemins(client_orchestration):
    """Vérifiable sans lire le code."""
    client, cle = client_orchestration

    rapport = client.get("/orchestrator/paths", headers=cle).json()

    assert set(rapport["paths"]) == {CHEMIN_DEMANDE, CHEMIN_ROUTINE}
    assert rapport["measured"]["workflows_declared"] >= 8


def test_la_route_exige_une_cle(client_orchestration):
    """Elle n'est pas publique."""
    client, _ = client_orchestration

    assert client.get("/orchestrator/paths").status_code in (401, 403)
