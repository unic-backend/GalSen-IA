"""
Dire ce qu'un élève a démontré, et refuser d'en dire plus
(VOLET 15 de Darra J).

La directive XXX demande une maîtrise par compétence, avec *preuve
insuffisante* comme état de premier rang. Cette seconde moitié est tout le
travail : un modèle de maîtrise produit toujours un niveau pour tout le monde,
parce qu'un niveau est ce qu'on lui a demandé, et « pas assez de données » finit
arrondi au niveau le plus bas. Un enfant ayant répondu deux fois apparaît alors
« faible » plutôt que « non mesuré », et l'étiquette le suit.

Ce que ces tests gardent :

1. **`NOT_MEASURED` et `INSUFFICIENT_EVIDENCE` sont hors échelle.**
2. **Sous le plancher, le ratio n'est pas rendu** — même à 100 %.
3. **Aucun total, aucune note, aucune comparaison.**
4. **Les seuils sont déclarés.**
5. **Un état dont les prérequis n'ont jamais été mesurés est qualifié**, pas
   abaissé.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.darra_j import (  # noqa: E402
    CurriculumUnit,
    CurriculumVersion,
    EducationSystem,
    Grade,
    Period,
    Subject,
    make_provenance,
)
from src.darra_j.assessment import (  # noqa: E402
    PREUVES_MINIMALES,
    Attempt,
    QuizItem,
    score_attempt,
)
from src.darra_j.graph import NOEUD_UNITE, build_graph  # noqa: E402
from src.darra_j.mastery import (  # noqa: E402
    ACQUIS,
    ECHELLE,
    EMERGENT,
    EN_COURS,
    ETATS_HORS_ECHELLE,
    NON_MESURE,
    PREUVE_INSUFFISANTE,
    SEUIL_ACQUIS,
    SEUIL_EN_COURS,
    MasteryRefused,
    level_for,
    mastery_by_objective,
    mastery_report,
    qualify_with_prerequisites,
)
from src.darra_j.registry import CurriculumRegistry  # noqa: E402

SYSTEME = EducationSystem(country="sn", system_id="sn-general")
OBJECTIF = "Comparer deux fractions"


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


def _items(nombre, objectif=OBJECTIF):
    """Des items corrigeables sur un objectif."""
    return [
        QuizItem(unit_id="u-10", content_hash="h", objective=objectif,
                 prompt=f"Question {index}", answer_key="oui")
        for index in range(nombre)
    ]


def _copie(nombre, justes, objectif=OBJECTIF):
    """Une correction : `justes` bonnes réponses sur `nombre` items."""
    reponses = {index: ("oui" if index < justes else "non")
                for index in range(nombre)}
    return score_attempt(_items(nombre, objectif), Attempt(answers=reponses))


# ----------------------------------------------------------------------
# 1. Les états hors échelle
# ----------------------------------------------------------------------

def test_rien_de_mesure_n_est_pas_un_niveau():
    """Zéro item corrigé décrit la mesure, pas l'élève."""
    etat = level_for(scored=0, correct=0)

    assert etat["state"] == NON_MESURE
    assert etat["on_scale"] is False
    assert etat["ratio"] is None


def test_sous_le_plancher_l_etat_est_hors_echelle():
    """Deux réponses ne placent personne sur une échelle."""
    etat = level_for(scored=2, correct=1)

    assert etat["state"] == PREUVE_INSUFFISANTE
    assert etat["on_scale"] is False


def test_sous_le_plancher_meme_un_sans_faute_ne_rend_pas_de_ratio():
    """
    Le cas qui rendrait la garantie décorative.

    Trois justes sur trois franchit le plancher ; deux sur deux ne le franchit
    pas, et rendre 1.0 inviterait à le lire comme un niveau.
    """
    etat = level_for(scored=2, correct=2)

    assert etat["state"] == PREUVE_INSUFFISANTE
    assert etat["ratio"] is None
    assert "lire comme un niveau" in etat["reason"]


