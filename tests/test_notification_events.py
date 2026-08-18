"""
Les événements que personne ne verrait (phase 50.1).

L'audit du programme rangeait les notifications parmi les capacités
**partielles**, « pas de moteur ». C'est faux, et il faut le dire : le service
existe entièrement — gestionnaire, deux magasins, gabarits, déduplication,
rétention, six routes, isolation par destinataire. Ce qui lui manquait, ce sont
les **événements** de la vague III : une routine qui s'arrête d'elle-même à
trois heures du matin, une exécution longue qui meurt au huitième agent. Tous
deux n'existaient que dans les journaux — et un journal est lu par quelqu'un
qui soupçonne déjà quelque chose.

Ce que ces tests gardent :

1. **Ce qui s'arrête tout seul se dit.** C'est l'événement pour lequel ce
   module existe.
2. **Le destinataire est déduit du propriétaire**, jamais choisi. Ce qui
   appartient à la plateforme part vers l'exploitation par son rôle.
3. **Notifier ne fait jamais tomber ce qu'on observe.** Un témoin, pas un
   maillon.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.routines import (  # noqa: E402
    RoutineAction,
    RoutineRegistry,
    RoutineSafety,
    RoutineScheduler,
)
from src.services.notification import (  # noqa: E402
    NotificationManagerImpl,
    NotificationType,
    PlatformNotifier,
    ROLE_EXPLOITATION,
)
from src.services.notification.store import InMemoryNotificationStore  # noqa: E402
from src.tool.capabilities import load_capabilities  # noqa: E402

HEURE = 3600


class _MoteurCasse:
    """Moteur d'outils dont chaque appel échoue."""

    def __init__(self):
        self.capabilities = load_capabilities()

    def execute_tool(self, tool_id, *args, **kwargs):
        raise RuntimeError("le fournisseur ne répond pas")


@pytest.fixture
def gestionnaire():
    """Un service de notification en mémoire, propre."""
    return NotificationManagerImpl(store=InMemoryNotificationStore())


@pytest.fixture
def temoin(gestionnaire):
    """Le témoin branché sur ce service."""
    return PlatformNotifier(gestionnaire)


def _recues(gestionnaire, **filtres):
    """Les notifications présentes dans le magasin."""
    return gestionnaire.list_notifications(limit=50, **filtres)


# ----------------------------------------------------------------------
# 1. Une routine qui s'arrête le dit
# ----------------------------------------------------------------------

def test_une_routine_arretee_apres_trois_echecs_previent_son_proprietaire(
    gestionnaire, temoin
):
    """
    De bout en bout : le planificateur arrête la routine, et le propriétaire
    l'apprend. Sans cela, elle paraîtrait veiller encore.
    """
    registre = RoutineRegistry()
    registre.declare("veille", "Surveiller les métriques",
                     [RoutineAction("metrics", "read")], HEURE, subject="awa")
    registre.enable("veille")
    planificateur = RoutineScheduler(
        registre, tool_engine=_MoteurCasse(), notifier=temoin,
    )

    for tour in range(3):
        planificateur.run(registre.get("veille"), now=tour * HEURE)

    recues = _recues(gestionnaire, recipient="awa")
    assert len(recues) == 1
    assert "veille" in recues[0].title
    assert "réactiv" in recues[0].message
    assert recues[0].notification_type is NotificationType.TASK_FAILED


def test_un_budget_epuise_previent_aussi(gestionnaire, temoin):
    """
    L'autre façon dont une routine s'arrête. Le budget épuisé **arrête** la
    routine ; sans notification, il l'arrêterait en silence.
    """
    registre = RoutineRegistry()
    registre.declare("veille", "Surveiller", [RoutineAction("metrics", "read")],
                     HEURE, subject="awa")
    registre.enable("veille")
    surete = RoutineSafety()
    surete.set_limit("veille", 1)
    planificateur = RoutineScheduler(
        registre, tool_engine=_MoteurCasse(), safety=surete, notifier=temoin,
    )

    planificateur.run(registre.get("veille"), now=0)
    planificateur.run(registre.get("veille"), now=HEURE)

    messages = " ".join(n.message for n in _recues(gestionnaire, recipient="awa"))
    assert "Budget épuisé" in messages


