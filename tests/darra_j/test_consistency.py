"""
Quatre personnes, quatre phrases, un seul fait officiel
(VOLET 7 de Darra J).

C'est l'exigence institutionnelle de la directive VI, et la seule qu'un système
éducatif ne peut pas négocier : un élève, un parent, un enseignant et une
administration qui posent la même question doivent obtenir le même fait. Si les
réponses divergent, ce n'est pas une réponse qui s'est trompée — c'est la notion
même de curriculum officiel qui cesse d'avoir un sens.

Ce que ces tests gardent :

1. **La cohérence est mesurée**, pas espérée : on compare l'identité canonique
   des réponses, jamais leur formulation.
2. **L'empreinte compte autant que l'identifiant** : deux réponses peuvent
   désigner la même case et porter deux textes.
3. **Un groupe à moitié résolu est incohérent** — `UNKNOWN` d'un côté et un
   enregistrement de l'autre n'est pas « partiellement correct ».
4. **Une divergence est rapportée, jamais réconciliée.**
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
from src.darra_j.consistency import (  # noqa: E402
    COHERENT,
    INCOHERENT,
    RIEN_A_COMPARER,
    canonical_identity,
    check_group,
    consistency_report,
    same_coordinates,
)
from src.darra_j.registry import INCONNU, TROUVE, CurriculumRegistry  # noqa: E402
from src.darra_j.resolution import CurriculumQuery, resolve  # noqa: E402

SYSTEME = EducationSystem(country="sn", system_id="sn-general")


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


def _publie(depot, version_id="v-2026"):
    """Fait franchir à une version tous les états jusqu'à `PUBLISHED`."""
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        depot.advance(version_id, etat)
    depot.publish(version_id, decided_by="Direction des curricula")


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
        subject=Subject("maths", "Mathématiques", aliases=("matematik",)),
        period=Period(academic_year="2026-2027", week=10),
        official_title="Les fractions",
        objectives=("Comparer deux fractions",),
        provenance=_officielle(),
    ))
    _publie(depot)
    return depot


# ----------------------------------------------------------------------
# 1. L'identité canonique
# ----------------------------------------------------------------------

def test_l_identite_porte_l_identifiant_et_l_empreinte(registre):
    """Un identifiant seul ne suffirait pas à prouver l'égalité du contenu."""
    resolution = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=10),
        registre,
    )

    identite = canonical_identity(resolution)

    assert resolution["status"] == TROUVE
    assert identite == f"{resolution['unit_id']}:{resolution['unit']['content_hash']}"


def test_une_question_non_resolue_n_a_pas_d_identite():
    """Rien à comparer n'est pas la même chose que comparer à rien."""
    resolution = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=10),
        CurriculumRegistry(),
    )

    assert resolution["status"] == INCONNU
    assert canonical_identity(resolution) is None


# ----------------------------------------------------------------------
# 2. Quatre rôles, un fait
# ----------------------------------------------------------------------

def test_quatre_roles_quatre_phrases_un_seul_fait(registre):
    """Le cas exact de la directive VI."""
    verdict = check_group(
        same_coordinates("2026-2027", "g6", "maths", week=10), registre,
    )

    assert verdict["verdict"] == COHERENT
    assert len(verdict["identities"]) == 1
    assert verdict["diverging"] == []


def test_les_formulations_different_bien(registre):
    """La présentation **doit** varier : c'est le fait qui ne le peut pas."""
    questions = same_coordinates("2026-2027", "g6", "maths", week=10)

    formulations = {question.text for question in questions}
    roles = [question.asked_by_role for question in questions]

    assert len(formulations) == len(questions)
    assert roles == ["student", "parent", "teacher", "school_admin"]


def test_le_role_n_entre_pas_dans_la_resolution(registre):
    """Un rôle qui changerait la réponse ferait deux curriculums."""
    eleve = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=10, asked_by_role="student"),
        registre,
    )
    autorite = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=10,
                        asked_by_role="education_authority"),
        registre,
    )

    assert eleve["unit"] == autorite["unit"]


def test_un_alias_de_matiere_designe_le_meme_enregistrement(registre):
    """« matematik » et « Mathématiques » ne sont pas deux programmes."""
    questions = same_coordinates("2026-2027", "g6", "maths", week=10)
    questions.append(CurriculumQuery(
        text="Programme ?", academic_year="2026-2027", grade_id="g6",
        subject="matematik", week=10, asked_by_role="teacher",
    ))

    assert check_group(questions, registre)["verdict"] == COHERENT


# ----------------------------------------------------------------------
# 3. Un groupe à moitié résolu est incohérent
# ----------------------------------------------------------------------

