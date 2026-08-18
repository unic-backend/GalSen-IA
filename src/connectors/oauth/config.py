"""
OAuth client configuration: read from the environment, never from the code.

A client secret in a repository is a client secret published. This module reads
providers from `config/oauth/providers.yaml` — endpoints, scopes, and the
**names** of the environment variables that carry the credentials — and it never
holds a secret in an attribute: each value is re-read at the moment it is used,
so nothing survives in a serialisable object, a traceback, or a debugger frame.

Two refusals live here, and both matter more than they look:

**No credentials means NOT_CONFIGURED, never a guess.** The platform does not
have Google credentials in this environment and will not invent any. Every path
that would need them reports which variables are missing, by name.

**A scope that is not declared cannot be requested.** OAuth's failure mode is
asking for too much, once, at the only moment a person is likely to click yes.
The allowlist lives in configuration, next to the provider, and a request beyond
it is refused before any URL is built.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

#: Chemin par défaut du registre des fournisseurs.
REGISTRE_PAR_DEFAUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "config", "oauth", "providers.yaml",
)


class OAuthNotConfigured(RuntimeError):
    """Les identifiants d'un fournisseur sont absents. Nomme ce qui manque."""


class ProviderUnknown(ValueError):
    """Un fournisseur qui n'est pas au registre. Aucun n'est deviné."""


class ScopeRefused(ValueError):
    """Une portée demandée hors de celles déclarées pour ce fournisseur."""


@dataclass(frozen=True)
class Provider:
    """
    Un fournisseur OAuth, tel que la configuration le déclare.

    Attributes:
        id: Identifiant court — `google`.
        name: Nom lisible.
        discovery_url: Le document que le fournisseur publie lui-même. Il fait
            autorité sur les points d'accès ci-dessous ; ceux-ci en sont une
            copie, à confronter au moment de la configuration.
        authorization_endpoint: Où la personne est envoyée pour consentir.
        token_endpoint: Où le code est échangé contre des jetons.
        revocation_endpoint: Où un accès est retiré côté fournisseur.
        client_id_variable: **Nom** de la variable portant l'identifiant client.
        client_secret_variable: **Nom** de la variable portant le secret.
        redirect_uri_variable: **Nom** de la variable portant l'URI de retour.
        allowed_scopes: Les portées que la plateforme s'autorise à demander.
    """

    id: str
    name: str
    discovery_url: str
    authorization_endpoint: str
    token_endpoint: str
    revocation_endpoint: str
    client_id_variable: str
    client_secret_variable: str
    redirect_uri_variable: str
    allowed_scopes: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Les valeurs, relues à chaque appel
    # ------------------------------------------------------------------

    def _lire(self, variable: str) -> Optional[str]:
        """Lit une variable, la chaîne vide valant absence."""
        valeur = os.environ.get(variable)
        return valeur if valeur else None

    def missing_variables(self) -> List[str]:
        """
        Les variables d'environnement attendues qui sont absentes.

        Returns:
            Leurs noms, dans l'ordre de déclaration. Jamais de valeur.
        """
        return [
            nom for nom in (
                self.client_id_variable,
                self.client_secret_variable,
                self.redirect_uri_variable,
            )
            if self._lire(nom) is None
        ]

    def is_configured(self) -> bool:
        """Indique si les trois valeurs sont présentes. Aucun appel réseau."""
        return not self.missing_variables()

    def client_id(self) -> str:
        """
        L'identifiant client.

        Returns:
            Sa valeur, relue depuis l'environnement.

        Raises:
            OAuthNotConfigured: Si une variable manque, nommée dans le message.
        """
        return self._exiger(self.client_id_variable)

    def client_secret(self) -> str:
        """
        Le secret client.

        Il n'est **jamais** conservé en attribut ni retourné dans un rapport :
        seule la mécanique d'échange de jetons l'appelle, au moment de l'appel.

        Returns:
            Sa valeur, relue depuis l'environnement.

        Raises:
            OAuthNotConfigured: Si une variable manque.
        """
        return self._exiger(self.client_secret_variable)

    def redirect_uri(self) -> str:
        """
        L'URI de retour déclarée.

        Elle vient de l'environnement et **jamais d'une requête** : une URI de
        retour choisie par l'appelant est une redirection ouverte, c'est-à-dire
        un code d'autorisation livré à qui la demande.

        Returns:
            Sa valeur.

        Raises:
            OAuthNotConfigured: Si une variable manque.
        """
        return self._exiger(self.redirect_uri_variable)

    def _exiger(self, variable: str) -> str:
        """Lit une variable ou refuse en nommant ce qui manque."""
        valeur = self._lire(variable)
        if valeur is None:
            raise OAuthNotConfigured(
                f"Fournisseur '{self.id}' : variable '{variable}' absente. "
                f"Manquantes : {', '.join(self.missing_variables()) or variable}. "
                "Aucun identifiant n'est fabriqué."
            )
        return valeur

    # ------------------------------------------------------------------
    # Les portées
    # ------------------------------------------------------------------

    def check_scopes(self, scopes: List[str]) -> List[str]:
        """
        Vérifie que les portées demandées sont toutes déclarées.

        Args:
            scopes: Les portées voulues.

        Returns:
            Les portées, dédoublonnées et triées.

        Raises:
            ScopeRefused: Si l'une d'elles n'est pas déclarée, ou si la liste
                est vide — demander « rien » produirait un consentement que la
                personne ne pourrait pas interpréter.
        """
        voulues = sorted({portee for portee in scopes if portee})
        if not voulues:
            raise ScopeRefused(
                f"Fournisseur '{self.id}' : aucune portée demandée. Un écran de "
                "consentement sans objet ne s'interprète pas."
            )

        hors_liste = [p for p in voulues if p not in self.allowed_scopes]
        if hors_liste:
            raise ScopeRefused(
                f"Fournisseur '{self.id}' : portée(s) non déclarée(s) "
                f"{', '.join(hors_liste)}. Les portées autorisées sont dans "
                "`config/oauth/providers.yaml` ; demander au-delà est le mode "
                "d'échec propre à OAuth."
            )
        return voulues

    def as_dict(self) -> Dict[str, Any]:
        """
        Représentation sérialisable, **sans aucune valeur de secret**.

        Returns:
            Les points d'accès, les portées, l'état de configuration, et le
            **nom** des variables manquantes.
        """
        return {
            "id": self.id,
            "name": self.name,
            "discovery_url": self.discovery_url,
            "authorization_endpoint": self.authorization_endpoint,
            "token_endpoint": self.token_endpoint,
            "revocation_endpoint": self.revocation_endpoint,
            "allowed_scopes": list(self.allowed_scopes),
            "configured": self.is_configured(),
            "missing_variables": self.missing_variables(),
        }


