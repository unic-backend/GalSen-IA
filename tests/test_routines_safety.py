"""
La sûreté des routines : budget, arrêt d'urgence, portée (phase 48.1).

La phase 47 a rendu les routines correctes. Celle-ci les rend **bornées**, ce
qui est une autre propriété : une routine parfaitement correcte peut appeler une
API facturée toutes les cinq minutes pendant un an, et personne ne s'en aperçoit
avant la facture.

Ce que ces tests gardent :

1. **Le budget épuisé arrête la routine, il ne la saute pas.** Une routine
   sautée en silence paraît tourner et ne fait rien — précisément le mode de
   panne que tout ce VOLET cherche à éviter.
2. **L'arrêt d'urgence est global et ne se lève jamais tout seul.** Un arrêt qui
   expire après une heure n'est pas un arrêt mais un délai, et celui qui l'a
   engagé devrait continuer à surveiller.
3. **Ce qui protège ne dépend pas de ce qui exécute.** Un arrêt d'urgence logé
   dans le moteur qu'il arrête est un arrêt qu'une panne de ce moteur emporte.
4. **Une routine ne peut pas se relever elle-même.** Aucun outil ne gère les
   routines ; c'est vrai par construction, et le test le garde parce que cela
   cesserait silencieusement le jour où un outil `routines` serait ajouté.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.routines import (  # noqa: E402
    FENETRE_SECONDES,
    TOURS_PAR_FENETRE_PAR_DEFAUT,
    RoutineAction,
    RoutineRegistry,
    RoutineSafety,
    RoutineScheduler,
    routine_reachable_tools,
)
from src.tool.capabilities import load_capabilities  # noqa: E402

HEURE = 3600


class _Moteur:
    """Moteur d'outils factice qui répond toujours."""

    capabilities = None

    def __init__(self):
        self.appels = []
        self.capabilities = load_capabilities()

    def execute_tool(self, tool_id, *args, **kwargs):
        self.appels.append(tool_id)
        return {"ok": True}


@pytest.fixture
def surete():
    """Une couche de sûreté neuve."""
    return RoutineSafety()


@pytest.fixture
def registre():
    """Un registre portant une routine horaire active."""
    registre = RoutineRegistry()
    registre.declare("veille", "Surveiller les métriques",
                     [RoutineAction("metrics", "read")], HEURE)
    registre.enable("veille")
    return registre


@pytest.fixture
def planificateur(registre, surete):
    """Un planificateur relié à cette couche de sûreté."""
    return RoutineScheduler(registre, tool_engine=_Moteur(), safety=surete)


# ----------------------------------------------------------------------
# 1. Le budget
# ----------------------------------------------------------------------

def test_demander_n_est_pas_depenser(surete):
    """`check` observe ; `consume` décompte."""
    surete.set_limit("veille", 2)

    for _ in range(5):
        assert surete.check("veille", now=0)[0] is True

    assert surete.budget_state("veille")["runs"] == 0


def test_le_budget_se_consomme_et_s_epuise(surete):
    """Deux tours autorisés, le troisième refusé."""
    surete.set_limit("veille", 2)

    surete.consume("veille", now=0)
    surete.consume("veille", now=1)

    autorise, motif = surete.check("veille", now=2)
    assert autorise is False
    assert "Budget épuisé" in motif


def test_une_nouvelle_fenetre_rouvre_le_budget(surete):
    """Un budget quotidien qui ne se renouvelle pas est une désactivation."""
    surete.set_limit("veille", 1)
    surete.consume("veille", now=0)

    assert surete.check("veille", now=FENETRE_SECONDES - 1)[0] is False
    assert surete.check("veille", now=FENETRE_SECONDES)[0] is True


def test_une_limite_nulle_est_refusee(surete):
    """
    Elle laisserait une routine paraître active sans jamais tourner. Arrêter
    une routine se fait explicitement.
    """
    with pytest.raises(ValueError, match="désactivation déguisée"):
        surete.set_limit("veille", 0)


def test_le_defaut_ne_restreint_pas_ce_qui_est_deja_declarable(surete):
    """
    288 tours = un toutes les cinq minutes, la cadence maximale que le plancher
    d'intervalle autorise. Le défaut attrape ce qui **change** après coup, pas
    ce qui a été déclaré dans les règles.
    """
    assert TOURS_PAR_FENETRE_PAR_DEFAUT * 300 == FENETRE_SECONDES


def test_le_budget_epuise_arrete_la_routine(planificateur, registre, surete):
    """
    Le point de cette phase. Sauter en silence ferait paraître la routine
    active alors qu'elle ne fait plus rien.
    """
    surete.set_limit("veille", 1)
    routine = registre.get("veille")

    planificateur.run(routine, now=0)
    tour = planificateur.run(routine, now=HEURE)

    assert tour.skipped
    assert tour.disabled_after is True
    assert registre.get("veille").enabled is False


def test_un_tour_hors_budget_n_appelle_aucun_outil(registre, surete):
    """Refuser après avoir appelé ne serait pas refuser."""
    moteur = _Moteur()
    planificateur = RoutineScheduler(registre, tool_engine=moteur, safety=surete)
    surete.set_limit("veille", 1)

    planificateur.run(registre.get("veille"), now=0)
    planificateur.run(registre.get("veille"), now=HEURE)

    assert moteur.appels == ["metrics"]