def test_un_groupe_a_moitie_resolu_est_incoherent(registre):
    """`UNKNOWN` d'un côté et un fait de l'autre n'est pas « à moitié bon »."""
    questions = same_coordinates("2026-2027", "g6", "maths", week=10)
    questions.append(CurriculumQuery(
        text="Et en semaine 11 ?", academic_year="2026-2027", grade_id="g6",
        subject="maths", week=11, asked_by_role="parent",
    ))

    verdict = check_group(questions, registre)

    assert verdict["verdict"] == INCOHERENT
    assert verdict["unresolved"] == ["parent"]


def test_un_registre_vide_est_coherent_dans_l_ignorance():
    """Tout le monde reçoit `UNKNOWN` : c'est l'état attendu aujourd'hui."""
    verdict = check_group(
        same_coordinates("2026-2027", "g6", "maths", week=10),
        CurriculumRegistry(),
    )

    assert verdict["verdict"] == COHERENT
    assert verdict["identities"] == []
    assert len(verdict["unresolved"]) == 4


def test_le_role_divergent_est_nomme(registre):
    """Savoir qu'un groupe diverge sans savoir qui ne sert à rien."""
    questions = same_coordinates("2026-2027", "g6", "maths",
                                 roles=["student", "parent", "teacher"], week=10)
    questions[1] = CurriculumQuery(
        text="Quel est le programme de mon enfant ?",
        academic_year="2026-2027", grade_id="g5", subject="maths", week=10,
        asked_by_role="parent",
    )

    verdict = check_group(questions, registre)

    assert verdict["verdict"] == INCOHERENT
    assert [e["role"] for e in verdict["diverging"]] == ["parent"]


def test_une_seule_question_n_est_pas_une_comparaison(registre):
    """Rendre `CONSISTENT` ici laisserait croire qu'on a vérifié quelque chose."""
    verdict = check_group(
        same_coordinates("2026-2027", "g6", "maths", roles=["student"], week=10),
        registre,
    )

    assert verdict["verdict"] == RIEN_A_COMPARER


# ----------------------------------------------------------------------
# 4. L'empreinte, pas seulement l'identifiant
# ----------------------------------------------------------------------

def test_deux_versions_du_meme_contenu_partagent_l_identite():
    """
    La même case, le même texte, deux registres : une seule identité.

    C'est ce qui permet de comparer deux instances sans comparer des objets.
    """
    def _construire():
        depot = CurriculumRegistry()
        depot.register_version(CurriculumVersion(
            version_id="v-2026", education_system=SYSTEME,
            academic_year="2026-2027", provenance=_officielle(),
        ))
        depot.add_unit(CurriculumUnit(
            version_id="v-2026", grade=Grade("g6", "Sixième"),
            subject=Subject("maths", "Mathématiques"),
            period=Period(academic_year="2026-2027", week=10),
            official_title="Les fractions", provenance=_officielle(),
        ))
        _publie(depot)
        return depot

    question = CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                               subject="maths", week=10)

    premier = canonical_identity(resolve(question, _construire()))
    second = canonical_identity(resolve(question, _construire()))

    assert premier == second is not None


def test_un_titre_reecrit_change_l_identite_pas_l_identifiant():
    """
    Le cas que l'identifiant seul manquerait.

    Deux enregistrements aux mêmes coordonnées portent le même `unit_id`. Si le
    titre officiel diffère, comparer les identifiants dirait « cohérent » alors
    que deux élèves lisent deux programmes.
    """
    def _construire(titre):
        depot = CurriculumRegistry()
        depot.register_version(CurriculumVersion(
            version_id="v-2026", education_system=SYSTEME,
            academic_year="2026-2027", provenance=_officielle(),
        ))
        depot.add_unit(CurriculumUnit(
            version_id="v-2026", grade=Grade("g6", "Sixième"),
            subject=Subject("maths", "Mathématiques"),
            period=Period(academic_year="2026-2027", week=10),
            official_title=titre, provenance=_officielle(),
        ))
        _publie(depot)
        return depot

    question = CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                               subject="maths", week=10)

    original = resolve(question, _construire("Les fractions"))
    reecrit = resolve(question, _construire("Les fractions simples"))

    assert original["unit_id"] == reecrit["unit_id"]
    assert canonical_identity(original) != canonical_identity(reecrit)


# ----------------------------------------------------------------------
# 5. Ce que le module ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_refuse_de_reconcilier():
    """Mettre les réponses d'accord cacherait ce qu'on cherche à voir."""
    interdits = " ".join(consistency_report()["does_not"])

    assert "réconciliée" in interdits
    assert "cacherait" in interdits


def test_le_rapport_nomme_ce_qui_est_compare():
    """Comparer des formulations serait une garantie vide."""
    rapport = consistency_report()

    assert rapport["compares"] == ["unit_id", "content_hash"]
    assert set(rapport["verdicts"]) == {COHERENT, INCOHERENT, RIEN_A_COMPARER}
