"""
La déclaration d'une routine, et ses refus (phase 47.1).

Une routine est un travail que la plateforme fait **sans personne devant**. Ce
seul fait la distingue de tout ce qui a été construit jusqu'ici : nul ne lit
l'avertissement, nul n'approuve une étape, et nul ne remarque qu'elle échoue
chaque nuit depuis mardi.

Tout ce qui coûte cher est donc vérifié à la **déclaration**. Une fois au
registre, une routine est connue pour n'être faite que d'outils exécutables sans
témoin — le moteur qui la déclenchera n'a plus rien à décider, donc rien à
décider de travers.

C'est ici que `may_run_unattended`, construit en phase 38.1, trouve son premier
vrai appelant. Et il est appelé avec l'**opération**, pas seulement le nom de
l'outil : `python -m pytest` est pré-approuvé, `python -c` ne l'est pas, et les
deux nomment `terminal`.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.routines import (  # noqa: E402
    ACTIONS_MAXIMUM,
    INTERVALLE_MINIMAL_SECONDES,
    RoutineAction,
    RoutineRefused,
    RoutineRegistry,
)
from src.tool.capabilities import DataScope, load_capabilities  # noqa: E402

HEURE = 3600


@pytest.fixture
def registre():
    """Un registre de routines sur les capacités réelles des 22 outils."""
    return RoutineRegistry()


#: Sentinelle : `None` veut dire « prends le défaut », `[]` veut dire « aucune
#: action », et `actions or defaut` confondait les deux — un test de la liste
#: vide passait alors sur la liste par défaut, sans rien vérifier.
_DEFAUT = object()


def _declarer(registre, identifiant="veille", actions=_DEFAUT, intervalle=HEURE,
              sujet=None, description="Surveiller la CI chaque heure"):
    """Déclare une routine, avec des valeurs par défaut valables."""
    if actions is _DEFAUT:
        actions = [RoutineAction("github", "list_runs")]
    return registre.declare(
        identifiant, description, actions, intervalle, subject=sujet,
    )


# ----------------------------------------------------------------------
# 1. Déclarer n'est pas activer
# ----------------------------------------------------------------------

def test_une_routine_nait_desactivee(registre):
    """
    Même règle que le registre des sources : écrire une routine et la faire
    tourner sont deux décisions, à deux moments.
    """
    routine = _declarer(registre)

    assert routine.enabled is False
    assert registre.enabled_routines() == []


def test_l_activation_est_un_acte_separe(registre):
    """Et elle est réversible."""
    _declarer(registre)

    registre.enable("veille")
    assert [r.routine_id for r in registre.enabled_routines()] == ["veille"]

    registre.disable("veille")
    assert registre.enabled_routines() == []


def test_une_routine_inconnue_ne_s_active_pas(registre):
    """Activer ce qui n'existe pas doit se voir."""
    with pytest.raises(RoutineRefused, match="inconnue"):
        registre.enable("jamais-declaree")


def test_un_doublon_est_refuse(registre):
    """Un doublon silencieux ferait disparaître l'une des deux sans trace."""
    _declarer(registre)

    with pytest.raises(RoutineRefused, match="déjà déclarée"):
        _declarer(registre)


# ----------------------------------------------------------------------
# 2. Ce qui tourne sans témoin, et ce qui ne le peut pas
# ----------------------------------------------------------------------

def test_un_outil_sous_portillon_est_refuse_a_la_declaration(registre):
    """
    Refuser ici vaut mieux qu'échouer chaque nuit sans témoin. `terminal`
    exige une approbation humaine ; une routine n'en a pas.
    """
    with pytest.raises(RoutineRefused, match="approbation humaine"):
        _declarer(registre, actions=[RoutineAction("terminal", ["python", "-c", "1"])])


