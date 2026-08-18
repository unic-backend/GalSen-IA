"""
Planifier et déclencher une routine (phase 47.2).

Deux choses sont séparées ici à dessein, parce que les confondre est ce qui rend
un planificateur intestable.

**Décider est pur.** `due_at(now)` est une fonction du registre et d'un instant.
Aucune horloge n'est lue, aucun fil n'est démarré, rien ne dort — le temps vient
de l'appelant. Un planificateur qui lit `time.time()` en interne ne se teste
qu'en attendant, et un test qui attend est un test qu'on finit par supprimer.

**Exécuter est gardé.** Trois gardes, chacune née de ce que « personne ne
regarde » veut dire :

1. **La capacité est revérifiée au déclenchement.** La déclaration l'avait
   vérifiée (47.1), mais le registre d'outils peut avoir été rechargé entre-temps.
2. **Une routine ne se chevauche pas elle-même.** Deux copies du même travail
   nocturne qui se courent après sont un bogue que personne ne débogue à cette
   heure-là.
3. **L'échec répété arrête la routine, en le disant.** Une routine qui échoue
   chaque tour ne surveille rien ; elle occupe un créneau. S'arrêter en silence
   serait pire, car on croirait qu'elle veille encore.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.routines import (  # noqa: E402
    ECHECS_AVANT_ARRET,
    RoutineAction,
    RoutineRegistry,
    RoutineScheduler,
)
from src.tool.capabilities import CapabilityRegistry, load_capabilities, parse_capability  # noqa: E402

HEURE = 3600


class _Moteur:
    """Un moteur d'outils factice : il compte les appels, et peut casser."""

    def __init__(self, casse=False):
        self.casse = casse
        self.appels = []
        self.capabilities = load_capabilities()

    def execute_tool(self, tool_id, *args, **kwargs):
        self.appels.append((tool_id, args[0] if args else None))
        if self.casse:
            raise RuntimeError("service indisponible")
        return {"ok": True}


@pytest.fixture
def registre():
    """Un registre portant une routine horaire active."""
    registre = RoutineRegistry()
    registre.declare(
        "veille", "Surveiller les métriques chaque heure",
        [RoutineAction("metrics", "read")], HEURE,
    )
    registre.enable("veille")
    return registre


@pytest.fixture
def moteur():
    """Un moteur d'outils qui répond."""
    return _Moteur()


@pytest.fixture
def planificateur(registre, moteur):
    """Un planificateur sur ce registre et ce moteur."""
    return RoutineScheduler(registre, tool_engine=moteur)


# ----------------------------------------------------------------------
# 1. Décider est pur
# ----------------------------------------------------------------------

def test_une_routine_jamais_executee_est_due_tout_de_suite(planificateur):
    """
    Attendre un intervalle complet avant le premier tour rendrait une routine
    horaire inerte pendant une heure après son activation.
    """
    assert [r.routine_id for r in planificateur.due_at(0)] == ["veille"]


def test_elle_n_est_plus_due_juste_apres(planificateur):
    """La marque du dernier tour est posée à l'exécution, pas à la fin."""
    planificateur.tick(0)

    assert planificateur.due_at(10) == []


def test_elle_redevient_due_apres_son_intervalle(planificateur):
    """Le temps vient de l'appelant : le test avance l'heure, il n'attend pas."""
    planificateur.tick(0)

    assert planificateur.due_at(HEURE - 1) == []
    assert [r.routine_id for r in planificateur.due_at(HEURE)] == ["veille"]


def test_une_routine_inactive_n_est_jamais_due(registre, planificateur):
    """Désactiver arrête réellement, pas seulement en apparence."""
    registre.disable("veille")

    assert planificateur.due_at(HEURE * 10) == []


def test_le_prochain_tour_est_calculable(planificateur):
    """Une interface doit pouvoir le montrer sans rien exécuter."""
    planificateur.tick(0)

    assert planificateur.next_due("veille", 0) == HEURE
    assert planificateur.next_due("inconnue", 0) is None


def test_rien_n_est_execute_par_la_seule_decision(planificateur, moteur):
    """`due_at` observe ; elle n'agit pas."""
    planificateur.due_at(0)
    planificateur.due_at(HEURE)

    assert moteur.appels == []