def test_une_routine_qui_tourne_ne_notifie_rien(gestionnaire, temoin):
    """
    Une boîte qui reçoit tout enterre le message qui comptait. Seul ce qui
    demande une décision est notifié.
    """
    registre = RoutineRegistry()
    registre.declare("veille", "Surveiller", [RoutineAction("metrics", "read")],
                     HEURE, subject="awa")
    registre.enable("veille")

    class _MoteurQuiRepond:
        capabilities = load_capabilities()

        def execute_tool(self, tool_id, *args, **kwargs):
            return {"ok": True}

    planificateur = RoutineScheduler(
        registre, tool_engine=_MoteurQuiRepond(), notifier=temoin,
    )
    planificateur.run(registre.get("veille"), now=0)

    assert _recues(gestionnaire) == []


def test_un_planificateur_sans_temoin_fonctionne(gestionnaire):
    """Le témoin est facultatif : rien ne dépend de lui."""
    registre = RoutineRegistry()
    registre.declare("veille", "Surveiller", [RoutineAction("metrics", "read")], HEURE)
    registre.enable("veille")
    planificateur = RoutineScheduler(registre, tool_engine=_MoteurCasse())

    for tour in range(3):
        tour_fait = planificateur.run(registre.get("veille"), now=tour * HEURE)

    assert tour_fait.disabled_after is True


def test_un_temoin_qui_echoue_ne_fait_pas_tomber_le_tour():
    """Un témoin, pas un maillon. La routine s'arrête quand même."""

    class _TemoinCasse:
        def routine_stopped(self, *args, **kwargs):
            raise RuntimeError("service de notification indisponible")

    registre = RoutineRegistry()
    registre.declare("veille", "Surveiller", [RoutineAction("metrics", "read")], HEURE)
    registre.enable("veille")
    planificateur = RoutineScheduler(
        registre, tool_engine=_MoteurCasse(), notifier=_TemoinCasse(),
    )

    for tour in range(3):
        tour_fait = planificateur.run(registre.get("veille"), now=tour * HEURE)

    assert tour_fait.disabled_after is True
    assert registre.get("veille").enabled is False


# ----------------------------------------------------------------------
# 2. Le destinataire est déduit, jamais choisi
# ----------------------------------------------------------------------

def test_ce_qui_appartient_a_la_plateforme_part_vers_l_exploitation(
    gestionnaire, temoin
):
    """Une routine sans propriétaire n'est la donnée privée de personne."""
    temoin.routine_stopped("veille-systeme", "3 échecs consécutifs.", subject=None)

    recue = _recues(gestionnaire)[0]
    assert recue.recipient is None
    assert recue.role == ROLE_EXPLOITATION


def test_ce_qui_appartient_a_quelqu_un_ne_part_pas_au_role(gestionnaire, temoin):
    """Sinon l'exploitation lirait ce qui regarde une personne."""
    temoin.routine_stopped("veille", "3 échecs consécutifs.", subject="awa")

    recue = _recues(gestionnaire)[0]
    assert recue.recipient == "awa"
    assert recue.role is None


def test_l_arret_d_urgence_est_urgent_et_global(gestionnaire, temoin):
    """Il vaut pour les routines de tout le monde : il va à l'exploitation."""
    temoin.routines_halted("awa", "incident chez le fournisseur")

    recue = _recues(gestionnaire)[0]
    assert recue.role == ROLE_EXPLOITATION
    assert recue.priority.value == "urgent"
    assert "awa" in recue.message
    assert "n'expire pas" in recue.message


def test_la_levee_se_notifie_autant_que_l_engagement(gestionnaire, temoin):
    """Savoir que les routines ont repris fait partie de savoir ce qui tourne."""
    temoin.routines_released("awa")

    recue = _recues(gestionnaire)[0]
    assert "levé" in recue.title.lower()
    assert "awa" in recue.message


# ----------------------------------------------------------------------
# 3. Les exécutions longues
# ----------------------------------------------------------------------

def test_une_execution_interrompue_dit_comment_la_reprendre(gestionnaire, temoin):
    """
    Sans cela, le point de reprise existe et personne ne sait qu'il existe :
    la reprise resterait une possibilité théorique.
    """
    temoin.workflow_interrupted(
        "run_abc123", "revue", failing_agent="security", subject="awa",
    )

    recue = _recues(gestionnaire, recipient="awa")[0]
    assert "security" in recue.message
    assert "/workflow/runs/run_abc123/resume" in recue.message
    assert recue.related_id == "run_abc123"


def test_un_temoin_sans_gestionnaire_ne_fait_rien_et_le_dit():
    """L'appelant n'a pas à savoir si le service est monté."""
    orphelin = PlatformNotifier(None)

    assert orphelin.available is False
    assert orphelin.routine_stopped("veille", "x") is None
    assert orphelin.workflow_interrupted("run_x", "revue") is None
