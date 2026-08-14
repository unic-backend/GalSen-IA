"""
Le routeur passe par ses points de reprise (phase 49.2).

La phase 49.1 a construit le point de reprise ; celle-ci le branche sur le
chemin réel. Ce qui compte ici n'est pas que l'objet existe, c'est qu'une
exécution interrompue **reprenne** : les tests conduisent donc `RouterEngine`
de bout en bout, avec un répartiteur d'agents contrôlé, et comptent ce qui a
réellement tourné.

Trois choses que ces tests gardent :

1. **Un agent déjà abouti ne retourne pas au feu.** C'est la règle entière du
   VOLET : refaire une étape qui a eu un effet au-dehors est la façon dont un
   courriel devient deux.
2. **Une étape qui attend une approbation n'est pas consignée.** La marquer
   aboutie ferait passer la décision humaine pour acquise.
3. **Le point de reprise n'échoue jamais la requête qu'il observe.** C'est un
   filet, pas un maillon.
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.router.router_engine import RouterEngine  # noqa: E402
from src.router.workflow_checkpoint import (  # noqa: E402
    CheckpointRefused,
    RunStatus,
    WorkflowCheckpoints,
)

#: Le workflow le plus court du dépôt : deux agents, exécutés en séquence.
WORKFLOW = "revue"
ETAPES = ["reviewer", "security"]


@pytest.fixture(autouse=True)
def silence():
    """Le routeur journalise ses échecs ; ils sont attendus ici."""
    logging.disable(logging.ERROR)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture
def moteur():
    """
    Un routeur dont le répartiteur est contrôlé.

    Les réessais sont ramenés à une tentative : ce qui est éprouvé ici est le
    point de reprise, pas le gestionnaire de réessais, et trois tentatives
    coûteraient deux secondes d'attente par agent en échec.
    """
    routeur = RouterEngine()
    routeur.retry_manager.max_attempts = 1
    routeur.retry_manager.delay_seconds = 0
    return routeur


def _repartiteur(lances, echec_sur=None, statut="error"):
    """Un répartiteur qui note ce qu'on lui demande et échoue où on le dit."""

    def repartir(agent_config, input_data, context=None):
        agent_id = agent_config.get("id")
        lances.append(agent_id)
        if agent_id == echec_sur:
            return {"agent": agent_id, "status": statut, "error": "panne simulée"}
        return {"agent": agent_id, "status": "success", "result": f"sortie de {agent_id}"}

    return repartir


# ----------------------------------------------------------------------
# 1. Une exécution réelle ouvre, remplit et ferme son point de reprise
# ----------------------------------------------------------------------

def test_une_execution_rend_l_identifiant_de_son_point_de_reprise(moteur):
    """Sans lui, personne ne peut reprendre ce qui vient d'échouer."""
    lances = []
    moteur._dispatch_agent = _repartiteur(lances)

    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    assert reponse["run_id"].startswith("run_")
    assert moteur.checkpoints.get(reponse["run_id"]) is not None


def test_une_execution_complete_est_marquee_terminee(moteur):
    """Et n'est donc plus reprenable : la relancer refarait un travail fait."""
    moteur._dispatch_agent = _repartiteur([])

    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    point = moteur.checkpoints.get(reponse["run_id"])
    assert point.status is RunStatus.COMPLETED
    assert point.done_agents == ETAPES


def test_une_execution_interrompue_reste_reprenable(moteur):
    """Un échec en cours de route n'est pas une fin."""
    moteur._dispatch_agent = _repartiteur([], echec_sur="security")

    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    point = moteur.checkpoints.get(reponse["run_id"])
    assert point.status is RunStatus.FAILED
    assert point.next_step() == "security"


def test_une_exception_avant_le_premier_agent_ne_laisse_pas_de_point(moteur):
    """Un workflow inexistant n'ouvre rien : il n'y a rien à reprendre."""
    reponse = moteur.process_request("x", workflow_id="fantome_inexistant")

    assert reponse["status"] == "error"
    assert "run_id" not in reponse


