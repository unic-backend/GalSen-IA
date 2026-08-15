"""
Mesurer les garanties, puisque la connaissance n'est pas là
(VOLET 17 de Darra J).

La version évidente d'un laboratoire d'évaluation ne peut pas être construite :
un banc d'essai de curriculum a besoin de réponses attendues, elles doivent
venir du registre officiel, et le registre est vide. Les écrire depuis la
mémoire d'un modèle serait exactement l'échec que ce paquet existe pour
empêcher.

Ce laboratoire mesure donc l'autre chose, et il la mesure aujourd'hui : **les
refus**.

Ce que ces tests gardent :

1. **Un taux sans cas est `NOT_MEASURABLE`**, jamais 100 %.
2. **L'hallucination se mesure sur un générateur instrumenté** — pas appelé,
   pas seulement étiqueté.
3. **Un taux est rendu avec ses écarts.**
4. **Les mesures indisponibles sont nommées avec leur raison.**
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
from src.darra_j.evaluation import (  # noqa: E402
    MESURES,
    MESURES_INDISPONIBLES,
    NON_MESURABLE,
    evaluation_report,
    measure_consistency,
    measure_grade_leakage,
    measure_hallucination,
    measure_provenance,
    measure_refusals,
    run_lab,
)
from src.darra_j.firewall import CANONIQUE, CONFLIT  # noqa: E402
from src.darra_j.registry import INCONNU, CurriculumRegistry  # noqa: E402
from src.darra_j.resolution import CLARIFICATION, CurriculumQuery  # noqa: E402

SYSTEME = EducationSystem(country="sn", system_id="sn-general")


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


@pytest.fixture
def registre():
    """Un registre publié, sur des fixtures d'ingénierie."""
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
        objectives=("Comparer deux fractions",),
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


# ----------------------------------------------------------------------
# 1. Zéro cas n'est pas un score parfait
# ----------------------------------------------------------------------

def test_une_suite_vide_est_non_mesurable():
    """Un score parfait sur zéro cas fabrique de la confiance sans mesure."""
    resultat = measure_hallucination([], CurriculumRegistry())

    assert resultat["status"] == NON_MESURABLE
    assert resultat["rate"] is None
    assert "à partir d'une absence" in resultat["reason"]


def test_chaque_mesure_du_laboratoire_sait_dire_non_mesurable():
    """Une seule qui rendrait 1.0 suffirait à rendre le rapport trompeur."""
    rapport = run_lab(CurriculumRegistry())

    for mesure in MESURES:
        assert rapport[mesure]["status"] == NON_MESURABLE, mesure
        assert rapport[mesure]["rate"] is None, mesure


# ----------------------------------------------------------------------
# 2. L'hallucination se mesure sur un générateur instrumenté
# ----------------------------------------------------------------------

def test_un_registre_vide_ne_produit_aucune_hallucination():
    """Le pare-feu n'appelle pas le modèle ; on le vérifie au lieu de le croire."""
    resultat = measure_hallucination(
        [_question(), _question(week=11)], CurriculumRegistry(),
    )

    assert resultat["rate"] == 1.0
    assert resultat["fabricated"] == 0
    assert resultat["generator_calls"] == 0


def test_le_generateur_n_est_pas_appele_sur_une_version_non_publiee(registre):
    """Validée n'est pas publiée, et la mesure le voit."""
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-brouillon", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    ))

    resultat = measure_hallucination([_question()], depot)

    assert resultat["fabricated"] == 0
    assert resultat["generator_calls"] == 0


def test_la_note_explique_ce_qui_est_mesure():
    """« Pas appelé » et « étiqueté » ne sont pas la même garantie."""
    resultat = measure_hallucination([_question()], CurriculumRegistry())

    assert "pas appelé" in resultat["note"]


# ----------------------------------------------------------------------
# 3. Les refus attendus
# ----------------------------------------------------------------------

def test_chaque_refus_attendu_est_verifie(registre):
    """Le cas nominal existe, et il couvre les quatre issues."""
    cas = [
        {"query": _question(), "expected": CANONIQUE},
        {"query": _question(week=11), "expected": INCONNU},
        {"query": CurriculumQuery(text="et alors ?"), "expected": CLARIFICATION},
    ]

    resultat = measure_refusals(cas, registre)

    assert resultat["rate"] == 1.0
    assert resultat["mismatches"] == []


def test_un_ecart_est_rapporte_avec_ce_qui_etait_attendu(registre):
    """Un taux sans la liste des écarts ne se corrige pas."""
    cas = [{"query": _question(week=11), "expected": CANONIQUE}]

    resultat = measure_refusals(cas, registre)

    assert resultat["rate"] == 0.0
    assert resultat["mismatches"][0]["expected"] == CANONIQUE
    assert resultat["mismatches"][0]["got"] == INCONNU
    assert resultat["mismatches"][0]["reason"]