# ----------------------------------------------------------------------
# 2. Exécuter
# ----------------------------------------------------------------------

def test_un_tour_execute_les_actions_dans_l_ordre(registre, moteur):
    """L'ordre déclaré est l'ordre exécuté."""
    registre.declare(
        "suite", "Trois lectures",
        [RoutineAction("metrics", "read"), RoutineAction("git", "summary"),
         RoutineAction("rag", "search")],
        HEURE,
    )
    registre.enable("suite")
    planificateur = RoutineScheduler(registre, tool_engine=moteur)

    planificateur.run(registre.get("suite"), now=0)

    assert [appel[0] for appel in moteur.appels] == ["metrics", "git", "rag"]


def test_un_tour_reussi_est_rapporte_comme_tel(planificateur, registre):
    """Encadrer n'est pas empêcher."""
    tour = planificateur.run(registre.get("veille"), now=0)

    assert tour.ok is True
    assert tour.actions[0].status == "success"


def test_un_outil_qui_leve_devient_un_echec_pas_un_plantage(registre):
    """Une routine ne doit pas faire tomber ce qui l'exécute."""
    planificateur = RoutineScheduler(registre, tool_engine=_Moteur(casse=True))

    tour = planificateur.run(registre.get("veille"), now=0)

    assert tour.ok is False
    assert "indisponible" in tour.actions[0].detail


def test_sans_moteur_d_outils_le_tour_echoue_au_lieu_de_reussir_a_vide(registre):
    """
    Rapporter un succès sans avoir rien fait serait la pire réponse : la
    routine paraîtrait veiller.
    """
    planificateur = RoutineScheduler(registre, tool_engine=None)

    tour = planificateur.run(registre.get("veille"), now=0)

    assert tour.ok is False
    assert "indisponible" in tour.actions[0].detail


# ----------------------------------------------------------------------
# 3. La revérification au déclenchement
# ----------------------------------------------------------------------

def test_la_capacite_est_reverifiee_au_declenchement(registre, moteur):
    """
    La déclaration l'avait vérifiée ; le registre d'outils peut avoir été
    rechargé depuis. Ici, l'outil devient soumis à approbation entre les deux.
    """
    resserre = CapabilityRegistry(capabilities={
        "metrics": parse_capability("metrics", {"capability": {
            "effects": ["read"], "data_scope": "system",
            "requires_approval": True, "unattended": False,
        }}),
    })
    planificateur = RoutineScheduler(
        registre, tool_engine=moteur, capabilities=resserre
    )

    tour = planificateur.run(registre.get("veille"), now=0)

    assert tour.ok is False
    assert tour.actions[0].status == "refused"
    assert "Revérifié au déclenchement" in tour.actions[0].detail


def test_une_action_refusee_n_atteint_pas_l_outil(registre, moteur):
    """Refuser après avoir appelé ne serait pas refuser."""
    vide = CapabilityRegistry(capabilities={})
    planificateur = RoutineScheduler(registre, tool_engine=moteur, capabilities=vide)

    planificateur.run(registre.get("veille"), now=0)

    assert moteur.appels == []


# ----------------------------------------------------------------------
# 4. Le non-chevauchement
# ----------------------------------------------------------------------

def test_une_routine_ne_se_chevauche_pas_elle_meme(registre, moteur):
    """
    Le tour est sauté **et dit**. Deux copies du même travail nocturne qui se
    courent après sont un bogue que personne ne débogue à cette heure-là.
    """
    planificateur = RoutineScheduler(registre, tool_engine=moteur)
    routine = registre.get("veille")

    class _MoteurReentrant(_Moteur):
        def execute_tool(self, tool_id, *args, **kwargs):
            # Pendant l'exécution, un second tour est tenté.
            self.second = planificateur.run(routine, now=1)
            return super().execute_tool(tool_id, *args, **kwargs)

    reentrant = _MoteurReentrant()
    planificateur._outils = reentrant

    planificateur.run(routine, now=0)

    assert reentrant.second.skipped
    assert "pas terminé" in reentrant.second.skipped


def test_un_tour_saute_n_est_pas_un_succes(registre, moteur):
    """Le compter comme réussi cacherait une routine qui ne tourne jamais."""
    planificateur = RoutineScheduler(registre, tool_engine=moteur)
    routine = registre.get("veille")
    planificateur._en_cours.add("veille")

    tour = planificateur.run(routine, now=0)

    assert tour.skipped
    assert tour.ok is False
    assert tour.actions == []


