"""
Où passe le temps d'une orchestration (VOLET 19, chapitre 03 étapes 5 et 7).

Seule la durée **totale** d'une requête était mesurée. L'orchestration ne
pouvait donc pas nommer son propre goulot d'étranglement : l'historique disait
« 45 s » et rien ne disait pourquoi. Mesuré sur le pipeline livré, un seul agent
consommait 96 % du temps de chaque requête, quelle qu'elle soit.
"""

import pytest

from src.router.workflow_history import WorkflowHistory


@pytest.fixture
def historique():
    """Historique vide."""
    return WorkflowHistory()


def test_la_duree_de_chaque_agent_est_conservee(historique):
    """Elle n'était nulle part : seul le total l'était."""
    historique.record("standard", "success", 45.2,
                      agent_durations={"tester": 43.5, "planner": 0.1})

    assert historique.recent(1)[0]["agent_durations"] == {"tester": 43.5, "planner": 0.1}


def test_le_goulot_d_etranglement_ressort_en_tete(historique):
    """C'est la mesure qui motivait tout : nommer l'agent qui coûte."""
    historique.record("standard", "success", 45.2,
                      agent_durations={"tester": 43.5, "researcher": 1.25, "planner": 0.09})

    temps = historique.stats("standard")["agent_time"]
    assert list(temps)[0] == "tester"
    assert temps["tester"]["share"] > 0.95


def test_le_temps_s_additionne_sur_plusieurs_executions(historique):
    """Un agent lent une fois n'est pas un agent lent ; la somme le dit."""
    for _ in range(3):
        historique.record("standard", "success", 10.0, agent_durations={"tester": 9.0})

    temps = historique.stats()["agent_time"]
    assert temps["tester"]["executions"] == 3
    assert temps["tester"]["total_seconds"] == 27.0


def test_la_part_se_calcule_sur_le_temps_d_agent(historique):
    """
    Pas sur la durée des requêtes : ce qui se passe entre deux agents
    n'appartient à aucun d'eux, et rapporter une part sur le total ferait
    croire à du temps perdu là où il n'y en a pas.
    """
    historique.record("standard", "success", 100.0,
                      agent_durations={"a": 3.0, "b": 1.0})

    temps = historique.stats()["agent_time"]
    assert temps["a"]["share"] == 0.75
    assert temps["b"]["share"] == 0.25


def test_sans_mesure_le_rapport_est_vide(historique):
    """Une répartition inventée sur zéro mesure serait pire que vide."""
    historique.record("standard", "success", 5.0)

    assert historique.stats()["agent_time"] == {}


def test_le_temps_suit_le_filtre_par_workflow(historique):
    """Regarder un workflow ne doit pas ramener le temps d'un autre."""
    historique.record("standard", "success", 5.0, agent_durations={"tester": 4.0})
    historique.record("revue", "success", 2.0, agent_durations={"reviewer": 1.5})

    assert list(historique.stats("standard")["agent_time"]) == ["tester"]
