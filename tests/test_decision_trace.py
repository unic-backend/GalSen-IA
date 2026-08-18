"""
Trace de décision (VOLET 22, chapitre 03 étape 10).

Le manuel décrit un moteur de décision à onze composants. Aucun n'existe. Mais
la plateforme **prend** bien une décision — `PlannerAgent` déduit des intentions
d'une demande les agents nécessaires — et cette décision est jetée : le pipeline
déclaré s'exécute en entier, quoi qu'elle dise. Une décision prise puis perdue
n'est ni enregistrée ni explicable.
"""

from src.router.decision_trace import decision_trace


def _planificateur(agents):
    """Résultat d'un planificateur recommandant `agents`."""
    return {"agent": "planner", "status": "success", "result": {"agents_required": list(agents)}}


def test_l_ecart_entre_la_decision_et_l_execution_est_visible():
    """Le cas mesuré : trois agents recommandés, neuf exécutés."""
    trace = decision_trace(
        [_planificateur(["researcher", "deployment", "monitor"])],
        ["router", "planner", "researcher", "coder", "tester", "deployment", "monitor"],
    )

    assert trace["recommended_agents"] == ["researcher", "deployment", "monitor"]
    assert trace["executed_not_recommended"] == ["coder", "planner", "tester"]
    assert trace["recommended_not_executed"] == []


def test_la_trace_dit_que_la_recommandation_n_est_pas_suivie():
    """
    Sans ce champ explicite, un lecteur croirait que la décision oriente
    l'exécution — c'est justement ce qu'elle ne fait pas.
    """
    trace = decision_trace([_planificateur(["monitor"])], ["monitor"])

    assert trace["applied"] is False
    assert "jamais suivie" in trace["detail"]


def test_l_orchestrateur_n_est_pas_compte_comme_un_agent():
    """Le routeur n'est dans aucune recommandation : il orchestre, il n'exécute pas."""
    trace = decision_trace([_planificateur(["monitor"])], ["router", "monitor"])

    assert "router" not in trace["executed_agents"]
    assert trace["executed_not_recommended"] == []


def test_sans_planificateur_aucune_decision_n_est_inventee():
    """
    « Le planificateur n'a pas tourné » et « il n'a rien recommandé » sont deux
    cas différents. Les confondre ferait passer une absence pour un choix.
    """
    trace = decision_trace([{"agent": "coder", "status": "success"}], ["coder"])

    assert trace["recommended_agents"] is None
    assert "n'a pas tourné" in trace["detail"]


def test_une_recommandation_vide_reste_une_decision():
    """Décider de ne mobiliser personne est une décision, et se distingue de rien."""
    trace = decision_trace([_planificateur([])], ["coder"])

    assert trace["recommended_agents"] == []
    assert trace["executed_not_recommended"] == ["coder"]


def test_un_agent_recommande_et_non_execute_est_signale():
    """Le manque est le symétrique du coût, et se lit aussi mal sans mesure."""
    trace = decision_trace([_planificateur(["monitor", "security"])], ["monitor"])

    assert trace["recommended_not_executed"] == ["security"]


def test_un_planificateur_en_echec_ne_rend_pas_de_recommandation():
    """Un résultat sans `agents_required` n'est pas une liste vide."""
    trace = decision_trace(
        [{"agent": "planner", "status": "error", "result": {}}], ["planner"],
    )

    assert trace["recommended_agents"] is None
