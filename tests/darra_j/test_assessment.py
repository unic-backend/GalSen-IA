"""
Interroger un élève sans inventer ni le programme, ni le résultat
(VOLET 9 de Darra J).

Deux fabrications se rencontrent ici, et les deux figurent dans la liste des
choses que Darra J ne doit jamais faire : **fabriquer du contenu de curriculum**
et **fabriquer des notes**. Une question générée ressemble à une question
officielle une fois imprimée ; un décompte ressemble à une note une fois dans un
bulletin.

Ce que ces tests gardent :

1. **Aucun quiz sans fait canonique** — le générateur n'est pas appelé.
2. **Chaque item est accroché à un objectif officiel** repris mot pour mot, et
   porte l'empreinte de l'enregistrement visé.
3. **Un décompte n'est pas une note** : `grade` vaut toujours `None`.
4. **Un item sans clé n'est pas compté faux** : il est nommé.
5. **`INSUFFICIENT_EVIDENCE` est un verdict**, pas un score bas.
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
from src.darra_j.assessment import (  # noqa: E402
    ITEM_GENERE,
    PREUVE_INSUFFISANTE,
    PREUVE_SUFFISANTE,
    PREUVES_MINIMALES,
    AssessmentRefused,
    Attempt,
    QuizItem,
    assessment_report,
    build_quiz,
    check_anchor,
    evidence_by_objective,
    score_attempt,
)
from src.darra_j.firewall import answer  # noqa: E402
from src.darra_j.registry import CurriculumRegistry  # noqa: E402
from src.darra_j.resolution import CurriculumQuery  # noqa: E402

SYSTEME = EducationSystem(country="sn", system_id="sn-general")
OBJECTIFS = (
    "Comparer deux fractions",
    "Additionner deux fractions de même dénominateur",
    "Placer une fraction sur une droite graduée",
)


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


@pytest.fixture
def registre():
    """Un registre publié, avec trois objectifs officiels en semaine 10."""
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    ))
    depot.add_unit(CurriculumUnit(
        version_id="v-2026", grade=Grade("g6", "Sixième"),
        subject=Subject("maths", "Mathématiques"),
        period=Period(academic_year="2026-2027", week=10),
        official_title="Les fractions",
        objectives=OBJECTIFS,
        evaluation_requirements=("Un devoir surveillé d'une heure",),
        provenance=_officielle(),
    ))
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        depot.advance("v-2026", etat)
    depot.publish("v-2026", decided_by="Direction des curricula")
    return depot


@pytest.fixture
def canonique(registre):
    """La réponse canonique du pare-feu."""
    return answer(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=10),
        registre,
    )


def _generateur(prefixe="Question sur : "):
    """Un générateur d'énoncés qui retient ce qu'il a reçu."""
    recus = []

    def generateur(contexte):
        recus.append(contexte)
        return prefixe + contexte["objective"]

    generateur.recus = recus
    return generateur


# ----------------------------------------------------------------------
# 1. Aucun quiz sans fait canonique
# ----------------------------------------------------------------------

def test_sans_fait_canonique_aucun_quiz_n_est_construit(registre):
    """Une question inventée est aussi enseignable qu'une leçon inventée."""
    absente = answer(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=11),
        registre,
    )

    with pytest.raises(AssessmentRefused) as refus:
        build_quiz(absente)

    assert "personne n'a publié" in str(refus.value)


def test_sans_fait_canonique_le_generateur_n_est_pas_appele(registre):
    """Pas « étiqueté » : pas appelé, comme au pare-feu."""
    generateur = _generateur()

    with pytest.raises(AssessmentRefused):
        build_quiz(answer(CurriculumQuery(text="et alors ?"), registre),
                   generator=generateur)

    assert generateur.recus == []


# ----------------------------------------------------------------------
# 2. Chaque item est accroché à un objectif officiel
# ----------------------------------------------------------------------

def test_un_item_par_objectif_officiel(canonique):
    """Il ne peut pas y avoir plus d'items que d'objectifs publiés."""
    quiz = build_quiz(canonique, generator=_generateur())

    assert len(quiz["items"]) == len(OBJECTIFS)
    assert [item["objective"] for item in quiz["items"]] == list(OBJECTIFS)


def test_l_objectif_est_repris_mot_pour_mot(canonique):
    """Le reformuler serait réécrire un champ officiel."""
    quiz = build_quiz(canonique, generator=_generateur())

    for item in quiz["items"]:
        assert item["objective"] in OBJECTIFS


