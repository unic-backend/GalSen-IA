"""
RBAC — Role-Based Access Control for GalSen IA.

Defines roles, permissions and the authorization logic used by the API layer.
Every protected endpoint declares the minimum permission required.

Roles are associated with API keys via the GALSEN_API_KEYS environment variable
using the format: "key1:role1,key2:role2".

A role without an explicit mapping defaults to "user".
"""

from __future__ import annotations

import enum
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Optional, Set

logger = logging.getLogger(__name__)


class Role(str, enum.Enum):
    """Rôles utilisateur dans la plateforme GalSen IA."""

    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"
    READONLY = "readonly"


class Permission(str, enum.Enum):
    """Permissions granulaires pour chaque ressource de la plateforme."""

    # Santé et métadonnées
    HEALTH_VIEW = "health:view"

    # Mémoire
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_DELETE = "memory:delete"

    # Modèles IA
    MODEL_GENERATE = "model:generate"
    MODEL_MANAGE = "model:manage"

    # Outils
    TOOL_EXECUTE = "tool:execute"
    TOOL_MANAGE = "tool:manage"

    # Connaissances
    KNOWLEDGE_SEARCH = "knowledge:search"
    KNOWLEDGE_WRITE = "knowledge:write"

    # Approbation humaine
    APPROVAL_VIEW = "approval:view"
    APPROVAL_DECIDE = "approval:decide"

    # Connecteurs externes (ADR-007)
    # La lecture décrit les intégrations et interroge leur état ; la
    # vérification déclenche un appel sortant, elle est donc distinguée.
    CONNECTOR_VIEW = "connector:view"
    CONNECTOR_CHECK = "connector:check"

    # Administration
    ADMIN_MANAGE = "admin:manage"
    ADMIN_AUDIT = "admin:audit"


# Correspondance rôle → permissions
_ROLE_PERMISSIONS: Dict[Role, FrozenSet[Permission]] = {
    Role.ADMIN: frozenset({p for p in Permission}),
    Role.OPERATOR: frozenset({
        Permission.HEALTH_VIEW,
        Permission.MEMORY_READ,
        Permission.KNOWLEDGE_SEARCH,
        Permission.TOOL_EXECUTE,
        Permission.APPROVAL_VIEW,
        Permission.APPROVAL_DECIDE,
        Permission.ADMIN_AUDIT,
        Permission.CONNECTOR_VIEW,
        Permission.CONNECTOR_CHECK,
    }),
    Role.USER: frozenset({
        Permission.HEALTH_VIEW,
        Permission.MEMORY_READ,
        Permission.MEMORY_WRITE,
        Permission.MODEL_GENERATE,
        Permission.KNOWLEDGE_SEARCH,
        Permission.TOOL_EXECUTE,
        Permission.APPROVAL_VIEW,
        Permission.CONNECTOR_VIEW,
    }),
    Role.READONLY: frozenset({
        Permission.HEALTH_VIEW,
        Permission.KNOWLEDGE_SEARCH,
        Permission.APPROVAL_VIEW,
        Permission.CONNECTOR_VIEW,
    }),
}


def get_permissions_for_role(role: Role) -> FrozenSet[Permission]:
    """
    Retourne l'ensemble des permissions associées à un rôle.

    Args:
        role: Le rôle dont on veut les permissions.

    Returns:
        Ensemble immuable de permissions.
    """
    return _ROLE_PERMISSIONS.get(role, frozenset())


