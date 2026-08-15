"""
Un tour n'est pas une unité de coût (phase 67.1).

Le budget des routines comptait les **tours** : 288 par jour, soit la cadence
maximale que le plancher d'intervalle autorise. C'était juste tant qu'un tour
valait un appel d'outil. Depuis le VOLET 64, un tour peut faire tourner un
**workflow entier** — et une routine peut rester très en deçà de ses 288 tours en
exécutant huit agents à chaque fois. Le jour où quelqu'un ajoute un agent au
workflow, la dépense augmente d'un tiers sans qu'aucun budget ne bouge.

Ce que ces tests gardent :

1. **Le travail est compté à part**, en agents réellement exécutés.
2. **Il est décompté après l'exécution** : le coût d'un workflow n'est pas connu
   avant de l'avoir fait tourner, et refuser sur une estimation refuserait à
   tort.
3. **Un dépassement arrête la routine**, comme le budget en tours — il ne la
   saute pas en silence.
4. **Un appel d'outil ne consomme aucun travail** : il n'exécute aucun agent.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.routines import (  # noqa: E402
    AGENTS_PAR_FENETRE_PAR_DEFAUT,
    RoutineAction,
    RoutineRegistry,
    RoutineSafety,
    RoutineScheduler,
    WorkflowAction,
)

HEURE = 3600


class _Orchestrateur:
    """Un orchestrateur qui rapporte le nombre d'agents qu'il a exécutés."""

    def __init__(self, agents=8, statut="success"):
        self.agents = agents
        self.statut = statut

    def process_request(self, user_request, **_):
        return {
            "status": self.statut,
            "run_id": "run-1",
            "metadata": {"total_agents_executed": self.agents},
        }


class _Moteur:
    """Un moteur d'outils qui réussit."""

    def execute_tool(self, *args, **kwargs):
        return {"status": "success"}


def _routine_de_workflow(registre, identifiant="veille"):
    """Une routine qui déclenche un workflow, active."""
    routine = registre.declare(
        identifiant, "Un workflow chaque heure.",
        [WorkflowAction(workflow_id="standard")],
        interval_seconds=HEURE, subject="awa",
    )
    registre.enable(routine.routine_id)
    return routine


# ----------------------------------------------------------------------
# 1. Le travail est compté, et il est compté à part
# ----------------------------------------------------------------------

def test_un_tour_de_workflow_consomme_du_travail():
    """Huit agents exécutés coûtent huit, pas un tour."""
    registre = RoutineRegistry()
    surete = RoutineSafety()
    routine = _routine_de_workflow(registre)
    planificateur = RoutineScheduler(
        registre, safety=surete, orchestrator=_Orchestrateur(agents=8),
    )

    planificateur.run(routine, now=1000.0)

    budget = surete.budget_state(routine.routine_id)
    assert budget["runs"] == 1
    assert budget["agents"] == 8


def test_un_appel_d_outil_ne_consomme_aucun_travail():
    """Il n'exécute aucun agent : lui en compter serait une invention."""
    registre = RoutineRegistry()
    surete = RoutineSafety()
    routine = registre.declare(
        "outil", "Un appel d'outil.", [RoutineAction("metrics", "read")],
        interval_seconds=HEURE, subject="awa",
    )
    registre.enable(routine.routine_id)
    planificateur = RoutineScheduler(registre, tool_engine=_Moteur(), safety=surete)

    planificateur.run(routine, now=1000.0)

    assert surete.budget_state(routine.routine_id)["agents"] == 0


def test_le_travail_est_decompte_meme_quand_le_tour_echoue():
    """Un budget qui n'enregistre que les succès se laisse épuiser par les
    échecs."""
    registre = RoutineRegistry()
    surete = RoutineSafety()
    routine = _routine_de_workflow(registre)
    planificateur = RoutineScheduler(
        registre, safety=surete,
        orchestrator=_Orchestrateur(agents=5, statut="partial_success"),
    )

    tour = planificateur.run(routine, now=1000.0)

    assert tour.ok is False
    assert surete.budget_state(routine.routine_id)["agents"] == 5


