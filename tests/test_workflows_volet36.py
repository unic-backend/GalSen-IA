"""
Les quatre agents du VOLET 36 étaient injoignables (workflows, 2026-08-13).

Ils sont déclarés au registre depuis les chapitres D et G, et **aucun workflow
ne les citait**. Ce n'est pas un détail de configuration : la sélection du
planificateur **restreint** un pipeline et ne l'élargit jamais — c'est
l'invariant de sécurité du VOLET 22 — donc les axes `risk` et
`geographic_scope` recommandaient `verifier` et `senegal` à une exécution qui ne
pouvait pas les retenir.

Une capacité livrée que rien n'atteint est exactement le défaut que ce dépôt
traque depuis vingt-cinq VOLETs. Ces tests épinglent qu'elle est atteinte, et
que le tri promis par le chapitre F se produit vraiment.
"""

import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.planner.agent import AGENT_PAR_AXE, PlannerAgent  # noqa: E402
from src.agent.context import AgentContext  # noqa: E402
from src.router.decision_trace import selection_appliquee  # noqa: E402
from src.router.workflow_loader import WorkflowLoader  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRE = os.path.join(RACINE, "workflows", "workflows.yaml")

#: Les quatre agents du VOLET 36 et le workflow qui les rend joignables.
ATTENDUS = {
    "senegal": "question",
    "verifier": "question",
    "knowledge_architect": "ingestion",
    "data_engineer": "series",
}


@pytest.fixture(scope="module")
def registre():
    """Le registre des workflows, tel qu'il est déclaré."""
    with open(REGISTRE, encoding="utf-8") as fichier:
        return yaml.safe_load(fichier)["workflows"]


def _pipeline(registre, nom):
    """Retourne le pipeline déclaré d'un workflow."""
    return list(registre[nom].get("pipeline", []))


def test_les_quatre_agents_sont_joignables_par_un_workflow(registre):
    """
    Le défaut que ces workflows réparent.

    Un agent au registre mais absent de tout pipeline est une capacité annoncée
    que rien n'exécute — et rien dans le dépôt ne le disait.
    """
    for agent, workflow in ATTENDUS.items():
        assert workflow in registre, f"Le workflow « {workflow} » n'existe pas"
        assert agent in _pipeline(registre, workflow), (
            f"« {agent} » n'est cité par aucun pipeline : il reste inatteignable"
        )


def test_le_registre_des_workflows_reste_valide():
    """Un workflow citant un agent inconnu casserait le chargement pour tous."""
    chargeur = WorkflowLoader(REGISTRE)

    assert chargeur.get_problems() == []
    for workflow in ATTENDUS.values():
        assert chargeur.is_executable(workflow)


# ----------------------------------------------------------------------
# Ce que les axes du chapitre F provoquent réellement
# ----------------------------------------------------------------------

def _recommandation(requete: str, **options):
    """Les agents recommandés par le planificateur pour cette demande."""
    contexte = AgentContext(request=requete, agent_id="planner", options=options or None)
    return PlannerAgent().perform(contexte)["agents_required"]


def test_une_question_senegalaise_a_risque_retient_les_deux_agents(registre):
    """
    Le chaînon complet : axe → recommandation → **exécution**.

    Sans le workflow, cette recommandation se heurtait à un pipeline qui ne
    contenait ni `senegal` ni `verifier`, et l'intersection vide faisait
    retomber l'orchestrateur sur le pipeline entier — l'inverse du tri voulu.
    """
    recommandes = _recommandation("Quelle loi encadre le foncier à Ziguinchor ?")
    retenus = selection_appliquee(_pipeline(registre, "question"), recommandes)

    assert AGENT_PAR_AXE["geographic_scope"] in retenus
    assert AGENT_PAR_AXE["risk"] in retenus


def test_une_question_ordinaire_ne_retient_aucun_des_deux(registre):
    """
    Le contre-test, et c'est lui qui donne son sens au précédent : un workflow
    qui ferait tourner `senegal` sur toute question ne trierait rien.
    """
    recommandes = _recommandation("Comment fonctionne l'irrigation goutte à goutte ?")
    retenus = selection_appliquee(_pipeline(registre, "question"), recommandes)

    assert retenus is not None, (
        "L'intersection est vide : l'orchestrateur retomberait sur le pipeline "
        "entier, et le tri promis par les axes n'aurait pas lieu"
    )
    assert set(retenus).isdisjoint(set(AGENT_PAR_AXE.values()))


def test_le_workflow_question_declare_la_selection(registre):
    """
    Le branchement reste une option déclarée, jamais un comportement caché —
    même règle que pour `standard`.
    """
    execution = registre["question"].get("execution") or {}

    assert execution.get("agent_selection") == "planner"


def test_l_ordre_de_question_est_une_dependance(registre):
    """
    `verifier` confronte des affirmations à des passages : il lui faut ce que
    les agents précédents ont rendu. L'ordre n'est pas une préférence.
    """
    pipeline = _pipeline(registre, "question")

    assert pipeline.index("verifier") > pipeline.index("researcher")
    assert pipeline.index("senegal") > pipeline.index("planner")


@pytest.mark.parametrize("workflow", ["ingestion", "series"])
def test_les_agents_qui_proposent_restent_seuls_dans_leur_pipeline(registre, workflow):
    """
    Classer un document ou décrire une série n'a rien à voir avec répondre.
    Les glisser dans `question` ferait tourner l'architecte à chaque question.
    """
    pipeline = _pipeline(registre, workflow)

    assert len(pipeline) == 1
    assert pipeline[0] in ATTENDUS
    assert (registre[workflow].get("execution") or {}).get("agent_selection") is None
