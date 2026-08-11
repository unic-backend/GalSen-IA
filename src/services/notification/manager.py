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
from .templates import TemplateError, TemplateRegistry
from .types import Notification, NotificationPriority, NotificationType
from src.storage.paths import sqlite_enabled

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

    def __init__(self, store: Optional[NotificationStore] = None,
                 templates: Optional[TemplateRegistry] = None) -> None:
        self._templates = templates if templates is not None else TemplateRegistry()
        if store is not None:
            self._store = store
        elif sqlite_enabled():
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

    def send_from_template(
        self,
        template_name: str,
        values: Optional[Dict[str, Any]] = None,
        recipient: Optional[str] = None,
        role: Optional[str] = None,
        source: Optional[str] = None,
        related_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        priority: Optional[NotificationPriority] = None,
    ) -> Optional[str]:
        """
        Envoie une notification composée à partir d'un gabarit enregistré.

        Le chapitre 02 du VOLET 17 nomme un « Template Manager » et le chapitre
        04 en fait un domaine de gestion. Sans lui, le même événement s'annonçait
        différemment selon l'endroit du code qui le signalait, et la
        déduplication — qui compare des chaînes exactes — ne pouvait pas les
        rapprocher.

        Un gabarit inconnu ou incomplet **échoue** au lieu d'envoyer un message
        à trous : « Le disque {nom} est plein » a l'air d'une vraie alerte et ne
        dit rien.

        Args:
            template_name: nom du gabarit enregistré.
            values: valeurs des paramètres du gabarit.
            recipient: destinataire, comme pour `send_notification`.
            role: rôle destinataire.
            source: origine de l'événement.
            related_id: identifiant de l'objet concerné.
            metadata: métadonnées libres.
            priority: priorité, si elle doit primer sur celle du gabarit.

        Returns:
            L'identifiant de la notification, ou None si le gabarit est
            inutilisable ou l'envoi impossible.
        """
        try:
            champs = self._templates.render(template_name, values)
        except TemplateError as error:
            self._logger.warning("Gabarit inutilisable : %s", error)
            return None

        return self.send_notification(
            notification_type=champs["notification_type"],
            title=champs["title"],
            message=champs["message"],
            priority=priority or champs["priority"],
            recipient=recipient,
            role=role,
            source=source,
            related_id=related_id,
            metadata=metadata,
        )

    @property
    def templates(self) -> TemplateRegistry:
        """Registre des gabarits de ce service."""
        return self._templates

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

    def delivery_report(self, recipient: Optional[str] = None) -> Dict[str, Any]:
        """
        Ce que deviennent les notifications, une fois créées (VOLET 17, ch. 06 et 09).

        Les deux chapitres demandent un taux de succès de livraison, une latence
        de file et un compte d'échecs. Aucune de ces trois métriques n'a de sens
        ici et les rendre quand même serait rendre des chiffres flatteurs :
        le canal est une boîte interne, créer la notification **est** la
        livraison, il n'y a pas de file et rien n'échoue. Un « taux de livraison
        de 100 % » ne mesurerait que cette tautologie.

        Ce qui se mesure vraiment, c'est ce qui arrive **après** : une
        notification livrée mais jamais lue n'a rien accompli. Le rapport donne
        donc le taux d'accusé de réception, l'âge de la plus vieille non lue, et
        les incidents les plus répétés.

        Args:
            recipient: limiter le rapport à un destinataire.

        Returns:
            Les mesures réelles, et un bloc `unavailable` nommant les trois
            métriques du manuel qui ne s'appliquent pas.
        """
        try:
            notifications = self._store.list_notifications(limit=100000, recipient=recipient)
        except Exception as error:
            self._logger.warning("Rapport de livraison impossible : %s", error)
            return {}

        total = len(notifications)
        lues = sum(1 for n in notifications if n.read)
        maintenant = time.time()
        non_lues = [n for n in notifications if not n.read]
        plus_ancienne = max((maintenant - n.created_at for n in non_lues), default=None)

        repetees = sorted(
            (
                {
                    "title": n.title,
                    "recipient": n.recipient,
                    "occurrences": int(n.metadata.get("occurrences", 1)),
                }
                for n in notifications
                if int(n.metadata.get("occurrences", 1)) > 1
            ),
            key=lambda entree: entree["occurrences"],
            reverse=True,
        )

        return {
            "total": total,
            "unread": len(non_lues),
            # Le vrai indicateur de bout en bout : ce qui a été vu.
            "acknowledgement_rate": round(lues / total, 4) if total else None,
            "oldest_unread_seconds": round(plus_ancienne, 1) if plus_ancienne else None,
            "most_repeated": repetees[:5],
            "unavailable": {
                "delivery_success_rate": (
                    "le canal est une boîte interne : créer la notification est "
                    "la livraison, un taux vaudrait toujours 100 %"
                ),
                "queue_latency": "aucune file : l'envoi est synchrone",
                "failed_deliveries": (
                    "aucune livraison ne peut échouer sans canal externe ; "
                    "les échecs d'envoi d'e-mail sont mesurés côté service Email"
                ),
            },
        }

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
