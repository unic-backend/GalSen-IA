"""
Ce qu'une erreur 500 dit à l'appelant (VOLET 15, chapitre 03, étape 6).

Le chapitre range la détection d'erreur parmi ses contrôles qualité et le
chapitre 07 demande de protéger les données sensibles de l'API. Quatre routes
recopiaient le texte de l'exception dans `detail` : un chemin de fichier, un
nom d'hôte interne ou un fragment de requête partait au client dès qu'il
savait faire échouer l'appel.
"""

import os
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GALSEN_API_KEYS", "test-key-0123456789abcdef")

from src.api import server  # noqa: E402
from src.api.rate_limiter import set_valid_api_key_digests  # noqa: E402

CLE = "test-key-0123456789abcdef"

# Ce qu'une exception interne peut transporter, et qui ne doit jamais ressortir.
FUITE = "http://interne:11434 (fichier /home/user/GalSen-IA/data/knowledge.sqlite)"


@pytest.fixture
def client(monkeypatch):
    """Client administrateur sur l'application réelle."""
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin")
    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())
    with TestClient(server.app) as instance:
        yield instance


def _explose(*args, **kwargs):
    """Lève une exception dont le message contient de l'information interne."""
    raise RuntimeError(f"connexion refusée vers {FUITE}")


def test_le_message_d_exception_ne_part_pas_au_client(client, monkeypatch):
    """Mesuré avant correction : la réponse contenait l'hôte et le chemin."""
    monkeypatch.setattr(server.search_manager, "search", _explose)

    reponse = client.post("/search", json={"query": "test"}, headers={"X-API-Key": CLE})

    assert reponse.status_code == 500
    detail = reponse.json()["detail"]
    assert "interne:11434" not in detail
    assert "knowledge.sqlite" not in detail
    assert FUITE not in detail


def test_l_appelant_recoit_un_identifiant_d_incident(client, monkeypatch):
    """
    Taire la cause sans rien donner en échange rend le support impossible.

    L'appelant obtient un identifiant qu'il peut citer ; l'opérateur le retrouve
    dans le journal, avec la pile d'appels complète.
    """
    monkeypatch.setattr(server.search_manager, "search", _explose)

    detail = client.post("/search", json={"query": "test"},
                         headers={"X-API-Key": CLE}).json()["detail"]

    assert re.search(r"incident [0-9a-f]{12}", detail), detail


def test_deux_incidents_ne_portent_pas_le_meme_identifiant(client, monkeypatch):
    """Un identifiant constant ne distinguerait rien dans le journal."""
    monkeypatch.setattr(server.search_manager, "search", _explose)

    identifiants = {
        client.post("/search", json={"query": "test"},
                    headers={"X-API-Key": CLE}).json()["detail"]
        for _ in range(3)
    }

    assert len(identifiants) == 3


def test_la_cause_reelle_est_journalisee(client, monkeypatch, caplog):
    """La cause n'est pas perdue : elle change de destinataire."""
    monkeypatch.setattr(server.search_manager, "search", _explose)

    with caplog.at_level("ERROR", logger="src.api.server"):
        detail = client.post("/search", json={"query": "test"},
                             headers={"X-API-Key": CLE}).json()["detail"]

    incident = re.search(r"incident ([0-9a-f]{12})", detail).group(1)
    journal = caplog.text
    assert incident in journal
    assert "interne:11434" in journal
    assert "RuntimeError" in journal


def test_aucune_route_ne_recopie_une_exception_dans_un_500():
    """
    Le correctif tient sur quatre appels ; ce test le tient sur les suivants.

    Il lit la source plutôt que d'exercer chaque route : provoquer une panne
    interne sur les 63 routes demanderait de casser chaque moteur un par un,
    alors que le défaut est visible à l'écriture.
    """
    source = (Path(server.__file__)).read_text(encoding="utf-8")
    fautifs = re.findall(r"status_code=500[^)]*\{(?:str\()?e[\)\}]", source)

    assert not fautifs, (
        f"{len(fautifs)} route(s) recopient le texte d'une exception dans un 500 ; "
        f"utilisez erreur_interne() qui journalise la cause et rend un identifiant"
    )


def test_une_erreur_de_requete_reste_un_400_lisible(client):
    """
    Le correctif ne doit pas rendre muettes les erreurs que l'appelant peut corriger.

    Une requête invalide est sa faute, et le lui dire précisément est utile ;
    seule la panne interne devient opaque.
    """
    reponse = client.post("/search", json={}, headers={"X-API-Key": CLE})

    assert reponse.status_code == 422
    assert reponse.json()["detail"]
