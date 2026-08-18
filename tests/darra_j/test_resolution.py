"""
Résoudre *quel* enregistrement est demandé, avant d'en regarder un seul
(VOLET 4 de Darra J).

« Semaine 10 » n'est pas un terme de recherche : c'est une coordonnée parmi
cinq. La même semaine porte un contenu différent en 2026 et en 2027, et une
récupération par ressemblance rendrait le programme de l'an dernier avec
assurance — le pire résultat possible pour un fait institutionnel.

Ce que ces tests gardent :

1. **Quatre issues, dont deux refus** : `FOUND`, `UNKNOWN`, `AMBIGUOUS`,
   `CLARIFICATION_REQUIRED`.
2. **Rien n'est deviné** : l'année, le niveau et la matière ne sortent jamais
   d'une phrase.
3. **Une coordonnée déclarée l'emporte** sur une coordonnée repérée.
4. **La formulation ne change pas le résultat** — la fondation de la cohérence
   entre usagers (VOLET 7).
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
from src.darra_j.registry import AMBIGU, INCONNU, TROUVE, CurriculumRegistry  # noqa: E402
from src.darra_j.resolution import (  # noqa: E402
    CLARIFICATION,
    CurriculumQuery,
    extract_dimensions,
    resolution_report,
    resolve,
)

SYSTEME = EducationSystem(country="sn", system_id="sn-general")
MATHS = Subject(subject_id="maths", official_name="Mathématiques",
                aliases=("math", "matematik"))


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


def _unite(version_id, semaine, titre="Titre officiel", matiere=MATHS, annee="2026-2027"):
    """Une unité de curriculum."""
    return CurriculumUnit(
        version_id=version_id, grade=Grade("g6", "Sixième"), subject=matiere,
        period=Period(academic_year=annee, week=semaine),
        official_title=titre, provenance=_officielle(),
    )


@pytest.fixture
def registre():
    """Un registre avec une version publiée et deux unités."""
    depot = CurriculumRegistry()
    version = CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    )
    depot.register_version(version)
    depot.add_unit(_unite("v-2026", 10, "Les fractions"))
    depot.add_unit(_unite("v-2026", 11, "Les décimaux"))
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        depot.advance("v-2026", etat)
    depot.publish("v-2026", decided_by="Direction des curricula")
    return depot


# ----------------------------------------------------------------------
# 1. Les coordonnées, et ce qui manque
# ----------------------------------------------------------------------

def test_une_question_sans_annee_ni_niveau_demande_une_precision(registre):
    """« Qu'est-ce qu'on étudie en semaine 10 ? » n'a pas de réponse seule."""
    resultat = resolve(CurriculumQuery(text="Qu'étudie-t-on en semaine 10 ?"), registre)

    assert resultat["status"] == CLARIFICATION
    assert set(resultat["missing"]) >= {"academic_year", "grade_id", "subject"}
    assert "ne porte pas le même contenu" in resultat["reason"]


def test_une_question_sans_periode_demande_une_precision(registre):
    """Sans période, la question porte sur l'année : c'en est une autre."""
    resultat = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6", subject="maths"),
        registre,
    )

    assert resultat["status"] == CLARIFICATION
    assert "period" in resultat["missing"]


def test_des_coordonnees_completes_trouvent_l_unite(registre):
    """Le cas nominal : une résolution par identité, pas par classement."""
    resultat = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=10),
        registre,
    )

    assert resultat["status"] == TROUVE
    assert resultat["unit"]["official_title"] == "Les fractions"
    assert "sans classement ni similarité" in resultat["reason"]


def test_la_reponse_porte_sa_provenance(registre):
    """Un fait sans origine n'est pas un fait institutionnel."""
    resultat = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=10),
        registre,
    )

    assert resultat["provenance"]["authority"] == "Ministère de l'Éducation nationale"
    assert resultat["provenance"]["is_official"] is True


# ----------------------------------------------------------------------
# 2. Rien n'est deviné
# ----------------------------------------------------------------------

def test_l_annee_scolaire_n_est_jamais_tiree_d_une_phrase():
    """La deviner produirait une réponse plausible et fausse."""
    dimensions = extract_dimensions(
        CurriculumQuery(text="le programme de 2026-2027 en semaine 10")
    )

    assert "academic_year" not in dimensions.values
    assert "academic_year" in dimensions.missing


def test_le_niveau_n_est_jamais_tire_d_une_phrase():
    """« Sixième » dans une phrase n'est pas une déclaration de niveau."""
    dimensions = extract_dimensions(CurriculumQuery(text="la sixième, semaine 10"))

    assert "grade_id" not in dimensions.values


def test_une_semaine_ecrite_en_toutes_lettres_est_reperee():
    """Les marqueurs reconnaissent des chiffres — et seulement eux."""
    dimensions = extract_dimensions(CurriculumQuery(text="le programme de semaine 10"))

    assert dimensions.values["week"] == 10
    assert dimensions.methods["week"] == "keywords"


def test_une_dimension_declaree_l_emporte_sur_une_dimension_reperee():
    """Les marqueurs ne comprennent rien, et le dire est la moitié de leur usage."""
    dimensions = extract_dimensions(
        CurriculumQuery(text="et la semaine 3 alors ?", week=10)
    )

    assert dimensions.values["week"] == 10
    assert dimensions.methods["week"] == "declared"


