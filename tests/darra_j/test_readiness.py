"""
Dire dans quel état on est vraiment, avec les mots de la directive
(VOLET 20 de Darra J).

La directive nomme elle-même la réponse à donner tant que le registre est vide :
**ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING**. Ce module refuse de
dire plus fort — non par prudence, par mesure.

Le défaut fermé ici est petit et très répandu : une vérification d'aptitude qui
prend un drapeau, ou qui rend « prêt » parce que ses contrôles passent et que
ses contrôles tournent sur des fixtures, produit un rapport vert pour un système
vide. Quelqu'un lit ce rapport et planifie un déploiement.

Ce que ces tests gardent :

1. **L'état est mesuré sur le registre**, jamais déclaré.
2. **Une fixture n'est pas une donnée officielle** — la marque existe pour ça.
3. **Aucun argument n'atteint « prêt à servir »** sans données publiées.
4. **Ce qui est prêt est dit plainement.**
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.darra_j import (  # noqa: E402
    CurriculumStatus,
    CurriculumVersion,
    EducationSystem,
    make_provenance,
)
from src.darra_j import fixture_provenance as provenance_de_fixture  # noqa: E402
from src.darra_j.evaluation import MESURES  # noqa: E402
from src.darra_j.readiness import (  # noqa: E402
    ARCHITECTURE_PRETE,
    CONDITIONS_DE_SERVICE,
    PRET_A_SERVIR,
    readiness,
    readiness_report,
)
from src.darra_j.registry import CurriculumRegistry  # noqa: E402

SYSTEME = EducationSystem(country="sn", system_id="sn-general")


def _publie(provenance):
    """Un registre avec une version publiée, portant cette provenance."""
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=provenance,
    ))
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        depot.advance("v-2026", etat)
    depot.publish("v-2026", decided_by="Direction des curricula")
    return depot


# ----------------------------------------------------------------------
# 1. L'état est mesuré
# ----------------------------------------------------------------------

def test_un_registre_vide_donne_l_etat_de_la_directive():
    """C'est l'état actuel du dépôt, et il est écrit tel quel."""
    etat = readiness()

    assert etat["state"] == ARCHITECTURE_PRETE
    assert etat["conditions_met"] is False
    assert etat["official_versions"] == 0


def test_une_version_officielle_publiee_change_l_etat():
    """L'état doit pouvoir changer, sinon ce n'est pas une mesure."""
    depot = _publie(make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    ))

    etat = readiness(depot)

    assert etat["state"] == PRET_A_SERVIR
    assert etat["conditions_met"] is True
    assert etat["blocked_by"] == []


def test_ce_qui_bloque_dit_qui_doit_le_fournir():
    """« GalSen IA n'est pas l'autorité » est une conséquence, pas un slogan."""
    bloque = " ".join(readiness()["blocked_by"])

    assert "n'appartient pas à cette plateforme" in bloque
    assert "n'est pas l'autorité" in bloque


# ----------------------------------------------------------------------
# 2. Une fixture n'est pas une donnée officielle
# ----------------------------------------------------------------------

def test_un_registre_de_fixtures_publiees_reste_sans_donnees_officielles():
    """
    Le défaut que ce volet ferme.

    Des contrôles qui tournent sur des fixtures et rendent « prêt » produisent
    un rapport vert pour un système vide. La marque `NON_OFFICIAL_TEST_DATA`
    existe pour que cette fonction puisse les distinguer — et elle le fait.
    """
    depot = _publie(provenance_de_fixture("readiness"))

    etat = readiness(depot)

    assert etat["state"] == ARCHITECTURE_PRETE
    assert etat["official_versions"] == 0


def test_aucun_argument_ne_declare_le_systeme_pret():
    """Un générateur disponible ne remplace pas un curriculum publié."""
    etat = readiness(CurriculumRegistry(), generator_available=True)

    assert etat["state"] == ARCHITECTURE_PRETE
    assert etat["capability_state"] in ("AVAILABLE", "DEGRADED")


def test_la_condition_de_sortie_est_declaree():
    """Une condition implicite ne se vérifie pas."""
    etat = readiness()

    assert etat["serving_conditions"] == list(CONDITIONS_DE_SERVICE)
    assert "TIER_A" in etat["serving_conditions"][0]
    assert "NON_OFFICIAL_TEST_DATA" in etat["serving_conditions"][0]


# ----------------------------------------------------------------------
# 3. Ce qui est prêt est dit plainement
# ----------------------------------------------------------------------

def test_ce_qui_fonctionne_est_enumere_sans_couvrir():
    """Une liste vague se lirait comme une excuse."""
    prets = readiness()["ready_now"]

    assert len(prets) >= 10
    joint = " ".join(prets)
    assert "aucune génération sans fait canonique" in joint.lower()
    assert "INSUFFICIENT_EVIDENCE" in joint


def test_le_mesurable_et_l_immesurable_sont_distingues():
    """Une liste qui ne montre que le mesurable se lit comme complète."""
    etat = readiness()

    assert set(etat["measurable_now"]) == set(MESURES)
    assert "curriculum_accuracy" in etat["not_measurable_yet"]


def test_les_capacites_sont_rapportees_avec_l_etat():
    """Un état global sans le détail ne se diagnostique pas."""
    etat = readiness()

    assert "curriculum_retrieval" in etat["capabilities"]
    assert etat["capabilities"]["curriculum_retrieval"]["state"] == "AVAILABLE"


# ----------------------------------------------------------------------
# 4. Ce que l'aptitude refuse de dire
# ----------------------------------------------------------------------

def test_le_rapport_refuse_de_declarer_une_integration():
    """La phrase interdite par la directive, refusée là où elle serait écrite."""
    interdits = " ".join(readiness_report()["does_not"])

    assert "Déclarer une intégration du curriculum sénégalais" in interdits
    assert "presque prêt" in interdits
    assert "Promettre une date" in interdits


def test_l_etat_de_la_directive_est_repris_mot_pour_mot():
    """Le reformuler serait la nuance qu'un lecteur pressé retient."""
    assert ARCHITECTURE_PRETE == \
        "ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING"


@pytest.mark.parametrize("etat", [ARCHITECTURE_PRETE, PRET_A_SERVIR])
def test_les_deux_seuls_etats_sont_declares(etat):
    """Un troisième état intermédiaire inviterait à s'y installer."""
    assert etat in readiness_report()["states"]
    assert len(readiness_report()["states"]) == 2
