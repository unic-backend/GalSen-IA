"""
`/cloud/*` est annoncée en fin de vie (ADR-016, étape 2 ; ADR-011).

ADR-016 a mesuré que les services `file` et `cloud` sont une même conception
écrite deux fois. ADR-011 interdit d'en supprimer une de but en blanc sur une
version publiée : les six routes restent, et **s'annoncent**.

Deux défauts ont été trouvés en les inscrivant, et chacun a son test ici :

1. Le registre de dépréciation était indexé par **chemin exact**, donc aucune
   route paramétrée ne pouvait être dépréciée — `/cloud/{file_id}` n'aurait
   jamais reconnu `/cloud/file_ab12`. La moitié de l'annonce aurait été
   silencieuse, sans que rien ne le signale.
2. `/file/stats` et `/cloud/stats` étaient **inatteignables** : déclarées après
   `/{file_id}`, elles étaient captées par lui. En écrivant la règle générale
   plutôt que les deux cas, `/calendar/stats` et `/email/stats` sont apparues —
   **quatre** endpoints documentés d'une version publiée que personne ne pouvait
   appeler.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402

import src.api.server as server_module  # noqa: E402
from src.api.server import app  # noqa: E402

CLE = "cle-depreciation"


@pytest.fixture
def client(monkeypatch):
    """
    Client HTTP authentifié, avec restauration de l'état RBAC partagé.

    Le registre de clés est global au processus : le laisser modifié ferait
    échouer un autre fichier de tests selon l'ordre d'exécution.
    """
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:admin")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    yield TestClient(app)
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def _entetes(reponse):
    """Extrait les en-têtes RFC 8594 d'une réponse."""
    return {
        nom.lower(): valeur for nom, valeur in reponse.headers.items()
        if nom.lower() in ("deprecation", "sunset", "link")
    }


# ----------------------------------------------------------------------
# L'annonce atteint les routes paramétrées
# ----------------------------------------------------------------------

def test_une_route_parametree_porte_l_annonce(client):
    """
    Le défaut central. `request.url.path` vaut `/cloud/file_ab12` et le registre
    est indexé par `/cloud/{file_id}` : la correspondance par chemin exact ne
    pouvait rien reconnaître. Trois des six routes `/cloud/*` sont paramétrées.
    """
    reponse = client.get("/cloud/file_inexistant", headers={"X-API-Key": CLE})

    entetes = _entetes(reponse)
    assert entetes["deprecation"] == "true"
    assert "/file/{file_id}" in entetes["link"]


def test_l_annonce_vaut_aussi_quand_la_route_echoue(client):
    """
    Un appelant dont les paramètres sont mauvais depuis des mois n'appelle la
    route qu'en erreur — c'est justement celui qu'il faut prévenir.
    """
    reponse = client.get("/cloud/file_inexistant", headers={"X-API-Key": CLE})

    assert reponse.status_code == 404
    assert _entetes(reponse)["deprecation"] == "true"


def test_une_route_litterale_porte_aussi_l_annonce(client):
    """Le contre-test : réparer les gabarits ne doit pas casser les chemins fixes."""
    reponse = client.get("/cloud/stats", headers={"X-API-Key": CLE})

    assert reponse.status_code == 200
    assert _entetes(reponse)["deprecation"] == "true"


def test_le_service_de_fichiers_n_est_pas_deprecie(client):
    """
    Le remplaçant ne doit pas porter l'annonce du remplacé — ce serait dire à
    l'appelant de partir de là où on l'envoie.
    """
    reponse = client.get("/file/stats", headers={"X-API-Key": CLE})

    assert reponse.status_code == 200
    assert _entetes(reponse) == {}


def test_les_six_routes_cloud_sont_marquees_dans_l_openapi():
    """
    L'en-tête prévient un client automatisé ; la documentation prévient un
    humain qui choisit une route. Les deux sont nécessaires.
    """
    schema = app.openapi()
    depreciees = {
        (chemin, methode)
        for chemin, operations in schema["paths"].items()
        for methode, operation in operations.items()
        if operation.get("deprecated")
    }

    assert depreciees == {
        ("/cloud/upload", "post"),
        ("/cloud/list", "post"),
        ("/cloud/stats", "get"),
        ("/cloud/{file_id}", "get"),
        ("/cloud/{file_id}", "delete"),
        ("/cloud/{file_id}/download", "get"),
    }


def test_aucune_date_de_retrait_n_est_inventee(client):
    """
    ADR-011 : une date inventée serait pire qu'absente, on la croirait. Le
    retrait de `/cloud/*` n'est pas daté — il vient après le retrait de
    `CloudFileItem`, qui n'est pas fait.
    """
    reponse = client.get("/cloud/stats", headers={"X-API-Key": CLE})

    assert "sunset" not in _entetes(reponse)


# ----------------------------------------------------------------------
# Les routes de statistiques étaient captées par `/{file_id}`
# ----------------------------------------------------------------------

@pytest.mark.parametrize("chemin", [
    "/file/stats", "/cloud/stats", "/calendar/stats", "/email/stats",
])
def test_les_statistiques_sont_atteignables(client, chemin):
    """
    FastAPI retient la **première** route qui correspond. `/{id}` était déclarée
    avant, donc `GET /file/stats` rendait « Fichier stats introuvable ».

    Quatre routes, pas deux : la règle générale ci-dessous a trouvé le calendrier
    et les e-mails alors que la dépréciation de `/cloud/*` ne les concernait pas.
    Quatre endpoints documentés d'une version publiée, morts.
    """
    reponse = client.get(chemin, headers={"X-API-Key": CLE})

    assert reponse.status_code == 200
    assert "total" in reponse.json()


def test_un_chemin_litteral_precede_toujours_son_gabarit():
    """
    La règle, plutôt que les quatre cas trouvés : dans un même préfixe, un
    chemin fixe déclaré après un gabarit qui l'accepte **pour la même méthode**
    est du code mort.

    La méthode compte : `POST /file/list` cohabite sans problème avec
    `GET /file/{file_id}`, parce que Starlette poursuit sa recherche quand le
    chemin correspond mais pas la méthode.
    """
    from fastapi.routing import APIRoute

    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    captees = []
    for position, route in enumerate(routes):
        if "{" in route.path:
            continue
        for precedente in routes[:position]:
            if ("{" in precedente.path
                    and precedente.path_regex.match(route.path)
                    and (route.methods or set()) & (precedente.methods or set())):
                captees.append((route.path, precedente.path))
                break

    assert captees == [], f"Routes inatteignables : {captees}"
