"""
Le curriculum comme enregistrement institutionnel (VOLET 2 de Darra J).

Une phrase décide de la forme de tout ce module : **GalSen IA ne définit pas le
curriculum.** Un ministère le fait. Ces tests gardent les quatre propriétés qui
rendent cette phrase vraie dans le code plutôt que dans une intention.

1. **Un objet canonique est gelé.** Une correction est une nouvelle version ;
   modifier en place effacerait la trace de ce que l'officiel disait avant.
2. **Rien n'existe sans provenance.** Autorité, rang, document : exigés à la
   construction, pas vérifiés plus tard.
3. **L'identité est déterministe.** Deux imports du même enregistrement donnent
   le même `unit_id` — c'est ce qui rendra la cohérence entre usagers
   vérifiable.
4. **Une fixture n'est jamais officielle**, quoi qu'elle déclare.

Et une propriété par omission, tout aussi importante : **aucun contenu de
curriculum sénégalais n'est écrit ici**. La structure existe ; le contenu vient
d'une autorité.
"""

import dataclasses
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.darra_j import (  # noqa: E402
    ETATS_CANONIQUES,
    MARQUE_TEST,
    CanonicalRefused,
    CurriculumStatus,
    CurriculumUnit,
    CurriculumVersion,
    EducationSystem,
    Grade,
    Period,
    Subject,
    canonical_report,
    make_provenance,
    may_transition,
)
# Importée sous un autre nom : une fixture pytest porte déjà ce nom-là.
from src.darra_j import fixture_provenance as provenance_de_fixture  # noqa: E402


@pytest.fixture
def systeme():
    """Un système éducatif de test."""
    return EducationSystem(
        country="sn", system_id="sn-general",
        official_name=f"{MARQUE_TEST} — système de test",
    )


@pytest.fixture
def fixture_provenance():
    """Une provenance de fixture, marquée comme telle."""
    return provenance_de_fixture("volet-2")


@pytest.fixture
def provenance_officielle():
    """Une provenance de rang officiel, telle qu'une autorité en produirait."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026/decret-x",
        document_title="Programme officiel",
        publication_date="2026-07-01",
    )


def _unite(provenance, titre="Titre officiel", semaine=10, **extra):
    """Une unité de curriculum de test."""
    return CurriculumUnit(
        version_id=extra.pop("version_id", "v-2026"),
        grade=Grade(grade_id="g6", official_name="Sixième"),
        subject=Subject(subject_id="maths", official_name="Mathématiques"),
        period=Period(academic_year="2026-2027", week=semaine),
        official_title=titre, provenance=provenance, **extra,
    )


# ----------------------------------------------------------------------
# 1. Gelé
# ----------------------------------------------------------------------

def test_une_unite_ne_se_modifie_pas(fixture_provenance):
    """Modifier en place effacerait ce que l'officiel disait avant."""
    unite = _unite(fixture_provenance)

    with pytest.raises(dataclasses.FrozenInstanceError):
        unite.official_title = "réécrit"


