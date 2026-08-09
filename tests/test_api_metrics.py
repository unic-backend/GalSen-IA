"""
Tests de la mesure du trafic (VOLET_04 ch. 09, critère de sortie C5).

Ce que ces tests protègent : `/health` répond « qu'est-ce qui est configuré »,
`/metrics` répond « qu'est-ce qui se passe ». Un compteur qui ne bouge pas, ou
qui bouge pour la mauvaise raison, est pire qu'aucun compteur — il donne une
fausse assurance.

Deux propriétés valent le reste du fichier : une requête en erreur doit être
comptée comme telle, et le nombre de séries de latence ne doit pas suivre le
trafic.
"""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("GALSEN_RATE_LIMIT_ENABLED", "false")

from src.api import server  # noqa: E402
from src.api.metrics import (  # noqa: E402
    LATENCE,
    PAR_CLASSE,
    TOTAL,
    get_shared_metrics,
    metrics_snapshot,
    reset_metrics,
)
from src.api.rate_limiter import set_valid_api_key_digests  # noqa: E402

CLE = "cle-metrics"


@pytest.fixture
def client(monkeypatch):
    """Client authentifié, compteurs remis à zéro, état RBAC restauré ensuite."""
    ancien_mapping = dict(server.rbac_manager._key_role_map)
    anciennes_revocations = set(server.rbac_manager._revoked_digests)

    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:readonly")
    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    reset_metrics()

    with TestClient(server.app) as instance:
        yield instance

    server.rbac_manager._key_role_map = ancien_mapping
    server.rbac_manager._revoked_digests = anciennes_revocations
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    reset_metrics()


@pytest.fixture
def entetes():
    """En-têtes portant la clé de lecture."""
    return {"X-API-Key": CLE}


class TestComptage:
    """Les chiffres doivent refléter le trafic, pas le décrire approximativement."""

    def test_chaque_requete_est_comptee(self, client, entetes):
        """Deux appels avant la lecture : la lecture ne se compte pas elle-même.

        L'intergiciel enregistre **après** la réponse, donc `/metrics` rapporte
        le trafic qui l'a précédée. C'est la seule sémantique cohérente : se
        compter soi-même donnerait un total qui augmente à chaque consultation.
        """
        client.get("/health")
        client.get("/health")
        corps = client.get("/metrics", headers=entetes).json()
        assert corps["requests_total"] == 2

        # La lecture précédente apparaît, elle, dans la suivante.
        assert client.get("/metrics", headers=entetes).json()["requests_total"] == 3

    def test_les_erreurs_sont_comptees_comme_telles(self, client, entetes):
        """Une requête refusée est une erreur : la compter en 2xx masquerait la panne."""
        client.post("/agri/advice", json={"question": "x"})  # 401, pas de clé
        corps = client.get("/metrics", headers=entetes).json()
        assert corps["counters"][PAR_CLASSE.format(classe="4xx")] == 1

    def test_taux_d_erreur_derive_et_borne(self, client, entetes):
        """Le taux est calculé côté serveur : deux consommateurs ne doivent pas diverger."""
        client.get("/health")
        client.post("/agri/advice", json={"question": "x"})
        corps = client.get("/metrics", headers=entetes).json()
        assert 0.0 < corps["error_rate"] <= 1.0
        attendu = corps["counters"][PAR_CLASSE.format(classe="4xx")] / corps["requests_total"]
        assert corps["error_rate"] == round(attendu, 4)

    def test_taux_nul_sans_trafic(self):
        """Aucune requête ne doit pas produire une division par zéro."""
        reset_metrics()
        instantane = metrics_snapshot()
        assert instantane["requests_total"] == 0
        assert instantane["error_rate"] == 0.0

    def test_la_latence_est_mesuree(self, client, entetes):
        """Sans durée, « ça répond » ne dit pas « ça répond vite »."""
        client.get("/health")
        latences = client.get("/metrics", headers=entetes).json()["latency_ms"]
        serie = LATENCE.format(methode="get", route="health")
        assert serie in latences
        assert latences[serie]["count"] >= 1
        assert latences[serie]["mean"] > 0


class TestCardinalite:
    """Le coût de la mesure ne doit pas croître avec le trafic."""

    def test_les_identifiants_ne_creent_pas_une_serie_chacun(self, client, entetes):
        """`/memory/{id}` est une série, pas une par identifiant.

        Sans gabarit de route, un scan d'URL ferait grossir la mémoire du
        collecteur à chaque tentative — la mesure deviendrait la panne.
        """
        for identifiant in ("a", "b", "c", "d"):
            client.get(f"/memory/retrieve/{identifiant}", headers=entetes)

        latences = client.get("/metrics", headers=entetes).json()["latency_ms"]
        series_memoire = [nom for nom in latences if "memory.retrieve" in nom]
        assert len(series_memoire) == 1, series_memoire
        assert latences[series_memoire[0]]["count"] == 4


class TestAcces:
    """Les volumes de trafic décrivent un usage, pas une architecture."""

    def test_cle_requise(self, client):
        """Contrairement à `/health`, `/metrics` ne doit pas être ouverte."""
        assert client.get("/metrics").status_code == 401

    def test_lecture_seule_suffit(self, client, entetes):
        """Un collecteur de supervision n'a aucune raison d'être administrateur."""
        assert client.get("/metrics", headers=entetes).status_code == 200


class TestHonnetete:
    """La portée de la mesure doit être annoncée, pas devinée."""

    def test_la_portee_est_annoncee(self, client, entetes):
        """Compteurs en mémoire : un redémarrage les perd, une autre instance a les siens."""
        corps = client.get("/metrics", headers=entetes).json()
        assert corps["scope"] == "instance"
        assert "redémarrage" in corps["detail"]

    def test_aucun_secret_dans_la_reponse(self, client, entetes):
        """Les noms de séries ne doivent porter ni clé ni identifiant."""
        import json

        contenu = json.dumps(client.get("/metrics", headers=entetes).json())
        assert CLE not in contenu
        assert "X-API-Key" not in contenu


class TestRobustesse:
    """Une mesure ratée ne doit jamais faire échouer la requête mesurée."""

    def test_un_collecteur_en_panne_ne_casse_pas_l_api(self, client, entetes):
        """C'est la propriété qui autorise à instrumenter tout le trafic."""
        collecteur = get_shared_metrics()
        original = collecteur.execute

        def echoue(*_args, **_kwargs):
            raise RuntimeError("collecteur indisponible")

        # Restauré explicitement plutôt que par monkeypatch : la fixture remet
        # les compteurs à zéro en fin de test, et elle passerait par la version
        # en panne si celle-ci était encore en place.
        collecteur.execute = echoue
        try:
            assert client.get("/health").status_code == 200
        finally:
            collecteur.execute = original

    def test_le_compteur_total_a_un_nom_stable(self):
        """Une faute de frappe créerait un second compteur au lieu d'incrémenter."""
        assert TOTAL == "http.requests.total"