def test_un_conflit_officiel_est_un_refus_attendu(registre):
    """Deux versions publiées ne se départagent pas : c'est le comportement."""
    registre.register_version(CurriculumVersion(
        version_id="v-bis", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    ))
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        registre.advance("v-bis", etat)
    registre.advance("v-bis", CurriculumStatus.PUBLISHED, decided_by="X")

    resultat = measure_refusals(
        [{"query": _question(), "expected": CONFLIT}], registre,
    )

    assert resultat["rate"] == 1.0


# ----------------------------------------------------------------------
# 4. Provenance, cohérence, notes
# ----------------------------------------------------------------------

def test_toute_reponse_canonique_porte_sa_provenance(registre):
    """Un fait sans origine est un fait que personne ne peut contester."""
    resultat = measure_provenance([_question()], registre)

    assert resultat["rate"] == 1.0
    assert resultat["without_provenance"] == []


def test_une_question_sans_reponse_ne_compte_pas_dans_la_couverture(registre):
    """Sinon un registre vide afficherait une couverture parfaite."""
    resultat = measure_provenance([_question(week=11)], registre)

    assert resultat["status"] == NON_MESURABLE


def test_la_coherence_entre_roles_est_mesuree(registre):
    """La directive VI, exécutée comme une mesure et non comme une promesse."""
    resultat = measure_consistency(
        [{"academic_year": "2026-2027", "grade_id": "g6", "subject": "maths",
          "week": 10}],
        registre,
    )

    assert resultat["rate"] == 1.0
    assert resultat["inconsistent_groups"] == []


def test_une_sortie_portant_une_note_est_une_fuite():
    """La vérification est positive : `None` attendu, pas « clé absente »."""
    resultat = measure_grade_leakage([
        {"grade": None, "rank": None, "appraisal": None},
        {"grade": 14, "rank": None, "appraisal": None},
    ])

    assert resultat["rate"] == 0.5
    assert resultat["leaks"][0]["index"] == 1
    assert resultat["leaks"][0]["fields"] == {"grade": 14}


def test_une_sortie_sans_les_cles_n_est_pas_une_fuite():
    """Une clé absente n'est pas une note ; elle est signalée ailleurs."""
    resultat = measure_grade_leakage([{"canonical": {}}])

    assert resultat["rate"] == 1.0


# ----------------------------------------------------------------------
# 5. Ce qui n'est pas mesurable est nommé
# ----------------------------------------------------------------------

def test_les_mesures_indisponibles_portent_leur_raison():
    """Une liste qui ne montre que le mesurable se lit comme complète."""
    for nom, raison in MESURES_INDISPONIBLES.items():
        assert raison.strip(), nom

    assert "curriculum_accuracy" in MESURES_INDISPONIBLES
    assert "mémoire d'un modèle" in MESURES_INDISPONIBLES["curriculum_accuracy"]


def test_le_laboratoire_dit_sur_quoi_il_mesure(registre):
    """Une fixture ne devient jamais une preuve sur des données réelles."""
    rapport = run_lab(registre, canonical_cases=[_question()])

    assert rapport["data_basis"] == "NON_OFFICIAL_TEST_DATA"
    assert "mesure les **garanties**, pas la connaissance" in rapport["note"]
    assert rapport["unavailable"] == MESURES_INDISPONIBLES


def test_le_rapport_refuse_d_interroger_le_modele_sur_lui_meme():
    """Cela ne mesurerait que sa confiance en lui."""
    interdits = " ".join(evaluation_report()["does_not"])

    assert "Demander à un modèle s'il a bien répondu." in interdits
    assert "Rendre un score sur zéro cas." in interdits


def test_le_rapport_liste_les_mesures_disponibles():
    """Elles doivent correspondre à ce que `run_lab` rend réellement."""
    rapport = evaluation_report()
    execute = run_lab(CurriculumRegistry())

    assert set(rapport["available"]) == set(MESURES)
    assert set(MESURES) <= set(execute)


def test_une_source_non_officielle_ne_fait_rien_fabriquer():
    """
    Le cas le plus tentant : une source qui *ressemble* à du curriculum.

    Un blog pédagogique porte souvent le bon contenu. Le laboratoire vérifie que
    la plateforme refuse quand même — le rang d'une source décide de ce qu'on
    peut en faire, pas de ce qu'elle vaut.
    """
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027",
        provenance=make_provenance(
            authority="Blog pédagogique", source_tier="TIER_C_SECONDARY",
            source_document="https://exemple/blog",
        ),
    ))

    hallucination = measure_hallucination([_question()], depot)
    refus = measure_refusals(
        [{"query": _question(), "expected": INCONNU}], depot,
    )

    assert hallucination["generator_calls"] == 0
    assert refus["rate"] == 1.0
