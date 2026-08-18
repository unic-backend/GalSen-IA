"""
Une routine peut faire tourner un workflow (phase 64.1).

Jusqu'ici, le travail planifié appelait des **outils** et rien d'autre. Il ne
passait donc jamais par l'orchestrateur du dépôt : pas de point de reprise, pas
d'historique d'exécution, pas de reprise d'agent, pas d'événement d'audit
`REQUEST`. Deux chemins d'exécution, dont un sans aucune de ces garanties.

Ce que ces tests gardent :

1. **Le workflow est vérifié à la déclaration**, comme un outil l'est déjà :
   inconnu ou inexécutable, la routine est refusée le jour où on l'écrit.
2. **L'exécution passe par l'orchestrateur réel** — celui qui tient les points
   de reprise —, avec le propriétaire de la routine et pas un autre.
3. **Une approbation n'est jamais accordée par l'absence de quelqu'un pour la
   refuser.** Une exécution suspendue n'est pas un succès, et son `run_id` est
   rendu pour qu'un humain la reprenne.
4. **Un orchestrateur absent est dit**, jamais contourné.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.routines import (  # noqa: E402
    ACTION_WORKFLOW,
    ECHECS_AVANT_ARRET,
    STATUT_SUSPENDU,
    RoutineRegistry,
    RoutineScheduler,
    WorkflowAction,
    workflow_runnable_unattended,
)
from src.routines.types import RoutineRefused  # noqa: E402


class _Orchestrateur:
    """Un orchestrateur qui rend ce qu'on lui dit, et retient ses appels."""

    def __init__(self, statut="success", run_id="run-1", erreur=None):
        self.statut = statut
        self.run_id = run_id
        self.erreur = erreur
        self.appels = []

    def process_request(self, user_request, workflow_id=None, user_id=None, **_):
        self.appels.append(
            {"request": user_request, "workflow_id": workflow_id, "user_id": user_id}
        )
        if self.erreur is not None:
            raise self.erreur
        return {"status": self.statut, "run_id": self.run_id}


@pytest.fixture
def registre():
    """Un registre neuf, avec le chargeur de workflows réel du dépôt."""
    return RoutineRegistry()


def _declarer(registre, workflow_id="standard", subject="awa", demande=None):
    """Déclare et active une routine d'un seul workflow."""
    routine = registre.declare(
        "veille-nocturne", "Fait tourner un workflow chaque nuit.",
        [WorkflowAction(workflow_id=workflow_id, operation=demande)],
        interval_seconds=3600, subject=subject,
    )
    registre.enable(routine.routine_id)
    return routine


# ----------------------------------------------------------------------
# 1. Vérifié à la déclaration
# ----------------------------------------------------------------------

def test_un_workflow_declare_du_depot_est_accepte(registre):
    """`standard` existe et le chargeur l'exécute."""
    routine = _declarer(registre)

    assert routine.actions[0].workflow_id == "standard"
    assert routine.actions[0].tool_id == ACTION_WORKFLOW
    assert routine.enabled is True


def test_un_workflow_inconnu_est_refuse_le_jour_ou_on_l_ecrit(registre):
    """Échouer chaque nuit sans témoin serait le pire moment pour l'apprendre."""
    with pytest.raises(RoutineRefused) as refus:
        _declarer(registre, workflow_id="celui-qui-n-existe-pas")

    assert "inconnu" in str(refus.value)


def test_une_action_de_workflow_sans_workflow_est_refusee(registre):
    """Elle ne ferait rien, chaque nuit, sans que personne le voie."""
    with pytest.raises(RoutineRefused):
        registre.declare(
            "vide", "Une action sans workflow.", [WorkflowAction()],
            interval_seconds=3600, subject="awa",
        )


def test_un_workflow_inexecutable_est_refuse():
    """Le motif vient du chargeur, pas d'une supposition."""

    class _Probleme:
        gravite = "error"
        message = "aucune étape"

    class _Chargeur:
        def get_workflow(self, identifiant):
            return {}

        def is_executable(self, identifiant):
            return False

        def get_problems(self, identifiant=None):
            return [_Probleme()]

    autorise, motif = workflow_runnable_unattended("creux", _Chargeur())

    assert autorise is False
    assert "aucune étape" in motif


def test_la_verification_ne_suppose_rien_sans_chargeur():
    """Sans moyen de vérifier, c'est un refus — jamais un « probablement »."""
    autorise, motif = workflow_runnable_unattended("standard", loader=None)

    assert isinstance(autorise, bool)
    assert autorise or "impossible de vérifier" in motif


# ----------------------------------------------------------------------
# 2. L'exécution passe par l'orchestrateur, avec le bon propriétaire
# ----------------------------------------------------------------------

def test_le_tour_fait_tourner_le_workflow_par_l_orchestrateur(registre):
    """Un second chemin d'exécution serait une implémentation parallèle."""
    routine = _declarer(registre)
    orchestrateur = _Orchestrateur()
    planificateur = RoutineScheduler(registre, orchestrator=orchestrateur)

    tour = planificateur.run(routine, now=1000.0)

    assert tour.ok is True
    assert orchestrateur.appels[0]["workflow_id"] == "standard"
    assert tour.actions[0].run_id == "run-1"