def test_sans_curriculum_officiel_la_reponse_est_inconnue():
    """L'état attendu aujourd'hui, et il ne se déguise pas."""
    resultat = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=10),
        CurriculumRegistry(),
    )

    assert resultat["status"] == INCONNU
    assert "vide tant qu'une autorité" in resultat["reason"]


def test_une_semaine_absente_du_curriculum_rend_inconnu(registre):
    """Combler avec ce qu'un modèle croit savoir serait remplacer un fait."""
    resultat = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=42),
        registre,
    )

    assert resultat["status"] == INCONNU
    assert "vraisemblance" in resultat["reason"]


# ----------------------------------------------------------------------
# 3. La matière : exacte, alias compris
# ----------------------------------------------------------------------

@pytest.mark.parametrize("nom", ["maths", "Mathématiques", "MATHEMATIQUES", "matematik"])
def test_un_alias_de_matiere_resout_la_meme_unite(registre, nom):
    """Un alias déclaré est un nom ; il n'est pas une approximation."""
    resultat = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject=nom, week=10),
        registre,
    )

    assert resultat["status"] == TROUVE
    assert resultat["unit"]["official_title"] == "Les fractions"


def test_une_matiere_voisine_par_le_nom_ne_correspond_pas(registre):
    """Aucun rapprochement approché : la leçon a déjà été payée une fois."""
    resultat = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="mathématiques appliquées", week=10),
        registre,
    )

    assert resultat["status"] == INCONNU


# ----------------------------------------------------------------------
# 4. La formulation ne change pas le résultat
# ----------------------------------------------------------------------

def test_quatre_formulations_donnent_la_meme_unite(registre):
    """
    La fondation de la garantie de cohérence entre usagers (directive VI).

    L'élève, le parent, l'enseignant et l'administration ne posent pas la même
    phrase ; ils désignent le même enregistrement.
    """
    formulations = [
        ("Qu'est-ce que j'étudie cette semaine ?", "student"),
        ("Quel est le programme de mathématiques de mon enfant ?", "parent"),
        ("Quel est le contenu officiel de la semaine 10 ?", "teacher"),
        ("Contenu officiel semaine 10 niveau sixième", "school_admin"),
    ]

    resultats = [
        resolve(
            CurriculumQuery(text=texte, academic_year="2026-2027", grade_id="g6",
                            subject="maths", week=10, asked_by_role=role),
            registre,
        )
        for texte, role in formulations
    ]

    identifiants = {resultat["unit_id"] for resultat in resultats}
    assert len(identifiants) == 1, identifiants
    assert all(resultat["status"] == TROUVE for resultat in resultats)


def test_le_role_n_entre_pas_dans_la_resolution(registre):
    """Il n'existe que pour la présentation en aval."""
    eleve = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6", subject="maths",
                        week=10, asked_by_role="student"),
        registre,
    )
    autorite = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6", subject="maths",
                        week=10, asked_by_role="education_authority"),
        registre,
    )

    assert eleve["unit"]["content_hash"] == autorite["unit"]["content_hash"]


# ----------------------------------------------------------------------
# 5. L'ambiguïté n'est pas tranchée
# ----------------------------------------------------------------------

def test_deux_versions_officielles_rendent_ambigu(registre):
    """La résolution hérite du refus de choisir du registre."""
    seconde = CurriculumVersion(
        version_id="v-2026-bis", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    )
    registre.register_version(seconde)
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        registre.advance("v-2026-bis", etat)
    registre.advance("v-2026-bis", CurriculumStatus.PUBLISHED, decided_by="X")

    resultat = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6",
                        subject="maths", week=10),
        registre,
    )

    assert resultat["status"] == AMBIGU
    assert len(resultat["candidates"]) == 2


def test_une_version_historique_explicite_est_resolue(registre):
    """Une question sur une année passée nomme sa version."""
    resultat = resolve(
        CurriculumQuery(academic_year="2026-2027", grade_id="g6", subject="maths",
                        week=11, version_id="v-2026"),
        registre,
    )

    assert resultat["status"] == TROUVE
    assert resultat["unit"]["official_title"] == "Les décimaux"


# ----------------------------------------------------------------------
# 6. Le rapport
# ----------------------------------------------------------------------

def test_le_rapport_nomme_les_quatre_issues():
    """Une issue qu'on ne peut pas lire n'est pas une issue."""
    rapport = resolution_report()

    assert set(rapport["outcomes"]) == {TROUVE, INCONNU, AMBIGU, CLARIFICATION}


def test_le_rapport_dit_qu_aucune_similarite_n_est_utilisee():
    """C'est la garantie centrale du volet."""
    regles = " ".join(resolution_report()["rules"])

    assert "Aucune similarité" in regles
    assert "jamais" in regles


def test_le_rapport_dit_ce_que_la_resolution_refuse():
    """Trois refus, et ils sont écrits."""
    interdits = " ".join(resolution_report()["does_not"])

    assert "Choisir entre plusieurs" in interdits
    assert "mémoire d'un modèle" in interdits
