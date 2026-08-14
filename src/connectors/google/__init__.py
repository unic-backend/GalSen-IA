"""
Connecteurs Google — liés à une personne, en lecture.

Aucun identifiant n'existe dans cet environnement, aucun n'est fabriqué, et
aucun appel réseau n'est fait : ces connecteurs **construisent** des requêtes.
"""

from .apis import ApiUnknown, GoogleApi, get_api, load_apis
from .gmail import GmailConnector

__all__ = ["ApiUnknown", "GmailConnector", "GoogleApi", "get_api", "load_apis"]
