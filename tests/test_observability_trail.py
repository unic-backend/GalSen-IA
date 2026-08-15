"""
Suivre un travail de bout en bout (phases 66.1, 66.2).

Chaque sous-système consignait déjà ce qu'il faisait. Aucun ne savait répondre à
la question posée à trois heures du matin : *qu'est-il arrivé à ce travail-là ?*
Un tour de routine, le workflow qu'il déclenchait et les événements d'audit de
celui-ci portaient trois identifiants que rien ne reliait.

Ce que ces tests gardent :

1. **L'identifiant traverse les frontières** : le tour le pose, l'exécution le
   reprend au lieu d'en générer un autre.
2. **Vide et illisible ne se confondent pas.** « Aucun événement ne porte cet
   identifiant » et « le moteur d'audit est indisponible » mènent à des
   conclusions opposées.
3. **Rien n'est rapproché par l'heure.** C'est ainsi qu'une piste devient
   confiante et fausse.
4. **Suivre une piste n'est pas une dérogation** : chaque source garde son
   audience.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.observability import (  # noqa: E402
    ILLISIBLE,
    RIEN,
    TROUVE,
    observability_report,
    trail,
)
from src.routines import (  # noqa: E402
    RoutineJournal,
    RoutineRegistry,
    RoutineScheduler,
    WorkflowAction,
)


class _Orchestrateur:
    """Un orchestrateur qui retient l'identifiant qu'on lui donne."""

    def __init__(self):
        self.appels = []

    def process_request(self, user_request, workflow_id=None, user_id=None,
                        request_id=None, **_):
        self.appels.append({"request_id": request_id})
        return {"status": "success", "run_id": "run-42", "request_id": request_id}


@pytest.fixture
def routine_et_journal():
    """Une routine de workflow, son planificateur et son journal."""
    registre = RoutineRegistry()
    routine = registre.declare(
        "veille", "Un workflow chaque nuit.",
        [WorkflowAction(workflow_id="standard")],
        interval_seconds=3600, subject="awa",
    )
    registre.enable(routine.routine_id)
    orchestrateur = _Orchestrateur()
    return routine, RoutineScheduler(registre, orchestrator=orchestrateur), \
        RoutineJournal(), orchestrateur


# ----------------------------------------------------------------------
# 1. L'identifiant traverse les frontières (66.1)
# ----------------------------------------------------------------------

def test_chaque_tour_porte_un_identifiant(routine_et_journal):
    """Posé avant les gardes : un tour refusé est un fait à retrouver."""
    routine, planificateur, _, _ = routine_et_journal

    tour = planificateur.run(routine, now=1000.0)

    assert tour.correlation_id
    assert tour.as_dict()["correlation_id"] == tour.correlation_id


def test_le_workflow_reprend_l_identifiant_du_tour(routine_et_journal):
    """En générer un nouveau couperait la piste là où elle traverse."""
    routine, planificateur, _, orchestrateur = routine_et_journal

    tour = planificateur.run(routine, now=1000.0)

    assert orchestrateur.appels[0]["request_id"] == tour.correlation_id


def test_deux_tours_ne_partagent_pas_leur_identifiant(routine_et_journal):
    """Sinon deux travaux distincts se liraient comme un seul."""
    routine, planificateur, _, _ = routine_et_journal

    premier = planificateur.run(routine, now=1000.0)
    second = planificateur.run(routine, now=8000.0)

    assert premier.correlation_id != second.correlation_id


def test_le_routeur_reel_accepte_un_identifiant_fourni():
    """Le contrat vérifié sur le moteur, pas sur un double."""
    from src.router.router_engine import RouterEngine

    reponse = RouterEngine().process_request(
        "Bonjour", workflow_id="standard", request_id="corr-xyz",
    )

    assert reponse["request_id"] == "corr-xyz"


# ----------------------------------------------------------------------
# 2. La piste rassemble, et dit ce qui manque (66.2)
# ----------------------------------------------------------------------

def test_la_piste_retrouve_le_tour_par_son_identifiant(routine_et_journal):
    """C'est l'écart que ce VOLET referme."""
    routine, planificateur, journal, _ = routine_et_journal
    tour = planificateur.run(routine, now=1000.0)
    journal.record(tour, subject="awa")

    piste = trail(tour.correlation_id, journal=journal, subject="awa")

    assert "routine_runs" in piste["found_in"]
    assert piste["fragments"]["routine_runs"]["items"][0]["routine_id"] == "veille"


def test_une_source_vide_et_une_source_illisible_ne_se_confondent_pas(
    routine_et_journal
):
    """Elles mènent à des conclusions opposées."""
    _, _, journal, _ = routine_et_journal

    piste = trail("inconnu", journal=journal, audit_manager=None)

    assert piste["fragments"]["routine_runs"]["state"] == RIEN
    # Sans journal fourni, la source est illisible — pas vide.
    sans_journal = trail("inconnu", journal=None)
    assert sans_journal["fragments"]["routine_runs"]["state"] == ILLISIBLE


def test_un_audit_indisponible_est_dit_illisible(routine_et_journal):
    """« Aucun événement » ne doit pas se lire quand personne n'a pu regarder."""
    _, _, journal, _ = routine_et_journal

    class _Casse:
        def list_events(self, *args, **kwargs):
            raise RuntimeError("base fermée")

    piste = trail("corr-1", journal=journal, audit_manager=_Casse())

    fragment = piste["fragments"]["audit_events"]
    assert fragment["state"] == ILLISIBLE
    assert "audit_events" in piste["unreadable"]