# ----------------------------------------------------------------------
# 2. La reprise ne refait pas ce qui a abouti
# ----------------------------------------------------------------------

def test_un_agent_deja_abouti_ne_retourne_pas_au_feu(moteur):
    """
    Le point de tout le VOLET, mesuré sur le chemin réel : on compte les
    agents réellement lancés, pas ce que le compte rendu affirme.
    """
    premier = []
    moteur._dispatch_agent = _repartiteur(premier, echec_sur="security")
    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    second = []
    moteur._dispatch_agent = _repartiteur(second)
    moteur.process_request("Relire le code", resume_run_id=reponse["run_id"])

    assert premier == ETAPES
    assert second == ["security"], "reviewer avait abouti : il ne se relance pas"


def test_la_reprise_termine_l_execution(moteur):
    """Reprendre sert à finir, pas seulement à ne pas refaire."""
    moteur._dispatch_agent = _repartiteur([], echec_sur="security")
    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    moteur._dispatch_agent = _repartiteur([])
    reprise = moteur.process_request("Relire le code", resume_run_id=reponse["run_id"])

    assert reprise["run_id"] == reponse["run_id"]
    assert moteur.checkpoints.get(reponse["run_id"]).status is RunStatus.COMPLETED


def test_la_production_des_etapes_abouties_revient_dans_le_compte_rendu(moteur):
    """
    Sinon la reprise rendrait une réponse amputée de la moitié du travail, et
    l'agent suivant ne verrait pas ce qui l'a précédé.
    """
    moteur._dispatch_agent = _repartiteur([], echec_sur="security")
    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    moteur._dispatch_agent = _repartiteur([])
    reprise = moteur.process_request("Relire le code", resume_run_id=reponse["run_id"])

    agents = [r.get("agent") for r in reprise["agent_results"]]
    assert agents == ETAPES
    assert reprise["metadata"]["resumed_steps"] == 1


def test_le_workflow_d_une_reprise_vient_du_point_de_reprise(moteur):
    """
    Reprendre sous un autre workflow serait en commencer un autre sous
    l'identifiant du premier, avec les étapes déjà faites de celui-ci.
    """
    moteur._dispatch_agent = _repartiteur([], echec_sur="security")
    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    moteur._dispatch_agent = _repartiteur([])
    reprise = moteur.process_request(
        "Relire le code", workflow_id="rangement", resume_run_id=reponse["run_id"]
    )

    assert reprise["workflow_used"] == WORKFLOW


def test_l_execution_d_une_autre_personne_ne_se_reprend_pas(moteur):
    """
    Reprendre le workflow d'autrui, ce serait lancer des agents sur ses
    données. Le refus **remonte** au lieu de devenir un compte rendu d'échec :
    rien n'a démarré, et une exécution qui n'a pas eu lieu ne doit pas peser
    sur le taux de succès des workflows.
    """
    moteur._dispatch_agent = _repartiteur([], echec_sur="security")
    reponse = moteur.process_request(
        "Relire le code", workflow_id=WORKFLOW, user_id="awa"
    )
    moteur.history.clear()

    lances = []
    moteur._dispatch_agent = _repartiteur(lances)
    with pytest.raises(CheckpointRefused, match="inconnue"):
        moteur.process_request(
            "Relire le code", user_id="fatou", resume_run_id=reponse["run_id"]
        )

    assert lances == [], "Aucun agent ne doit tourner sur un refus"
    assert moteur.history.stats()["executions"] == 0


# ----------------------------------------------------------------------
# 3. Ce qui n'a pas tourné, et ce qui n'a pas fini
# ----------------------------------------------------------------------