def test_chaque_item_porte_l_empreinte_de_l_enregistrement(canonique):
    """Un quiz bâti sur un enregistrement réécrit doit pouvoir le dire."""
    quiz = build_quiz(canonique, generator=_generateur())

    empreinte = canonique["canonical"]["content_hash"]
    assert {item["content_hash"] for item in quiz["items"]} == {empreinte}


def test_le_generateur_recoit_une_copie_du_fait(canonique):
    """Modifier ce qu'il reçoit ne doit pas modifier le fait de l'appelant."""
    def saboteur(contexte):
        contexte["canonical"]["official_title"] = "Autre chose"
        return "Question."

    build_quiz(canonique, generator=saboteur)

    assert canonique["canonical"]["official_title"] == "Les fractions"


def test_les_exigences_officielles_sont_rendues_telles_quelles(canonique):
    """Elles viennent du ministère : ce ne sont pas des items générés."""
    quiz = build_quiz(canonique, generator=_generateur())

    assert quiz["official_evaluation_requirements"] == [
        "Un devoir surveillé d'une heure"
    ]
    assert {item["item_type"] for item in quiz["items"]} == {ITEM_GENERE}


def test_sans_generateur_le_quiz_est_vide_et_le_dit(canonique):
    """L'absence de génération ne produit pas d'items par défaut."""
    quiz = build_quiz(canonique, generator=None)

    assert quiz["items"] == []
    assert quiz["generation_available"] is False
    assert quiz["official_objectives"] == list(OBJECTIFS)


def test_un_enonce_qui_echoue_est_nomme_pas_comble(canonique):
    """Un objectif sans énoncé reste sans énoncé."""
    def casse(contexte):
        if "Additionner" in contexte["objective"]:
            raise RuntimeError("modèle indisponible")
        return "Question."

    quiz = build_quiz(canonique, generator=casse)

    assert len(quiz["items"]) == 2
    assert quiz["generation_failures"] == [
        {"objective": OBJECTIFS[1], "error": "RuntimeError"}
    ]


def test_un_enonce_vide_ne_devient_pas_un_item(canonique):
    """Une question vide interrogée en classe n'interroge rien."""
    quiz = build_quiz(canonique, generator=lambda contexte: "   ")

    assert quiz["items"] == []
    assert [e["error"] for e in quiz["generation_failures"]] == ["empty_prompt"] * 3


# ----------------------------------------------------------------------
# 3. L'ancrage se périme, et il le dit
# ----------------------------------------------------------------------

def test_un_item_accroche_a_l_enregistrement_en_vigueur_est_valide(canonique):
    """Le cas nominal existe."""
    quiz = build_quiz(canonique, generator=_generateur())

    verdict = check_anchor(quiz["objects"][0], canonique["canonical"])

    assert verdict["valid"] is True


def test_un_enregistrement_reecrit_perime_l_item(canonique):
    """Interroger dessus testerait un contenu que l'élève n'a plus."""
    quiz = build_quiz(canonique, generator=_generateur())
    reecrit = dict(canonique["canonical"], content_hash="autre-empreinte")

    verdict = check_anchor(quiz["objects"][0], reecrit)

    assert verdict["valid"] is False
    assert verdict["content_unchanged"] is False
    assert verdict["objective_still_official"] is True


def test_un_objectif_retire_du_programme_perime_l_item(canonique):
    """Un objectif supprimé n'est plus une question légitime."""
    quiz = build_quiz(canonique, generator=_generateur())
    ampute = dict(canonique["canonical"], objectives=list(OBJECTIFS[1:]))

    verdict = check_anchor(quiz["objects"][0], ampute)

    assert verdict["objective_still_official"] is False
    assert verdict["valid"] is False


# ----------------------------------------------------------------------
# 4. Un décompte n'est pas une note
# ----------------------------------------------------------------------

def _items_avec_cle():
    """Trois items corrigeables sur le même objectif."""
    return [
        QuizItem(unit_id="u-10", content_hash="h", objective=OBJECTIFS[0],
                 prompt=f"Question {index}", answer_key="oui")
        for index in range(3)
    ]


def test_aucune_note_n_est_produite():
    """Une note est une décision institutionnelle, pas un calcul."""
    resultat = score_attempt(
        _items_avec_cle(), Attempt(answers={0: "oui", 1: "oui", 2: "non"}),
    )

    assert resultat["grade"] is None
    assert resultat["is_official_grade"] is False
    assert "pas une note" in resultat["note"]