def test_une_version_ne_se_modifie_pas(systeme, fixture_provenance):
    """La même règle vaut pour la version elle-même."""
    version = CurriculumVersion(
        version_id="v-2026", education_system=systeme,
        academic_year="2026-2027", provenance=fixture_provenance,
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        version.status = CurriculumStatus.PUBLISHED


def test_une_version_publiee_ne_redevient_pas_brouillon():
    """Elle est remplacée, ce qui laisse les deux lisibles."""
    permise, motif = may_transition(
        CurriculumStatus.PUBLISHED, CurriculumStatus.PARSED,
    )

    assert permise is False
    assert "remplacée" in motif


def test_une_version_remplacee_reste_terminale():
    """Une question historique doit encore la trouver ; elle ne revient pas."""
    permise, motif = may_transition(
        CurriculumStatus.SUPERSEDED, CurriculumStatus.PUBLISHED,
    )

    assert permise is False
    assert "historiques" in motif


def test_le_chemin_normal_de_publication_est_permis():
    """Le cas nominal existe aussi, et il passe par une validation humaine."""
    chemin = [
        CurriculumStatus.INGESTED, CurriculumStatus.PARSED,
        CurriculumStatus.VALIDATION_REQUIRED, CurriculumStatus.VALIDATED,
        CurriculumStatus.PUBLISHED, CurriculumStatus.SUPERSEDED,
    ]

    for depuis, vers in zip(chemin, chemin[1:]):
        assert may_transition(depuis, vers)[0] is True, f"{depuis} → {vers}"


# ----------------------------------------------------------------------
# 2. Rien sans provenance
# ----------------------------------------------------------------------

@pytest.mark.parametrize("manquant", ["authority", "source_tier", "source_document"])
def test_une_provenance_incomplete_est_refusee(manquant):
    """« D'où vient ce fait ? » doit avoir une réponse à trois volets."""
    champs = {
        "authority": "Ministère", "source_tier": "TIER_A_PRIMARY_OFFICIAL",
        "source_document": "jo://x",
    }
    champs[manquant] = "   "

    with pytest.raises(CanonicalRefused) as refus:
        make_provenance(**champs)

    assert manquant in str(refus.value)


def test_une_unite_sans_titre_officiel_est_refusee(fixture_provenance):
    """Un fait qu'on ne peut pas citer n'est pas un fait institutionnel."""
    with pytest.raises(CanonicalRefused):
        _unite(fixture_provenance, titre="")


def test_une_unite_sans_annee_scolaire_est_refusee(fixture_provenance):
    """La semaine 10 de 2026 et celle de 2027 ne portent pas le même contenu."""
    with pytest.raises(CanonicalRefused):
        CurriculumUnit(
            version_id="v-2026", grade=Grade("g6", "Sixième"),
            subject=Subject("maths", "Mathématiques"),
            period=Period(academic_year=""), official_title="x",
            provenance=fixture_provenance,
        )


def test_la_provenance_survit_a_la_serialisation(provenance_officielle):
    """Un objet sérialisé sans sa provenance serait un fait sans origine."""
    unite = _unite(provenance_officielle)

    rendu = unite.as_dict()

    assert rendu["provenance"]["authority"] == "Ministère de l'Éducation nationale"
    assert rendu["provenance"]["source_document"] == "jo://curriculum/2026/decret-x"


# ----------------------------------------------------------------------
# 3. L'identité est déterministe
# ----------------------------------------------------------------------

def test_deux_imports_du_meme_enregistrement_ont_la_meme_identite(fixture_provenance):
    """C'est ce qui rendra la cohérence entre usagers vérifiable."""
    premier = _unite(fixture_provenance, titre="Un libellé")
    second = _unite(fixture_provenance, titre="Un autre libellé")

    assert premier.unit_id == second.unit_id


def test_une_dimension_differente_donne_une_identite_differente(fixture_provenance):
    """Semaine 10 et semaine 11 ne sont pas la même unité."""
    assert _unite(fixture_provenance, semaine=10).unit_id != \
        _unite(fixture_provenance, semaine=11).unit_id


def test_une_version_differente_donne_une_identite_differente(fixture_provenance):
    """Deux années officielles restent séparément adressables."""
    assert _unite(fixture_provenance, version_id="v-2026").unit_id != \
        _unite(fixture_provenance, version_id="v-2027").unit_id


def test_l_empreinte_de_contenu_distingue_ce_qui_est_ecrit(fixture_provenance):
    """L'identité dit de quoi on parle ; l'empreinte dit ce qui est écrit."""
    premier = _unite(fixture_provenance, titre="Un libellé")
    second = _unite(fixture_provenance, titre="Un autre libellé")

    assert premier.unit_id == second.unit_id
    assert premier.content_hash() != second.content_hash()


def test_l_empreinte_est_stable_entre_deux_constructions(fixture_provenance):
    """Une empreinte qui change sans que rien ne change ne prouve rien."""
    assert _unite(fixture_provenance).content_hash() == \
        _unite(fixture_provenance).content_hash()


# ----------------------------------------------------------------------
# 4. Une fixture n'est jamais officielle
# ----------------------------------------------------------------------

def test_une_version_de_fixture_n_est_pas_officielle(systeme, fixture_provenance):
    """Publiée ou non, une fixture ne porte pas de fait officiel."""
    version = CurriculumVersion(
        version_id="v-test", education_system=systeme,
        academic_year="2026-2027", provenance=fixture_provenance,
        status=CurriculumStatus.PUBLISHED,
    )

    assert version.is_official is False


def test_la_marque_de_test_survit_dans_l_autorite(fixture_provenance):
    """Elle survit à la sérialisation, à la copie et au stockage."""
    assert MARQUE_TEST in fixture_provenance.as_dict()["authority"]
    assert fixture_provenance.is_test_data is True


def test_une_version_officielle_publiee_l_est(systeme, provenance_officielle):
    """Le cas réel : rang officiel, état publié, aucune marque de test."""
    version = CurriculumVersion(
        version_id="v-2026", education_system=systeme,
        academic_year="2026-2027", provenance=provenance_officielle,
        status=CurriculumStatus.PUBLISHED,
    )

    assert version.is_official is True


def test_une_version_validee_n_est_pas_encore_officielle(systeme, provenance_officielle):
    """Validé veut dire « quelqu'un a relu » ; publié veut dire « en vigueur »."""
    version = CurriculumVersion(
        version_id="v-2026", education_system=systeme,
        academic_year="2026-2027", provenance=provenance_officielle,
        status=CurriculumStatus.VALIDATED,
    )

    assert version.is_official is False
    assert CurriculumStatus.VALIDATED not in ETATS_CANONIQUES


def test_un_rang_non_officiel_ne_devient_pas_officiel_en_etant_publie(systeme):
    """Publier une source secondaire ne la promeut pas."""
    secondaire = make_provenance(
        authority="Un éditeur scolaire", source_tier="TIER_C_SECONDARY",
        source_document="https://exemple.invalid/manuel",
    )
    version = CurriculumVersion(
        version_id="v-2026", education_system=systeme,
        academic_year="2026-2027", provenance=secondaire,
        status=CurriculumStatus.PUBLISHED,
    )

    assert version.is_official is False


# ----------------------------------------------------------------------
# 5. Ce que le module ne contient pas
# ----------------------------------------------------------------------

def test_aucun_niveau_scolaire_n_est_declare_dans_le_code():
    """
    Écrire `CI`, `CP`, `CE1`… serait décider à la place de l'autorité.

    La directive III le dit : *do not assume the final official structure if it
    has not been provided.*
    """
    from src.darra_j import canonical

    source = open(canonical.__file__, encoding="utf-8").read()
    # Les niveaux n'apparaissent que dans la prose expliquant qu'ils ne sont pas
    # déclarés ; aucune structure de données ne les contient.
    assert "GRADES = " not in source
    assert "NIVEAUX = " not in source


def test_le_rapport_dit_que_le_contenu_vient_d_une_autorite():
    """L'état honnête est écrit, pas seulement sous-entendu."""
    interdits = " ".join(canonical_report()["does_not"])

    assert "curriculum sénégalais" in interdits
    assert "le contenu vient d'une autorité" in interdits


def test_le_rapport_nomme_ses_regles():
    """Une garantie qu'on ne peut pas lire n'en est pas une."""
    regles = " ".join(canonical_report()["rules"])

    assert "gelé" in regles
    assert "provenance" in regles
    assert "dérivée" in regles


def test_rejouer_le_meme_import_donne_la_meme_empreinte(systeme):
    """
    Défaut trouvé en rejouant un import, pas en relisant le code.

    `ingested_at` disait quand **nous** avions reçu le document ; le mettre dans
    l'empreinte rendait deux imports du même décret officiellement différents,
    et le registre refusait alors un import identique.
    """
    premier = make_provenance(
        authority="Ministère", source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://x", ingested_at=1000.0,
    )
    second = make_provenance(
        authority="Ministère", source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://x", ingested_at=2000.0,
    )

    def _version(provenance):
        return CurriculumVersion(
            version_id="v", education_system=systeme,
            academic_year="2026-2027", provenance=provenance,
        )

    assert _version(premier).content_hash() == _version(second).content_hash()


def test_un_document_different_donne_une_empreinte_differente(systeme):
    """Ce qui vient du document, lui, compte."""
    def _version(document):
        return CurriculumVersion(
            version_id="v", education_system=systeme, academic_year="2026-2027",
            provenance=make_provenance(
                authority="Ministère", source_tier="TIER_A_PRIMARY_OFFICIAL",
                source_document=document,
            ),
        )

    assert _version("jo://a").content_hash() != _version("jo://b").content_hash()
