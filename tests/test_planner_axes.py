"""
Les dix axes d'une demande (VOLET 36, ch. F).

Le planificateur produisait des intentions et des tâches, et rien d'autre : rien
ne disait si une demande portait sur la santé, si elle concernait le Sénégal, ni
si la base savait quelque chose à son sujet.

Les axes ne sont **pas un second planificateur** — il n'y en a qu'un, et ce
chapitre ne devait pas en créer un deuxième. Ce sont des attributs de la demande,
attachés au plan que le planificateur produit déjà.

Deux axes agissent, huit sont observés. Ces tests épinglent la frontière : un axe
qui changerait le routage sans se voir est exactement ce qui rend un
planificateur inexplicable.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.planner.agent import (  # noqa: E402
    AGENT_PAR_AXE,
    AXES_OBSERVES,
    PlannerAgent,
)
from src.agent.context import AgentContext  # noqa: E402


def plan(requete: str, **options):
    """Le plan produit pour une demande."""
    return PlannerAgent().perform(
        AgentContext(request=requete, agent_id="planner", options=options or None)
    )


# ----------------------------------------------------------------------
# Les dix axes existent, chacun avec sa méthode
# ----------------------------------------------------------------------

def test_les_dix_axes_sont_rendus_avec_leur_methode():
    """
    La méthode voyage avec la valeur.

    `keywords` n'a pas la même valeur qu'une mesure, et `declared` encore moins
    qu'une détection : lu sans sa méthode, un axe passerait pour une observation
    dans les trois cas.
    """
    axes = plan("Comparer deux bibliothèques de graphes")["axes"]

    attendus = set(AXES_OBSERVES) | set(AGENT_PAR_AXE)
    assert set(axes) == attendus
    assert len(axes) == 10
    for nom, axe in axes.items():
        assert "value" in axe and axe["method"], f"L'axe « {nom} » ne dit pas d'où il vient"


def test_la_langue_est_declaree_et_le_dit():
    """
    Aucun détecteur de langue n'existe (ch. B). L'axe porte donc `detected:
    False` — sans quoi une langue déclarée passerait pour une langue reconnue.
    """
    axe = plan("Mbay mi ci Senegaal", language="wo")["axes"]["language"]

    assert axe["value"] == "wo"
    assert axe["method"] == "declared"
    assert axe["detected"] is False


def test_la_complexite_est_annoncee_grossiere():
    """
    Deux signaux — nombre d'intentions, longueur — ne mesurent pas une
    difficulté. L'axe rend une étiquette et le dit, plutôt qu'un chiffre qui
    serait lu comme une estimation d'effort.
    """
    axe = plan("Documenter et déployer l'API")["axes"]["complexity"]

    assert axe["method"] == "crude"
    assert axe["value"] in ("low", "moderate", "high")


def test_la_recherche_requise_est_mesuree_et_non_devinee():
    """
    Le seul axe adossé à une mesure : ce que la base porte réellement sur cette
    demande. Une base muette veut dire qu'il faut chercher.
    """
    axe = plan("Quelles variétés de mil pour le bassin arachidier ?")["axes"]["research_required"]

    assert axe["method"] == "measured"
    assert axe["value"] is (axe["knowledge_items"] == 0)


# ----------------------------------------------------------------------
# Les deux axes qui agissent
# ----------------------------------------------------------------------

def test_un_sujet_a_risque_recommande_le_verificateur():
    """
    Santé, droit et argent : une réponse fausse y coûte plus qu'ailleurs, et
    c'est là que la vérification des faits cesse d'être un luxe.
    """
    resultat = plan("Quel dosage de traitement contre le paludisme ?")

    assert resultat["axes"]["risk"]["value"] == "elevated"
    assert AGENT_PAR_AXE["risk"] in resultat["agents_required"]
    assert resultat["axes_effect"][0]["axis"] == "risk"


def test_une_question_senegalaise_recommande_l_agent_senegal():
    """
    Une ville suffit : « les prix à Kaolack » est une question sénégalaise qui
    ne prononce jamais « Sénégal ».
    """
    resultat = plan("Quels sont les prix du marché à Kaolack ?")

    assert resultat["axes"]["geographic_scope"]["value"] == "country:sn"
    assert AGENT_PAR_AXE["geographic_scope"] in resultat["agents_required"]


def test_une_demande_ordinaire_n_ajoute_aucun_agent():
    """
    Le contre-test qui donne son sens aux deux précédents : sans marqueur, rien
    ne s'ajoute. Un axe qui recommanderait toujours ne recommanderait rien.
    """
    resultat = plan("Documenter le module de journalisation")

    assert resultat["axes_effect"] == []
    assert set(AGENT_PAR_AXE.values()).isdisjoint(resultat["agents_required"])


def test_chaque_agent_ajoute_dit_quel_axe_l_a_ajoute():
    """
    La traçabilité du routage. Sans `axes_effect`, un agent apparaîtrait dans le
    plan sans que personne puisse dire pourquoi.
    """
    resultat = plan("Quelle loi encadre le foncier à Ziguinchor ?")

    ajouts = {effet["agent_added"]: effet["axis"] for effet in resultat["axes_effect"]}
    assert ajouts == {"verifier": "risk", "senegal": "geographic_scope"}
    for agent in ajouts:
        assert agent in resultat["agents_required"]


@pytest.mark.parametrize("axe", AXES_OBSERVES)
def test_les_huit_autres_axes_ne_changent_rien(axe):
    """
    Le cœur du chapitre.

    Les axes observés sont rendus et mesurés **avant** d'être branchés à quoi
    que ce soit : un axe branché avant d'avoir été lu sur de vraies demandes est
    une décision que personne n'a prise.
    """
    resultat = plan("Documenter le module de journalisation")

    assert axe in resultat["axes"]
    assert all(effet["axis"] != axe for effet in resultat["axes_effect"])


# ----------------------------------------------------------------------
# Ce que ce chapitre ne devait pas faire
# ----------------------------------------------------------------------

def test_il_n_y_a_toujours_qu_un_seul_planificateur():
    """
    Les axes sont un champ de plus sur le plan existant — pas un module, pas un
    agent, pas un second planificateur.
    """
    import yaml

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "agents", "registry.yaml"), encoding="utf-8") as fichier:
        registre = yaml.safe_load(fichier)

    planificateurs = [
        agent["id"] for agent in registre["agents"]
        if "plann" in agent["id"] or "plann" in agent.get("role", "").lower()
    ]
    assert planificateurs == ["planner"]


def test_le_plan_reste_deterministe():
    """
    Deux fois la même demande, deux fois les mêmes axes. Un axe qui varierait
    d'un appel à l'autre rendrait le plan irrelisible.
    """
    premier = plan("Quel dosage contre le paludisme à Dakar ?")
    second = plan("Quel dosage contre le paludisme à Dakar ?")

    assert premier["axes"] == second["axes"]
    assert premier["agents_required"] == second["agents_required"]
