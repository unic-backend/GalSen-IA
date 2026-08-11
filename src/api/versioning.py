"""
Versionnement et dépréciation des routes de l'API (VOLET 15, chapitres 04 et 08).

Les deux chapitres demandent de tenir un contrôle de version et de « retirer les
API obsolètes en sécurité ». Il n'existait ni l'un ni l'autre : aucun préfixe de
version, aucune façon d'annoncer qu'une route va disparaître. Le seul retrait
possible était la suppression — l'appelant l'apprenait par un 404 en production.

Ce module ne crée pas de schéma de versionnage d'URL (décision → ADR-011). Il
fournit le minimum qui manquait vraiment : **annoncer** qu'une route est en fin
de vie, assez tôt pour que l'appelant s'en aille de lui-même.

Le mécanisme suit la RFC 8594 : une réponse dépréciée porte `Deprecation: true`
et, quand la date de retrait est connue, `Sunset: <date HTTP>`. Les deux en-têtes
sont standards et déjà compris par des clients existants.

**Le registre est vide.** Aucune route n'est dépréciée aujourd'hui, et en
inscrire une pour montrer que le mécanisme fonctionne fabriquerait un fait —
`.claude/rules/verification.md`. Le mécanisme est vérifié par les tests, pas par
une fausse entrée.
"""

from dataclasses import dataclass
from email.utils import formatdate
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.version import __version__


@dataclass(frozen=True)
class Deprecation:
    """
    Annonce de fin de vie d'une route.

    Attributes:
        path: Chemin exact de la route, tel qu'il est monté.
        since: Version de la plateforme depuis laquelle la route est dépréciée.
        sunset: Horodatage Unix du retrait prévu, ou None s'il n'est pas décidé.
        replacement: Route à utiliser à la place, ou None s'il n'y en a pas.
        reason: Pourquoi elle disparaît, en une phrase.
    """

    path: str
    since: str
    reason: str
    sunset: Optional[float] = None
    replacement: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Retourne l'annonce sous forme sérialisable."""
        return {
            "path": self.path,
            "since": self.since,
            "reason": self.reason,
            "sunset": formatdate(self.sunset, usegmt=True) if self.sunset else None,
            "replacement": self.replacement,
        }


# Routes dépréciées, par chemin. Vide tant qu'aucune ne l'est réellement.
DEPRECATIONS: Dict[str, Deprecation] = {}


def deprecation_for(path: str) -> Optional[Deprecation]:
    """Retourne l'annonce de dépréciation d'un chemin, ou None."""
    return DEPRECATIONS.get(path)


def deprecation_headers(path: str) -> Dict[str, str]:
    """
    Retourne les en-têtes RFC 8594 à poser sur la réponse d'une route dépréciée.

    Args:
        path: Chemin de la route servie.

    Returns:
        Un dictionnaire vide si la route n'est pas dépréciée.
    """
    annonce = deprecation_for(path)
    if annonce is None:
        return {}

    entetes = {"Deprecation": "true"}
    if annonce.sunset is not None:
        entetes["Sunset"] = formatdate(annonce.sunset, usegmt=True)
    if annonce.replacement is not None:
        # `Link` avec la relation `successor-version` est la façon standard de
        # désigner le remplaçant ; un message en clair dans le corps serait
        # invisible pour un client automatisé.
        entetes["Link"] = f'<{annonce.replacement}>; rel="successor-version"'
    return entetes


class DeprecationHeadersMiddleware(BaseHTTPMiddleware):
    """
    Pose les en-têtes de dépréciation sur les réponses concernées.

    Un intergiciel plutôt qu'une dépendance par route : l'annonce doit valoir
    pour toutes les réponses d'une route dépréciée, y compris ses erreurs, et
    une dépendance oubliée redonnerait le silence qu'on cherche à supprimer.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Ajoute les en-têtes RFC 8594 quand la route est dépréciée."""
        reponse = await call_next(request)
        for nom, valeur in deprecation_headers(request.url.path).items():
            reponse.headers[nom] = valeur
        return reponse


def version_report() -> Dict[str, Any]:
    """
    Décrit la version servie et l'état des dépréciations.

    Le rapport dit explicitement qu'il n'existe pas de versionnage d'URL, plutôt
    que de laisser croire à un `/v1` implicite : un appelant qui suppose une
    stabilité que rien ne garantit construit sur du sable.

    Returns:
        La version, le schéma de versionnage et la liste des dépréciations.
    """
    return {
        "version": __version__,
        "url_versioning": None,
        "url_versioning_note": (
            "Aucun préfixe de version dans les URL. Toute route peut changer "
            "tant que la plateforme est un prototype ; les changements de "
            "rupture sont annoncés par la dépréciation (ADR-011)."
        ),
        "deprecations": [annonce.to_dict() for annonce in DEPRECATIONS.values()],
        "deprecated_count": len(DEPRECATIONS),
    }
