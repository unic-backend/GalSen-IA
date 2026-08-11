"""
Sélection des agents par le planificateur (P1 du backlog, suite du VOLET 22).

Le pipeline `standard` tournait en entier pour toute demande : « bonjour »
coûtait 45,2 s, dont 43,5 s dans l'agent `tester` qui exécute toute la suite
pytest du projet. Le planificateur calculait déjà les agents nécessaires — 3 sur
9 pour une demande de supervision — et sa décision était jetée.

Elle est désormais suivie, pour les workflows qui le **déclarent**
(`execution.agent_selection: planner`), et seulement pour restreindre.
"""

import os

import pytest
import yaml

os.environ.setdefault("GALSEN_API_KEYS", "test-key-0123456789abcdef")

from src.router.decision_trace import decision_trace, recommended_agents  # noqa: E402
from src.router.workflow_loader import WorkflowLoader  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRE = os.path.join(RACINE, "workflows", "workflows.yaml")


def _planificateur(agents):
    """Résultat d'un planificateur recommandant `agents`."""
    return {"agent": "planner", "status": "success",
            "result": {"agents_required": list(agents)}}


def test_le_workflow_standard_declare_la_selection():
    """Le branchement est une option déclarée, pas un comportement caché."""
    registre = yaml.safe_load(open(REGISTRE, encoding="utf-8"))
    execution = registre["workflows"]["standard"].get("execution") or {}

    assert execution.get("agent_selection") == "planner"


def test_le_workflow_revue_ne_la_declare_pas():
    """Un workflow de deux agents n'a rien à restreindre : le contre-cas existe."""
    registre = yaml.safe_load(open(REGISTRE, encoding="utf-8"))
    execution = registre["workflows"]["revue"].get("execution") or {}

    assert execution.get("agent_selection") is None


def test_le_registre_reste_valide_avec_la_nouvelle_cle():
    """Une clé inconnue est signalée par le validateur : celle-ci doit être connue."""
    chargeur = WorkflowLoader(REGISTRE)
    chargeur.validate(["router", "planner", "researcher", "coder", "reviewer",
                       "tester", "security", "documentation", "deployment", "monitor"])

    bloquants = [p.message for p in chargeur.get_problems("standard") if p.gravite == "error"]
    assert bloquants == []
    assert chargeur.is_executable("standard")


def test_la_recommandation_est_lisible_depuis_les_resultats():
    """C'est le point d'entrée du branchement."""
    assert recommended_agents([_planificateur(["monitor"])]) == ["monitor"]
    assert recommended_agents([{"agent": "coder", "status": "success"}]) is None


def test_la_trace_declare_que_la_decision_a_ete_suivie():
    """
    `applied` disait toujours `false`. Le laisser à `false` alors que la
    sélection s'applique serait le mensonge inverse de celui du VOLET 22.
    """
    trace = decision_trace([_planificateur(["monitor"])], ["planner", "monitor"], applied=True)

    assert trace["applied"] is True
    assert "restreint le pipeline" in trace["detail"]


def test_la_trace_reste_honnete_quand_la_selection_ne_s_applique_pas():
    """Un workflow qui ne déclare pas l'option garde l'ancien constat."""
    trace = decision_trace([_planificateur(["monitor"])], ["planner", "coder", "monitor"])

    assert trace["applied"] is False
    assert "jamais suivie" in trace["detail"]


def test_le_repli_du_planificateur_ne_lance_plus_la_suite_de_tests():
    """
    Une demande non reconnue tombait sur `research` **et** `quality`, et
    `quality` mobilise `tester` : « bonjour » exécutait toute la suite pytest —
    43 secondes pour vérifier un code que personne n'avait produit. Comprendre
    une demande, c'est la chercher, pas la tester.
    """
    from agents.planner.agent import PlannerAgent

    assert PlannerAgent.FALLBACK_INTENTS == ("research",)
    agents_de_repli = {
        agent
        for intention in PlannerAgent.FALLBACK_INTENTS
        for agent in PlannerAgent.INTENT_RULES[intention]["agents"]
    }
    assert "tester" not in agents_de_repli


def test_une_demande_de_test_mobilise_toujours_le_testeur():
    """Le contre-test : la réduction ne doit pas rendre `tester` inatteignable."""
    from agents.planner.agent import PlannerAgent

    assert "tester" in PlannerAgent.INTENT_RULES["quality"]["agents"]
    mots = PlannerAgent.INTENT_RULES["quality"]["keywords"]
    assert "tester" in mots and "test" in mots


def test_les_accents_ne_changent_pas_l_intention_detectee():
    """
    « deploiement » est la façon dont on tape sur un clavier sénégalais, et le
    backlog le note depuis longtemps. Depuis que la recommandation pilote
    l'exécution, une intention manquée ne coûte plus un agent inutile : elle
    coûte un agent **absent**.
    """
    from agents.planner.agent import PlannerAgent

    planificateur = PlannerAgent()
    assert planificateur._detect_intents("Preparer un deploiement") == \
        planificateur._detect_intents("Préparer un déploiement")


def test_un_mot_cle_doit_commencer_un_mot():
    """
    « veille » se trouvait dans « surveiller » : toute demande de supervision
    déclenchait aussi une recherche. Le début de mot est exigé, la fin ne l'est
    pas — « application » doit encore reconnaître « applications ».
    """
    from agents.planner.agent import PlannerAgent

    planificateur = PlannerAgent()

    assert planificateur._detect_intents("Surveiller les logs") == ["monitoring"]
    assert "implementation" in planificateur._detect_intents("developper des applications")


def test_une_demande_de_deploiement_mobilise_le_testeur():
    """
    Préparer une mise en production sans savoir si les tests passent, c'est la
    vitesse préférée à la vérité que la constitution écarte (VOLET 01, ch. 04).
    L'agent de déploiement lit ce verdict et rapporte `test_state.known: false`
    sans lui.
    """
    from agents.planner.agent import PlannerAgent

    assert "tester" in PlannerAgent.INTENT_RULES["deployment"]["agents"]
