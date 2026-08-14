"""
Google API surfaces, read from configuration.

Same rule as the OAuth endpoints: a base URL is configuration, not code. Each
entry names the documentation that describes it, so the value can be confronted
with its authority instead of being trusted because it is written down.

Nothing here is fetched when the file is read. The API base URLs have **not**
been confronted with their documentation — unlike the OAuth endpoints, which
were, on 2026-08-14 — so they remain a copy until someone checks them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml

#: Chemin par défaut de la configuration des API Google.
CONFIGURATION_PAR_DEFAUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "config", "connectors", "google.yaml",
)


class ApiUnknown(ValueError):
    """Une API Google non déclarée. Aucune adresse n'est devinée."""


@dataclass(frozen=True)
class GoogleApi:
    """
    Une surface d'API Google déclarée.

    Attributes:
        name: Son nom court — `gmail`.
        base_url: La racine des appels.
        documentation_url: Ce qui fait autorité sur `base_url`.
        scope_read: La portée OAuth de lecture correspondante.
        user_id: L'identifiant d'utilisateur employé, quand l'API en demande un.
    """

    name: str
    base_url: str
    documentation_url: str
    scope_read: str
    user_id: str = "me"

    def url(self, chemin: str) -> str:
        """
        Construit une adresse sous la racine de cette API.

        Args:
            chemin: Le chemin relatif, avec ou sans barre initiale.

        Returns:
            L'adresse complète.
        """
        return f"{self.base_url.rstrip('/')}/{chemin.lstrip('/')}"

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "name": self.name,
            "base_url": self.base_url,
            "documentation_url": self.documentation_url,
            "scope_read": self.scope_read,
            "user_id": self.user_id,
        }


def load_apis(path: Optional[str] = None) -> Dict[str, GoogleApi]:
    """
    Charge les API déclarées.

    Args:
        path: Chemin de la configuration.

    Returns:
        Les API par nom. Vide si le fichier est absent.
    """
    chemin = path or CONFIGURATION_PAR_DEFAUT
    try:
        with open(chemin, "r", encoding="utf-8") as fichier:
            donnees = yaml.safe_load(fichier) or {}
    except FileNotFoundError:
        return {}

    apis: Dict[str, GoogleApi] = {}
    for nom, entree in (donnees.get("apis") or {}).items():
        apis[nom] = GoogleApi(
            name=nom,
            base_url=(entree or {}).get("base_url", ""),
            documentation_url=(entree or {}).get("documentation_url", ""),
            scope_read=(entree or {}).get("scope_read", ""),
            user_id=(entree or {}).get("user_id", "me"),
        )
    return apis


def get_api(name: str, path: Optional[str] = None) -> GoogleApi:
    """
    Retourne une API déclarée.

    Args:
        name: Son nom.
        path: Chemin de la configuration.

    Returns:
        L'API.

    Raises:
        ApiUnknown: Si elle n'est pas déclarée. Une adresse inventée enverrait
            un jeton d'accès quelque part que personne n'a choisi.
    """
    apis = load_apis(path)
    api = apis.get(name)
    if api is None:
        raise ApiUnknown(
            f"API Google '{name}' non déclarée. Déclarées : "
            f"{', '.join(sorted(apis)) or 'aucune'}."
        )
    return api