def test_une_etape_en_attente_d_approbation_n_est_pas_consignee(moteur):
    """
    La marquer aboutie ferait passer la décision humaine pour acquise. Elle
    reste à faire, et la reprise la relancera une fois la décision prise.
    """
    moteur._dispatch_agent = _repartiteur(
        [], echec_sur="reviewer", statut="requires_approval"
    )

    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    point = moteur.checkpoints.get(reponse["run_id"])
    assert point.done_agents == []
    assert point.next_step() == "reviewer"


def test_un_agent_desactive_est_marque_saute_et_l_execution_se_termine(moteur):
    """
    Un agent désactivé ne tournera pas davantage à la reprise : le laisser
    « à faire » rendrait l'exécution indéfiniment inachevée.
    """
    moteur._dispatch_agent = _repartiteur([])
    moteur.agent_loader.is_enabled = lambda agent_id: agent_id != "security"

    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    point = moteur.checkpoints.get(reponse["run_id"])
    assert point.status is RunStatus.COMPLETED
    saut = [e for e in point.completed if e.agent_id == "security"][0]
    assert "désactivé" in saut.skipped
    assert saut.output == "", "Une étape sautée ne prétend rien avoir produit"


def test_une_etape_sautee_n_est_pas_rejouee_comme_un_resultat(moteur):
    """Elle n'a rien produit : la rejouer inventerait une sortie."""
    moteur._dispatch_agent = _repartiteur([], echec_sur="reviewer")
    moteur.agent_loader.is_enabled = lambda agent_id: agent_id != "security"
    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    moteur._dispatch_agent = _repartiteur([])
    reprise = moteur.process_request("Relire le code", resume_run_id=reponse["run_id"])

    assert [r.get("agent") for r in reprise["agent_results"]] == ["reviewer"]


def test_un_point_de_reprise_en_echec_ne_fait_pas_echouer_la_requete(moteur):
    """
    Il est un filet, pas un maillon. Ici l'exécution est annulée pendant
    qu'elle tourne : consigner devient impossible, la requête aboutit quand
    même.
    """
    lances = []
    normal = _repartiteur(lances)

    def annuler_puis_repartir(agent_config, input_data, context=None):
        resultat = normal(agent_config, input_data, context)
        for identifiant in list(moteur.checkpoints.list_runs()):
            moteur.checkpoints.cancel(
                identifiant["run_id"], reason="annulée en cours de route"
            )
        return resultat

    moteur._dispatch_agent = annuler_puis_repartir
    reponse = moteur.process_request("Relire le code", workflow_id=WORKFLOW)

    assert reponse["status"] in ("success", "partial_success")
    assert lances == ETAPES


# ----------------------------------------------------------------------
# 4. La borne, puisque le routeur en ouvre un par requête
# ----------------------------------------------------------------------

def test_les_terminees_sont_oubliees_avant_les_reprenables():
    """
    Oublier une exécution reprenable, c'est perdre la reprise elle-même. Elles
    partent en dernier.
    """
    points = WorkflowCheckpoints(max_runs=2)
    finie = points.start("w", ["a"])
    points.record_step(finie.run_id, "a", ok=True)
    vivante = points.start("w", ["a", "b"])
    points.record_step(vivante.run_id, "a", ok=False)

    points.start("w", ["a"])

    assert points.get(finie.run_id) is None
    assert points.get(vivante.run_id) is not None


def test_ce_qui_est_oublie_est_compte():
    """
    Une reprise devenue impossible parce que son point a été élagué doit avoir
    une cause visible.
    """
    points = WorkflowCheckpoints(max_runs=1)
    premiere = points.start("w", ["a"])
    points.record_step(premiere.run_id, "a", ok=False)
    points.start("w", ["a"])

    rapport = points.checkpoint_report()
    assert rapport["runs"] == 1
    assert rapport["forgotten"] == 1
    assert rapport["forgotten_resumable"] == 1


def test_le_routeur_borne_ses_points_de_reprise(moteur):
    """Un point de reprise par requête, sans borne, croîtrait avec le trafic."""
    assert moteur.checkpoints.checkpoint_report()["max_runs"] > 0