def test_une_borne_pre_approuvee_passe(registre):
    """
    Le point précis de la phase 39.3 : la borne est approuvée, pas l'outil.
    Ces deux actions nomment `terminal` et n'ont pas le même verdict.
    """
    routine = _declarer(
        registre, identifiant="tests-nuit",
        actions=[RoutineAction("terminal", ["python", "-m", "pytest", "-q"])],
        description="Exécuter la suite de tests chaque nuit",
    )

    assert routine.routine_id == "tests-nuit"


def test_un_outil_non_declare_est_refuse(registre):
    """« Non déclaré » n'est pas « inoffensif », y compris dans une routine."""
    with pytest.raises(RoutineRefused, match="non déclarée"):
        _declarer(registre, actions=[RoutineAction("outil_fantome", "x")])


def test_le_refus_nomme_l_action_fautive(registre):
    """
    Une routine refusée sans motif est une routine que son auteur réécrira à
    l'identique. La position dans la liste est dite.
    """
    with pytest.raises(RoutineRefused, match="action 2"):
        _declarer(registre, actions=[
            RoutineAction("metrics", "read"),
            RoutineAction("gui", "click"),
        ])


def test_toutes_les_actions_sont_verifiees_pas_seulement_la_premiere(registre):
    """Vérifier la première seulement laisserait passer tout le reste."""
    with pytest.raises(RoutineRefused):
        _declarer(registre, actions=[
            RoutineAction("metrics", "read"),
            RoutineAction("git", "summary"),
            RoutineAction("docker", "run"),
        ])

    assert registre.get("veille") is None


# ----------------------------------------------------------------------
# 3. Une routine appartient à quelqu'un, ou à la plateforme
# ----------------------------------------------------------------------

def _outil_prive_et_sans_temoin():
    """Un outil réel à la fois `user_private` et exécutable sans témoin."""
    capacites = load_capabilities()
    for tool_id in capacites.unattended_ids():
        if capacites.get(tool_id).data_scope is DataScope.USER_PRIVATE:
            return tool_id
    raise AssertionError("Le registre devrait porter un tel outil")


def test_une_routine_de_plateforme_ne_touche_pas_la_donnee_d_une_personne(registre):
    """
    À trois heures du matin il n'y a pas de session dont déduire un
    propriétaire, et lire les données de « personne en particulier » n'a pas
    de sens.
    """
    outil = _outil_prive_et_sans_temoin()

    with pytest.raises(RoutineRefused, match="n'en nomme aucune"):
        _declarer(registre, actions=[RoutineAction(outil, "read")], sujet=None)


def test_la_meme_routine_passe_quand_elle_nomme_sa_personne(registre):
    """La symétrie : encadrer n'est pas interdire."""
    outil = _outil_prive_et_sans_temoin()

    routine = _declarer(
        registre, identifiant="tri-perso",
        actions=[RoutineAction(outil, "read")], sujet="fatou",
        description="Trier les documents de Fatou chaque matin",
    )

    assert routine.subject == "fatou"
    assert routine.belongs_to_platform is False


def test_une_routine_sans_sujet_appartient_a_la_plateforme(registre):
    """Et elle le dit, au lieu de laisser deviner."""
    routine = _declarer(registre)

    assert routine.subject is None
    assert routine.belongs_to_platform is True


def test_une_personne_ne_voit_pas_les_routines_d_une_autre(registre):
    """La liste des routines de quelqu'un dit ce qu'il surveille."""
    outil = _outil_prive_et_sans_temoin()
    _declarer(registre, identifiant="commune")
    _declarer(registre, identifiant="a-fatou", actions=[RoutineAction(outil, "read")],
              sujet="fatou", description="Pour Fatou")
    _declarer(registre, identifiant="a-moussa", actions=[RoutineAction(outil, "read")],
              sujet="moussa", description="Pour Moussa")

    vues = [r.routine_id for r in registre.list_routines(subject="fatou")]

    assert vues == ["a-fatou", "commune"]


