"""
Gestionnaire d'agents : décomposition, délégation, état partagé (VOLET 29).

Ce qui existait : le planificateur découpait une demande en tâches ordonnées et
les assignait à des agents. Ce qui manquait, et qui était mesurable :

- **Personne ne lisait l'assignation.** `coder` vérifiait qu'un plan *existait*
  puis rapportait `plan_followed: true` — vrai sur l'existence du plan, faux sur
  son suivi.
- **Aucune délégation.** Un agent pouvait lire ce que les précédents avaient
  produit ; il ne pouvait rien demander à un autre.
- **Aucun état de travail partagé.** `previous_results` est un compte rendu de ce
  qui est fini, pas un espace où déposer une observation en cours de route.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.planner.agent import PlannerAgent  # noqa: E402
from src.agent.blackboard import Blackboard  # noqa: E402
from src.agent.context import MAX_DELEGATION_DEPTH, AgentContext  # noqa: E402

DEMANDE = "Développer une API de conseil agricole sécurisée et la déployer"


@pytest.fixture
def plan():
    """Plan réel, produit par le planificateur sur une demande composite."""
    return PlannerAgent().perform(AgentContext(request=DEMANDE, agent_id="planner"))


@pytest.fixture
def contexte(plan):
    """Contexte d'un agent qui suit le planificateur."""
    return AgentContext(
        request=DEMANDE,
        agent_id="coder",
        previous_results=[{"agent": "planner", "status": "success", "result": plan}],
    )


# ----------------------------------------------------------------------
# Décomposition d'objectif : le plan est lu, pas seulement produit
# ----------------------------------------------------------------------

def test_le_plan_assigne_une_tache_a_un_agent(plan):
    """Une tâche sans agent responsable ne peut être suivie par personne."""
    assert plan["tasks"], "Le planificateur n'a produit aucune tâche"
    for tache in plan["tasks"]:
        assert tache["assigned_agent"], f"Tâche sans responsable : {tache['id']}"
        assert tache["assigned_agent"] in tache["assigned_agents"]


def test_un_agent_lit_les_taches_qui_lui_reviennent(contexte):
    """Le fait qui manquait : l'assignation est écrite depuis le début, jamais lue."""
    taches = contexte.tasks_for()

    assert taches, "Le codeur ne voit aucune tâche alors que la demande en contient"
    assert all(tache["assigned_agent"] == "coder" for tache in taches)


def test_chaque_agent_voit_ses_taches_et_pas_celles_des_autres(contexte):
    """Sinon « assigner » ne veut rien dire."""
    du_codeur = {tache["id"] for tache in contexte.tasks_for("coder")}
    de_la_securite = {tache["id"] for tache in contexte.tasks_for("security")}

    assert du_codeur and de_la_securite
    assert du_codeur.isdisjoint(de_la_securite)


def test_sans_planificateur_aucune_tache_n_est_inventee():
    """Un agent qui tourne seul ne doit pas croire suivre un plan."""
    contexte = AgentContext(request=DEMANDE, agent_id="coder")

    assert contexte.tasks() == []
    assert contexte.tasks_for() == []


def test_le_codeur_ne_pretend_plus_suivre_un_plan_vide():
    """
    `plan_followed: bool(plan)` était vrai dès qu'un plan existait, même si
    aucune tâche n'était assignée au codeur. La mesure porte désormais sur les
    tâches reçues.
    """
    from agents.coder.agent import CoderAgent

    # Un plan qui ne confie rien au codeur.
    plan_sans_codeur = {"tasks": [
        {"id": "task_1", "assigned_agent": "security", "assigned_agents": ["security"]}
    ]}
    contexte = AgentContext(
        request="Auditer la sécurité", agent_id="coder",
        previous_results=[{"agent": "planner", "status": "success", "result": plan_sans_codeur}],
    )

    resultat = CoderAgent().perform(contexte)

    assert resultat["plan_followed"] is False
    assert resultat["assigned_tasks"] == []


def test_la_securite_est_detectee_sur_la_forme_courante():
    """
    « sécurisée » est la façon dont la demande s'écrit réellement.

    Le lexique ne contenait que « sécurité » et « sécuriser » : une API
    « sécurisée » ne déclenchait aucune analyse de sécurité, et depuis que la
    recommandation pilote l'exécution, une intention manquée coûte un agent
    absent.
    """
    plan = PlannerAgent().perform(
        AgentContext(request="Construire une API sécurisée", agent_id="planner")
    )

    assert "security" in plan["detected_intents"]


# ----------------------------------------------------------------------
# État de travail partagé
# ----------------------------------------------------------------------

