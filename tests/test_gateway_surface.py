"""
Surface exposée par la passerelle API (VOLET 15, chapitres 02 et 03).

La passerelle n'est pas un service séparé : c'est l'application FastAPI
elle-même, et ses garde-fous sont des dépendances déclarées route par route.
Un tel dispositif ne tombe pas en panne bruyamment — il tombe en panne
silencieusement, le jour où quelqu'un ajoute une route en oubliant sa
dépendance. Ces tests énumèrent les routes réelles de l'application et
verrouillent ce qui doit rester vrai de **toutes**.
"""

import os

import pytest
from fastapi.routing import APIRoute

os.environ.setdefault("GALSEN_API_KEYS", "test-key-0123456789abcdef")

from src.api.server import app  # noqa: E402  (après la clé de test)

# Les seules routes délibérément ouvertes.
#
# `/` ne fait que rediriger vers le tableau de bord — une racine qui répondait
# 404 laissait croire que rien n'écoutait. Les trois sondes doivent répondre
# sans clé : un orchestrateur qui redémarre un conteneur ne s'authentifie pas,
# et une sonde de vivacité protégée par une clé expirée fait redémarrer une
# application parfaitement saine.
ROUTES_PUBLIQUES = {"/", "/health", "/ready", "/live"}

# `/` est servie par une redirection statique, sans travail derrière : la
# compter dans le budget de l'appelant n'apporte rien.
ROUTES_SANS_LIMITEUR = {"/"}


def _routes():
    """Retourne les routes applicatives réelles, montées dans l'application."""
    return [route for route in app.routes if isinstance(route, APIRoute)]


def _dependances(route) -> str:
    """Retourne les dépendances d'une route sous forme textuelle."""
    return " ".join(str(dep.call) for dep in route.dependant.dependencies)


def test_l_application_expose_bien_des_routes():
    """Un test qui n'énumère rien passerait toujours."""
    assert len(_routes()) > 50


@pytest.mark.parametrize("route", _routes(), ids=lambda r: f"{sorted(r.methods - {'HEAD'})}{r.path}")
def test_toute_route_exige_une_authentification(route):
    """
    Chapitre 03, étapes 2 et 3 : authentifier puis autoriser, avant tout le reste.

    Une route ajoutée sans `require_auth` ni `require_permission` est ouverte à
    l'internet entier, et rien ne le signale au moment où elle est écrite.
    """
    if route.path in ROUTES_PUBLIQUES:
        return
    dependances = _dependances(route)
    assert "require_auth" in dependances or "require_permission" in dependances, (
        f"{route.path} n'exige ni authentification ni permission ; "
        f"si elle doit être publique, ajoutez-la à ROUTES_PUBLIQUES et dites pourquoi"
    )


@pytest.mark.parametrize("route", _routes(), ids=lambda r: f"{sorted(r.methods - {'HEAD'})}{r.path}")
def test_toute_route_passe_par_le_limiteur(route):
    """
    Chapitre 05 : la limitation de débit est le seul contrôle de trafic livré.

    Elle ne protège que ce qu'elle couvre ; une route qui la contourne est le
    chemin qu'un appelant abusif finira par trouver.
    """
    if route.path in ROUTES_SANS_LIMITEUR:
        return
    assert "rate_limit_dependency" in _dependances(route), (
        f"{route.path} ne passe pas par le limiteur de débit"
    )


def test_la_liste_des_routes_publiques_ne_derive_pas():
    """Une exception qui grandit sans qu'on la relise cesse d'être une exception."""
    chemins = {route.path for route in _routes()}
    inconnues = ROUTES_PUBLIQUES - chemins
    assert not inconnues, f"ROUTES_PUBLIQUES nomme des routes qui n'existent plus : {inconnues}"
    assert len(ROUTES_PUBLIQUES) == 4
