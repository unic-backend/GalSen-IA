"""
Gabarits de notification (VOLET 17, chapitres 02 et 04).

Le chapitre 02 nomme un « Template Manager » parmi ses composants, le chapitre
04 en fait un domaine de gestion, et rien de tel n'existait : chaque appelant
composait son titre et son message à la main.
"""

import pytest

from src.services.notification.manager import NotificationManagerImpl
from src.services.notification.templates import (
    NotificationTemplate,
    TemplateError,
    TemplateRegistry,
)
from src.services.notification.types import NotificationPriority, NotificationType


@pytest.fixture
def gabarit():
    """Gabarit d'alerte disque, avec deux paramètres."""
    return NotificationTemplate(
        name="disque_plein",
        notification_type=NotificationType.ERROR,
        title="Disque {nom} plein",
        message="Le disque {nom} atteint {taux} % de sa capacité.",
        priority=NotificationPriority.URGENT,
        description="Alerte de saturation d'un volume",
    )


@pytest.fixture
def notifications(gabarit):
    """Service isolé avec le gabarit enregistré."""
    service = NotificationManagerImpl()
    service.templates.register(gabarit)
    return service


def test_le_registre_est_vide_par_defaut():
    """
    Fournir des gabarits d'avance fabriquerait des messages que personne n'a
    demandés. Les appelants enregistrent les leurs.
    """
    assert len(NotificationManagerImpl().templates) == 0


def test_les_parametres_sont_deduits_du_gabarit(gabarit):
    """L'appelant n'a pas à tenir une liste à jour à la main."""
    assert gabarit.parameters == ["nom", "taux"]


def test_le_gabarit_produit_le_meme_message_a_chaque_fois(notifications):
    """C'est tout l'intérêt : le même événement s'annonce pareil partout."""
    identifiant = notifications.send_from_template(
        "disque_plein", {"nom": "data", "taux": 98}, recipient="awa",
    )

    notification = notifications.get(identifiant)
    assert notification.title == "Disque data plein"
    assert notification.message == "Le disque data atteint 98 % de sa capacité."
    assert notification.priority == NotificationPriority.URGENT
    assert notification.notification_type == NotificationType.ERROR


def test_un_parametre_manquant_n_envoie_rien(notifications):
    """
    Un message à trous a l'air d'une vraie alerte et ne dit rien.

    Envoyer « Le disque data atteint {taux} % » serait pire que ne rien envoyer.
    """
    assert notifications.send_from_template("disque_plein", {"nom": "data"}, recipient="awa") is None
    assert notifications.list_notifications(recipient="awa") == []


def test_un_gabarit_inconnu_n_envoie_rien(notifications):
    """Et le message d'erreur nomme les gabarits connus."""
    assert notifications.send_from_template("inexistant", {}, recipient="awa") is None

    with pytest.raises(TemplateError, match="disque_plein"):
        notifications.templates.render("inexistant")


def test_la_priorite_de_l_appelant_prime_sur_celle_du_gabarit(notifications):
    """Le même événement n'a pas toujours la même urgence selon le contexte."""
    identifiant = notifications.send_from_template(
        "disque_plein", {"nom": "data", "taux": 71}, recipient="awa",
        priority=NotificationPriority.LOW,
    )

    assert notifications.get(identifiant).priority == NotificationPriority.LOW


def test_deux_evenements_du_meme_gabarit_ne_se_confondent_pas(notifications):
    """La déduplication compare le texte rendu, donc les valeurs comptent."""
    notifications.send_from_template("disque_plein", {"nom": "data", "taux": 98}, recipient="awa")
    notifications.send_from_template("disque_plein", {"nom": "backup", "taux": 91}, recipient="awa")

    assert len(notifications.list_notifications(recipient="awa")) == 2


def test_deux_fois_le_meme_evenement_est_regroupe(notifications):
    """Et à l'inverse, un gabarit rendu à l'identique reste un seul incident."""
    for _ in range(3):
        notifications.send_from_template("disque_plein", {"nom": "data", "taux": 98}, recipient="awa")

    boite = notifications.list_notifications(recipient="awa")
    assert len(boite) == 1
    assert boite[0].metadata["occurrences"] == 3


def test_une_valeur_ne_reintroduit_pas_de_substitution():
    """
    Une valeur est du texte, pas un gabarit.

    Sans quoi une valeur venue d'un utilisateur pourrait faire lire un autre
    paramètre — et `str.format` donnerait en plus accès aux attributs des objets
    passés, ce que `{a.__class__}` suffit à montrer.
    """
    registre = TemplateRegistry()
    registre.register(NotificationTemplate(
        name="echo", notification_type=NotificationType.INFO,
        title="Bonjour {nom}", message="{nom}",
    ))

    rendu = registre.render("echo", {"nom": "{secret}", "secret": "confidentiel"})

    assert rendu["message"] == "{secret}"
    assert "confidentiel" not in rendu["title"]


def test_le_registre_se_relit(gabarit):
    """Un opérateur doit pouvoir savoir quels gabarits existent."""
    registre = TemplateRegistry()
    registre.register(gabarit)

    inscrits = registre.list_templates()
    assert len(inscrits) == 1
    assert inscrits[0]["name"] == "disque_plein"
    assert inscrits[0]["parameters"] == ["nom", "taux"]
    assert inscrits[0]["type"] == "error"
