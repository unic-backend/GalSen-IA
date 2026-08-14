"""
Les points de reprise des workflows longs (phase 49.1).

Le dépôt savait charger un workflow et raconter ce qu'il avait fait une fois
fini. Ce qu'il n'a jamais eu, c'est l'état d'une exécution **pendant** qu'elle
dure : un workflow de dix agents mort au huitième repartait du premier, et les
sept étapes qui avaient déjà touché le monde le touchaient une seconde fois.

Ce que ces tests gardent :

1. **Une étape terminée n'est jamais refaite.** Refaire une étape qui a déjà eu
   un effet au-dehors est la façon dont un courriel devient deux — la leçon que
   l'exécuteur de requêtes avait apprise sur les réessais (VOLET 44).
2. **Une annulation est terminale.** Si elle reprenait, « annuler » voudrait
   dire « suspendre », et la différence compte exactement une fois : pour celui
   qui a annulé en croyant que cela s'arrêtait.
3. **Un point de reprise porte du travail réel, donc il appartient à
   quelqu'un.** Reprendre l'exécution d'une autre personne, ce serait lancer des
   agents sur ses données.
4. **Une troncature se dit.** Une sortie coupée en silence est une sortie
   fausse.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.router.workflow_checkpoint import (  # noqa: E402
    REPRISES_MAXIMUM,
    TAILLE_MAXIMALE_ETAPE,
    CheckpointRefused,
    RunStatus,
    WorkflowCheckpoints,
)

ETAPES = ["analyzer", "researcher", "writer"]


@pytest.fixture
def points():
    """Des points de reprise neufs."""
    return WorkflowCheckpoints()


def _lancer(points, subject=None, steps=None):
    """Ouvre une exécution de trois étapes."""
    return points.start("standard", steps or list(ETAPES), subject=subject)


# ----------------------------------------------------------------------
# 1. Une étape terminée n'est jamais refaite
# ----------------------------------------------------------------------

def test_la_reprise_repart_de_la_premiere_etape_inachevee(points):
    """
    Le point de cette phase. Sans cela, huit étapes mortes à la neuvième
    recommencent à la première, effets au-dehors compris.
    """
    execution = _lancer(points)
    points.record_step(execution.run_id, "analyzer", ok=True, output="A")
    points.record_step(execution.run_id, "researcher", ok=False, output="panne")

    reprise = points.resume(execution.run_id)

    assert reprise.next_step() == "researcher"
    assert reprise.done_agents == ["analyzer"]


def test_un_workflow_repris_n_execute_chaque_agent_qu_une_fois(points):
    """
    La règle vue de bout en bout : on simule une exécution qui meurt au
    milieu, on reprend, et on compte ce qui a réellement tourné. Un agent
    lancé deux fois, c'est le courriel envoyé deux fois.
    """
    execution = _lancer(points)
    lances = []

    def derouler(panne_sur=None):
        """Exécute depuis l'étape courante, en tombant sur `panne_sur`."""
        while (agent := execution.next_step()) is not None:
            lances.append(agent)
            if agent == panne_sur:
                points.record_step(execution.run_id, agent, ok=False)
                return
            points.record_step(execution.run_id, agent, ok=True)

    derouler(panne_sur="researcher")
    points.resume(execution.run_id)
    derouler()

    assert lances == ["analyzer", "researcher", "researcher", "writer"]
    assert execution.done_agents == ETAPES
    assert lances.count("analyzer") == 1


def test_une_etape_echouee_est_a_refaire_elle(points):
    """
    Une étape qui a échoué n'a pas eu son effet : c'est elle qu'on reprend.
    Ne pas la refaire laisserait un trou au milieu du workflow.
    """
    execution = _lancer(points)
    points.record_step(execution.run_id, "analyzer", ok=False, output="timeout")

    assert execution.next_step() == "analyzer"
    assert execution.status is RunStatus.FAILED


def test_le_resultat_de_chaque_etape_est_conserve(points):
    """Sans lui, la reprise ne pourrait pas enchaîner sur l'étape suivante."""
    execution = _lancer(points)
    points.record_step(execution.run_id, "analyzer", ok=True, output="rapport")

    assert execution.completed[0].output == "rapport"


