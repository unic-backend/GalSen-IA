"""
OAuth 2.0 pour GalSen IA — le flux, sa configuration, ses refus.

Aucun identifiant n'est fabriqué et aucun appel réseau n'est fait depuis ce
paquet. Dans cet environnement, aucun fournisseur n'est configuré : l'état
rapporté est `NOT_CONFIGURED`, avec le **nom** des variables manquantes.
"""

from .config import (
    OAuthNotConfigured,
    Provider,
    ProviderUnknown,
    ScopeRefused,
    configuration_report,
    get_provider,
    load_providers,
)
from .flow import (
    AuthorizationStart,
    FlowRefused,
    PendingAuthorization,
    PendingStore,
    challenge_for,
    flow_report,
    generate_state,
    generate_verifier,
    start_authorization,
    token_request,
)
from .tokens import (
    StoredToken,
    TokenStorageUnavailable,
    TokenStore,
    require_encryption,
)

__all__ = [
    "AuthorizationStart",
    "FlowRefused",
    "OAuthNotConfigured",
    "PendingAuthorization",
    "PendingStore",
    "Provider",
    "ProviderUnknown",
    "ScopeRefused",
    "challenge_for",
    "configuration_report",
    "flow_report",
    "generate_state",
    "generate_verifier",
    "get_provider",
    "load_providers",
    "require_encryption",
    "start_authorization",
    "StoredToken",
    "token_request",
    "TokenStorageUnavailable",
    "TokenStore",
]