def load_providers(path: Optional[str] = None) -> Dict[str, Provider]:
    """
    Charge les fournisseurs déclarés.

    Args:
        path: Chemin du registre. Par défaut `config/oauth/providers.yaml`.

    Returns:
        Les fournisseurs, par identifiant. Vide si le fichier est absent —
        l'absence de registre rend la couche muette, jamais permissive.
    """
    chemin = path or REGISTRE_PAR_DEFAUT
    try:
        with open(chemin, "r", encoding="utf-8") as fichier:
            donnees = yaml.safe_load(fichier) or {}
    except FileNotFoundError:
        return {}

    fournisseurs: Dict[str, Provider] = {}
    for entree in donnees.get("providers", []) or []:
        identifiant = (entree or {}).get("id")
        if not identifiant:
            continue
        fournisseurs[identifiant] = Provider(
            id=identifiant,
            name=entree.get("name", identifiant),
            discovery_url=entree.get("discovery_url", ""),
            authorization_endpoint=entree.get("authorization_endpoint", ""),
            token_endpoint=entree.get("token_endpoint", ""),
            revocation_endpoint=entree.get("revocation_endpoint", ""),
            client_id_variable=entree.get("client_id_variable", ""),
            client_secret_variable=entree.get("client_secret_variable", ""),
            redirect_uri_variable=entree.get("redirect_uri_variable", ""),
            allowed_scopes=list(entree.get("allowed_scopes", []) or []),
        )
    return fournisseurs


def get_provider(provider_id: str, path: Optional[str] = None) -> Provider:
    """
    Retourne un fournisseur déclaré.

    Args:
        provider_id: Son identifiant.
        path: Chemin du registre.

    Returns:
        Le fournisseur.

    Raises:
        ProviderUnknown: S'il n'est pas au registre. Aucun n'est deviné : un
            point d'accès inventé enverrait une personne consentir ailleurs.
    """
    fournisseurs = load_providers(path)
    fournisseur = fournisseurs.get(provider_id)
    if fournisseur is None:
        raise ProviderUnknown(
            f"Fournisseur '{provider_id}' absent du registre. "
            f"Déclarés : {', '.join(sorted(fournisseurs)) or 'aucun'}."
        )
    return fournisseur


def configuration_report(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Ce qui est déclaré, et ce qui manque pour s'en servir.

    Args:
        path: Chemin du registre.

    Returns:
        L'état de chaque fournisseur. Aucun secret, seulement des **noms** de
        variables.
    """
    fournisseurs = load_providers(path)
    return {
        "registry_path": path or REGISTRE_PAR_DEFAUT,
        "providers": [f.as_dict() for f in fournisseurs.values()],
        "configured": sorted(f.id for f in fournisseurs.values() if f.is_configured()),
        "not_configured": sorted(
            f.id for f in fournisseurs.values() if not f.is_configured()
        ),
        "note": (
            "Les points d'accès sont une copie de ce que le fournisseur publie "
            "à son `discovery_url`. Les confronter appartient à qui détient les "
            "identifiants ; aucun appel réseau n'est fait ici."
        ),
    }
