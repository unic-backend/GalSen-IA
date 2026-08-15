"""
Montrer à un parent le programme de son enfant — le même, et le sien seul
(VOLET 12 de Darra J).

Deux garanties se rencontrent ici. Le parent est l'un des quatre demandeurs de
la directive VI : il reçoit **le même** enregistrement officiel que l'élève et
l'enseignant. Et le lien vers l'enfant est **déclaré**, jamais déduit — une
plateforme qui devine qui est le parent finira par se tromper, et cette
erreur-là remet un enfant à la mauvaise famille.

Ce que ces tests gardent :

1. **Le même fait officiel**, mesuré avec la garantie de cohérence du VOLET 7.
2. **Aucun lien déduit** : sans déclaration, rien.
3. **Aucun autre enfant que ceux déclarés.**
4. **Ni note, ni rang, ni comparaison** — et `INSUFFICIENT_EVIDENCE` rendu tel
   quel, même s'il se lit mal.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.darra_j import (  # noqa: E402
    CurriculumStatus,
    CurriculumUnit,
    CurriculumVersion,
    EducationSystem,
    Grade,
    Period,
    Subject,
    make_provenance,
)
from src.darra_j.access import AccessRefused, access_report  # noqa: E402
from src.darra_j.assessment import (  # noqa: E402
    PREUVE_INSUFFISANTE,
    PREUVE_SUFFISANTE,
    Attempt,
    QuizItem,
    score_attempt,
)
from src.darra_j.consistency import COHERENT, check_group  # noqa: E402
from src.darra_j.parent import (  # noqa: E402
    child_curriculum,
    child_progress,
    parent_report,
)
from src.darra_j.registry import CurriculumRegistry  # noqa: E402
from src.darra_j.resolution import CurriculumQuery  # noqa: E402
from src.darra_j.student import student_answer  # noqa: E402

SYSTEME = EducationSystem(country="sn", system_id="sn-general")
OBJECTIF = "Comparer deux fractions"
DECLARES = ["enfant-7f3a"]


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


@pytest.fixture
def registre():
    """Un registre publié, avec une unité en semaine 10."""
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    ))
    depot.add_unit(CurriculumUnit(
        version_id="v-2026", grade=Grade("g6", "Sixième"),
        subject=Subject("maths", "Mathématiques"),
        period=Period(academic_year="2026-2027", week=10),
        official_title="Les fractions", objectives=(OBJECTIF,),
        provenance=_officielle(),
    ))
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        depot.advance("v-2026", etat)
    depot.publish("v-2026", decided_by="Direction des curricula")
    return depot


def _question(**extra):
    """Une question complète sur la semaine 10."""
    champs = {"academic_year": "2026-2027", "grade_id": "g6",
              "subject": "maths", "week": 10}
    champs.update(extra)
    return CurriculumQuery(**champs)


def _vue_parent(registre, **extra):
    """La vue parent nominale."""
    return child_curriculum(
        _question(), registre, child_ref="enfant-7f3a",
        viewer_ref="parent-1", authorized_children=DECLARES, **extra,
    )


def _items(nombre=3):
    """Des items corrigeables sur le même objectif."""
    return [
        QuizItem(unit_id="u-10", content_hash="h", objective=OBJECTIF,
                 prompt=f"Question {index}", answer_key="oui")
        for index in range(nombre)
    ]


# ----------------------------------------------------------------------
# 1. Le même fait officiel
# ----------------------------------------------------------------------

def test_le_parent_recoit_le_meme_enregistrement_que_l_eleve(registre):
    """Une version « simplifiée pour les parents » serait un second curriculum."""
    parent = _vue_parent(registre)
    eleve = student_answer(_question(), registre)

    assert parent["canonical"] == eleve["canonical"]


def test_la_coherence_entre_les_quatre_demandeurs_est_mesuree(registre):
    """La directive VI, vérifiée par le VOLET 7 et non par une promesse."""
    questions = [
        CurriculumQuery(text=texte, academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=10, asked_by_role=role)
        for role, texte in (
            ("student", "Qu'est-ce que je dois étudier ?"),
            ("parent", "Quel est le programme de mon enfant ?"),
            ("teacher", "Quel est le contenu officiel ?"),
            ("school_admin", "Contenu officiel du programme."),
        )
    ]

    assert check_group(questions, registre)["verdict"] == COHERENT


def test_l_explication_est_a_cote_du_fait_pas_a_sa_place(registre):
    """Le parent doit voir ce qui vient du ministère et ce qui vient d'ici."""
    vue = _vue_parent(registre, generator=lambda contexte: "Une part d'un tout.")

    assert vue["canonical"]["official_title"] == "Les fractions"
    assert vue["explanation"] == "Une part d'un tout."


def test_sans_enregistrement_rien_n_est_invente(registre):
    """Inventer pour rassurer tromperait sur ce que fait l'enfant."""
    vue = child_curriculum(
        _question(week=11), registre, child_ref="enfant-7f3a",
        viewer_ref="parent-1", authorized_children=DECLARES,
        generator=lambda contexte: "Un programme.",
    )

    assert vue["canonical"] is None
    assert "rassurer un parent" in vue["note"]


# ----------------------------------------------------------------------
# 2. Le lien est déclaré, jamais déduit
# ----------------------------------------------------------------------

def test_sans_declaration_rien_n_est_montre(registre):
    """C'est l'état attendu tant qu'aucune source d'inscription n'existe."""
    with pytest.raises(AccessRefused) as refus:
        child_curriculum(_question(), registre, child_ref="enfant-7f3a",
                         viewer_ref="parent-1", authorized_children=None)

    assert "Aucun lien déclaré" in str(refus.value)