def test_un_audit_lisible_mais_sans_trace_est_dit_vide():
    """L'identifiant peut être exact et son audit déjà purgé."""
    from src.audit_engine.audit_manager import AuditManagerImpl

    piste = trail("corr-jamais-vue", audit_manager=AuditManagerImpl())

    fragment = piste["fragments"]["audit_events"]
    assert fragment["state"] == RIEN
    assert "purgé" in fragment["reason"]


def test_l_audit_reel_est_lu_par_la_trace_existante():
    """
    La lecture de l'audit par `request_id` existe depuis le VOLET 19.

    En écrire une seconde donnerait deux réponses qui divergeraient le jour où
    l'une serait corrigée.
    """
    from src.audit_engine.audit_manager import AuditManagerImpl
    from src.audit_engine.types import AuditEvent, AuditEventType, AuditStatus

    gestionnaire = AuditManagerImpl()
    gestionnaire.record(AuditEvent(
        event_type=AuditEventType.REQUEST, action="process_request",
        status=AuditStatus.SUCCESS, request_id="corr-9",
    ))

    piste = trail("corr-9", audit_manager=gestionnaire)

    assert piste["fragments"]["audit_events"]["state"] == TROUVE
    assert piste["fragments"]["audit_events"]["items"]


def test_les_executions_viennent_des_fragments_jamais_de_l_heure(routine_et_journal):
    """Deux événements à une seconde d'intervalle ne sont pas le même travail."""
    _, _, journal, _ = routine_et_journal

    class _Points:
        def get(self, run_id, subject=None):
            raise AssertionError("aucune exécution ne devait être demandée")

    piste = trail("corr-vide", journal=journal, checkpoints=_Points())

    assert piste["fragments"]["workflow_runs"]["state"] == RIEN
    assert "rapproché par l'heure" in piste["fragments"]["workflow_runs"]["reason"]


def test_une_piste_sans_identifiant_est_refusee():
    """Ce ne serait pas une piste, mais un export."""
    with pytest.raises(ValueError):
        trail("   ")


# ----------------------------------------------------------------------
# 3. Suivre une piste n'est pas une dérogation
# ----------------------------------------------------------------------

def test_la_piste_de_quelqu_un_d_autre_ne_se_lit_pas(routine_et_journal):
    """Le journal de quelqu'un dit ce qu'il surveille."""
    routine, planificateur, journal, _ = routine_et_journal
    tour = planificateur.run(routine, now=1000.0)
    journal.record(tour, subject="awa")

    piste = trail(tour.correlation_id, journal=journal, subject="moussa")

    assert piste["fragments"]["routine_runs"]["state"] == RIEN


def test_le_journal_filtre_par_correlation_comme_par_routine(routine_et_journal):
    """La même règle d'audience, pas une seconde qui divergerait."""
    routine, planificateur, journal, _ = routine_et_journal
    tour = planificateur.run(routine, now=1000.0)
    journal.record(tour, subject="awa")

    assert journal.find_by_correlation(tour.correlation_id, subject="awa")
    assert journal.find_by_correlation(tour.correlation_id, subject="moussa") == []


# ----------------------------------------------------------------------
# 4. Ce qui n'est pas traçable est nommé
# ----------------------------------------------------------------------

def test_le_rapport_nomme_ce_qui_n_est_pas_correle():
    """Mieux vaut le dire que le laisser découvrir en cherchant."""
    rapport = observability_report()

    assert "notifications" in rapport["not_correlated"]
    assert "tool_calls" in rapport["not_correlated"]
    assert any("l'heure" in ligne for ligne in rapport["does_not"])


# ----------------------------------------------------------------------
# 5. Les routes
# ----------------------------------------------------------------------

@pytest.fixture
def client_observabilite(monkeypatch):
    """Client HTTP et clé nommée."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    with TestClient(server_module.app) as essai:
        yield essai, {"X-API-Key": "cle-awa"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def test_la_route_rend_une_piste_meme_inconnue(client_observabilite):
    """Un identifiant exact dont l'audit a été purgé n'est pas une erreur."""
    client, cle = client_observabilite

    piste = client.get("/observability/trail/corr-inconnu", headers=cle).json()

    assert piste["correlation_id"] == "corr-inconnu"
    assert set(piste["fragments"]) == {"routine_runs", "audit_events", "workflow_runs"}


def test_la_route_du_rapport_publie_les_limites(client_observabilite):
    """Ce qui n'est pas corrélé se lit sans ouvrir le code."""
    client, cle = client_observabilite

    rapport = client.get("/observability/report", headers=cle).json()

    assert "notifications" in rapport["not_correlated"]


def test_les_routes_d_observabilite_exigent_une_cle(client_observabilite):
    """Une piste nomme des routines, des exécutions et des propriétaires."""
    client, _ = client_observabilite

    assert client.get("/observability/trail/x").status_code in (401, 403)
    assert client.get("/observability/report").status_code in (401, 403)
