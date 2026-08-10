"""
Package d'authentification GalSen IA (ADR-007).

Fournit l'authentification hybride JWT/OAuth en parallèle de l'API-key RBAC
existant. Les dépendances FastAPI produites par ce package coexistent avec
require_auth() dans server.py — aucune régression sur les endpoints existants.
"""

from .jwt_handler import JWTHandler
from .user_manager import UserManager
from .session_manager import SessionManager

__all__ = [
    "JWTHandler",
    "UserManager",
    "SessionManager",
]
