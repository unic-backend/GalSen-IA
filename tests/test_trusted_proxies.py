"""
À qui la plateforme croit quand une requête dit d'où elle vient (chantier 2).

`X-Forwarded-For` était lu sans condition. Sans proxy devant l'application —
c'est-à-dire dans l'état où elle se trouvait — n'importe quel appelant pouvait
l'envoyer, changer d'adresse à chaque requête, et obtenir ainsi **un quota
illimité tout en restant invisible** du détecteur de menaces, qui compte les
échecs d'authentification par source.
"""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GALSEN_API_KEYS", "test-key-0123456789abcdef")

import src.api.rate_limiter as rate_limiter_module  # noqa: E402
from src.api import server  # noqa: E402
from src.api.rate_limiter import set_valid_api_key_digests  # noqa: E402
from src.api.threat_detection import get_shared_detector  # noqa: E402
from src.api.trusted_proxies import (  # noqa: E402
    TRUSTED_PROXIES_VARIABLE,
    client_ip,
    forwarded_proto,
    is_trusted_proxy,
)

CLE = "test-key-0123456789abcdef"


class _RequeteFactice:
    """Requête minimale : un pair et des en-têtes."""

    class _Client:
        def __init__(self, host):
            self.host = host

    class _Url:
        scheme = "http"

    def __init__(self, pair=None, entetes=None):
        self.client = self._Client(pair) if pair else None
        self.headers = entetes or {}
        self.url = self._Url()


# ----------------------------------------------------------------------
# La règle de confiance
# ----------------------------------------------------------------------

def test_sans_proxy_declare_l_en_tete_est_ignore(monkeypatch):
    """
    Le défaut, et le cas qui était vulnérable : aucun proxy déclaré, donc ce
    que la requête raconte sur son origine n'engage qu'elle.
    """
    monkeypatch.delenv(TRUSTED_PROXIES_VARIABLE, raising=False)
    requete = _RequeteFactice("203.0.113.7", {"X-Forwarded-For": "1.2.3.4"})

    assert client_ip(requete) == "203.0.113.7"


def test_un_proxy_declare_est_cru(monkeypatch):
    """Le contre-test : la correction ne doit pas rendre le proxy inutile."""
    monkeypatch.setenv(TRUSTED_PROXIES_VARIABLE, "10.0.0.1")
    requete = _RequeteFactice("10.0.0.1", {"X-Forwarded-For": "1.2.3.4"})

    assert client_ip(requete) == "1.2.3.4"


def test_un_bloc_cidr_est_accepte(monkeypatch):
    """Un réseau Docker se déclare par bloc, pas adresse par adresse."""
    monkeypatch.setenv(TRUSTED_PROXIES_VARIABLE, "172.16.0.0/12")

    assert is_trusted_proxy("172.18.0.2")
    assert not is_trusted_proxy("203.0.113.7")


def test_la_chaine_se_lit_de_droite_a_gauche(monkeypatch):
    """
    Chaque proxy ajoute son prédécesseur à la fin. Prendre le premier élément
    de gauche — ce que faisait le code — revient à prendre exactement la valeur
    qu'un appelant contrôle.
    """
    monkeypatch.setenv(TRUSTED_PROXIES_VARIABLE, "10.0.0.0/8")
    requete = _RequeteFactice("10.0.0.1", {
        # Le client a forgé « 9.9.9.9 » ; les deux derniers maillons sont réels.
        "X-Forwarded-For": "9.9.9.9, 203.0.113.7, 10.0.0.2",
    })

    assert client_ip(requete) == "203.0.113.7"


def test_une_chaine_entierement_interne_retombe_sur_le_pair(monkeypatch):
    """Rien d'exploitable dans la chaîne : l'adresse honnête est celle du pair."""
    monkeypatch.setenv(TRUSTED_PROXIES_VARIABLE, "10.0.0.0/8")
    requete = _RequeteFactice("10.0.0.1", {"X-Forwarded-For": "10.0.0.2, 10.0.0.3"})

    assert client_ip(requete) == "10.0.0.1"


def test_une_adresse_mal_ecrite_est_signalee_et_non_devinee(monkeypatch, caplog):
    """
    « 10.0.0.300 » est une adresse ratée, pas un nom d'hôte. La traiter comme un
    nom ferait taire une faute de frappe, et l'opérateur croirait avoir déclaré
    un proxy qui ne l'est pas.
    """
    monkeypatch.setenv(TRUSTED_PROXIES_VARIABLE, "10.0.0.300")

    with caplog.at_level("ERROR"):
        assert not is_trusted_proxy("10.0.0.1")
        assert not is_trusted_proxy("10.0.0.300")

    assert "illisible" in caplog.text