def test_une_declaration_vide_n_accorde_rien(registre):
    """Vide refuse, au lieu de laisser passer."""
    with pytest.raises(AccessRefused):
        child_curriculum(_question(), registre, child_ref="enfant-7f3a",
                         viewer_ref="parent-1", authorized_children=[])


def test_un_enfant_hors_declaration_est_refuse(registre):
    """Deviner remettrait un enfant à la mauvaise famille."""
    with pytest.raises(AccessRefused) as refus:
        child_curriculum(_question(), registre, child_ref="enfant-autre",
                         viewer_ref="parent-1", authorized_children=DECLARES)

    assert "jamais déduit" in str(refus.value)


def test_les_progres_passent_par_la_meme_verification():
    """Une seule porte vérifiée et une autre ouverte ne vaut rien."""
    resultats = [score_attempt(_items(), Attempt(answers={0: "oui"}))]

    with pytest.raises(AccessRefused):
        child_progress(resultats, child_ref="enfant-autre",
                       viewer_ref="parent-1", authorized_children=DECLARES)


def test_un_responsable_non_identifie_est_refuse():
    """Une référence absente ne montre rien."""
    with pytest.raises(AccessRefused):
        child_progress([], child_ref="enfant-7f3a", viewer_ref="",
                       authorized_children=DECLARES)


# ----------------------------------------------------------------------
# 3. Des mesures, pas un jugement
# ----------------------------------------------------------------------

def test_aucune_note_aucun_rang_aucune_comparaison():
    """Ce sont des décisions d'enseignant, et la plateforme n'en prend pas."""
    resultats = [score_attempt(_items(), Attempt(answers={0: "oui", 1: "oui",
                                                          2: "non"}))]

    progres = child_progress(resultats, child_ref="enfant-7f3a",
                             viewer_ref="parent-1", authorized_children=DECLARES)

    assert progres["grade"] is None
    assert progres["rank"] is None
    assert progres["comparison_with_other_children"] is None


def test_les_mesures_sont_agregees_objectif_par_objectif():
    """Un total global cacherait ce qui est mesuré et ce qui ne l'est pas."""
    resultats = [
        score_attempt(_items(2), Attempt(answers={0: "oui", 1: "non"})),
        score_attempt(_items(2), Attempt(answers={0: "oui", 1: "oui"})),
    ]

    progres = child_progress(resultats, child_ref="enfant-7f3a",
                             viewer_ref="parent-1", authorized_children=DECLARES)

    assert progres["by_objective"][OBJECTIF]["scored"] == 4
    assert progres["by_objective"][OBJECTIF]["correct"] == 3
    assert progres["attempts"] == 2


def test_le_verdict_est_recalcule_sur_le_cumul_pas_recopie():
    """
    Deux devoirs de deux items mesurent quatre items.

    Recopier le verdict d'un devoir dirait « pas assez » pour chacun pris seul,
    alors que le cumul dépasse le plancher. C'est le cas qu'un simple report
    manquerait.
    """
    resultats = [
        score_attempt(_items(2), Attempt(answers={0: "oui", 1: "oui"})),
        score_attempt(_items(2), Attempt(answers={0: "oui", 1: "oui"})),
    ]

    progres = child_progress(resultats, child_ref="enfant-7f3a",
                             viewer_ref="parent-1", authorized_children=DECLARES)

    assert progres["by_objective"][OBJECTIF]["verdict"] == PREUVE_SUFFISANTE


def test_une_mesure_insuffisante_n_est_pas_arrondie():
    """Elle se lit mal quand on s'inquiète : c'est pourquoi elle reste telle."""
    resultats = [score_attempt(_items(1), Attempt(answers={0: "non"}))]

    progres = child_progress(resultats, child_ref="enfant-7f3a",
                             viewer_ref="parent-1", authorized_children=DECLARES)

    assert progres["by_objective"][OBJECTIF]["scored"] == 1
    assert progres["by_objective"][OBJECTIF]["verdict"] == PREUVE_INSUFFISANTE
    assert "absence de mesure" in progres["by_objective"][OBJECTIF]["reason"]
    assert progres["appraisal"] is None


def test_une_reussite_totale_sur_un_item_ne_dit_pas_maitrise():
    """
    Le défaut que ce volet a trouvé.

    Sans verdict rendu, « 1 sur 1 » se lit comme une maîtrise là où il n'y a
    aucune mesure — et c'est un parent qui le lit.
    """
    resultats = [score_attempt(_items(1), Attempt(answers={0: "oui"}))]

    progres = child_progress(resultats, child_ref="enfant-7f3a",
                             viewer_ref="parent-1", authorized_children=DECLARES)

    mesure = progres["by_objective"][OBJECTIF]
    assert (mesure["scored"], mesure["correct"]) == (1, 1)
    assert mesure["verdict"] == PREUVE_INSUFFISANTE


# ----------------------------------------------------------------------
# 4. Ce que le mode parent ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_refuse_de_simplifier_le_programme():
    """Un ton plus aimable resterait un second curriculum."""
    interdits = " ".join(parent_report()["does_not"])

    assert "Simplifier le programme officiel" in interdits
    assert "Montrer un autre enfant" in interdits


def test_la_frontiere_refuse_de_deviner_un_lien_de_parente():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(access_report()["does_not"])

    assert "lien de parenté" in interdits
    assert "tout montrer" in interdits