def parse_api_key_mappings() -> Dict[str, Role]:
    """
    Parse la variable d'environnement GALSEN_API_KEYS en un mapping
    clé API → rôle.

    Format attendu (après la virgule, après le deux-points) :
        "sk-admin123:admin,sk-user456:user,sk-operator789:operator"

    Une clé sans rôle explicite reçoit le rôle USER par défaut.
    Une clé invalide (mauvais format) est ignorée avec un avertissement.

    Returns:
        Dictionnaire {clé_api: rôle}.
    """
    raw = os.environ.get("GALSEN_API_KEYS", "").strip()
    if not raw:
        return {}

    mappings: Dict[str, Role] = {}
    parts = [p.strip() for p in raw.split(",") if p.strip()]

    for part in parts:
        if ":" in part:
            key, role_name = part.split(":", 1)
            key = key.strip()
            role_name = role_name.strip().lower()
        else:
            key = part.strip()
            role_name = "user"

        if not key:
            continue

        try:
            role = Role(role_name)
        except ValueError:
            logger.warning(
                "Rôle '%s' inconnu pour la clé '%s...'. "
                "Rôles valides : %s. Utilisation du rôle 'user' par défaut.",
                role_name, key[:8], [r.value for r in Role],
            )
            role = Role.USER

        mappings[key] = role

    return mappings


@dataclass
class RBACContext:
    """
    Contexte d'autorisation pour une requête.

    Porté par chaque requête authentifiée, il permet aux dépendances
    FastAPI de vérifier rapidement si l'utilisateur a le droit d'effectuer
    une action.
    """

    api_key: str
    role: Role
    permissions: FrozenSet[Permission] = field(init=False)

    def __post_init__(self):
        self.permissions = get_permissions_for_role(self.role)

    def has_permission(self, permission: Permission) -> bool:
        """
        Vérifie si ce contexte dispose d'une permission donnée.

        Args:
            permission: La permission à vérifier.

        Returns:
            True si l'utilisateur a cette permission.
        """
        return permission in self.permissions

    def has_any_permission(self, *permissions: Permission) -> bool:
        """
        Vérifie si ce contexte dispose d'au moins une des permissions données.

        Args:
            permissions: Les permissions à vérifier.

        Returns:
            True si l'utilisateur a au moins une de ces permissions.
        """
        return any(p in self.permissions for p in permissions)

    def require_permission(self, permission: Permission) -> None:
        """
        Vérifie la permission et lève une exception si elle est absente.

        Args:
            permission: La permission requise.

        Raises:
            PermissionError: Si l'utilisateur n'a pas cette permission.
        """
        if not self.has_permission(permission):
            raise PermissionError(
                f"Permission '{permission.value}' requise. "
                f"Rôle actuel : '{self.role.value}'."
            )


class RBACManager:
    """
    Gestionnaire RBAC — point d'entrée unique pour l'autorisation.

    Maintient le mapping clé API → rôle à partir de la variable
    d'environnement et fournit la méthode d'authentification avec rôle.
    """

    def __init__(self):
        """Initialise le gestionnaire en parsant la variable d'environnement."""
        self._key_role_map: Dict[str, Role] = {}
        self.reload()

    def reload(self) -> None:
        """Recharge le mapping clé → rôle depuis la variable d'environnement."""
        self._key_role_map = parse_api_key_mappings()
        roles_present = set(self._key_role_map.values())
        logger.info(
            "RBAC chargé : %s clé(s) mappée(s) vers %s",
            len(self._key_role_map),
            {r.value for r in roles_present} if roles_present else "{}",
        )

    def authenticate(self, api_key: Optional[str]) -> RBACContext:
        """
        Authentifie une clé API et retourne son contexte RBAC.

        Args:
            api_key: La clé API à authentifier. None si aucune clé fournie.

        Returns:
            Contexte RBAC avec le rôle et les permissions.

        Raises:
            PermissionError: Si la clé est invalide ou absente.
        """
        if not api_key:
            raise PermissionError("Clé API manquante.")

        role = self._key_role_map.get(api_key)
        if role is None:
            raise PermissionError("Clé API invalide.")

        return RBACContext(api_key=api_key, role=role)

    def get_valid_keys(self) -> Set[str]:
        """
        Retourne l'ensemble des clés API valides.

        Utile pour synchroniser avec le limiteur de taux.

        Returns:
            Ensemble des clés API valides.
        """
        return set(self._key_role_map.keys())

    @property
    def has_keys(self) -> bool:
        """Indique si au moins une clé API est configurée."""
        return len(self._key_role_map) > 0