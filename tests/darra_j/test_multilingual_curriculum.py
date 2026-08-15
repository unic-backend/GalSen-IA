"""
Poser la question en trois langues sans jamais traduire l'enregistrement
(VOLET 16 de Darra J).

La directive XXVII veut un curriculum atteignable en français, wolof et anglais.
La XXVIII ajoute ce qui rend la promesse honnête : la capacité wolof doit être
**mesurée**, pas affirmée.

Ce que ces tests gardent :

1. **La question voyage, l'enregistrement non** — les champs officiels restent
   dans leur langue de publication.
2. **Le terme déclaré passe avant tout alias.**
3. **Aucun équivalent n'est deviné** : un terme absent de la table n'ajoute rien.
4. **La réserve « wolof non relu » est portée jusqu'à la réponse.**
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
from src.darra_j.multilingual import (  # noqa: E402
    AUCUN_ALIAS,
    DIRECTE,
    LANGUES_EDUCATIVES,
    PAR_ALIAS,
    explanation_language,
    multilingual_report,
    official_language_of,
    resolve_multilingual,
    subject_candidates,
)
from src.darra_j.registry import TROUVE, CurriculumRegistry  # noqa: E402
from src.darra_j.resolution import CurriculumQuery  # noqa: E402

SYSTEME = EducationSystem(country="sn", system_id="sn-general", language="fr")


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


@pytest.fixture
def registre():
    """Une unité officielle en agriculture — un concept de la table d'alias."""
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    ))
    depot.add_unit(CurriculumUnit(
        version_id="v-2026", grade=Grade("g6", "Sixième"),
        subject=Subject("agriculture", "Agriculture"),
        period=Period(academic_year="2026-2027", week=10),
        official_title="Les cultures vivrières",
        objectives=("Nommer trois cultures de saison sèche",),
        provenance=_officielle(),
    ))
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        depot.advance("v-2026", etat)
    depot.publish("v-2026", decided_by="Direction des curricula")
    return depot


def _question(matiere, **extra):
    """Une question complète sur la semaine 10."""
    champs = {"academic_year": "2026-2027", "grade_id": "g6",
              "subject": matiere, "week": 10}
    champs.update(extra)
    return CurriculumQuery(**champs)


# ----------------------------------------------------------------------
# 1. Le terme déclaré passe en premier
# ----------------------------------------------------------------------

def test_le_terme_declare_resout_directement(registre):
    """Un alias ne doit jamais l'emporter sur ce qui est écrit explicitement."""
    reponse = resolve_multilingual(_question("agriculture"), registre)

    assert reponse["status"] == TROUVE
    assert reponse["matched_by"] == DIRECTE
    assert reponse["unreviewed_terms_used"] is False


def test_un_terme_anglais_atteint_l_enregistrement_francais(registre):
    """La question voyage : c'est elle qui est étendue, pas le programme."""
    reponse = resolve_multilingual(_question("farming"), registre)

    assert reponse["status"] == TROUVE
    assert reponse["matched_by"] == PAR_ALIAS
    assert reponse["matched_term"] == "agriculture"
    assert reponse["asked_term"] == "farming"


def test_un_terme_wolof_atteint_l_enregistrement_francais(registre):
    """« mbéy » désigne l'agriculture ; l'orthographe CLAD est préservée."""
    reponse = resolve_multilingual(_question("mbéy"), registre)

    assert reponse["status"] == TROUVE
    assert reponse["matched_by"] == PAR_ALIAS


# ----------------------------------------------------------------------
# 2. L'enregistrement n'est jamais traduit
# ----------------------------------------------------------------------

def test_les_champs_officiels_restent_dans_leur_langue(registre):
    """Les traduire produirait un enregistrement que personne n'a ratifié."""
    francais = resolve_multilingual(_question("agriculture"), registre)
    wolof = resolve_multilingual(_question("mbéy"), registre)

    assert francais["unit"]["official_title"] == "Les cultures vivrières"
    assert wolof["unit"]["official_title"] == "Les cultures vivrières"
    assert wolof["unit"]["objectives"] == francais["unit"]["objectives"]


