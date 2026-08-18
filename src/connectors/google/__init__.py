"""
Connecteurs Google — liés à une personne, en lecture.

Aucun identifiant n'existe dans cet environnement et aucun n'est fabriqué. Les
hôtes Google, eux, **sont joignables** d'ici (mesuré le 2026-08-14) : ce qui
manque est un identifiant, pas un réseau.

Les connecteurs construisent des requêtes ; `RequestExecutor` les envoie. Cette
séparation rend chaque branche testable sans identifiant et sans réseau.
"""

from .apis import ApiUnknown, GoogleApi, get_api, load_apis
from .base import GoogleReadConnector
from .calendar import CalendarConnector
from .drive import DriveConnector
from .executor import ExecutionResult, RequestExecutor, strip_credentials
from .gmail import GmailConnector

__all__ = [
    "ApiUnknown",
    "CalendarConnector",
    "DriveConnector",
    "ExecutionResult",
    "GmailConnector",
    "GoogleReadConnector",
    "GoogleApi",
    "RequestExecutor",
    "get_api",
    "load_apis",
    "strip_credentials",
]