def test_le_decompte_suit_la_cle_de_correction():
    """Ce que la clé dit, rien de plus."""
    resultat = score_attempt(
        _items_avec_cle(), Attempt(answers={0: "oui", 1: "OUI ", 2: "non"}),
    )

    assert (resultat["scored_count"], resultat["correct_count"]) == (3, 2)


def test_un_item_sans_cle_est_nomme_pas_compte_faux():
    """Le compter faux inventerait un résultat sur cet élève."""
    items = _items_avec_cle() + [
        QuizItem(unit_id="u-10", content_hash="h", objective=OBJECTIFS[1],
                 prompt="Question ouverte"),
    ]

    resultat = score_attempt(items, Attempt(answers={0: "oui", 3: "une phrase"}))

    assert resultat["scored_count"] == 3
    assert [entree["index"] for entree in resultat["not_scored"]] == [3]
    assert "inventerait un résultat" in resultat["not_scored"][0]["reason"]


def test_une_absence_de_reponse_est_comptee_a_part():
    """Ne pas répondre et se tromper ne sont pas la même information."""
    resultat = score_attempt(_items_avec_cle(), Attempt(answers={0: "oui"}))

    assert resultat["unanswered_count"] == 2
    assert resultat["correct_count"] == 1


def test_un_quiz_sans_aucune_cle_n_est_pas_corrige():
    """`NOT_SCORED` est l'état, pas un zéro."""
    items = [QuizItem(unit_id="u-10", content_hash="h",
                      objective=OBJECTIFS[0], prompt="Question")]

    resultat = score_attempt(items, Attempt(answers={0: "réponse"}))

    assert resultat["status"] == "NOT_SCORED"
    assert resultat["correct_count"] == 0


# ----------------------------------------------------------------------
# 5. La preuve a un plancher
# ----------------------------------------------------------------------

def test_trois_items_suffisent_a_mesurer_un_objectif():
    """Le seuil est déclaré, donc contestable."""
    resultat = score_attempt(
        _items_avec_cle(), Attempt(answers={0: "oui", 1: "oui", 2: "oui"}),
    )

    preuve = evidence_by_objective(resultat)

    assert preuve["by_objective"][OBJECTIFS[0]]["verdict"] == PREUVE_SUFFISANTE
    assert preuve["objectives_measured"] == [OBJECTIFS[0]]
    assert preuve["minimum_items"] == PREUVES_MINIMALES


def test_une_seule_reponse_ne_mesure_rien():
    """`INSUFFICIENT_EVIDENCE` n'est pas une mauvaise note."""
    items = _items_avec_cle()[:1]

    preuve = evidence_by_objective(score_attempt(items, Attempt(answers={0: "non"})))

    entree = preuve["by_objective"][OBJECTIFS[0]]
    assert entree["verdict"] == PREUVE_INSUFFISANTE
    assert "absence de mesure" in entree["reason"]
    assert preuve["objectives_measured"] == []


def test_la_preuve_est_comptee_objectif_par_objectif():
    """Un objectif bien mesuré ne compense pas un objectif à peine effleuré."""
    items = _items_avec_cle() + [
        QuizItem(unit_id="u-10", content_hash="h", objective=OBJECTIFS[1],
                 prompt="Question", answer_key="oui"),
    ]

    preuve = evidence_by_objective(
        score_attempt(items, Attempt(answers={0: "oui", 1: "oui", 2: "oui",
                                              3: "oui"})),
    )

    assert preuve["by_objective"][OBJECTIFS[0]]["verdict"] == PREUVE_SUFFISANTE
    assert preuve["by_objective"][OBJECTIFS[1]]["verdict"] == PREUVE_INSUFFISANTE


# ----------------------------------------------------------------------
# 6. Ce que le module ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_refuse_la_note_et_le_rang():
    """Les deux fabrications interdites sont nommées."""
    interdits = " ".join(assessment_report()["does_not"])

    assert "note, un rang" in interdits
    assert "objectif absent du programme officiel" in interdits


def test_le_rapport_declare_le_plancher_de_preuve():
    """Un seuil implicite ne se conteste pas."""
    rapport = assessment_report()

    assert rapport["minimum_items_per_objective"] == PREUVES_MINIMALES
    assert PREUVE_INSUFFISANTE in rapport["evidence_verdicts"]