def test_toutes_les_etapes_abouties_terminent_l_execution(points):
    """Et une exécution terminée n'est pas relançable."""
    execution = _lancer(points)
    for agent in ETAPES:
        points.record_step(execution.run_id, agent, ok=True)

    assert execution.status is RunStatus.COMPLETED
    assert execution.next_step() is None
    with pytest.raises(CheckpointRefused, match="travail déjà fait"):
        points.resume(execution.run_id)


def test_l_avancement_se_lit_sans_compter_soi_meme(points):
    """Une interface doit pouvoir l'afficher sans reconstruire l'état."""
    execution = _lancer(points)
    points.record_step(execution.run_id, "analyzer", ok=True)

    assert execution.progress == "1/3"


# ----------------------------------------------------------------------
# 2. L'annulation est terminale
# ----------------------------------------------------------------------

def test_une_execution_annulee_ne_reprend_pas(points):
    """
    Si elle reprenait, « annuler » voudrait dire « suspendre », et la
    différence compte exactement une fois.
    """
    execution = _lancer(points)
    points.cancel(execution.run_id, reason="le client a changé d'avis")

    with pytest.raises(CheckpointRefused, match="annulée"):
        points.resume(execution.run_id)


def test_aucune_etape_ne_se_consigne_apres_une_annulation(points):
    """Sinon l'annulation serait effacée par l'étape suivante."""
    execution = _lancer(points)
    points.cancel(execution.run_id, reason="incident")

    with pytest.raises(CheckpointRefused, match="cancelled"):
        points.record_step(execution.run_id, "analyzer", ok=True)


def test_une_annulation_sans_raison_est_refusee(points):
    """Elle est définitive : la raison est tout ce qui restera pour l'expliquer."""
    execution = _lancer(points)

    with pytest.raises(CheckpointRefused, match="dit pourquoi"):
        points.cancel(execution.run_id, reason="   ")


def test_l_annulation_garde_sa_raison(points):
    """Elle sera lue par quelqu'un qui n'était pas là."""
    execution = _lancer(points)

    annulee = points.cancel(execution.run_id, reason="budget épuisé")

    assert annulee.status is RunStatus.CANCELLED
    assert annulee.cancelled_reason == "budget épuisé"


def test_un_statut_terminal_n_est_pas_reprenable(points):
    """La propriété qui porte la règle, vérifiée pour elle-même."""
    assert RunStatus.RUNNING.resumable is True
    assert RunStatus.FAILED.resumable is True
    assert RunStatus.COMPLETED.resumable is False
    assert RunStatus.CANCELLED.resumable is False


# ----------------------------------------------------------------------
# 3. Un point de reprise appartient à quelqu'un
# ----------------------------------------------------------------------

def test_l_execution_d_une_autre_personne_est_invisible(points):
    """Le même refus qu'une exécution inexistante : dire « elle existe mais
    elle n'est pas à vous » renseignerait sur ce que l'autre fait tourner."""
    execution = _lancer(points, subject="awa")

    assert points.get(execution.run_id, subject="fatou") is None
    with pytest.raises(CheckpointRefused, match="inconnue"):
        points.resume(execution.run_id, subject="fatou")


def test_le_refus_est_le_meme_mot_a_mot_qu_une_execution_inexistante(points):
    """Un message différent serait un canal d'information à lui seul."""
    execution = _lancer(points, subject="awa")

    with pytest.raises(CheckpointRefused) as autrui:
        points.resume(execution.run_id, subject="fatou")
    with pytest.raises(CheckpointRefused) as inexistante:
        points.resume("run_inexistante", subject="fatou")

    assert str(autrui.value).replace(execution.run_id, "X") == str(
        inexistante.value
    ).replace("run_inexistante", "X")


def test_nul_autre_ne_consigne_ni_n_annule(points):
    """Reprendre le workflow d'autrui, ce serait lancer des agents sur ses données."""
    execution = _lancer(points, subject="awa")

    with pytest.raises(CheckpointRefused, match="inconnue"):
        points.record_step(execution.run_id, "analyzer", ok=True, subject="fatou")
    with pytest.raises(CheckpointRefused, match="inconnue"):
        points.cancel(execution.run_id, reason="x", subject="fatou")