def test_la_langue_officielle_vient_du_systeme_educatif(registre):
    """Jamais d'une supposition sur le pays."""
    langue = official_language_of(registre, "v-2026")

    assert langue == {"known": True, "language": "fr", "rule": langue["rule"]}
    assert "second enregistrement officiel" in langue["rule"]


def test_une_version_inconnue_ne_suppose_aucune_langue():
    """Supposer « fr » parce que c'est le Sénégal serait une supposition."""
    langue = official_language_of(CurriculumRegistry(), "v-absente")

    assert langue["known"] is False
    assert langue["language"] is None


def test_l_explication_change_de_langue_le_fait_non():
    """Traduire les deux ensemble effacerait ce que l'autorité a écrit."""
    verdict = explanation_language(requested="wo", official_language="fr")

    assert verdict["explanation_language"] == "wo"
    assert verdict["canonical_language"] == "fr"
    assert verdict["canonical_translated"] is False
    assert verdict["explanation_type"] == "AI_GENERATED"


# ----------------------------------------------------------------------
# 3. Rien n'est deviné
# ----------------------------------------------------------------------

def test_un_terme_absent_de_la_table_n_ajoute_aucun_candidat():
    """Deviner une traduction plausible est le seul moyen de se tromper ici."""
    expansion = subject_candidates("thermodynamique")

    assert expansion["candidates"] == ["thermodynamique"]
    assert expansion["expanded"] is False
    assert "aucune traduction devinée" in expansion["reason"]


def test_un_terme_inconnu_ne_resout_rien_et_le_dit(registre):
    """Le refus est le même que celui de la résolution, par une autre porte."""
    reponse = resolve_multilingual(_question("thermodynamique"), registre)

    assert reponse["status"] != TROUVE
    assert reponse["matched_by"] == AUCUN_ALIAS
    assert reponse["matched_term"] is None


def test_les_candidats_essayes_sont_rapportes(registre):
    """Un échec sans savoir ce qui a été essayé ne se diagnostique pas."""
    reponse = resolve_multilingual(_question("fishing"), registre)

    assert reponse["matched_by"] == AUCUN_ALIAS
    assert reponse["candidates_tried"], "les termes essayés doivent être rendus"


def test_aucun_rapprochement_par_ressemblance(registre):
    """« agricole » n'est pas « agriculture » tant que la table ne le dit pas."""
    expansion = subject_candidates("agricol")

    assert expansion["candidates"] == ["agricol"]


# ----------------------------------------------------------------------
# 4. La réserve wolof est portée jusqu'au bout
# ----------------------------------------------------------------------

def test_un_terme_wolof_non_relu_porte_sa_reserve(registre):
    """
    La garantie de la directive XXVIII.

    Les termes wolof sont déclarés par un locuteur nommé et non confrontés à un
    dictionnaire. La laisser tomber au dernier pas transformerait une capacité
    mesurée en capacité affirmée.
    """
    reponse = resolve_multilingual(_question("mbéy"), registre)

    assert reponse["unreviewed_terms_used"] is True
    assert "non confronté à un dictionnaire" in reponse["reserve"]


def test_un_terme_relu_ne_porte_pas_de_reserve(registre):
    """La réserve doit disparaître quand sa raison disparaît."""
    reponse = resolve_multilingual(_question("farming"), registre)

    assert reponse["unreviewed_terms_used"] is False
    assert reponse.get("reserve") is None


def test_l_expansion_signale_qu_elle_contient_du_non_relu():
    """Un appelant doit pouvoir le voir avant même de résoudre."""
    expansion = subject_candidates("agriculture")

    assert expansion["includes_unreviewed"] is True
    assert "mbéy" in expansion["candidates"]


# ----------------------------------------------------------------------
# 5. Ce que la couche ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_mesure_la_table_au_lieu_de_l_affirmer():
    """La couverture est un décompte, pas une promesse."""
    rapport = multilingual_report()

    assert rapport["languages"] == list(LANGUES_EDUCATIVES)
    assert rapport["alias_table"]["concepts"] > 0
    assert rapport["wolof_reviewed"] is False


def test_le_rapport_refuse_de_traduire_un_champ_officiel():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(multilingual_report()["does_not"])

    assert "Traduire un titre" in interdits
    assert "Deviner un équivalent" in interdits
    assert "couverture wolof que la table ne porte pas" in interdits
