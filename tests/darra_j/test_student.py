"""
Répondre à un élève sans le noter, et sans lui donner la clé
(VOLET 11 de Darra J).

Un élève est le lecteur pour qui tout ce paquet a été construit, et celui qui a
le plus à perdre d'une réponse fausse : il n'a aucun moyen de la vérifier.

Ce que ces tests gardent :

1. **La vue élève d'un quiz est construite, pas expurgée** — un champ ajouté
   plus tard à `QuizItem` ne fuit pas par défaut.
2. **Aucune note, aucun rang, aucune appréciation.**
3. **Un objectif trop peu mesuré est dit tel quel** — ce n'est pas un échec.
4. **Un élève ne voit jamais le travail d'un autre**, et une référence absente
   ne montre rien.
5. **Sans enregistrement officiel, aucun substitut.**
"""

import dataclasses
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
from src.darra_j.access import AccessRefused  # noqa: E402
from src.darra_j.assessment import Attempt, QuizItem, score_attempt  # noqa: E402
from src.darra_j.registry import CurriculumRegistry  # noqa: E402
from src.darra_j.resolution import CurriculumQuery  # noqa: E402
from src.darra_j.student import (  # noqa: E402
    CHAMPS_VISIBLES_ELEVE,
    own_results,
    student_answer,
    student_quiz,
    student_report,
    study_plan,
)

SYSTEME = EducationSystem(country="sn", system_id="sn-general")
OBJECTIF = "Comparer deux fractions"


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


def _items(nombre=3, avec_cle=True):
    """Des items de quiz, corrigeables ou non."""
    return [
        QuizItem(unit_id="u-10", content_hash="h", objective=OBJECTIF,
                 prompt=f"Question {index}",
                 answer_key="oui" if avec_cle else None)
        for index in range(nombre)
    ]


# ----------------------------------------------------------------------
# 1. La vue élève ne porte pas la clé
# ----------------------------------------------------------------------

def test_la_vue_eleve_ne_porte_aucune_cle():
    """La garantie la plus simple, et celle qu'on doit pouvoir montrer."""
    vue = student_quiz(_items())

    rendu = repr(vue)
    assert "answer_key" not in rendu
    assert "oui" not in rendu


def test_la_vue_eleve_est_construite_pas_expurgee():
    """
    Le mécanisme, pas l'intention.

    Les champs visibles forment une liste **positive** : la vue ne contient que
    ceux-là, donc un champ ajouté plus tard à `QuizItem` ne passe pas tout seul.
    """
    vue = student_quiz(_items())

    for item in vue["items"]:
        assert set(item) == set(CHAMPS_VISIBLES_ELEVE)


def test_un_champ_ajoute_a_l_item_ne_fuit_pas():
    """
    Le test qui prouve que « construite » vaut mieux que « expurgée ».

    On compare les champs de `QuizItem` à ceux de la vue : tout champ non
    déclaré visible est absent, y compris ceux qui n'existaient pas quand la
    vue a été écrite.
    """
    champs_item = {champ.name for champ in dataclasses.fields(QuizItem)}
    visibles = set(CHAMPS_VISIBLES_ELEVE)

    caches = champs_item - visibles
    vue = student_quiz(_items())

    assert "answer_key" in caches
    for item in vue["items"]:
        assert not caches & set(item)


def test_l_enonce_et_l_objectif_restent_visibles():
    """Un quiz sans énoncé ne sert à rien : la vue n'est pas vide.

    Sans cela, « aucune fuite » serait garanti par une vue qui ne montre rien.
    """
    vue = student_quiz(_items(2))

    assert vue["count"] == 2
    assert vue["items"][0]["prompt"] == "Question 0"
    assert vue["items"][0]["objective"] == OBJECTIF
    assert vue["items"][0]["index"] == 0


# ----------------------------------------------------------------------
# 2. Une réponse, jamais une note
# ----------------------------------------------------------------------

def test_l_eleve_recoit_le_fait_officiel_et_son_explication(registre):
    """Le fait tel quel, l'explication à côté."""
    reponse = student_answer(_question(), registre,
                             generator=lambda contexte: "Une part d'un tout.")

    assert reponse["canonical"]["official_title"] == "Les fractions"
    assert reponse["explanation"] == "Une part d'un tout."
    assert reponse["grade"] is None


def test_le_niveau_par_defaut_est_celui_de_la_classe(registre):
    """Parler plus bas à un élève supposerait quelque chose de non mesuré."""
    reponse = student_answer(_question(), registre,
                             generator=lambda contexte: "Texte.")

    assert (reponse["level"], reponse["level_name"]) == (2, "classroom")