def test_la_plateforme_ne_voit_pas_les_routines_des_personnes(registre):
    """Une tâche de fond ne lit les affaires de personne, listes comprises."""
    outil = _outil_prive_et_sans_temoin()
    _declarer(registre, identifiant="commune")
    _declarer(registre, identifiant="a-fatou", actions=[RoutineAction(outil, "read")],
              sujet="fatou", description="Pour Fatou")

    vues = [r.routine_id for r in registre.list_routines()]

    assert vues == ["commune"]


# ----------------------------------------------------------------------
# 4. Les bornes
# ----------------------------------------------------------------------

def test_un_intervalle_trop_court_est_refuse(registre):
    """Une routine trop fréquente attaque sa propre plateforme."""
    with pytest.raises(RoutineRefused, match="plancher"):
        _declarer(registre, intervalle=INTERVALLE_MINIMAL_SECONDES - 1)


def test_le_plancher_lui_meme_est_accepte(registre):
    """Une borne exclusive à tort ferait échouer le cas exactement conforme."""
    routine = _declarer(registre, intervalle=INTERVALLE_MINIMAL_SECONDES)

    assert routine.interval_seconds == INTERVALLE_MINIMAL_SECONDES


def test_trop_d_actions_renvoie_vers_le_moteur_de_workflows(registre):
    """Une routine n'a ni reprise ni point de contrôle ; un workflow, si."""
    trop = [RoutineAction("metrics", "read")] * (ACTIONS_MAXIMUM + 1)

    with pytest.raises(RoutineRefused, match="workflow"):
        _declarer(registre, actions=trop)


def test_une_routine_sans_action_est_refusee(registre):
    """Elle consomme un créneau et ne se remarque jamais."""
    with pytest.raises(RoutineRefused, match="aucune action"):
        _declarer(registre, actions=[])


def test_une_description_vide_est_refusee(registre):
    """
    Elle sera lue par la personne à qui la routine appartient, au moment où
    elle se demandera pourquoi elle tourne.
    """
    with pytest.raises(RoutineRefused, match="description"):
        _declarer(registre, description="   ")


def test_un_identifiant_vide_est_refuse(registre):
    """Rien ne peut être arrêté qu'on ne peut pas nommer."""
    with pytest.raises(RoutineRefused, match="identifiant"):
        _declarer(registre, identifiant="  ")


# ----------------------------------------------------------------------
# 5. L'arrêt et le rapport
# ----------------------------------------------------------------------

def test_une_routine_s_arrete_toujours(registre):
    """Une routine qu'on ne peut pas arrêter est pire qu'une routine absente."""
    _declarer(registre)
    registre.enable("veille")

    registre.disable("veille")
    assert registre.get("veille").enabled is False

    assert registre.remove("veille") is True
    assert registre.get("veille") is None


def test_retirer_ce_qui_n_existe_pas_n_est_pas_une_erreur(registre):
    """C'est un `False`."""
    assert registre.remove("jamais") is False


def test_le_rapport_dit_ce_qui_est_refuse_a_la_declaration(registre):
    """Ce qu'un lecteur doit pouvoir vérifier sans lire le code."""
    _declarer(registre)
    registre.enable("veille")

    rapport = registre.registry_report()

    assert rapport["declared"] == 1
    assert rapport["enabled"] == 1
    assert rapport["platform_routines"] == 1
    assert rapport["minimum_interval_seconds"] == INTERVALLE_MINIMAL_SECONDES
    refus = " ".join(rapport["refuses_at_declaration"])
    assert "sans témoin" in refus
    assert "Déclarer n'est pas activer" in rapport["note"]


def test_une_routine_refusee_n_entre_pas_au_registre(registre):
    """Refuser après avoir enregistré ne serait pas refuser."""
    with pytest.raises(RoutineRefused):
        _declarer(registre, actions=[RoutineAction("gui", "click")])

    assert registre.registry_report()["declared"] == 0