def test_une_note_adressee_ne_va_qu_a_son_destinataire():
    """Sinon « adresser » ne veut rien dire."""
    tableau = Blackboard()
    tableau.post("sol", {"ph": 6.2}, author="researcher", to="coder")

    assert [note.value for note in tableau.read(pour="coder")] == [{"ph": 6.2}]
    assert tableau.read(pour="reviewer") == []


def test_une_note_sans_destinataire_est_lue_par_tous():
    """Une observation générale doit profiter à tout le monde."""
    tableau = Blackboard()
    tableau.post("météo", "saison des pluies", author="researcher")

    assert len(tableau.read(pour="coder")) == 1
    assert len(tableau.read(pour="reviewer")) == 1


def test_le_tableau_est_partage_par_les_contextes_derives():
    """
    Une copie ferait deux états de travail, et l'agent suivant ne verrait pas ce
    que son prédécesseur vient de déposer.
    """
    amont = AgentContext(request=DEMANDE, agent_id="researcher")
    amont.post("sol", {"ph": 6.2}, to="coder")

    aval = amont.derive("coder")

    assert aval.blackboard is amont.blackboard
    assert aval.read_notes("sol")[0]["value"] == {"ph": 6.2}


def test_le_tableau_est_borne():
    """Un état de travail qui grossit sans fin n'est plus un état de travail."""
    tableau = Blackboard(max_entries=5)
    for numero in range(20):
        tableau.post("mesure", numero, author="monitor")

    assert len(tableau) == 5
    # Ce sont les plus récentes qui restent : les anciennes décrivent un état dépassé.
    assert [note.value for note in tableau.read()] == [15, 16, 17, 18, 19]


# ----------------------------------------------------------------------
# Délégation
# ----------------------------------------------------------------------

def test_un_agent_peut_confier_un_travail_a_un_autre():
    """La capacité qui manquait : demander, et pas seulement lire après coup."""
    contexte = AgentContext(request="Analyser la sécurité du projet", agent_id="planner")

    resultat = contexte.delegate("security")

    assert resultat.get("status") == "success"
    assert resultat.get("agent") == "security"


def test_la_delegation_laisse_une_trace_sur_le_tableau():
    """Une délégation invisible rendrait le déroulé d'une requête indéchiffrable."""
    contexte = AgentContext(request="Analyser la sécurité", agent_id="planner")
    contexte.delegate("security")

    assert any(note["topic"] == "delegation" for note in contexte.read_notes())


def test_un_agent_ne_se_delegue_pas_a_lui_meme():
    """Le cycle le plus court, et le plus facile à écrire par accident."""
    contexte = AgentContext(request=DEMANDE, agent_id="coder")

    refus = contexte.delegate("coder")

    assert refus["status"] == "refused"
    assert refus["reason"] == "self_delegation"


def test_un_cycle_de_delegation_est_refuse():
    """A délègue à B, B ne doit pas redéléguer à A."""
    contexte = AgentContext(
        request=DEMANDE, agent_id="security",
        options={"delegation_chain": ["coder"]},
    )

    refus = contexte.delegate("coder")

    assert refus["status"] == "refused"
    assert refus["reason"] == "cycle"


def test_la_profondeur_de_delegation_est_bornee():
    """Sans borne, une décomposition devient une boucle qui consomme la requête."""
    contexte = AgentContext(
        request=DEMANDE, agent_id="coder", delegation_depth=MAX_DELEGATION_DEPTH,
    )

    refus = contexte.delegate("security")

    assert refus["status"] == "refused"
    assert refus["reason"] == "depth_exceeded"


def test_un_agent_inconnu_est_refuse_sans_lever():
    """L'appelant doit pouvoir continuer sans l'aide qu'il n'a pas obtenue."""
    contexte = AgentContext(request=DEMANDE, agent_id="coder")

    resultat = contexte.delegate("agent-qui-n-existe-pas")

    assert resultat["status"] in ("error", "refused")
    assert resultat.get("error") or resultat.get("detail")


def test_l_agent_delegue_partage_l_etat_de_la_requete():
    """
    Le sous-agent doit voir la même session et le même tableau : c'est ce qui
    distingue une délégation d'une exécution séparée.
    """
    contexte = AgentContext(request="Analyser la sécurité", agent_id="planner")
    contexte.post("consigne", "vérifier les secrets", to="security")

    contexte.delegate("security")

    # La note adressée à `security` reste lisible, et le tableau porte en plus
    # la trace de la délégation : un seul état de travail, pas deux.
    sujets = {note["topic"] for note in contexte.blackboard.snapshot()}
    assert {"consigne", "delegation"} <= sujets