def test_sans_enregistrement_aucun_substitut(registre):
    """Un élève n'a pas les moyens de vérifier une réponse fausse."""
    reponse = student_answer(_question(week=11), registre,
                             generator=lambda contexte: "Une leçon.")

    assert reponse["canonical"] is None
    assert reponse["explanation"] is None
    assert "vérifier une réponse fausse" in reponse["note"]


def test_sans_modele_le_fait_officiel_sort_quand_meme(registre):
    """Directive XXXV : le curriculum survit à l'absence de génération."""
    reponse = student_answer(_question(), registre, generator=None)

    assert reponse["canonical"]["official_title"] == "Les fractions"
    assert reponse["explanation_available"] is False


# ----------------------------------------------------------------------
# 3. Ses mesures, pas un jugement
# ----------------------------------------------------------------------

def test_l_eleve_voit_ses_mesures_sans_note():
    """Ni note, ni rang, ni appréciation."""
    resultat = score_attempt(_items(), Attempt(answers={0: "oui", 1: "oui",
                                                        2: "non"}))

    vue = own_results(resultat, subject_ref="eleve-1", viewer_ref="eleve-1")

    assert (vue["scored_count"], vue["correct_count"]) == (3, 2)
    assert vue["grade"] is None and vue["rank"] is None
    assert vue["appraisal"] is None


def test_un_objectif_trop_peu_mesure_est_dit_tel_quel():
    """`INSUFFICIENT_EVIDENCE` n'est pas un échec."""
    resultat = score_attempt(_items(1), Attempt(answers={0: "non"}))

    vue = own_results(resultat, subject_ref="eleve-1", viewer_ref="eleve-1")

    assert vue["objectives_measured"] == []
    assert vue["objectives_not_measured"] == [OBJECTIF]
    assert "n'est pas un échec" in vue["note"]


def test_les_items_non_corrigeables_sont_comptes_a_part():
    """Les taire laisserait croire que tout a été mesuré."""
    resultat = score_attempt(_items(avec_cle=False), Attempt(answers={0: "x"}))

    vue = own_results(resultat, subject_ref="eleve-1", viewer_ref="eleve-1")

    assert vue["not_scored_count"] == 3
    assert vue["scored_count"] == 0


# ----------------------------------------------------------------------
# 4. Jamais le travail d'un autre
# ----------------------------------------------------------------------

def test_un_eleve_ne_voit_pas_le_travail_d_un_autre():
    """La frontière la plus simple, et celle qui tombe par omission."""
    resultat = score_attempt(_items(), Attempt(answers={0: "oui"}))

    with pytest.raises(AccessRefused) as refus:
        own_results(resultat, subject_ref="eleve-1", viewer_ref="eleve-2")

    assert "un autre élève" in str(refus.value)


def test_une_reference_absente_ne_montre_rien():
    """C'est par l'omission que ces frontières tombent, pas par l'attaque."""
    resultat = score_attempt(_items(), Attempt(answers={0: "oui"}))

    with pytest.raises(AccessRefused):
        own_results(resultat, subject_ref="eleve-1", viewer_ref="")
    with pytest.raises(AccessRefused):
        own_results(resultat, subject_ref="", viewer_ref="")


def test_un_plan_de_reprise_passe_par_la_meme_verification():
    """Une seule porte vérifiée et une autre ouverte ne vaut rien."""
    unites = [{"unit_id": "u-10", "official_title": "Les fractions",
               "period": {"week": 10}, "prerequisites": []}]

    with pytest.raises(AccessRefused):
        study_plan(unites, subject_ref="eleve-1", viewer_ref="eleve-2")

    plan = study_plan(unites, subject_ref="eleve-1", viewer_ref="eleve-1")
    assert plan["content_type"] == "AI_GENERATED"
    assert plan["hours_estimate"] is None


# ----------------------------------------------------------------------
# 5. Ce que le mode élève ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_refuse_la_cle_et_la_note():
    """Les deux choses qu'un élève ne doit jamais recevoir."""
    interdits = " ".join(student_report()["does_not"])

    assert "clé de correction" in interdits
    assert "travail d'un autre élève" in interdits
    assert "note, un classement" in interdits


def test_le_rapport_declare_les_champs_visibles():
    """Une liste positive doit être lisible pour être contestable."""
    assert student_report()["visible_quiz_fields"] == list(CHAMPS_VISIBLES_ELEVE)
