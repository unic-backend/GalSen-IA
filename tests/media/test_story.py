"""
Quelle structure, et sur quelle matière réelle
(VOLET M07 du moteur média).

La directive §6 donne une liste — accroche, contexte, argument, preuve, appel à
l'action — puis ajoute la phrase qui compte davantage : *ne force pas cette
structure quand elle ne convient pas.*

Cette phrase est tout le volet, parce que le défaut qu'elle prévient est le
comportement par défaut de tout moteur narratif. La liste ci-dessus est une
structure **marketing**. Appliquée à un documentaire, elle produit une publicité
avec des images d'archive ; à une leçon, un argumentaire de vente sur la
photosynthèse. Le moteur n'a pas mal fonctionné : il a fait exactement ce pour
quoi il a été écrit, sur une matière qui ne l'a pas demandé.

Ce que ces tests gardent :

1. **Un domaine non déclaré n'a aucune structure** — pas de repli marketing.
2. **L'appel à l'action est un procédé, pas un universel.**
3. **Un rôle vide est nommé, jamais comblé.**
4. **Durée visée et durée mesurée ne se confondent pas.**
5. **Une incrustation qui répète la voix est signalée.**
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.story.planner import (  # noqa: E402
    ECART_DUREE_TOLERE,
    EMPLACEMENTS,
    PlannedScene,
    PlanRefused,
    check_redundancy,
    plan_scenes,
    planner_report,
)
from src.media.story.structures import (  # noqa: E402
    STRUCTURE_INCONNUE,
    STRUCTURE_TROUVEE,
    STRUCTURES,
    StoryRefused,
    assign_roles,
    check_cta,
    story_report,
    structure_for,
)


# ----------------------------------------------------------------------
# 1. Aucun repli vers la structure marketing
# ----------------------------------------------------------------------

def test_un_domaine_non_declare_n_a_aucune_structure():
    """
    Le défaut que ce volet existe pour empêcher.

    Retomber sur la structure marketing serait l'erreur nommée par la directive
    §6, atteinte par un défaut d'apparence parfaitement raisonnable.
    """
    resultat = structure_for("poesie_experimentale")

    assert resultat["status"] == STRUCTURE_INCONNUE
    assert "erreur que la directive" in resultat["reason"]
    assert "marketing" in resultat["declared_domains"]


def test_ranger_dans_un_domaine_inconnu_est_refuse():
    """Un plan produit là raconterait autre chose que la matière."""
    with pytest.raises(StoryRefused):
        assign_roles("poesie_experimentale", [{"role": "hook", "quote": "x"}])


def test_chaque_domaine_declare_sa_propre_structure():
    """Un gabarit unique décliné ne serait qu'un gabarit unique."""
    documentaire = structure_for("documentary")["roles"]
    marketing = structure_for("marketing")["roles"]

    assert documentaire != marketing
    assert "cta" not in documentaire


def test_la_science_exige_ses_limites():
    """Un résultat sans ses limites est une affirmation, pas une science."""
    assert "limitation" in structure_for("scientific")["roles"]


def test_l_information_exige_son_attribution():
    """Une information sans source n'est pas diffusable."""
    assert "attribution" in structure_for("news")["roles"]


# ----------------------------------------------------------------------
# 2. L'appel à l'action n'est pas un universel
# ----------------------------------------------------------------------

def test_un_appel_a_l_action_est_refuse_dans_un_documentaire():
    """Il le transforme en publicité, et c'est le client qui s'en aperçoit."""
    verdict = check_cta("documentary", has_cta=True)

    assert verdict["allowed"] is False
    assert "publicité" in verdict["reason"]


@pytest.mark.parametrize("domaine", ["education", "news", "scientific",
                                     "interview", "sports_analysis"])
def test_aucun_domaine_non_commercial_n_accepte_d_appel_a_l_action(domaine):
    """La liste est courte et doit le rester visiblement."""
    assert check_cta(domaine, has_cta=True)["allowed"] is False


def test_le_marketing_l_accepte():
    """Le refuser partout serait aussi faux que l'imposer partout."""
    assert check_cta("marketing", has_cta=True)["allowed"] is True