# ----------------------------------------------------------------------
# 2. L'arrêt d'urgence
# ----------------------------------------------------------------------

def test_l_arret_est_global_et_ne_demande_aucun_identifiant(planificateur, surete):
    """
    Au moment où l'on a besoin d'un arrêt d'urgence, on n'a pas la liste des
    routines.
    """
    surete.halt("awa", "incident chez le fournisseur")

    assert planificateur.due_at(0) == []


def test_un_tour_est_refuse_pendant_l_arret(planificateur, registre, surete):
    """Et le refus nomme qui l'a engagé, et pourquoi."""
    surete.halt("awa", "incident chez le fournisseur")

    tour = planificateur.run(registre.get("veille"), now=0)

    assert "awa" in tour.skipped
    assert "incident chez le fournisseur" in tour.skipped


def test_l_arret_ne_se_leve_pas_tout_seul(surete):
    """Un arrêt qui expire est un délai, pas un arrêt."""
    surete.halt("awa", "incident")

    assert surete.check("veille", now=FENETRE_SECONDES * 365)[0] is False
    assert surete.halted is True


def test_l_arret_se_leve_explicitement(surete, planificateur):
    """Et la levée se voit."""
    surete.halt("awa", "incident")

    assert surete.release() is True
    assert surete.halted is False
    assert planificateur.due_at(0) != []


def test_lever_un_arret_absent_n_est_pas_une_erreur(surete):
    """C'est un `False`."""
    assert surete.release() is False


def test_un_arret_anonyme_est_refuse(surete):
    """Sinon personne ne sait s'il a le droit de le lever."""
    with pytest.raises(ValueError, match="nomme qui l'engage"):
        surete.halt("  ", "incident")


def test_un_arret_sans_raison_est_refuse(surete):
    """Elle sera lue par celui qui envisagera de lever, peut-être des jours après."""
    with pytest.raises(ValueError, match="dit pourquoi"):
        surete.halt("awa", "   ")


def test_l_arret_n_interrompt_pas_un_tour_deja_commence(surete):
    """
    Le dire vaut mieux que le laisser croire : un tour en cours finit, et
    aucun autre ne démarre.
    """
    rapport = surete.safety_report()

    assert any("déjà commencé" in ligne for ligne in rapport["does_not"])


def test_l_arret_ne_remplace_pas_une_limite_chez_le_fournisseur(surete):
    """La plateforme borne ce qu'elle déclenche, pas ce qui est facturé ailleurs."""
    rapport = surete.safety_report()

    assert any("fournisseur" in ligne for ligne in rapport["does_not"])


# ----------------------------------------------------------------------
# 3. Ce qui protège ne dépend pas de ce qui exécute
# ----------------------------------------------------------------------

def test_la_surete_survit_a_un_planificateur_remplace(registre, surete):
    """
    Un arrêt d'urgence logé dans le moteur qu'il arrête est un arrêt qu'une
    panne de ce moteur emporte avec elle.
    """
    surete.halt("awa", "incident")

    nouveau = RoutineScheduler(registre, tool_engine=_Moteur(), safety=surete)

    assert nouveau.due_at(0) == []


def test_deux_planificateurs_partagent_le_meme_arret(registre, surete):
    """Un arrêt qui ne vaudrait que pour une instance n'arrêterait rien."""
    premier = RoutineScheduler(registre, tool_engine=_Moteur(), safety=surete)
    second = RoutineScheduler(registre, tool_engine=_Moteur(), safety=surete)

    premier.safety.halt("awa", "incident")

    assert second.due_at(0) == []


def test_le_rapport_du_planificateur_porte_l_etat_de_surete(planificateur, surete):
    """Une interface doit voir l'arrêt sans interroger deux objets."""
    surete.halt("awa", "incident chez le fournisseur")

    rapport = planificateur.scheduler_report(now=0)

    assert rapport["safety"]["halted"] is True
    assert rapport["safety"]["halt"]["engaged_by"] == "awa"


# ----------------------------------------------------------------------
# 4. Ce qu'une routine ne peut pas atteindre
# ----------------------------------------------------------------------

def test_aucun_outil_ne_gere_les_routines():
    """
    Une routine ne peut ni en activer une autre, ni relever son budget, ni
    lever l'arrêt d'urgence. Vrai **par construction** — et ce test le garde,
    parce que cela cesserait silencieusement le jour où un outil `routines`
    serait ajouté au catalogue.
    """
    rapport = routine_reachable_tools(load_capabilities())

    assert rapport["routine_management_tools"] == []
    assert rapport["self_escalation_possible"] is False


def test_les_outils_atteignables_sont_ceux_qui_tournent_sans_temoin():
    """La liste vient du registre des capacités, pas d'une seconde vérité."""
    capacites = load_capabilities()

    rapport = routine_reachable_tools(capacites)

    assert rapport["unattended_tools"] == sorted(capacites.unattended_ids())


def test_le_rapport_de_surete_nomme_ses_regles(surete):
    """Ce qu'un lecteur doit pouvoir vérifier sans lire le code."""
    regles = " ".join(surete.safety_report()["rules"])

    assert "il ne la saute pas" in regles
    assert "on n'a pas la liste des routines" in regles
    assert "un délai" in regles
