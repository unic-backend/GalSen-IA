"""
Préparer le matériel d'un enseignant sans jamais devenir l'enseignant
(VOLET 10 de Darra J).

La liste des interdits de la directive s'ouvre sur *se faire passer pour un
enseignant* et *se faire passer pour un ministère*. Dans une école, l'autorité
derrière une phrase est ce qui la rend applicable : les mêmes mots sur un élève
valent quelque chose venant d'un enseignant, et rien venant d'une machine.
Fabriquer de l'autorité est pire que fabriquer du contenu.

Ce que ces tests gardent :

1. **Rien de préparé n'a d'auteur** : `authored_by` vaut toujours `None`.
2. **S'attribuer une identité d'enseignant ou d'institution est refusé.**
3. **Une observation n'a pas de champ verdict** — il n'existe aucune forme dans
   laquelle elle pourrait dire « cet élève est absentéiste ».
4. **Une décision exige un décideur nommé**, comme la publication d'une version.
5. **Sans enregistrement officiel, rien n'est préparé.**
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
from src.darra_j import fixture_provenance as provenance_de_fixture  # noqa: E402
from src.darra_j.assessment import Attempt, QuizItem, score_attempt  # noqa: E402
from src.darra_j.registry import CurriculumRegistry  # noqa: E402
from src.darra_j.resolution import CurriculumQuery  # noqa: E402
from src.darra_j.teacher import (  # noqa: E402
    DECISIONS_RESERVEES,
    PREPARE_PAR,
    Observation,
    TeacherRefused,
    attribute_to,
    class_observations,
    is_platform_identity,
    prepare_lesson,
    record_decision,
    teacher_report,
)

SYSTEME = EducationSystem(country="sn", system_id="sn-general")


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


def _registre(provenance=None):
    """Un registre publié, avec une unité en semaine 10."""
    provenance = provenance or _officielle()
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=provenance,
    ))
    depot.add_unit(CurriculumUnit(
        version_id="v-2026", grade=Grade("g6", "Sixième"),
        subject=Subject("maths", "Mathématiques"),
        period=Period(academic_year="2026-2027", week=10),
        official_title="Les fractions",
        objectives=("Comparer deux fractions",),
        evaluation_requirements=("Un devoir surveillé d'une heure",),
        provenance=provenance,
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


# ----------------------------------------------------------------------
# 1. Rien de préparé n'a d'auteur
# ----------------------------------------------------------------------

def test_un_support_prepare_n_a_pas_d_auteur():
    """La plateforme prépare ; elle ne signe pas."""
    support = prepare_lesson(_question(), _registre(),
                             generator=lambda contexte: "Une part d'un tout.")

    assert support["prepared_by"] == PREPARE_PAR
    assert support["authored_by"] is None


def test_le_fait_officiel_est_repris_tel_quel():
    """Le support ne réécrit pas le programme, il le porte."""
    support = prepare_lesson(_question(), _registre(),
                             generator=lambda contexte: "Une part d'un tout.")

    assert support["canonical"]["official_title"] == "Les fractions"
    assert support["official_evaluation_requirements"] == [
        "Un devoir surveillé d'une heure"
    ]


def test_l_explication_est_separee_du_fait():
    """Un enseignant doit voir ce qui vient du ministère et ce qui vient d'ici."""
    support = prepare_lesson(_question(), _registre(),
                             generator=lambda contexte: "Une part d'un tout.")

    assert support["explanation"] == "Une part d'un tout."
    assert support["explanation_available"] is True
    assert support["canonical"]["official_title"] == "Les fractions"


def test_sans_generateur_le_fait_officiel_est_quand_meme_prepare():
    """Directive XXXV : le curriculum reste consultable sans le modèle."""
    support = prepare_lesson(_question(), _registre(), generator=None)

    assert support["canonical"]["official_title"] == "Les fractions"
    assert support["explanation"] is None
    assert support["explanation_available"] is False


# ----------------------------------------------------------------------
# 2. Sans enregistrement officiel, rien n'est préparé
# ----------------------------------------------------------------------