def test_les_etats_hors_echelle_ne_sont_pas_dans_l_echelle():
    """Les mélanger permettrait de les comparer, donc de les ordonner."""
    assert not set(ETATS_HORS_ECHELLE) & set(ECHELLE)
    assert ECHELLE == (EMERGENT, EN_COURS, ACQUIS)


def test_un_decompte_impossible_est_refuse():
    """Plus de justes que d'items est une erreur d'appel, pas un exploit."""
    with pytest.raises(MasteryRefused) as refus:
        level_for(scored=3, correct=4)

    assert "erreur d'appel" in str(refus.value)


# ----------------------------------------------------------------------
# 2. L'échelle et ses seuils déclarés
# ----------------------------------------------------------------------

def test_le_plancher_franchi_place_sur_l_echelle():
    """Le cas nominal existe."""
    etat = level_for(scored=PREUVES_MINIMALES, correct=PREUVES_MINIMALES)

    assert etat["state"] == ACQUIS
    assert etat["on_scale"] is True
    assert etat["ratio"] == 1.0


@pytest.mark.parametrize("justes,attendu", [
    (10, ACQUIS), (8, ACQUIS), (7, EN_COURS), (5, EN_COURS), (4, EMERGENT),
    (0, EMERGENT),
])
def test_les_seuils_declares_decident(justes, attendu):
    """Les seuils sont dans le module, donc contestables."""
    assert level_for(scored=10, correct=justes)["state"] == attendu


def test_les_seuils_sont_publies():
    """Un seuil implicite est une politique que personne ne peut discuter."""
    rapport = mastery_report()

    assert rapport["thresholds"] == {"developing": SEUIL_EN_COURS,
                                     "secure": SEUIL_ACQUIS}
    assert rapport["minimum_items"] == PREUVES_MINIMALES


# ----------------------------------------------------------------------
# 3. Objectif par objectif, jamais un total
# ----------------------------------------------------------------------

def test_la_maitrise_est_rendue_objectif_par_objectif():
    """Un objectif bien mesuré ne compense pas un objectif à peine effleuré."""
    resultats = [_copie(3, 3), _copie(1, 1, objectif="Autre objectif")]

    maitrise = mastery_by_objective(resultats)

    assert maitrise["by_objective"][OBJECTIF]["state"] == ACQUIS
    assert maitrise["by_objective"]["Autre objectif"]["state"] == \
        PREUVE_INSUFFISANTE
    assert maitrise["on_scale"] == [OBJECTIF]
    assert maitrise["not_on_scale"] == ["Autre objectif"]


def test_les_mesures_sont_cumulees_avant_d_etre_jugees():
    """Deux devoirs de deux items mesurent quatre items."""
    maitrise = mastery_by_objective([_copie(2, 2), _copie(2, 2)])

    etat = maitrise["by_objective"][OBJECTIF]
    assert etat["scored"] == 4
    assert etat["state"] == ACQUIS


def test_aucun_total_aucune_note_aucun_rang():
    """Un nombre unique se lirait comme une note."""
    maitrise = mastery_by_objective([_copie(3, 2)])

    assert maitrise["overall"] is None
    assert maitrise["grade"] is None
    assert maitrise["rank"] is None
    assert "se lirait comme une note" in maitrise["note"]


def test_aucune_correction_ne_donne_aucun_objectif():
    """L'absence de mesure ne fabrique pas d'objectif à évaluer."""
    maitrise = mastery_by_objective([])

    assert maitrise["by_objective"] == {}
    assert maitrise["on_scale"] == []


# ----------------------------------------------------------------------
# 4. Les prérequis qualifient, ils n'abaissent pas
# ----------------------------------------------------------------------

