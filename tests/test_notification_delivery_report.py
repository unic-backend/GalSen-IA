"""
Ce que deviennent les notifications une fois créées (VOLET 17, ch. 06 et 09).

Les deux chapitres demandent un taux de succès de livraison, une latence de file
et un compte d'échecs. Aucune des trois ne s'applique à une boîte interne, et les
rendre quand même produirait des chiffres flatteurs qui ne mesurent qu'une
tautologie. Ce qui se mesure vraiment, c'est ce qui arrive après la livraison.
"""

import time

import pytest

from src.services.notification.manager import NotificationManagerImpl
from src.services.notification.types import NotificationType


@pytest.fixture
def notifications():
    """Service de notification isolé."""
    return NotificationManagerImpl()


def _alerte(service, titre="Disque plein", destinataire="awa"):
    """Envoie une alerte et retourne son identifiant."""
    return service.send_notification(
        notification_type=NotificationType.ERROR, title=titre,
        message=f"{titre} sur le volume.", recipient=destinataire,
    )


def test_un_service_vide_ne_prétend_aucun_taux(notifications):
    """Un taux calculé sur zéro notification serait une invention."""
    rapport = notifications.delivery_report()

    assert rapport["total"] == 0
    assert rapport["acknowledgement_rate"] is None
    assert rapport["oldest_unread_seconds"] is None


def test_le_taux_d_accuse_mesure_ce_qui_a_ete_vu(notifications):
    """Une notification livrée mais jamais lue n'a rien accompli."""
    premier = _alerte(notifications, titre="Disque plein")
    _alerte(notifications, titre="Mémoire saturée")
    _alerte(notifications, titre="Réseau lent")
    notifications.mark_read(premier)

    rapport = notifications.delivery_report()
    assert rapport["total"] == 3
    assert rapport["unread"] == 2
    assert rapport["acknowledgement_rate"] == round(1 / 3, 4)


def test_l_age_de_la_plus_vieille_non_lue_est_rapporte(notifications):
    """C'est le signal qu'une boîte n'est plus relevée par personne."""
    identifiant = _alerte(notifications)
    ancienne = notifications.get(identifiant)
    ancienne.created_at = time.time() - 3600
    notifications._store.update(ancienne)

    assert notifications.delivery_report()["oldest_unread_seconds"] >= 3600


def test_une_notification_lue_ne_compte_plus_comme_en_attente(notifications):
    """Sinon l'âge ne redescendrait jamais et cesserait d'être un signal."""
    identifiant = _alerte(notifications)
    notifications.mark_read(identifiant)

    rapport = notifications.delivery_report()
    assert rapport["unread"] == 0
    assert rapport["oldest_unread_seconds"] is None


def test_les_incidents_repetes_remontent_en_tete(notifications):
    """Le regroupement rend cette mesure possible : sans lui, tout vaut 1."""
    for _ in range(7):
        _alerte(notifications, titre="Disque plein")
    _alerte(notifications, titre="Réseau lent")

    repetes = notifications.delivery_report()["most_repeated"]
    assert len(repetes) == 1
    assert repetes[0]["title"] == "Disque plein"
    assert repetes[0]["occurrences"] == 7


def test_les_metriques_du_manuel_qui_ne_s_appliquent_pas_sont_nommees(notifications):
    """
    Un « taux de livraison de 100 % » ne mesurerait que le fait que créer la
    notification est la livraison. Le dire vaut mieux que le chiffrer.
    """
    indisponibles = notifications.delivery_report()["unavailable"]

    assert "delivery_success_rate" in indisponibles
    assert "queue_latency" in indisponibles
    assert "failed_deliveries" in indisponibles


def test_aucun_taux_de_livraison_chiffre_n_est_rendu(notifications):
    """Le contre-test : personne ne doit pouvoir lire ce chiffre flatteur."""
    _alerte(notifications)
    rapport = notifications.delivery_report()

    assert "delivery_success_rate" not in rapport
    assert "delivery_rate" not in rapport


def test_le_rapport_se_limite_a_un_destinataire(notifications):
    """Un opérateur qui regarde une boîte ne doit pas voir celle des autres."""
    _alerte(notifications, destinataire="awa")
    _alerte(notifications, destinataire="moussa")
    _alerte(notifications, titre="Réseau lent", destinataire="moussa")

    assert notifications.delivery_report(recipient="awa")["total"] == 1
    assert notifications.delivery_report(recipient="moussa")["total"] == 2