def test_sans_enregistrement_officiel_rien_n_est_prepare():
    """Un support de cours serait un programme inventé."""
    support = prepare_lesson(_question(), CurriculumRegistry(),
                             generator=lambda contexte: "Une leçon.")

    assert support["canonical"] is None
    assert support["authored_by"] is None
    assert "programme inventé" in support["note"]


def test_une_fixture_ne_fait_pas_preparer_un_cours():
    """Une donnée de test ne devient jamais un support officiel."""
    support = prepare_lesson(
        _question(), _registre(provenance=provenance_de_fixture("teacher")),
    )

    assert support["canonical"] is None
    assert support["reason"]


def test_le_refus_porte_les_verifications_du_pare_feu():
    """La cause est dans la réponse, pas dans un journal."""
    support = prepare_lesson(_question(), CurriculumRegistry())

    assert support["checks"]
    assert any(not verification["passed"] for verification in support["checks"])


# ----------------------------------------------------------------------
# 3. L'identité ne s'emprunte pas
# ----------------------------------------------------------------------

@pytest.mark.parametrize("identite", [
    "teacher", "Enseignant", "Ministère de l'Éducation nationale",
    "education_authority", "school_admin", "Inspecteur d'académie",
])
def test_une_identite_d_autorite_est_refusee(identite):
    """Fabriquer de l'autorité est pire que fabriquer du contenu."""
    with pytest.raises(TeacherRefused) as refus:
        attribute_to(identite)

    assert "fabriquerait de l'autorité" in str(refus.value)


def test_une_identite_neutre_n_est_pas_refusee():
    """La règle vise l'autorité empruntée, pas toute chaîne de caractères."""
    attribute_to("support généré")


def test_les_decisions_reservees_sont_nommees_dans_le_support():
    """Un enseignant doit savoir ce que la plateforme ne fera pas."""
    support = prepare_lesson(_question(), _registre())

    assert set(support["reserved_decisions"]) == set(DECISIONS_RESERVEES)
    assert "grading" in support["reserved_decisions"]


# ----------------------------------------------------------------------
# 4. Une observation n'a pas de verdict
# ----------------------------------------------------------------------

def test_une_observation_n_a_pas_de_champ_verdict():
    """
    C'est le mécanisme, pas l'étiquette.

    Il n'existe aucune forme dans laquelle cet objet pourrait porter « cet élève
    est absentéiste » : le champ n'existe pas, et la classe est figée.
    """
    champs = {champ.name for champ in dataclasses.fields(Observation)}

    assert champs == {"fact", "measured_from", "subject_ref"}
    assert not {"verdict", "conclusion", "judgement", "grade"} & champs


def test_une_observation_est_figee():
    """Y ajouter une conclusion après coup est refusé par la structure."""
    observation = Observation(fact="2 items sans réponse.", measured_from="quiz")

    with pytest.raises(dataclasses.FrozenInstanceError):
        observation.fact = "Élève absentéiste."


def test_les_observations_de_classe_ne_notent_ni_ne_classent():
    """Ni note, ni classement : ce sont des décisions."""
    items = [QuizItem(unit_id="u", content_hash="h", objective="o",
                      prompt=f"q{index}", answer_key="oui") for index in range(3)]
    resultats = [
        score_attempt(items, Attempt(answers={0: "oui", 1: "oui", 2: "non"})),
        score_attempt(items, Attempt(answers={0: "oui"})),
    ]

    rapport = class_observations(resultats)

    assert rapport["grade"] is None
    assert rapport["ranking"] is None
    assert rapport["authored_by"] is None
    assert rapport["attempts"] == 2


def test_les_observations_rapportent_ce_qui_a_ete_mesure():
    """Une observation dit d'où elle vient, sinon elle ne se conteste pas."""
    items = [QuizItem(unit_id="u", content_hash="h", objective="o",
                      prompt="q", answer_key="oui")]
    rapport = class_observations([score_attempt(items, Attempt(answers={0: "oui"}))])

    assert all(o["measured_from"] == "quiz" for o in rapport["observations"])
    assert all(o["is_decision"] is False for o in rapport["observations"])
    assert "1 réponses justes sur 1 items corrigés." in \
        [o["fact"] for o in rapport["observations"]]


