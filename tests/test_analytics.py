"""
Tests de l'agrégation analytique (VOLET 09, chapitres 02, 04 et 06).

Deux exigences pèsent sur ce rapport : agréger ce qui existe **sans créer une
seconde collecte**, et ne jamais exposer ce que les gens demandent — le
chapitre 01 pose « privacy by design » comme principe, pas comme intention.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.analytics import UNAVAILABLE_CAPABILITIES, build_report, source_coverage  # noqa: E402
from src.api import server as server_module  # noqa: E402
from src.api.metrics import metrics_snapshot, record_search, reset_metrics  # noqa: E402
from src.api.server import app  # noqa: E402
from src.audit_engine.audit_manager import AuditManagerImpl  # noqa: E402
from src.audit_engine.types import AuditEvent, AuditEventType, AuditStatus  # noqa: E402
from src.router.workflow_history import WorkflowHistory  # noqa: E402


@pytest.fixture(autouse=True)
def compteurs_neufs():
    """Compteurs partagés remis à zéro autour de chaque test."""
    reset_metrics()
    yield
    reset_metrics()


@pytest.fixture
def audit():
    """Moteur d'audit contenant deux exécutions d'agent et un appel d'outil."""
    manager = AuditManagerImpl()
    manager.record(AuditEvent(agent_id="reviewer", event_type=AuditEventType.AGENT,
                              action="agent:reviewer", status=AuditStatus.SUCCESS,
                              execution_time_seconds=0.2))
    manager.record(AuditEvent(agent_id="reviewer", event_type=AuditEventType.AGENT,
                              action="agent:reviewer", status=AuditStatus.FAILURE,
                              execution_time_seconds=0.4))
    manager.record(AuditEvent(agent_id="reviewer", event_type=AuditEventType.TOOL,
                              action="tool:filesystem", status=AuditStatus.SUCCESS,
                              execution_time_seconds=0.01))
    return manager


@pytest.fixture
def cles(monkeypatch):
    """Clés admin et lecture seule, avec restauration de l'état RBAC partagé."""
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-admin:admin,cle-lecture:readonly")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield {"admin": "cle-admin", "readonly": "cle-lecture"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def test_une_source_absente_rend_null_et_non_zero():
    """Zéro se lirait comme une mesure ; `null` dit qu'il n'y a rien à mesurer."""
    rapport = build_report()
    assert rapport["agents"] is None
    assert rapport["workflows"] is None
    assert rapport["requests"] is None
    assert rapport["search"] is None


def test_la_couverture_distingue_declare_et_branche():
    """Les sept sources du chapitre 04 ne sont pas un inventaire de l'existant."""
    couverture = source_coverage()
    assert couverture["declared_count"] == 7
    assert couverture["wired_count"] == 4
    assert couverture["sources"]["memory_engine"]["wired"] is False
    assert couverture["sources"]["ai_services"]["fed_by"]


def test_les_capacites_absentes_sont_nommees():
    """Tendances, anomalies et tableaux de bord : déclarés absents avec leur raison."""
    rapport = build_report()
    assert set(rapport["unavailable"]) == set(UNAVAILABLE_CAPABILITIES)
    assert set(rapport["unavailable"]) == {"trends", "anomaly_detection", "dashboards"}
    for raison in rapport["unavailable"].values():
        assert raison.strip()


def test_le_detail_par_agent_ne_compte_que_les_executions_d_agent(audit):
    """Mélanger outils et agents gonflerait le compte d'exécutions."""
    rapport = build_report(audit_manager=audit)
    reviewer = rapport["agents"]["by_agent"]["reviewer"]

    assert reviewer["executions"] == 2, "l'appel d'outil ne doit pas être compté"
    assert reviewer["by_status"] == {"success": 1, "failure": 1}
    assert reviewer["success_rate"] == 0.5
    assert reviewer["median_duration_seconds"] in (0.2, 0.4)


def test_les_workflows_viennent_de_leur_historique():
    """Le rapport reprend l'historique du VOLET 08 sans le recalculer."""
    historique = WorkflowHistory()
    historique.record("revue", "success", 0.2)
    historique.record("revue", "error", 0.1)

    rapport = build_report(workflow_history=historique)
    assert rapport["workflows"]["executions"] == 2
    assert rapport["workflows"]["success_rate"] == 0.5


def test_les_compteurs_ne_sont_pas_recalcules():
    """Recalculer le trafic ici créerait une deuxième vérité sur le même trafic."""
    record_search(["knowledge"], results_count=0, duration_ms=1.0)
    instantane = metrics_snapshot()

    rapport = build_report(metrics=instantane)
    assert rapport["requests"]["total"] == instantane["requests_total"]
    assert rapport["search"] == instantane["search"]


def test_la_route_agrege_et_reste_reservee(cles):
    """`/analytics` décrit l'exploitation : lecture seule n'y accède pas."""
    with TestClient(app) as client:
        admin = client.get("/analytics", headers={"X-API-Key": cles["admin"]})
        lecture = client.get("/analytics", headers={"X-API-Key": cles["readonly"]})
        sans_cle = client.get("/analytics")

    assert admin.status_code == 200
    corps = admin.json()
    assert set(corps["unavailable"]) == {"trends", "anomaly_detection", "dashboards"}
    assert corps["coverage"]["declared_count"] == 7
    assert lecture.status_code == 403
    assert sans_cle.status_code == 401


def test_aucune_requete_utilisateur_dans_le_rapport(cles):
    """Mesurer le système n'est pas archiver ce que les gens demandent."""
    import json

    secret = "zzrequetesecretezz"
    with TestClient(app) as client:
        client.post("/knowledge/search", json={"query": secret, "limit": 5},
                    headers={"X-API-Key": cles["admin"]})
        reponse = client.get("/analytics", headers={"X-API-Key": cles["admin"]})

    assert secret not in json.dumps(reponse.json())
