"""
Gestionnaire du service de notification.

Fournit `NotificationManagerImpl`, une façade best-effort conforme à
`NotificationManager` : chaque appel est protégé et ne lève jamais ; en cas
d'échec, un avertissement est journalisé et une valeur vide est retournée.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from .interfaces import NotificationManager, NotificationStore
from .store import InMemoryNotificationStore
from .types import Notification, NotificationPriority, NotificationType

logger = logging.getLogger(__name__)


class NotificationManagerImpl(NotificationManager):
    """Façade du service de notification, toujours disponible en mémoire."""

    # Fenêtre pendant laquelle une notification identique est regroupée plutôt
    # que dupliquée. Configurable : un incident qui se répète toutes les heures
    # n'a pas la même signature qu'un qui se répète toutes les secondes.
    DEDUPLICATION_WINDOW_ENV = "GALSEN_NOTIFICATION_DEDUP_SECONDS"
    DEFAULT_DEDUPLICATION_WINDOW = 300

    # Âge par défaut au-delà duquel une notification **lue** peut être purgée.
    RETENTION_DAYS_ENV = "GALSEN_NOTIFICATION_RETENTION_DAYS"
    DEFAULT_RETENTION_DAYS = 90

    def __init__(self, store: Optional[NotificationStore] = None) -> None:
        if store is not None:
            self._store = store
        elif os.getenv("GALSEN_STORAGE_BACKEND", "in-memory").lower() == "sqlite":
            from src.storage.sqlite_notification_store import SQLiteNotificationStore
            self._store = SQLiteNotificationStore()
        else:
            self._store = InMemoryNotificationStore()
        self._logger = logging.getLogger(f"{__name__}.NotificationManagerImpl")

    def send_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        recipient: Optional[str] = None,
        role: Optional[str] = None,
        source: Optional[str] = None,
        related_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Envoie une notification et retourne son identifiant, ou None en cas d'échec.

        Une notification identique, non lue et récente n'est pas dupliquée : son
        compteur `occurrences` est incrémenté et le même identifiant est
        retourné. Le chapitre 03 range la prévention des doublons parmi ses
        contrôles qualité, et la raison est pratique — une alerte « disque
        plein » répétée toutes les minutes noyait la boîte du destinataire, donc
        les notifications qu'il n'avait pas encore lues.

        Deux notifications ne sont considérées identiques que si le type, le
        titre, le message et le destinataire coïncident : deux incidents
        différents ne se confondent jamais.
        """
        try:
            existante = self._trouver_doublon(notification_type, title, message, recipient, role)
            if existante is not None:
                return self._compter_occurrence(existante)

            notification = Notification(
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority,
                recipient=recipient,
                role=role,
                source=source,
                related_id=related_id,
                metadata=metadata or {},
            )
            return self._store.save(notification)
        except Exception as error:
            self._logger.warning("Échec de l'envoi d'une notification : %s", error)
            return None

    def get(self, notification_id: str) -> Optional[Notification]:
        """Retourne une notification par identifiant, ou None si absente."""
        try:
            return self._store.get(notification_id)
        except Exception as error:
            self._logger.warning("Échec de la lecture de la notification %s : %s", notification_id, error)
            return None

    def list_notifications(
        self,
        limit: int = 100,
        offset: int = 0,
        unread_only: bool = False,
        notification_type: Optional[str] = None,
        recipient: Optional[str] = None,
        role: Optional[str] = None,
    ) -> List[Notification]:
        """Retourne les notifications filtrées."""
        try:
            return self._store.list_notifications(
                limit=limit,
                offset=offset,
                unread_only=unread_only,
                notification_type=notification_type,
                recipient=recipient,
                role=role,
            )
        except Exception as error:
            self._logger.warning("Échec du filtrage des notifications : %s", error)
            return []

    def mark_read(self, notification_id: str) -> bool:
        """Marque une notification comme lue ; retourne False si absente."""
        try:
            return self._store.mark_read(notification_id)
        except Exception as error:
            self._logger.warning("Échec du marquage de la notification %s : %s", notification_id, error)
            return False

    def mark_all_read(self, recipient: Optional[str] = None) -> int:
        """Marque toutes les notifications comme lues."""
        try:
            return self._store.mark_all_read(recipient=recipient)
        except Exception as error:
            self._logger.warning("Échec du marquage de toutes les notifications : %s", error)
            return 0

    def delete(self, notification_id: str) -> bool:
        """Supprime une notification ; retourne False si absente."""
        try:
            return self._store.delete(notification_id)
        except Exception as error:
            self._logger.warning("Échec de la suppression de la notification %s : %s", notification_id, error)
            return False

    def stats(self, recipient: Optional[str] = None) -> Dict[str, Any]:
        """Retourne des statistiques agrégées."""
        try:
            return self._store.stats(recipient=recipient)
        except Exception as error:
            self._logger.warning("Échec du calcul des statistiques de notifications : %s", error)
            return {}

    def clear(self) -> int:
        """Supprime toutes les notifications et retourne le nombre supprimé."""
        try:
            return self._store.clear()
        except Exception as error:
            self._logger.warning("Échec de la suppression des notifications : %s", error)
            return 0

    # ------------------------------------------------------------------
    # Prévention des doublons et rétention (VOLET 13, chapitre 03)
    # ------------------------------------------------------------------

    def _fenetre_deduplication(self) -> int:
        """Durée pendant laquelle une notification identique est regroupée."""
        return _entier_env(self.DEDUPLICATION_WINDOW_ENV, self.DEFAULT_DEDUPLICATION_WINDOW)

    def _duree_retention_jours(self) -> int:
        """Âge au-delà duquel une notification lue peut être purgée."""
        return _entier_env(self.RETENTION_DAYS_ENV, self.DEFAULT_RETENTION_DAYS)

    def _trouver_doublon(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        recipient: Optional[str],
        role: Optional[str],
    ) -> Optional[Notification]:
        """
        Cherche une notification identique, **non lue** et dans la fenêtre.

        Une notification déjà lue n'est jamais regroupée : le destinataire l'a
        vue, et une nouvelle occurrence est une information nouvelle.
        """
        limite = time.time() - self._fenetre_deduplication()
        try:
            recentes = self._store.list_notifications(
                limit=200, unread_only=True, recipient=recipient, role=role,
            )
        except Exception as error:
            self._logger.warning("Recherche de doublon impossible : %s", error)
            return None

        for candidate in recentes:
            if candidate.created_at < limite:
                continue
            if (candidate.notification_type == notification_type
                    and candidate.title == title
                    and candidate.message == message
                    and candidate.recipient == recipient
                    and candidate.role == role):
                return candidate
        return None

    def _compter_occurrence(self, notification: Notification) -> Optional[str]:
        """
        Incrémente le compteur d'une notification regroupée.

        La date de création n'est pas touchée : elle dit quand le problème a
        commencé, ce qui vaut mieux que de la voir reculer à chaque répétition.
        `last_occurrence_at` porte la dernière.
        """
        try:
            occurrences = int(notification.metadata.get("occurrences", 1)) + 1
            notification.metadata["occurrences"] = occurrences
            notification.metadata["last_occurrence_at"] = time.time()
            if not self._store.update(notification):
                # La notification a disparu entre la recherche et la mise à jour :
                # mieux vaut ne rien compter que compter dans le vide.
                return None
            self._logger.debug(
                "Notification '%s' regroupée (%d occurrences)", notification.title, occurrences
            )
            return notification.id
        except Exception as error:
            self._logger.warning("Regroupement de notification impossible : %s", error)
            return notification.id

    def purge_expired(self, max_age_days: Optional[int] = None,
                      include_unread: bool = False) -> int:
        """
        Supprime les notifications lues plus anciennes que la durée de rétention.

        Le chapitre 03 termine son cycle par « rétention et suppression
        sécurisée » et rien ne purgeait : une boîte de réception grandissait
        sans fin, exactement comme le journal non borné que la plateforme a déjà
        payé une fois.

        Args:
            max_age_days: âge maximal ; la valeur configurée sinon
            include_unread: purger aussi les non lues. **False par défaut** :
                supprimer une notification que personne n'a vue revient à
                décider à sa place qu'elle était sans importance.

        Returns:
            Le nombre de notifications supprimées.
        """
        jours = max_age_days if max_age_days is not None else self._duree_retention_jours()
        limite = time.time() - jours * 86400
        supprimees = 0

        try:
            for notification in self._store.list_notifications(limit=100000):
                if notification.created_at >= limite:
                    continue
                if notification.read or include_unread:
                    if self._store.delete(notification.id):
                        supprimees += 1
        except Exception as error:
            self._logger.warning("Purge des notifications impossible : %s", error)
        return supprimees


def _entier_env(nom: str, defaut: int) -> int:
    """Lit un entier strictement positif dans l'environnement, avec repli."""
    brut = os.environ.get(nom)
    if not brut:
        return defaut
    try:
        valeur = int(brut)
    except ValueError:
        return defaut
    return valeur if valeur > 0 else defaut
