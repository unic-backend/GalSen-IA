"""
Le chemin d'une requête, reconstitué (phase 26.4).

L'audit portait déjà tout ce qu'il faut — un `request_id` sur chaque événement,
une durée sur les appels d'outils et de modèles — et l'orchestrateur rendait ce
`request_id` à l'appelant. Il manquait la question inverse : « qu'est-il arrivé
à **cette** requête, et où est passé le temps ». `/metrics` répond « combien »,
`/analytics` répond « en général » ; personne ne répondait « celle-ci ».

Ces tests vérifient que la trace vient bien de ce qui a réellement tourné, et
non d'un enregistrement fabriqué pour l'occasion.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("GALSEN_RATE_LIMIT_ENABLED", "false")

from src.api.tracing import build_trace  # noqa: E402
from src.integration.engine_registry import get_shared_registry  # noqa: E402

CLE = "cle-trace-0123456789"


@pytest.fixture
def client(monkeypatch):
    """Client authentifié en administrateur : la trace est une route d'audit."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin")
    monkeypatch.setenv("GALSEN_RATE_LIMIT_ENABLED", "false")

    from src.api import server
    from src.api.rate_limiter import set_valid_api_key_digests

    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    with TestClient(server.app) as instance:
        yield instance


# ----------------------------------------------------------------------
# La trace décrit ce qui a vraiment tourné
# ----------------------------------------------------------------------

def test_une_requete_produit_une_trace_lisible(client):
    """Le parcours complet : exécuter un workflow, puis demander sa trace."""
    entetes = {"X-API-Key": CLE}
    execution = client.post(
        "/workflow/run", json={"request": "Analyser l'etat du projet"}, headers=entetes
    )
    assert execution.status_code == 200

    request_id = execution.json()["request_id"]
    trace = client.get(f"/trace/{request_id}", headers=entetes).json()

    assert trace["available"] is True
    assert trace["request_id"] == request_id
    assert trace["step_count"] > 0, "Une exécution qui ne laisse aucune trace n'est pas traçable"
    # Les agents exécutés doivent se retrouver dans la trace : c'est le lien
    # entre ce que l'orchestrateur rapporte et ce que l'audit a enregistré.
    agents_executes = {
        r["agent"] for r in execution.json()["agent_results"] if r.get("agent")
    }
    agents_traces = {etape.get("agent_id") for etape in trace["steps"]}
    assert agents_executes & agents_traces, (
        f"aucun agent exécuté ne figure dans la trace : {agents_executes} vs {agents_traces}"
    )


def test_le_temps_mesure_ne_depasse_pas_le_temps_reel(client):
    """Une somme de durées supérieure au temps écoulé signalerait un double comptage."""
    entetes = {"X-API-Key": CLE}
    execution = client.post(
        "/workflow/run", json={"request": "Analyser l'etat du projet"}, headers=entetes
    ).json()

    trace = client.get(f"/trace/{execution['request_id']}", headers=entetes).json()

    # Marge large : les agents peuvent tourner en parallèle, donc la somme des
    # durées peut dépasser le temps mural — mais pas d'un ordre de grandeur.
    assert trace["measured_seconds"] <= execution["execution_time_seconds"] * 10 + 1


def test_les_etapes_non_mesurees_sont_comptees_a_part(client):
    """Une étape sans durée ne doit pas être supposée instantanée."""
    entetes = {"X-API-Key": CLE}
    execution = client.post(
        "/workflow/run", json={"request": "Analyser l'etat du projet"}, headers=entetes
    ).json()

    trace = client.get(f"/trace/{execution['request_id']}", headers=entetes).json()

    assert trace["unmeasured_steps"] + len(
        [etape for etape in trace["steps"] if "seconds" in etape]
    ) == trace["step_count"]


# ----------------------------------------------------------------------
# Les cas qui ne doivent pas se transformer en incident
# ----------------------------------------------------------------------

def test_un_identifiant_inconnu_rend_une_trace_vide(client):
    """Un `request_id` exact dont l'audit est purgé n'est pas une erreur."""
    reponse = client.get("/trace/req_inexistant", headers={"X-API-Key": CLE})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["available"] is True
    assert corps["steps"] == []
    assert corps["step_count"] == 0


def test_sans_moteur_d_audit_la_trace_le_dit(client):
    """Une capacité absente rapporte son état ; elle n'invente pas une trace."""
    trace = build_trace(None, "req_quelconque")

    assert trace["available"] is False
    assert trace["steps"] == []
    assert "audit" in trace["reason"].lower()


def test_la_trace_est_reservee_a_l_audit(client):
    """Le chemin d'une requête peut contenir la demande d'un utilisateur."""
    reponse = client.get("/trace/req_quelconque")

    assert reponse.status_code == 401


def test_deux_requetes_ne_se_melangent_pas(client):
    """Un `request_id` ne doit rendre que ses propres étapes."""
    entetes = {"X-API-Key": CLE}
    premiere = client.post(
        "/workflow/run", json={"request": "Premiere demande"}, headers=entetes
    ).json()["request_id"]
    seconde = client.post(
        "/workflow/run", json={"request": "Seconde demande"}, headers=entetes
    ).json()["request_id"]

    assert premiere != seconde
    trace = client.get(f"/trace/{premiere}", headers=entetes).json()

    registre = get_shared_registry()
    if registre.try_get("audit") is None:  # pragma: no cover - audit toujours présent ici
        pytest.skip("moteur d'audit indisponible")

    # Chaque étape remontée porte bien l'identifiant demandé : le filtre est
    # appliqué par l'audit, et non par une découpe approximative côté trace.
    evenements = registre.get("audit").list_events(limit=500, request_id=premiere)
    assert len(evenements) == trace["step_count"]