def test_les_items_non_corrigeables_sont_observes_pas_ignores():
    """Les taire laisserait croire que tout a été mesuré."""
    items = [QuizItem(unit_id="u", content_hash="h", objective="o", prompt="q")]

    rapport = class_observations([score_attempt(items, Attempt(answers={0: "x"}))])

    faits = " ".join(o["fact"] for o in rapport["observations"])
    assert "sans clé de correction" in faits


# ----------------------------------------------------------------------
# 5. Une décision exige un décideur
# ----------------------------------------------------------------------

def test_une_decision_sans_decideur_est_refusee():
    """Sinon la plateforme aurait décidé à la place d'un enseignant."""
    with pytest.raises(TeacherRefused) as refus:
        record_decision("Redoublement", decided_by="   ")

    assert "à la place d'un enseignant" in str(refus.value)


def test_une_decision_vide_est_refusee():
    """Une décision doit dire ce qui est décidé."""
    with pytest.raises(TeacherRefused):
        record_decision("  ", decided_by="M. Diop")


@pytest.mark.parametrize("decideur", [
    "GalSen IA", "Darra J", "l'assistant", "Le système", "Claude",
    "Agent pédagogique",
])
def test_la_plateforme_ne_peut_pas_etre_son_propre_decideur(decideur):
    """
    Le trou est petit et il annule toute la règle.

    Sans cela, la plateforme prend la décision puis l'enregistre sous son propre
    nom : elle est passée de « ne décide pas » à « décide et le note ».
    """
    with pytest.raises(TeacherRefused) as refus:
        record_decision("Redoublement", decided_by=decideur)

    assert "blanchirait" in str(refus.value)


@pytest.mark.parametrize("decideur", [
    "Mariama Ba", "M. Diop", "Aïssatou Sy", "Direction des curricula",
    "Conseil de classe", "Mme Ndiaye, professeure de mathématiques",
])
def test_un_decideur_humain_n_est_pas_pris_pour_la_plateforme(decideur):
    """
    « ia » est contenu dans « Mariama ».

    Une comparaison par sous-chaîne refuserait une décision parce que la
    personne s'appelle Mariama — un défaut bien pire que celui qu'on ferme.
    """
    trace = record_decision("Rattrapage proposé", decided_by=decideur)

    assert trace["decided_by"] == decideur


def test_le_libelle_de_la_plateforme_est_reconnu_comme_tel():
    """
    L'invariant qui ferme la boucle.

    Si le libellé sous lequel la plateforme prépare n'était pas reconnu comme
    une identité de plateforme, elle pourrait se citer elle-même comme décideur
    en recopiant simplement son propre nom.
    """
    assert is_platform_identity(PREPARE_PAR) is True

    with pytest.raises(TeacherRefused):
        record_decision("Redoublement", decided_by=PREPARE_PAR)


def test_une_decision_est_enregistree_pas_prise():
    """La plateforme conserve la trace et son auteur."""
    trace = record_decision(
        "Rattrapage proposé", decided_by="M. Diop", about="eleve-7f3a",
        rationale="Deux objectifs non mesurés.",
    )

    assert trace["decided_by"] == "M. Diop"
    assert trace["is_platform_decision"] is False
    assert trace["recorded_by"] == PREPARE_PAR


# ----------------------------------------------------------------------
# 6. Ce que le mode enseignant ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_refuse_de_conclure_a_l_absenteisme():
    """L'exemple exact de la directive."""
    interdits = " ".join(teacher_report()["does_not"])

    assert "absentéisme" in interdits
    assert "Noter, classer ou apprécier un élève" in interdits


def test_le_rapport_refuse_de_signer_au_nom_d_une_institution():
    """La règle est écrite autant qu'appliquée."""
    rapport = teacher_report()

    assert rapport["authored_by"] is None
    assert "teacher" in rapport["refused_identities"]
    assert any("décideur nommé" in regle for regle in rapport["rules"])
