"""
Tests du cycle de vie des notifications (VOLET 13, chapitre 03).

Deux contrôles du chapitre manquaient : la prévention des doublons et la
rétention. Une alerte répétée noyait la boîte du destinataire — donc les
notifications qu'il n'avait pas encore lues — et rien n'était jamais purgé.
"""

import time

import pytest

from src.services.notification.manager import NotificationManagerImpl
from src.services.notification.types import NotificationPriority, NotificationType


@pytest.fixture
def notifications():
    """Service de notification isolé pour un test."""
    return NotificationManagerImpl()


def _alerte(service, titre="Disque plein", message="Le disque est plein.",
            destinataire="awa", type_=NotificationType.ERROR):
    """Envoie une alerte et retourne son identifiant."""
    return service.send_notification(notification_type=type_, title=titre,
                                     message=message, recipient=destinataire)


def test_une_alerte_repetee_est_regroupee(notifications):
    """Cinq fois la même alerte ne doit pas produire cinq notifications."""
    identifiants = [_alerte(notifications) for _ in range(5)]

    assert len(set(identifiants)) == 1, "chaque répétition a créé une notification"
    boite = notifications.list_notifications(recipient="awa")
    assert len(boite) == 1
    assert boite[0].metadata["occurrences"] == 5
    assert boite[0].metadata["last_occurrence_at"] > 0


def test_la_date_de_creation_ne_recule_pas(notifications):
    """Elle dit quand le problème a commencé, pas quand il s'est répété."""
    premier = notifications.get(_alerte(notifications))
    debut = premier.created_at
    time.sleep(0.01)
    _alerte(notifications)

    assert notifications.get(premier.id).created_at == debut


def test_deux_incidents_differents_ne_se_confondent_pas(notifications):
    """Le regroupement ne doit pas avaler une information nouvelle."""
    _alerte(notifications, titre="Disque plein")
    _alerte(notifications, titre="Mémoire saturée", message="La mémoire est saturée.")

    assert len(notifications.list_notifications(recipient="awa")) == 2


def test_deux_destinataires_recoivent_chacun_la_leur(notifications):
    """Regrouper entre destinataires priverait quelqu'un de son alerte."""
    _alerte(notifications, destinataire="awa")
    _alerte(notifications, destinataire="moussa")

    assert len(notifications.list_notifications(recipient="awa")) == 1
    assert len(notifications.list_notifications(recipient="moussa")) == 1


def test_une_notification_lue_n_est_pas_regroupee(notifications):
    """Le destinataire l'a vue : une nouvelle occurrence est une information neuve."""
    premier = _alerte(notifications)
    notifications.mark_read(premier)

    second = _alerte(notifications)
    assert second != premier
    assert len(notifications.list_notifications(recipient="awa")) == 2


def test_hors_fenetre_une_alerte_reapparait(notifications, monkeypatch):
    """Un incident qui revient une heure plus tard n'est pas le même événement."""
    monkeypatch.setenv(NotificationManagerImpl.DEDUPLICATION_WINDOW_ENV, "1")
    premier = _alerte(notifications)
    time.sleep(1.1)
    second = _alerte(notifications)

    assert second != premier
    assert len(notifications.list_notifications(recipient="awa")) == 2


def test_la_purge_ne_touche_pas_les_notifications_recentes(notifications):
    """Purger ce qu'on vient de recevoir viderait la boîte à chaque passage."""
    _alerte(notifications)
    assert notifications.purge_expired(max_age_days=30) == 0
    assert len(notifications.list_notifications(recipient="awa")) == 1


def test_la_purge_emporte_les_notifications_lues_et_anciennes(notifications):
    """La rétention est l'étape 9 du cycle, et rien ne purgeait."""
    identifiant = _alerte(notifications)
    notifications.mark_read(identifiant)
    ancienne = notifications.get(identifiant)
    ancienne.created_at = time.time() - 200 * 86400
    notifications._store.update(ancienne)

    assert notifications.purge_expired(max_age_days=90) == 1
    assert notifications.list_notifications(recipient="awa") == []


def test_la_purge_epargne_les_non_lues_par_defaut(notifications):
    """Supprimer ce que personne n'a vu, c'est décider à sa place que c'était sans importance."""
    identifiant = _alerte(notifications)
    ancienne = notifications.get(identifiant)
    ancienne.created_at = time.time() - 200 * 86400
    notifications._store.update(ancienne)

    assert notifications.purge_expired(max_age_days=90) == 0
    assert len(notifications.list_notifications(recipient="awa")) == 1
    # L'appelant peut l'exiger explicitement.
    assert notifications.purge_expired(max_age_days=90, include_unread=True) == 1


def test_la_priorite_reste_respectee(notifications):
    """Le regroupement ne doit pas casser l'ordre de lecture."""
    notifications.send_notification(notification_type=NotificationType.INFO, title="Info",
                                    message="basse", recipient="awa",
                                    priority=NotificationPriority.LOW)
    notifications.send_notification(notification_type=NotificationType.ERROR, title="Urgent",
                                    message="critique", recipient="awa",
                                    priority=NotificationPriority.URGENT)

    ordre = [n.priority.value for n in notifications.list_notifications(recipient="awa")]
    assert ordre[0] == "urgent"
