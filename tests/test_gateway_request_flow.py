"""
Ordre réel des étapes traversées par une requête (VOLET 15, chapitre 02).

Le chapitre décrit un flux : recevoir, authentifier, autoriser, router,
répondre, enregistrer. `docs/architecture/gateway.md` affirme trois choses sur
la façon dont ce flux est réellement câblé — rien ne les protégeait. Un
`add_middleware` déplacé de deux lignes suffisait à les casser en silence :
les intergiciels s'exécutent dans l'ordre **inverse** de leur ajout, et cette
subtilité ne se voit pas à la lecture.
"""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GALSEN_API_KEYS", "test-key-0123456789abcdef")

import src.api.rate_limiter as rate_limiter_module  # noqa: E402
from src.api import server  # noqa: E402
from src.api.metrics import metrics_snapshot, reset_metrics  # noqa: E402

CLE = "test-key-0123456789abcdef"


@pytest.fixture
def client(monkeypatch):
    """Client sur l'application réelle, compteurs remis à zéro de part et d'autre."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:readonly")
    server.rbac_manager.reload()
    rate_limiter_module.set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    reset_metrics()
    with TestClient(server.app) as instance:
        yield instance
    reset_metrics()


@pytest.fixture
def client_limite(monkeypatch):
    """Client dont le budget non authentifié tient en deux requêtes."""
    monkeypatch.setenv("GALSEN_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM", "2")
    monkeypatch.setenv("GALSEN_RATE_LIMIT_BURST_MULTIPLIER", "1.0")
    ancien = rate_limiter_module._rate_limiter
    rate_limiter_module._rate_limiter = None
    try:
        with TestClient(server.app) as instance:
            yield instance
    finally:
        # Le limiteur est un singleton de processus : le laisser configuré à
        # deux requêtes par minute ferait échouer les suites suivantes.
        rate_limiter_module._rate_limiter = ancien


def test_les_en_tetes_de_securite_couvrent_aussi_les_erreurs(client):
    """
    Une réponse d'erreur est une réponse : elle traverse le navigateur de la
    même façon. Des en-têtes posés seulement sur les succès laissent le cas le
    plus fréquent — le refus — sans protection.
    """
    reponse = client.get("/metrics")

    assert reponse.status_code == 401
    entetes = {nom.lower() for nom in reponse.headers}
    assert "x-content-type-options" in entetes
    assert "x-frame-options" in entetes


def test_les_metriques_voient_le_code_reellement_renvoye(client):
    """
    L'intergiciel de mesure est ajouté **après** celui des en-têtes, donc il
    l'enveloppe et observe le statut final. S'il était ajouté avant, il
    mesurerait une réponse que personne ne reçoit.
    """
    client.get("/metrics")  # refusée : pas de clé

    instantane = metrics_snapshot()
    assert instantane["requests_total"] == 1
    assert instantane["error_rate"] == 1.0


def test_une_requete_authentifiee_n_est_pas_comptee_comme_une_erreur(client):
    """Sans ce contre-test, tout marquer en erreur ferait passer le précédent."""
    reponse = client.get("/metrics", headers={"X-API-Key": CLE})

    assert reponse.status_code == 200
    assert metrics_snapshot()["error_rate"] == 0.0


def test_le_limiteur_repond_avant_l_authentification(client_limite):
    """
    Un flot non authentifié doit être rejeté sans coûter une recherche de clé.

    Mesuré : les deux premières requêtes sans clé répondent 401, les suivantes
    429. Le limiteur tranche donc en amont — l'ordre que le chapitre 05 exige
    d'un contrôle de trafic, et l'inverse de ce que le flux du chapitre 02
    laisse lire.
    """
    codes = [client_limite.get("/metrics").status_code for _ in range(5)]

    assert codes[:2] == [401, 401]
    assert codes[2:] == [429, 429, 429]


def test_l_ordre_des_intergiciels_est_celui_qui_est_documente():
    """
    Verrouille l'ordre dont dépendent les deux tests précédents.

    `add_middleware` **insère en tête** de `user_middleware` : la liste est donc
    déjà dans l'ordre d'exécution, du plus externe au plus proche de la route,
    et non dans l'ordre d'ajout. CORS tranche en premier, la mesure enveloppe
    les en-têtes de sécurité — c'est ce qui lui fait voir le statut final.
    """
    execution = [couche.cls.__name__ for couche in server.app.user_middleware]

    assert execution.index("RequestMetricsMiddleware") < execution.index("SecurityHeadersMiddleware"), (
        "la mesure doit envelopper les en-têtes pour observer le statut réellement renvoyé"
    )
    assert execution.index("CORSMiddleware") < execution.index("RequestMetricsMiddleware")