# ----------------------------------------------------------------------
# 5. L'échec répété
# ----------------------------------------------------------------------

def test_trois_echecs_consecutifs_arretent_la_routine(registre):
    """Une routine qui échoue chaque tour ne surveille rien."""
    planificateur = RoutineScheduler(registre, tool_engine=_Moteur(casse=True))
    routine = registre.get("veille")

    for tour_numero in range(ECHECS_AVANT_ARRET):
        tour = planificateur.run(routine, now=tour_numero * HEURE)

    assert tour.disabled_after is True
    assert registre.get("veille").enabled is False


def test_l_arret_est_annonce_dans_le_compte_rendu(registre):
    """S'arrêter en silence laisserait croire qu'elle veille encore."""
    planificateur = RoutineScheduler(registre, tool_engine=_Moteur(casse=True))
    routine = registre.get("veille")

    for tour_numero in range(ECHECS_AVANT_ARRET):
        tour = planificateur.run(routine, now=tour_numero * HEURE)

    motifs = " ".join(action.detail for action in tour.actions)
    assert "échecs consécutifs" in motifs
    assert "occupe un créneau" in motifs


def test_deux_echecs_ne_suffisent_pas(registre):
    """Assez pour absorber une panne passagère."""
    planificateur = RoutineScheduler(registre, tool_engine=_Moteur(casse=True))
    routine = registre.get("veille")

    for tour_numero in range(ECHECS_AVANT_ARRET - 1):
        planificateur.run(routine, now=tour_numero * HEURE)

    assert registre.get("veille").enabled is True


def test_un_succes_remet_le_compteur_a_zero(registre, moteur):
    """Une panne passagère ne doit pas s'accumuler sur des semaines."""
    casse = _Moteur(casse=True)
    planificateur = RoutineScheduler(registre, tool_engine=casse)
    routine = registre.get("veille")

    planificateur.run(routine, now=0)
    planificateur.run(routine, now=HEURE)
    assert planificateur.consecutive_failures("veille") == 2

    planificateur._outils = moteur
    planificateur.run(routine, now=2 * HEURE)

    assert planificateur.consecutive_failures("veille") == 0
    assert registre.get("veille").enabled is True


# ----------------------------------------------------------------------
# 6. Le tour complet et le rapport
# ----------------------------------------------------------------------

def test_le_tour_execute_tout_ce_qui_est_du(registre, moteur):
    """Deux routines dues, deux comptes rendus."""
    registre.declare("seconde", "Autre veille",
                     [RoutineAction("git", "summary")], HEURE)
    registre.enable("seconde")
    planificateur = RoutineScheduler(registre, tool_engine=moteur)

    tours = planificateur.tick(0)

    assert sorted(tour.routine_id for tour in tours) == ["seconde", "veille"]
    assert all(tour.ok for tour in tours)


def test_le_rapport_dit_ce_qui_est_du_sans_l_executer(planificateur, moteur):
    """Une interface doit pouvoir montrer l'état sans déclencher quoi que ce soit."""
    rapport = planificateur.scheduler_report(now=0)

    assert rapport["enabled"] == 1
    assert rapport["due_now"] == ["veille"]
    assert rapport["tool_engine_attached"] is True
    assert moteur.appels == []


def test_le_rapport_nomme_les_regles_tenues(planificateur):
    """Ce qu'un lecteur doit pouvoir vérifier sans lire le code."""
    regles = " ".join(planificateur.scheduler_report(now=0)["rules"])

    assert "revérifiée au déclenchement" in regles
    assert "ne se chevauche pas" in regles
    assert "n'est pas un succès" in regles
    assert "vient de l'appelant" in regles


def test_le_compte_rendu_ne_porte_pas_le_resultat_de_l_outil(planificateur, registre):
    """
    Un journal de routines n'est pas un magasin de données : recopier ce qu'un
    outil a rendu y ferait entrer, tour après tour, ce que la routine a lu.
    """
    tour = planificateur.run(registre.get("veille"), now=0)

    serialise = str(tour.as_dict())
    assert "ok" in serialise
    assert "result" not in serialise
