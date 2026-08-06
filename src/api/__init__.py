"""
Module API pour la plateforme GalSen IA.

Expose les fonctionnalités du noyau via une API RESTful construite avec FastAPI.

Composants :
- server.py : Serveur FastAPI avec endpoints REST
- rate_limiter.py : Limiteur de taux configurable avec interface abstraite
- health.py : Vérificateur de santé avec interface abstraite
"""

from src.api.health import (
    ComponentHealth,
    ComponentHealthChecker,
    HealthChecker,
    HealthReport,
    get_health_checker,
    init_health_checker,
)
from src.api.rate_limiter import (
    APIRateLimiter,
    InMemoryRateLimiter,
    RateLimitConfig,
    RateLimitInfo,
    get_rate_limiter,
    set_valid_api_key_digests,
    rate_limit_dependency,
)

from src.api.rbac import (
    Permission,
    RBACContext,
    RBACManager,
    Role,
    get_permissions_for_role,
    parse_api_key_mappings,
)

__all__ = [
    # Limiteur de taux
    "APIRateLimiter",
    "InMemoryRateLimiter",
    "RateLimitConfig",
    "RateLimitInfo",
    "get_rate_limiter",
    "set_valid_api_key_digests",
    "rate_limit_dependency",
    # Vérificateur de santé
    "ComponentHealth",
    "ComponentHealthChecker",
    "HealthChecker",
    "HealthReport",
    "get_health_checker",
    "init_health_checker",
    # RBAC
    "Permission",
    "RBACContext",
    "RBACManager",
    "Role",
    "get_permissions_for_role",
    "parse_api_key_mappings",
]