def test_un_nom_d_hote_peut_etre_declare(monkeypatch):
    """
    Un proxy se désigne parfois par son nom de service — `caddy` sur un réseau
    Docker. Le nom est comparé au pair **tel que le serveur le voit** : cette
    identité vient de la connexion, pas d'un en-tête, donc un appelant distant
    ne peut pas la choisir.
    """
    monkeypatch.setenv(TRUSTED_PROXIES_VARIABLE, "caddy")

    assert is_trusted_proxy("caddy")
    assert not is_trusted_proxy("autre-conteneur")


def test_une_requete_sans_pair_ne_leve_pas(monkeypatch):
    """Un client de test ou une socket Unix n'a pas d'adresse."""
    monkeypatch.delenv(TRUSTED_PROXIES_VARIABLE, raising=False)

    assert client_ip(_RequeteFactice(None, {"X-Forwarded-For": "1.2.3.4"})) == "unknown"


def test_le_schema_transmis_suit_la_meme_regle(monkeypatch):
    """
    `X-Forwarded-Proto` fait poser un en-tête HSTS. Cru sans condition, il le
    fait poser sur une réponse qui n'a jamais été chiffrée.
    """
    entetes = {"x-forwarded-proto": "https"}

    monkeypatch.delenv(TRUSTED_PROXIES_VARIABLE, raising=False)
    assert forwarded_proto(_RequeteFactice("203.0.113.7", entetes)) == "http"

    monkeypatch.setenv(TRUSTED_PROXIES_VARIABLE, "203.0.113.7")
    assert forwarded_proto(_RequeteFactice("203.0.113.7", entetes)) == "https"


# ----------------------------------------------------------------------
# La conséquence : on ne contourne plus la limite ni la détection
# ----------------------------------------------------------------------

@pytest.fixture
def client_limite(monkeypatch):
    """Client dont le budget non authentifié tient en deux requêtes."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin")
    monkeypatch.setenv("GALSEN_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM", "2")
    monkeypatch.setenv("GALSEN_RATE_LIMIT_BURST_MULTIPLIER", "1.0")
    monkeypatch.delenv(TRUSTED_PROXIES_VARIABLE, raising=False)
    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    ancien = rate_limiter_module._rate_limiter
    rate_limiter_module._rate_limiter = None
    try:
        with TestClient(server.app) as instance:
            yield instance
    finally:
        rate_limiter_module._rate_limiter = ancien


def test_un_en_tete_forge_ne_donne_plus_un_quota_illimite(client_limite):
    """
    Le contournement mesuré : une adresse différente à chaque requête donnait
    un seau de jetons neuf à chaque fois, donc aucune limite.
    """
    codes = [
        client_limite.get("/metrics", headers={"X-Forwarded-For": f"1.2.3.{n}"}).status_code
        for n in range(5)
    ]

    assert 429 in codes, f"la limite est toujours contournable : {codes}"


@pytest.fixture
def client_sans_limite(monkeypatch):
    """Client sans limite de débit : le sujet du test est le détecteur."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin")
    monkeypatch.setenv("GALSEN_RATE_LIMIT_ENABLED", "false")
    monkeypatch.delenv(TRUSTED_PROXIES_VARIABLE, raising=False)
    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    ancien = rate_limiter_module._rate_limiter
    rate_limiter_module._rate_limiter = None
    try:
        with TestClient(server.app) as instance:
            yield instance
    finally:
        rate_limiter_module._rate_limiter = ancien


def test_un_attaquant_ne_se_disperse_plus_dans_le_detecteur(client_sans_limite):
    """
    Le détecteur signale une source qui répète des échecs. En changeant
    d'adresse à chaque tentative, un bourrage d'identifiants restait sous le
    seuil de **toutes** les sources à la fois.
    """
    detecteur = get_shared_detector()
    detecteur.clear()

    for n in range(12):
        client_sans_limite.get("/metrics", headers={
            "X-API-Key": f"mauvaise-cle-{n}",
            "X-Forwarded-For": f"5.6.7.{n}",
        })

    resume = detecteur.summary()
    # Une seule source suivie : celle du pair réel. Auparavant, douze adresses
    # annoncées donnaient douze sources d'un échec chacune, toutes sous le seuil.
    assert resume["tracked_sources"] == 1, (
        f"les adresses forgées sont encore comptées séparément : {resume}"
    )
    signalees = {menace["source"] for menace in resume["threats"]}
    assert not any(source.startswith("5.6.7.") for source in signalees)
    # Et le bourrage est effectivement signalé, au lieu de passer inaperçu.
    assert len(resume["threats"]) == 1
    assert resume["threats"][0]["failures"] >= 10
