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
ROUTES_PUBLIQUES = {
    "/", "/health", "/ready", "/live",
    # Les trois portes d'entrée de l'authentification par compte (ADR-029).
    # Elles ne peuvent pas exiger d'authentification : on ne s'authentifie pas
    # pour obtenir son premier identifiant. Ce qui les protège à la place :
    #
    # - le limiteur de taux, présent sur les trois — c'est lui qui rend une
    #   attaque par force brute coûteuse, et son absence ici serait la faute ;
    # - `/auth/register` crée un compte au rôle `user`, jamais davantage : une
    #   élévation demande une décision d'administrateur ;
    # - `/auth/login` répond la même chose pour un compte inconnu et pour un
    #   mot de passe faux, donc n'énumère pas les adresses connues.
    #
    # **Conséquence assumée d'ADR-029, option C** : l'inscription est ouverte.
    # Sur une instance joignable depuis Internet, n'importe qui obtient un
    # compte `user`. C'est ce que « full self-service » veut dire ; restreindre
    # l'inscription serait une décision distincte, à prendre explicitement.
    "/auth/register", "/auth/login", "/auth/refresh",
    # Les deux routes de réinitialisation (ADR-029, dette soldée). Exiger une
    # authentification pour récupérer un mot de passe oublié n'aurait pas de
    # sens : c'est précisément le moment où la personne n'en a plus. Ce qui les
    # protège à la place :
    #
    # - la demande répond **exactement pareil** qu'un compte existe ou non,
    #   donc elle n'énumère aucune adresse ;
    # - le jeton n'est jamais rendu dans la réponse : il part par un canal que
    #   seule la personne concernée lit ;
    # - le jeton est à usage unique, borné dans le temps, et consommé avant
    #   toute validation du nouveau mot de passe ;
    # - le limiteur de taux est présent sur les deux.
    "/auth/password-reset/request", "/auth/password-reset/confirm",
}

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
    """Une exception qui grandit sans qu'on la relise cesse d'être une exception.

    Le contrôle porte sur l'**ensemble exact**, plus seulement sur son cardinal :
    avec un simple compte, retirer une route publique et en ajouter une autre
    passait inaperçu. Chaque entrée doit être écrite ici comme dans
    `ROUTES_PUBLIQUES`, ce qui oblige à relire les deux ensemble.
    """
    chemins = {route.path for route in _routes()}
    inconnues = ROUTES_PUBLIQUES - chemins
    assert not inconnues, f"ROUTES_PUBLIQUES nomme des routes qui n'existent plus : {inconnues}"

    attendues = {
        # Sondes et redirection racine.
        "/", "/health", "/ready", "/live",
        # Portes d'entrée de l'authentification par compte (ADR-029) : on ne
        # s'authentifie pas pour obtenir son premier identifiant.
        "/auth/register", "/auth/login", "/auth/refresh",
        # Réinitialisation : on n'a plus le mot de passe qu'on vient récupérer.
        "/auth/password-reset/request", "/auth/password-reset/confirm",
    }
    assert ROUTES_PUBLIQUES == attendues, (
        "La liste des routes publiques a changé. Chaque entrée doit porter la "
        "raison pour laquelle elle ne peut pas exiger d'authentification, et ce "
        "que le limiteur de débit protège à la place."
    )
