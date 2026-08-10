"""
Gestionnaire d'utilisateurs pour GalSen IA.

CRUD utilisateurs avec hachage bcrypt, mapping des rôles vers l'enum Role
du RBAC, et intégration avec SQLiteUserStore.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.api.rbac import Role
from src.storage.sqlite_user_store import SQLiteUserStore, User

logger = logging.getLogger(__name__)


class UserManager:
    """Gestionnaire CRUD des utilisateurs de la plateforme.

    Encapsule SQLiteUserStore et ajoute :
    - Hachage bcrypt des mots de passe
    - Mapping role (str) → Role (enum RBAC)
    - Validation des emails et contraintes métier

    Usage :
        store = SQLiteUserStore()
        mgr = UserManager(store)
        user = mgr.create_user("x@y.com", "secret123", "Alice")
        auth_user = mgr.authenticate_user("x@y.com", "secret123")
    """

    # Coût bcrypt — 12 rounds (bon équilibre sécurité/performances)
    BCRYPT_ROUNDS = 12

    # Rôles valides (issus de l'enum RBAC Role)
    VALID_ROLES = {r.value for r in Role}

    def __init__(self, store: Optional[SQLiteUserStore] = None) -> None:
        self._store = store or SQLiteUserStore()

    # ------------------------------------------------------------------
    # Hachage
    # ------------------------------------------------------------------

    def _hash_password(self, password: str) -> str:
        """Hache un mot de passe avec bcrypt.

        Args:
            password: Mot de passe en clair.

        Returns:
            Hash bcrypt (str).
        """
        import bcrypt

        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=self.BCRYPT_ROUNDS),
        ).decode("utf-8")

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Vérifie un mot de passe contre son hash bcrypt.

        Args:
            password: Mot de passe en clair.
            password_hash: Hash bcrypt stocké.

        Returns:
            True si le mot de passe correspond.
        """
        import bcrypt

        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )

    # ------------------------------------------------------------------
    # CRUD utilisateurs
    # ------------------------------------------------------------------

    def create_user(
        self,
        email: str,
        password: str,
        name: str = "",
        role: str = "user",
    ) -> User:
        """Crée un nouvel utilisateur avec mot de passe haché.

        Args:
            email: Adresse email unique.
            password: Mot de passe en clair (sera haché).
            name: Nom d'affichage.
            role: Rôle RBAC ('admin', 'operator', 'user', 'readonly').

        Returns:
            L'utilisateur créé.

        Raises:
            ValueError: Si l'email est déjà pris ou le rôle invalide.
        """
        email = email.lower().strip()
        if not email:
            raise ValueError("L'email est requis.")

        if role not in self.VALID_ROLES:
            raise ValueError(
                f"Rôle '{role}' invalide. Rôles valides : {sorted(self.VALID_ROLES)}."
            )

        if self._store.is_email_taken(email):
            raise ValueError(f"L'email '{email}' est déjà utilisé.")

        if not password:
            raise ValueError("Le mot de passe est requis.")

        user = User(
            email=email,
            name=name.strip(),
            role=role,
            password_hash=self._hash_password(password),
        )
        self._store.save(user)
        logger.info("Utilisateur créé : %s (rôle=%s)", user.id, role)
        return user

    def create_oauth_user(
        self,
        email: str,
        provider: str,
        oauth_id: str,
        name: str = "",
        role: str = "user",
    ) -> User:
        """Crée ou met à jour un utilisateur OAuth.

        Si l'utilisateur existe déjà par email, il est mis à jour avec les
        informations OAuth. Sinon, un nouvel utilisateur est créé.

        Args:
            email: Adresse email.
            provider: Nom du fournisseur OAuth ('google', 'github', 'microsoft').
            oauth_id: Identifiant utilisateur chez le fournisseur.
            name: Nom d'affichage.
            role: Rôle RBAC.

        Returns:
            L'utilisateur créé ou mis à jour.
        """
        email = email.lower().strip()
        if not email:
            raise ValueError("L'email est requis.")

        existing = self._store.get_by_email(email)
        if existing is not None:
            # Mise à jour du lien OAuth
            existing.oauth_provider = provider
            existing.oauth_id = oauth_id
            if name and not existing.name:
                existing.name = name.strip()
            self._store.update(existing)
            logger.info("Utilisateur OAuth mis à jour : %s (%s)", existing.id, provider)
            return existing

        user = User(
            email=email,
            name=name.strip(),
            role=role,
            oauth_provider=provider,
            oauth_id=oauth_id,
        )
        self._store.save(user)
        logger.info("Utilisateur OAuth créé : %s (%s)", user.id, provider)
        return user

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authentifie un utilisateur par email et mot de passe.

        Args:
            email: Adresse email.
            password: Mot de passe en clair.

        Returns:
            L'utilisateur si l'authentification réussit, None sinon.
        """
        user = self._store.get_by_email(email)
        if user is None:
            return None
        if user.password_hash is None:
            # Compte OAuth uniquement — pas de mot de passe
            return None
        if not self._verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            logger.warning("Tentative de connexion utilisateur inactif : %s", email)
            return None
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Récupère un utilisateur par son identifiant."""
        return self._store.get(user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Récupère un utilisateur par son email."""
        return self._store.get_by_email(email)

    def get_user_by_oauth(self, provider: str, oauth_id: str) -> Optional[User]:
        """Récupère un utilisateur par son compte OAuth."""
        return self._store.get_by_oauth(provider, oauth_id)

    def update_user(self, user: User) -> bool:
        """Met à jour un utilisateur existant."""
        return self._store.update(user)

    def deactivate_user(self, user_id: str) -> bool:
        """Désactive un utilisateur (suppression logique).

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            True si la désactivation a réussi, False si l'utilisateur n'existe pas.
        """
        user = self._store.get(user_id)
        if user is None:
            return False
        user.is_active = False
        return self._store.update(user)

    def reactivate_user(self, user_id: str) -> bool:
        """Réactive un utilisateur désactivé.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            True si la réactivation a réussi, False si l'utilisateur n'existe pas.
        """
        user = self._store.get(user_id)
        if user is None:
            return False
        user.is_active = True
        return self._store.update(user)

    def delete_user(self, user_id: str) -> bool:
        """Supprime définitivement un utilisateur (suppression physique).

        Pour un retrait réversible, préférer `deactivate_user`.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            True si la suppression a réussi, False si l'utilisateur n'existe pas.
        """
        deleted = self._store.delete(user_id)
        if deleted:
            logger.info("Utilisateur supprimé : %s", user_id)
        return deleted

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Change le mot de passe d'un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.
            old_password: Ancien mot de passe (vérifié avant changement).
            new_password: Nouveau mot de passe.

        Returns:
            True si le changement a réussi.

        Raises:
            ValueError: Si l'ancien mot de passe est incorrect ou l'utilisateur introuvable.
        """
        user = self._store.get(user_id)
        if user is None:
            raise ValueError("Utilisateur introuvable.")
        if user.password_hash is None:
            raise ValueError("Ce compte n'a pas de mot de passe (OAuth uniquement).")
        if not self._verify_password(old_password, user.password_hash):
            raise ValueError("Ancien mot de passe incorrect.")

        user.password_hash = self._hash_password(new_password)
        self._store.update(user)
        logger.info("Mot de passe changé pour l'utilisateur : %s", user_id)
        return True

    def change_role(self, user_id: str, new_role: str) -> bool:
        """Change le rôle d'un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.
            new_role: Nouveau rôle RBAC.

        Returns:
            True si le changement a réussi.

        Raises:
            ValueError: Si le rôle est invalide ou l'utilisateur introuvable.
        """
        if new_role not in self.VALID_ROLES:
            raise ValueError(
                f"Rôle '{new_role}' invalide. Rôles valides : {sorted(self.VALID_ROLES)}."
            )

        user = self._store.get(user_id)
        if user is None:
            raise ValueError("Utilisateur introuvable.")

        user.role = new_role
        self._store.update(user)
        logger.info("Rôle changé pour %s : %s", user_id, new_role)
        return True

    def list_users(self, limit: int = 100, offset: int = 0, **filters: Any) -> List[User]:
        """Liste les utilisateurs avec pagination et filtres.

        Args:
            limit: Nombre maximum d'utilisateurs.
            offset: Décalage pour la pagination.
            **filters: Filtres (role, is_active, search).

        Returns:
            Liste d'utilisateurs.
        """
        return self._store.list_items(limit=limit, offset=offset, **filters)

    def count_users(self, **filters: Any) -> int:
        """Compte les utilisateurs correspondant aux filtres."""
        return self._store.count(**filters)

    def to_rbac_role(self, user: User) -> Role:
        """Convertit le rôle stocké (str) en enum Role RBAC.

        Args:
            user: L'utilisateur dont on veut le rôle RBAC.

        Returns:
            Role enum (fallback : Role.USER).
        """
        try:
            return Role(user.role)
        except ValueError:
            logger.warning("Rôle inconnu '%s' pour %s, fallback USER.", user.role, user.id)
            return Role.USER
