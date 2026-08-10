"""
Gestionnaire de sessions utilisateur pour GalSen IA.

Stocke les sessions actives en mémoire avec expiration automatique.
Une session lie un jeton de session à un utilisateur et un rôle RBAC.
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Une session utilisateur active."""

    session_id: str
    user_id: str
    role: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 86400)  # 24h par défaut
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Vérifie si la session a expiré."""
        return time.time() > self.expires_at

    @property
    def ttl_seconds(self) -> float:
        """Durée de vie restante en secondes (0 si expirée)."""
        return max(0.0, self.expires_at - time.time())


class SessionManager:
    """Gestionnaire de sessions utilisateur en mémoire.

    Nettoie automatiquement les sessions expirées à chaque opération de lecture.
    Thread-safe via un verrou.

    Usage :
        mgr = SessionManager(session_ttl=3600)
        session = mgr.create_session(user_id="u1", role="user")
        validated = mgr.get_session(session.session_id)  # → Session ou None
        mgr.delete_session(session.session_id)
    """

    def __init__(self, session_ttl: int = 86400) -> None:
        """
        Args:
            session_ttl: Durée de vie des sessions en secondes (défaut : 24h).
        """
        self._sessions: Dict[str, Session] = {}
        self._session_ttl = session_ttl
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # CRUD sessions
    # ------------------------------------------------------------------

    def create_session(
        self,
        user_id: str,
        role: str = "user",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Session:
        """Crée une nouvelle session pour un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.
            role: Rôle RBAC.
            metadata: Métadonnées supplémentaires (IP, user-agent, etc.).

        Returns:
            La session créée.
        """
        session_id = self._generate_session_id()
        expires_at = time.time() + self._session_ttl
        session = Session(
            session_id=session_id,
            user_id=user_id,
            role=role,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        with self._lock:
            self._sessions[session_id] = session
        logger.debug("Session créée : %s pour utilisateur %s", session_id, user_id)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Récupère une session par son identifiant.

        Les sessions expirées sont automatiquement supprimées.

        Args:
            session_id: Identifiant de session.

        Returns:
            La session si elle existe et n'est pas expirée, None sinon.
        """
        self._cleanup_expired()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.is_expired:
                del self._sessions[session_id]
                return None
            return session

    def delete_session(self, session_id: str) -> bool:
        """Supprime une session.

        Args:
            session_id: Identifiant de la session à supprimer.

        Returns:
            True si la session existait, False sinon.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.debug("Session supprimée : %s", session_id)
                return True
            return False

    def delete_user_sessions(self, user_id: str) -> int:
        """Supprime toutes les sessions d'un utilisateur.

        Args:
            user_id: Identifiant de l'utilisateur.

        Returns:
            Nombre de sessions supprimées.
        """
        with self._lock:
            to_delete = [
                sid for sid, s in self._sessions.items() if s.user_id == user_id
            ]
            for sid in to_delete:
                del self._sessions[sid]
            if to_delete:
                logger.debug(
                    "%d session(s) supprimée(s) pour utilisateur %s",
                    len(to_delete), user_id,
                )
            return len(to_delete)

    def refresh_session(self, session_id: str) -> Optional[Session]:
        """Prolonge la durée de vie d'une session.

        Args:
            session_id: Identifiant de session.

        Returns:
            La session mise à jour, ou None si elle n'existe pas ou est expirée.
        """
        session = self.get_session(session_id)
        if session is None:
            return None
        session.expires_at = time.time() + self._session_ttl
        logger.debug("Session rafraîchie : %s", session_id)
        return session

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def _generate_session_id(self) -> str:
        """Génère un identifiant de session aléatoire (64 caractères hex)."""
        return secrets.token_hex(32)

    def _cleanup_expired(self) -> int:
        """Supprime toutes les sessions expirées.

        Returns:
            Nombre de sessions nettoyées.
        """
        with self._lock:
            expired = [
                sid for sid, s in self._sessions.items() if s.is_expired
            ]
            for sid in expired:
                del self._sessions[sid]
            if expired:
                logger.debug("%d session(s) expirée(s) nettoyée(s).", len(expired))
            return len(expired)

    @property
    def active_count(self) -> int:
        """Nombre de sessions actives."""
        self._cleanup_expired()
        with self._lock:
            return len(self._sessions)

    @property
    def total_count(self) -> int:
        """Nombre total de sessions (y compris expirées, avant nettoyage)."""
        with self._lock:
            return len(self._sessions)
