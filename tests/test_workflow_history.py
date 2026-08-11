"""
Tests de l'historique d'exécution des workflows (VOLET 08, ch. 03 et 09).

Chaque exécution rapportait son statut et disparaissait : impossible de dire si
un workflow échouait une fois sur dix ou neuf fois sur dix. Le chapitre 09 fait
pourtant du taux de succès sa première métrique.
"""

import pytest

from src.router.workflow_history import DEFAULT_CAPACITY, WorkflowHistory


@pytest.fixture
def historique():
    """Journal d'exécution vide."""
    return WorkflowHistory()


def test_sans_execution_le_taux_est_indefini(historique):
    """`None` et non 0.0 : zéro exécution ne veut pas dire que tout échoue."""
    stats = historique.stats()
    assert stats["executions"] == 0
    assert stats["success_rate"] is None
    assert stats["median_duration_seconds"] is None


def test_le_taux_de_succes_compte_les_echecs(historique):
    """Un taux qui n'observe que les réussites vaut toujours 100 %."""
    historique.record("revue", "success", 0.2)
    historique.record("revue", "success", 0.3)
    historique.record("revue", "error", 0.1)

    stats = historique.stats()
    assert stats["executions"] == 3
    assert stats["by_status"] == {"success": 2, "error": 1}
    assert stats["success_rate"] == round(2 / 3, 4)


def test_les_statistiques_se_filtrent_par_workflow(historique):
    """Un workflow lent ne doit pas être masqué par la moyenne d'un autre."""
    historique.record("revue", "success", 0.2)
    historique.record("standard", "error", 90.0)

    assert historique.stats("revue")["success_rate"] == 1.0
    assert historique.stats("standard")["success_rate"] == 0.0
    assert historique.stats()["executions"] == 2


def test_les_executions_recentes_sont_dans_l_ordre_inverse(historique):
    """La plus récente d'abord : c'est celle qu'on regarde après un incident."""
    historique.record("revue", "success", 0.1, request_id="req_1")
    historique.record("revue", "error", 0.2, request_id="req_2")

    recentes = historique.recent(limit=5)
    assert [e["request_id"] for e in recentes] == ["req_2", "req_1"]


def test_l_historique_est_borne():
    """Un historique non borné est la dette que le journal a déjà coûtée."""
    historique = WorkflowHistory(capacity=3)
    for i in range(10):
        historique.record("revue", "success", 0.1, request_id=f"req_{i}")

    stats = historique.stats()
    assert stats["executions"] == 3
    assert stats["capacity"] == 3
    assert [e["request_id"] for e in historique.recent(10)] == ["req_9", "req_8", "req_7"]


def test_la_requete_utilisateur_n_est_pas_conservee(historique):
    """Mesurer un workflow n'est pas archiver ce que les gens demandent."""
    historique.record("revue", "success", 0.2, request_id="req_1")
    entree = historique.recent(1)[0]
    assert set(entree) == {"workflow", "status", "duration_seconds", "agents_executed",
                           "failed_agents", "request_id", "at"}


def test_la_portee_est_annoncee(historique):
    """Le rapport dit que l'historique meurt avec le processus (ADR-009)."""
    historique.record("revue", "success", 0.2)
    assert "processus" in historique.stats()["scope"]
    assert historique.stats()["capacity"] == DEFAULT_CAPACITY


def test_le_moteur_enregistre_ses_executions():
    """De bout en bout : une exécution réelle et un échec réel sont comptés."""
    import logging
    logging.disable(logging.ERROR)
    from src.router.router_engine import RouterEngine

    moteur = RouterEngine()
    moteur.history.clear()
    moteur.process_request("Relire le code", workflow_id="revue")
    moteur.process_request("Workflow absent", workflow_id="fantome_inexistant")
    logging.disable(logging.NOTSET)

    stats = moteur.history.stats()
    assert stats["executions"] == 2
    assert stats["by_status"].get("success") == 1
    assert stats["by_status"].get("error") == 1
    assert stats["success_rate"] == 0.5