def _graphe_avec_prerequis():
    """« Les fractions » exige « La division euclidienne »."""
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    ))
    for titre, semaine, prerequis in (
        ("La division euclidienne", 8, ()),
        ("Les fractions", 10, ("La division euclidienne",)),
    ):
        depot.add_unit(CurriculumUnit(
            version_id="v-2026", grade=Grade("g6", "Sixième"),
            subject=Subject("maths", "Mathématiques"),
            period=Period(academic_year="2026-2027", week=semaine),
            official_title=titre, prerequisites=prerequis,
            provenance=_officielle(),
        ))
    graphe = build_graph(depot, "v-2026")
    identifiants = {n["label"]: i for i, n in graphe.nodes.items()
                    if n["kind"] == NOEUD_UNITE}
    return graphe, identifiants


def test_un_prerequis_jamais_mesure_qualifie_l_etat():
    """
    `SECURE` sur les fractions alors que rien n'a été mesuré sur la division.

    C'est une affirmation fragile, et le dire est exactement ce que le graphe
    du VOLET 14 permet.
    """
    graphe, identifiants = _graphe_avec_prerequis()
    acquis = level_for(scored=5, correct=5)

    qualifie = qualify_with_prerequisites(
        acquis, identifiants["Les fractions"], graphe, measured_units=[],
    )

    assert qualifie["state"] == ACQUIS
    assert qualifie["qualified"] is True
    assert qualifie["unverified_prerequisites"] == [
        identifiants["La division euclidienne"]
    ]


def test_l_etat_n_est_pas_abaisse():
    """Inventer une pénalité serait aussi fabriqué qu'inventer le niveau."""
    graphe, identifiants = _graphe_avec_prerequis()
    acquis = level_for(scored=5, correct=5)

    qualifie = qualify_with_prerequisites(
        acquis, identifiants["Les fractions"], graphe, measured_units=[],
    )

    assert qualifie["state"] == acquis["state"]
    assert qualifie["ratio"] == acquis["ratio"]
    assert "pas abaissé" in qualifie["qualification"]


def test_un_prerequis_mesure_ne_qualifie_rien():
    """La qualification doit disparaître quand la raison disparaît."""
    graphe, identifiants = _graphe_avec_prerequis()

    qualifie = qualify_with_prerequisites(
        level_for(scored=5, correct=5), identifiants["Les fractions"], graphe,
        measured_units=[identifiants["La division euclidienne"]],
    )

    assert qualifie["qualified"] is False
    assert qualifie["qualification"] is None
    assert qualifie["unverified_prerequisites"] == []


def test_un_cycle_de_prerequis_est_rapporte_avec_l_etat():
    """Un état rendu sans dire que sa chaîne est cassée tromperait."""
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    ))
    for titre, semaine, prerequis in (("A", 1, ("B",)), ("B", 2, ("A",))):
        depot.add_unit(CurriculumUnit(
            version_id="v-2026", grade=Grade("g6", "Sixième"),
            subject=Subject("maths", "Mathématiques"),
            period=Period(academic_year="2026-2027", week=semaine),
            official_title=titre, prerequisites=prerequis,
            provenance=_officielle(),
        ))
    graphe = build_graph(depot, "v-2026")
    unite_a = [i for i, n in graphe.nodes.items() if n["label"] == "A"][0]

    qualifie = qualify_with_prerequisites(
        level_for(scored=5, correct=5), unite_a, graphe, measured_units=[],
    )

    assert qualifie["prerequisite_cycles"]


# ----------------------------------------------------------------------
# 5. Ce que le modèle ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_refuse_d_arrondir_une_absence_de_mesure():
    """La défaillance discrète de tout modèle de maîtrise."""
    interdits = " ".join(mastery_report()["does_not"])

    assert "Arrondir une absence de mesure" in interdits
    assert "Comparer un élève à un autre" in interdits


def test_le_rapport_refuse_de_predire():
    """Prédire une réussite fabriquerait un fait sur un enfant."""
    assert "Prédire ce qu'un élève réussira." in mastery_report()["does_not"]
