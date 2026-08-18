"""
Remonter d'une phrase lue par un enfant jusqu'à la personne qui l'a décidée
(VOLET 19 de Darra J).

Un ministère entend quelque chose de précis par « auditabilité ». Pas « il y a
des journaux ». La question qu'une inspection pose réellement est : *cette
phrase a été montrée à un élève — qui l'a décidée ?* Une réponse qui s'arrête à
« la récupération a trouvé u-10 » n'y a pas répondu.

Ce que ces tests gardent :

1. **La chaîne finit sur une personne nommée.**
2. **Un maillon absent est nommé**, jamais tu.
3. **Un refus est audité comme une réponse.**
4. **Aucune référence d'apprenant en clair.**
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
from src.darra_j.auditability import (  # noqa: E402
    ABSENT,
    MAILLONS,
    PRESENT,
    auditability_report,
    curriculum_trail,
    explain_answer,
)
from src.darra_j.firewall import CANONIQUE  # noqa: E402
from src.darra_j.registry import CurriculumRegistry  # noqa: E402
from src.darra_j.resolution import CLARIFICATION, CurriculumQuery  # noqa: E402

SYSTEME = EducationSystem(country="sn", system_id="sn-general")
DECIDEUR = "Direction des curricula"


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


@pytest.fixture
def registre():
    """Un registre publié par un décideur nommé."""
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
    depot.publish("v-2026", decided_by=DECIDEUR)
    return depot


def _unite_id(depot):
    """L'identifiant de la seule unité du registre."""
    return depot.units_in_version("v-2026")[0].unit_id


def _question(**extra):
    """Une question complète sur la semaine 10."""
    champs = {"academic_year": "2026-2027", "grade_id": "g6",
              "subject": "maths", "week": 10}
    champs.update(extra)
    return CurriculumQuery(**champs)


# ----------------------------------------------------------------------
# 1. La chaîne finit sur une personne
# ----------------------------------------------------------------------

def test_la_piste_nomme_la_personne_qui_a_publie(registre):
    """
    « La récupération a trouvé u-10 » ne répond pas à « qui l'a décidé ».

    Le décideur est lu dans le journal du registre, dont les clés sont `action`,
    `vers` et `decided_by` — les deviner (`from`/`to`) aurait produit une
    recherche qui ne trouve jamais rien, donc une piste déclarant en silence
    qu'aucun décideur n'a été consigné.
    """
    piste = curriculum_trail(_unite_id(registre), registre)

    assert piste["links"]["decided_by"]["state"] == PRESENT
    assert piste["links"]["decided_by"]["value"] == DECIDEUR


def test_la_piste_complete_remonte_au_document_et_a_l_autorite(registre):
    """La chaîne demandée par la directive XXXVII, de bout en bout."""
    piste = curriculum_trail(_unite_id(registre), registre)

    assert piste["complete"] is True
    assert piste["missing"] == []
    assert piste["links"]["authority"]["value"] == \
        "Ministère de l'Éducation nationale"
    assert piste["links"]["source_document"]["value"] == "jo://curriculum/2026"
    assert piste["is_official"] is True


def test_la_piste_porte_l_empreinte_du_contenu(registre):
    """Sans elle, on ne saurait pas *quelle* version du texte a été montrée."""
    piste = curriculum_trail(_unite_id(registre), registre)

    assert piste["links"]["unit"]["content_hash"]
    assert piste["links"]["source_document"]["document_hash"] is not None


# ----------------------------------------------------------------------
# 2. Un maillon absent est nommé
# ----------------------------------------------------------------------

def test_une_unite_inconnue_ne_produit_aucune_chaine_plausible(registre):
    """Reconstruire ici fabriquerait une décision institutionnelle."""
    piste = curriculum_trail("u-inexistante", registre)

    assert piste["complete"] is False
    assert "fabriquer une décision" in piste["reason"]
    assert set(piste["missing"]) <= set(MAILLONS)


def test_une_version_jamais_publiee_nomme_le_maillon_manquant():
    """C'est exactement ce qu'un auditeur vient vérifier."""
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

    piste = curriculum_trail(_unite_id(depot), depot)

    assert "decided_by" in piste["missing"]
    assert "publication_decision" in piste["missing"]
    assert "vient vérifier" in piste["links"]["decided_by"]["value"]


def test_une_chaine_incomplete_le_dit(registre):
    """Une piste qui tairait ses trous se lirait comme complète."""
    piste = curriculum_trail("u-inexistante", registre)

    assert piste["complete"] is False
    assert piste["missing"]


# ----------------------------------------------------------------------
# 3. Un refus est audité comme une réponse
# ----------------------------------------------------------------------

def test_une_reponse_canonique_porte_sa_piste(registre):
    """Le cas nominal existe."""
    audit = explain_answer(_question(), registre)

    assert audit["answer_type"] == CANONIQUE
    assert audit["failed_checks"] == []
    assert audit["trail"]["complete"] is True


def test_un_refus_est_audite_avec_ses_verifications(registre):
    """Savoir pourquoi le système n'a rien dit vaut autant que l'inverse."""
    audit = explain_answer(CurriculumQuery(text="et alors ?"), registre)

    assert audit["answer_type"] == CLARIFICATION
    assert audit["trail"] is None
    assert audit["reason"]
    assert "n'a rien dit" in audit["note"]


def test_une_verification_non_franchie_est_nommee():
    """« Non vérifié » sans cause fait chercher partout."""
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    ))

    audit = explain_answer(_question(), depot)

    assert audit["failed_checks"]
    assert audit["trail"] is None


# ----------------------------------------------------------------------
# 4. Aucune référence d'apprenant en clair
# ----------------------------------------------------------------------

def test_une_piste_ne_nomme_aucun_enfant(registre):
    """Une piste qui nomme des enfants ne peut être remise à personne."""
    piste = curriculum_trail(
        _unite_id(registre), registre,
        viewer_ref="prof-diop", subject_ref="awa-diop-6e-b",
    )

    rendu = repr(piste)
    assert "awa-diop" not in rendu
    assert "prof-diop" not in rendu
    assert piste["subject"].startswith("learner:")


def test_une_piste_sans_apprenant_ne_fabrique_pas_d_empreinte(registre):
    """Une empreinte de rien laisserait croire qu'un élève est concerné."""
    piste = curriculum_trail(_unite_id(registre), registre)

    assert "subject" not in piste
    assert "viewer" not in piste


# ----------------------------------------------------------------------
# 5. Ce que l'auditabilité ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_refuse_de_supposer_un_decideur():
    """Supposer ici serait fabriquer une décision officielle."""
    interdits = " ".join(auditability_report()["does_not"])

    assert "Supposer un décideur" in interdits
    assert "chaîne plausible" in interdits
    assert "journal parallèle" in interdits


def test_le_rapport_liste_les_maillons_attendus():
    """Un auditeur doit savoir ce qu'il devrait trouver."""
    rapport = auditability_report()

    assert "decided_by" in rapport["links"]
    assert rapport["link_states"] == [PRESENT, ABSENT]
