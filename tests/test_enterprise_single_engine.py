"""
Un moteur, un exemplaire (VOLET 25, chapitre 02).

La directive du chapitre tient en une ligne : « chaque moteur communique par des
interfaces normalisées ». La plateforme en faisait tourner **deux exemplaires** :
`server.py` construisait les siens, `EngineRegistry` construisait ceux des
agents. Mesuré avant correction, une alerte levée par un agent n'apparaissait
pas sur la route que l'utilisateur consulte.
"""

import os

import pytest

os.environ.setdefault("GALSEN_API_KEYS", "test-key-0123456789abcdef")

from src.api import server  # noqa: E402
from src.integration.engine_registry import get_shared_registry  # noqa: E402
from src.services.notification.types import NotificationType  # noqa: E402

# Moteurs exposés à la fois par l'API et par le registre des agents.
MOTEURS_PARTAGES = (
    "memory", "model", "knowledge", "approval", "notification",
    "search", "file", "cloud", "calendar", "email",
)


@pytest.fixture
def registre():
    """Registre partagé du processus."""
    return get_shared_registry()


@pytest.mark.parametrize("nom", MOTEURS_PARTAGES)
def test_l_api_et_les_agents_partagent_le_meme_moteur(nom, registre):
    """Deux exemplaires d'un moteur, c'est deux plateformes qui s'ignorent."""
    depuis_l_api = getattr(server, f"{nom}_manager")

    assert registre.try_get(nom) is depuis_l_api, (
        f"Le moteur '{nom}' existe en deux exemplaires : ce que l'API écrit reste "
        f"invisible aux agents, et réciproquement"
    )


def test_une_alerte_levee_par_un_agent_est_visible_par_l_api(registre):
    """
    Le défaut mesuré, dans ses conséquences.

    Un agent signale un incident par le registre ; l'utilisateur lit
    `/notification/list`, servi par `notification_manager`. Les deux doivent
    voir la même boîte.
    """
    destinataire = "destinataire_test_volet25"
    registre.notification.send_notification(
        notification_type=NotificationType.WARNING,
        title="Alerte agent", message="Un agent a détecté un problème.",
        recipient=destinataire,
    )

    vues_par_l_api = server.notification_manager.list_notifications(recipient=destinataire)
    assert len(vues_par_l_api) == 1
    assert vues_par_l_api[0].title == "Alerte agent"


def test_une_memoire_ecrite_par_l_api_est_lisible_par_un_agent(registre):
    """Le sens inverse : sans lui, un seul des deux chemins serait vérifié."""
    from src.memory_engine.types import MemoryItem, MemoryType

    identifiant = server.memory_manager.save_memory(MemoryItem(
        content="Le mil se sème en juin.", memory_type=MemoryType.KNOWLEDGE,
        user_id="sujet_test_volet25",
    ))

    assert registre.memory.get_memory(identifiant) is not None


def test_le_secours_est_journalise_et_non_silencieux(caplog, monkeypatch):
    """
    Le registre construit paresseusement et peut échouer.

    L'API garde alors un exemplaire à elle plutôt que de perdre la route, mais
    la duplication doit être **dite** : une duplication silencieuse est
    exactement ce que ce VOLET vient de corriger.
    """
    monkeypatch.setattr(server._registre_moteurs, "try_get", lambda nom: None)

    with caplog.at_level("WARNING"):
        secours = server._moteur_partage("notification", lambda: "exemplaire-de-secours")

    assert secours == "exemplaire-de-secours"
    assert "non partagé" in caplog.text