def test_son_absence_n_est_jamais_un_probleme():
    """Aucun domaine n'*exige* un appel à l'action."""
    for domaine in STRUCTURES:
        assert check_cta(domaine, has_cta=False)["allowed"] is True


# ----------------------------------------------------------------------
# 3. Un rôle vide est nommé, jamais comblé
# ----------------------------------------------------------------------

def test_les_roles_vides_sont_nommes():
    """
    « Ce documentaire n'a pas de partie preuve » est un fait dont le
    réalisateur a besoin.

    Générer une section plausible est la façon dont une machine se met à écrire
    l'argument au lieu de l'agencer.
    """
    resultat = assign_roles("documentary", [
        {"role": "hook", "quote": "Tout a commencé ici"},
        {"role": "context", "quote": "En 1960"},
    ])

    assert set(resultat["empty_roles"]) == {"development", "evidence", "resolution"}
    assert resultat["complete"] is False
    assert "jamais comblés" in resultat["note"]


def test_un_role_hors_structure_est_rapporte_pas_deplace():
    """Le ranger de force ferait raconter autre chose."""
    resultat = assign_roles("documentary", [
        {"role": "hook", "quote": "Tout a commencé ici"},
        {"role": "cta", "quote": "Abonnez-vous"},
    ])

    assert [entree["role"] for entree in resultat["outside_structure"]] == ["cta"]
    assert "raconter autre chose" in resultat["outside_structure"][0]["reason"]


def test_une_structure_complete_est_reconnue_comme_telle():
    """Le cas nominal existe."""
    resultat = assign_roles("interview", [
        {"role": role, "quote": f"matière {role}"}
        for role in structure_for("interview")["roles"]
    ])

    assert resultat["complete"] is True
    assert resultat["empty_roles"] == []


# ----------------------------------------------------------------------
# 4. Durée visée et durée mesurée
# ----------------------------------------------------------------------

def _scene(**extra):
    """Une scène planifiée minimale."""
    champs = {"scene_id": "scene-01", "purpose": "hook"}
    champs.update(extra)
    return PlannedScene(**champs)


def test_une_duree_visee_n_est_pas_une_duree_mesuree():
    """L'une est une demande, l'autre un fait ; les fondre ferait passer un
    souhait pour une mesure."""
    scene = _scene(target_duration=8.0, measured_duration=14.0)

    conflit = scene.duration_conflict

    assert conflit["target"] == 8.0
    assert conflit["measured"] == 14.0
    assert "coupera quelqu'un" in conflit["reason"]


def test_un_ecart_dans_la_tolerance_ne_declenche_rien():
    """Signaler chaque dixième de seconde rendrait le signal inutile."""
    scene = _scene(target_duration=10.0,
                   measured_duration=10.0 * (1 + ECART_DUREE_TOLERE / 2))

    assert scene.duration_conflict is None


def test_sans_l_une_des_deux_aucun_ecart_n_est_calcule():
    """Comparer une mesure à une absence produirait un écart imaginaire."""
    assert _scene(target_duration=8.0).duration_conflict is None
    assert _scene(measured_duration=8.0).duration_conflict is None


def test_une_scene_trop_courte_est_signalee_autrement():
    """Elle tiendra, mais l'écart vient d'une sélection que personne n'a revue."""
    conflit = _scene(target_duration=20.0, measured_duration=3.0).duration_conflict

    assert "bien plus courte" in conflit["reason"]


# ----------------------------------------------------------------------
# 5. Une incrustation qui répète la voix
# ----------------------------------------------------------------------

def test_une_incrustation_qui_repete_la_voix_est_signalee():
    """
    Le « grand texte générique » que la directive §7 refuse.

    Le spectateur a déjà ces mots, dans la voix ; l'écran dépense son seul
    canal à les répéter.
    """
    scene = _scene(slots={
        "voice": "Il faut comparer deux fractions avant de les additionner",
        "typography": "Il faut comparer deux fractions",
    })

    verdict = check_redundancy(scene)

    assert verdict["redundant"] is True
    assert verdict["overlap"] == 1.0
    assert "grand texte générique" in verdict["reason"]