# ----------------------------------------------------------------------
# 2. Le plafond arrête, il ne saute pas
# ----------------------------------------------------------------------

def test_un_plafond_de_travail_depasse_arrete_la_routine():
    """Comme le budget en tours : une routine sautée en silence paraît tourner."""
    registre = RoutineRegistry()
    surete = RoutineSafety()
    routine = _routine_de_workflow(registre)
    surete.set_agent_limit(routine.routine_id, 10)
    planificateur = RoutineScheduler(
        registre, safety=surete, orchestrator=_Orchestrateur(agents=8),
    )

    planificateur.run(routine, now=1000.0)           # 8 agents, sous le plafond
    planificateur.run(routine, now=1000.0 + HEURE)   # 16 : au-dessus
    tour = planificateur.run(routine, now=1000.0 + 2 * HEURE)

    assert "Budget épuisé" in tour.skipped
    assert "agents" in tour.skipped
    assert routine.enabled is False


def test_le_depassement_nomme_le_travail_et_non_les_tours():
    """Un exploitant doit savoir lequel des deux plafonds a cédé."""
    surete = RoutineSafety()
    surete.set_agent_limit("veille", 4)
    surete.consume_work("veille", 9, now=1000.0)

    permis, motif = surete.check("veille", now=1000.0)

    assert permis is False
    assert "9 agents exécutés" in motif
    assert "les tours restaient dans le leur" in motif


def test_les_tours_restent_plafonnes_independamment():
    """Les deux plafonds ne se remplacent pas."""
    surete = RoutineSafety()
    surete.set_limit("veille", 1)
    surete.consume("veille", now=1000.0)

    permis, motif = surete.check("veille", now=1000.0)

    assert permis is False
    assert "tours dans la fenêtre" in motif


def test_un_plafond_de_travail_nul_est_refuse():
    """Ce serait une désactivation déguisée."""
    with pytest.raises(ValueError):
        RoutineSafety().set_agent_limit("veille", 0)


# ----------------------------------------------------------------------
# 3. Le défaut ne restreint rien de ce qui tourne déjà
# ----------------------------------------------------------------------

def test_le_defaut_couvre_la_cadence_maximale_du_plus_gros_workflow():
    """288 tours × 8 agents : il attrape ce qui change, pas ce qui existe."""
    assert AGENTS_PAR_FENETRE_PAR_DEFAUT == 288 * 8


def test_le_rapport_dit_pourquoi_le_travail_est_plafonne_a_part():
    """La règle est écrite, pas seulement appliquée."""
    regles = " ".join(RoutineSafety().safety_report()["rules"])

    assert "Un tour n'est pas une unité de coût" in regles
    assert "**après** l'exécution" in regles


# ----------------------------------------------------------------------
# 4. La route
# ----------------------------------------------------------------------

@pytest.fixture
def client_budget(monkeypatch):
    """Client HTTP, clé nommée et registre neuf."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    monkeypatch.setattr(server_module, "routine_registry", RoutineRegistry())
    monkeypatch.setattr(server_module, "routine_safety", RoutineSafety())
    with TestClient(server_module.app) as essai:
        yield essai, {"X-API-Key": "cle-awa"}, server_module
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def test_la_route_fixe_les_deux_plafonds(client_budget):
    """Les tours et le travail se règlent au même endroit."""
    client, cle, serveur = client_budget
    _routine_de_workflow(serveur.routine_registry)

    reponse = client.put(
        "/routines/veille/budget",
        json={"runs_per_day": 24, "agents_per_day": 200}, headers=cle,
    ).json()

    assert reponse["runs_per_day"] == 24
    assert reponse["agents_per_day"] == 200


def test_la_route_conserve_le_plafond_en_place_si_rien_n_est_demande(client_budget):
    """Ne pas nommer un plafond n'est pas le remettre à zéro."""
    client, cle, serveur = client_budget
    _routine_de_workflow(serveur.routine_registry)

    reponse = client.put(
        "/routines/veille/budget", json={"runs_per_day": 24}, headers=cle,
    ).json()

    assert reponse["agents_per_day"] == AGENTS_PAR_FENETRE_PAR_DEFAUT