def test_le_proprietaire_reprend_la_sienne(points):
    """La frontière refuse les autres, pas le titulaire."""
    execution = _lancer(points, subject="awa")
    points.record_step(execution.run_id, "analyzer", ok=False, subject="awa")

    reprise = points.resume(execution.run_id, subject="awa")

    assert reprise.next_step() == "analyzer"


def test_une_execution_sans_sujet_appartient_a_la_plateforme(points):
    """Un workflow lancé par le système n'est la donnée privée de personne."""
    execution = _lancer(points)

    assert points.get(execution.run_id, subject="fatou") is not None


def test_la_liste_ne_montre_que_le_visible(points):
    """Compter les exécutions d'autrui serait déjà en dire trop."""
    _lancer(points, subject="awa")
    mienne = _lancer(points, subject="fatou")

    listees = points.list_runs(subject="fatou")

    assert [e["run_id"] for e in listees] == [mienne.run_id]


# ----------------------------------------------------------------------
# 4. Les bornes, et ce qui se dit
# ----------------------------------------------------------------------

def test_une_execution_sans_etape_est_refusee(points):
    """Elle n'a rien à reprendre, et l'ouvrir masquerait un workflow vide."""
    with pytest.raises(CheckpointRefused, match="aucune étape"):
        points.start("vide", [])


def test_une_sortie_tronquee_le_dit(points):
    """Une sortie coupée en silence est une sortie fausse."""
    execution = _lancer(points)

    points.record_step(
        execution.run_id, "analyzer", ok=True, output="x" * (TAILLE_MAXIMALE_ETAPE + 1)
    )

    etape = execution.completed[0]
    assert etape.truncated is True
    assert len(etape.output) == TAILLE_MAXIMALE_ETAPE


def test_une_sortie_courte_n_est_pas_marquee_tronquee(points):
    """Le drapeau doit vouloir dire quelque chose."""
    execution = _lancer(points)
    points.record_step(execution.run_id, "analyzer", ok=True, output="court")

    assert execution.completed[0].truncated is False


def test_le_quota_de_reprises_finit_par_refuser(points):
    """
    Au-delà, ce n'est plus une panne passagère mais une étape qui ne passera
    jamais : reprendre consomme sans avancer.
    """
    execution = _lancer(points)
    for _ in range(REPRISES_MAXIMUM):
        points.record_step(execution.run_id, "analyzer", ok=False)
        points.resume(execution.run_id)

    points.record_step(execution.run_id, "analyzer", ok=False)
    with pytest.raises(CheckpointRefused, match="reprises déjà"):
        points.resume(execution.run_id)


def test_une_reprise_se_compte(points):
    """Un quota qui ne compte pas n'est pas un quota."""
    execution = _lancer(points)
    points.record_step(execution.run_id, "analyzer", ok=False)

    points.resume(execution.run_id)

    assert execution.resumes == 1
    assert execution.status is RunStatus.RUNNING


def test_le_rapport_compte_par_statut_et_nomme_ses_regles(points):
    """Ce qu'un lecteur doit pouvoir vérifier sans lire le code."""
    terminee = _lancer(points)
    for agent in ETAPES:
        points.record_step(terminee.run_id, agent, ok=True)
    _lancer(points)

    rapport = points.checkpoint_report()

    assert rapport["by_status"] == {"completed": 1, "running": 1}
    regles = " ".join(rapport["rules"])
    assert "jamais refaite" in regles
    assert "terminale" in regles


def test_le_rapport_ne_liste_comme_reprenable_que_ce_qui_l_est(points):
    """Une exécution annulée ou hors quota n'y figure pas."""
    annulee = _lancer(points)
    points.cancel(annulee.run_id, reason="incident")
    vivante = _lancer(points)
    points.record_step(vivante.run_id, "analyzer", ok=False)

    assert points.checkpoint_report()["resumable"] == [vivante.run_id]