def test_une_incrustation_qui_apporte_autre_chose_ne_l_est_pas():
    """Le signal doit disparaître quand sa raison disparaît."""
    scene = _scene(slots={
        "voice": "Il faut comparer deux fractions avant de les additionner",
        "typography": "1/3 < 1/2",
    })

    assert check_redundancy(scene)["redundant"] is False


def test_sans_voix_ou_sans_incrustation_rien_n_est_compare():
    """Un recouvrement calculé là serait un chiffre sans mesure."""
    verdict = check_redundancy(_scene(slots={"voice": "quelque chose"}))

    assert verdict["redundant"] is False
    assert verdict["overlap"] is None


# ----------------------------------------------------------------------
# 6. Le plan complet
# ----------------------------------------------------------------------

def test_un_plan_est_construit_sur_les_roles_remplis():
    """Une scène par rôle rempli, dans l'ordre de la structure."""
    attribution = assign_roles("documentary", [
        {"role": "hook", "quote": "Tout a commencé ici"},
        {"role": "context", "quote": "En 1960"},
    ])

    plan = plan_scenes(attribution)

    assert [s["purpose"] for s in plan["scenes"]] == ["hook", "context"]
    assert set(plan["empty_roles"]) == {"development", "evidence", "resolution"}


def test_le_plan_remonte_les_incrustations_redondantes():
    """Invisible dans un plan, évident dans la vidéo finie."""
    attribution = assign_roles("marketing", [{"role": "hook", "quote": "x"}])

    plan = plan_scenes(attribution, slots_by_role={"hook": {
        "voice": "Notre produit change tout",
        "typography": "Notre produit change tout",
    }})

    assert plan["redundant_typography"][0]["scene_id"] == "scene-01"


def test_le_plan_remonte_les_conflits_de_duree():
    """S'en apercevoir au rendu coûte un rendu."""
    attribution = assign_roles("marketing", [{"role": "hook", "quote": "x"}])

    plan = plan_scenes(attribution, targets={"hook": 5.0},
                       measured={"hook": 12.0})

    assert plan["duration_conflicts"][0]["delta"] == 7.0


def test_les_emplacements_vides_sont_nommes():
    """Un défaut plausible ferait décrire une vidéo dont personne n'a parlé."""
    attribution = assign_roles("marketing", [{"role": "hook", "quote": "x"}])

    plan = plan_scenes(attribution, slots_by_role={"hook": {"voice": "Bonjour"}})

    assert set(plan["scenes"][0]["empty_slots"]) == set(EMPLACEMENTS) - {"voice"}


def test_un_emplacement_non_declare_est_refuse():
    """L'accepter ferait croire qu'il sera rendu."""
    with pytest.raises(PlanRefused) as refus:
        PlannedScene(scene_id="s", purpose="hook", slots={"parfum": "vanille"})

    assert "ferait croire qu'ils seront rendus" in str(refus.value)


def test_une_scene_sans_role_narratif_est_refusee():
    """Elle finit coupée sans que personne sache pourquoi elle était là."""
    with pytest.raises(PlanRefused) as refus:
        PlannedScene(scene_id="s", purpose="  ")

    assert "sans qu'on sache pourquoi" in str(refus.value)


def test_planifier_sur_zero_role_est_refuse():
    """Le plan décrirait une vidéo qui n'existe pas."""
    with pytest.raises(PlanRefused):
        plan_scenes({"roles": ["hook"], "filled": {}, "empty_roles": ["hook"]})


# ----------------------------------------------------------------------
# 7. Ce que le volet refuse
# ----------------------------------------------------------------------

def test_le_rapport_narratif_refuse_d_imposer_une_structure():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(story_report()["does_not"])

    assert "Imposer une structure" in interdits
    assert "Générer le contenu d'un rôle vide" in interdits


def test_le_rapport_du_planificateur_refuse_de_confondre_les_durees():
    """Un souhait ne doit jamais se lire comme une mesure."""
    rapport = planner_report()

    interdits = " ".join(rapport["does_not"])
    assert "durée demandée avec une durée mesurée" in interdits
    assert rapport["slots"] == list(EMPLACEMENTS)
    assert story_report()["states"] == [STRUCTURE_TROUVEE, STRUCTURE_INCONNUE]