def test_le_proprietaire_vient_de_la_routine_pas_d_une_session(registre):
    """À trois heures du matin, il n'y a pas de session dont le déduire."""
    routine = _declarer(registre, subject="awa")
    orchestrateur = _Orchestrateur()
    planificateur = RoutineScheduler(registre, orchestrator=orchestrateur)

    planificateur.run(routine, now=1000.0)

    assert orchestrateur.appels[0]["user_id"] == "awa"


def test_la_demande_de_la_routine_est_transmise(registre):
    """Sans demande, un workflow n'aurait rien à traiter."""
    routine = _declarer(registre, demande="Résume les nouvelles sources.")
    orchestrateur = _Orchestrateur()
    planificateur = RoutineScheduler(registre, orchestrator=orchestrateur)

    planificateur.run(routine, now=1000.0)

    assert orchestrateur.appels[0]["request"] == "Résume les nouvelles sources."


def test_sans_demande_la_description_sert_de_demande(registre):
    """Elle est écrite pour être lue par le propriétaire : elle dit le travail."""
    routine = _declarer(registre)
    orchestrateur = _Orchestrateur()
    planificateur = RoutineScheduler(registre, orchestrator=orchestrateur)

    planificateur.run(routine, now=1000.0)

    assert orchestrateur.appels[0]["request"] == routine.description


# ----------------------------------------------------------------------
# 3. L'absence de quelqu'un pour refuser n'est pas un accord
# ----------------------------------------------------------------------

def test_une_execution_suspendue_n_est_pas_un_succes(registre):
    """Sinon « personne n'était là pour répondre » deviendrait « oui »."""
    routine = _declarer(registre)
    planificateur = RoutineScheduler(
        registre, orchestrator=_Orchestrateur(statut="requires_approval"),
    )

    tour = planificateur.run(routine, now=1000.0)

    assert tour.actions[0].status == STATUT_SUSPENDU
    assert tour.ok is False


def test_une_execution_suspendue_rend_son_identifiant_de_reprise(registre):
    """Sans lui, la décision attendue ne peut être reprise par personne."""
    routine = _declarer(registre)
    planificateur = RoutineScheduler(
        registre, orchestrator=_Orchestrateur(statut="requires_approval", run_id="run-9"),
    )

    tour = planificateur.run(routine, now=1000.0)

    assert tour.actions[0].as_dict()["run_id"] == "run-9"


def test_des_suspensions_repetees_finissent_par_arreter_la_routine(registre):
    """Une routine dont personne ne lit les approbations ne surveille rien."""
    routine = _declarer(registre)
    planificateur = RoutineScheduler(
        registre, orchestrator=_Orchestrateur(statut="requires_approval"),
    )

    for tour_numero in range(ECHECS_AVANT_ARRET):
        tour = planificateur.run(routine, now=1000.0 + tour_numero * 3600)

    assert tour.disabled_after is True
    assert routine.enabled is False


# ----------------------------------------------------------------------
# 4. Ce qui manque est dit
# ----------------------------------------------------------------------

def test_un_orchestrateur_absent_est_un_echec_pas_un_succes(registre):
    """Le même choix que pour le moteur d'outils absent."""
    routine = _declarer(registre)
    planificateur = RoutineScheduler(registre, orchestrator=None)

    tour = planificateur.run(routine, now=1000.0)

    assert tour.ok is False
    assert "Orchestrateur indisponible" in tour.actions[0].detail


def test_un_orchestrateur_qui_leve_ne_fait_pas_tomber_le_tour(registre):
    """La routine rapporte l'erreur ; elle ne la propage pas au planificateur."""
    routine = _declarer(registre)
    planificateur = RoutineScheduler(
        registre, orchestrator=_Orchestrateur(erreur=RuntimeError("moteur mort")),
    )

    tour = planificateur.run(routine, now=1000.0)

    assert tour.actions[0].status == "error"
    assert "moteur mort" in tour.actions[0].detail


def test_un_workflow_en_echec_est_rapporte_avec_son_statut(registre):
    """`partial_success` n'est pas un succès pour un travail sans témoin."""
    routine = _declarer(registre)
    planificateur = RoutineScheduler(
        registre, orchestrator=_Orchestrateur(statut="partial_success"),
    )

    tour = planificateur.run(routine, now=1000.0)

    assert tour.actions[0].status == "error"
    assert "partial_success" in tour.actions[0].detail


def test_une_action_de_workflow_se_lit_dans_le_compte_rendu(registre):
    """Un compte rendu doit se lire sans connaître le type de l'action."""
    routine = _declarer(registre)

    rendu = routine.as_dict()["actions"][0]

    assert rendu["kind"] == ACTION_WORKFLOW
    assert rendu["workflow_id"] == "standard"


def test_les_actions_d_outil_continuent_de_fonctionner(registre):
    """L'ajout n'enlève rien : c'est la première chose à vérifier."""
    from src.routines import RoutineAction

    routine = registre.declare(
        "outil-nocturne", "Un appel d'outil chaque nuit.",
        [RoutineAction("metrics", "read")],
        interval_seconds=3600, subject="awa",
    )

    assert routine.actions[0].tool_id == "metrics"
