"""
Quasi-doublons et les dix contrôles de qualité (ADR-021, étape 8).

Chaque contrôle est testé **dans les deux sens** : ce qu'il arrête, et ce qu'il
laisse passer. Un contrôle qui n'arrête rien ne mesure rien ; un contrôle qui
arrête tout ne protège personne, et c'est le défaut le plus facile à ne pas voir
parce qu'il ressemble à de la prudence.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.acquisition.dedup import (  # noqa: E402
    compare,
    dedup_report,
    find_duplicates,
    normalize,
    similarity,
)
from src.acquisition.quality import (  # noqa: E402
    OK,
    QUARANTAINE,
    REFUS,
    check_authority,
    check_date,
    check_duplicate,
    check_licence,
    check_relevance,
    evaluate,
    quality_report,
)
from src.acquisition.record import AcquiredDocument, AcquisitionStatus  # noqa: E402

TEXTE = (
    "La production de mil dans la région de Kaolack a progressé pendant la campagne "
    "agricole. Les services de l'agriculture ont relevé une hausse des surfaces "
    "emblavées et une amélioration des rendements observés sur les parcelles suivies "
    "par les équipes techniques du ministère. " * 3
)

PRESQUE = TEXTE.replace("a progressé", "a nettement progressé")

AUTRE = (
    "Le trafic aérien à l'aéroport international a été perturbé par des conditions "
    "météorologiques défavorables pendant la période considérée par les services "
    "de l'aviation civile qui publient ce bulletin mensuel. " * 3
)


def _parsed(**champs) -> AcquiredDocument:
    """Un document complet, au statut `PARSED` — celui qui doit passer."""
    valeurs = {
        "institution": "ANSD",
        "source_tier": "TIER_A_PRIMARY_OFFICIAL",
        "retrieval_date": "2026-08-13T10:00:00+00:00",
        "content_hash": "a" * 64,
        "license_or_usage_status": "reference_only",
        "publication_date": "2024-03-15",
        "language": "fr",
        "language_declared": "fr",
    }
    valeurs.update(champs)
    document = AcquiredDocument(source_url="https://www.ansd.sn/mil-2024.pdf", **valeurs)
    document.provenance.update({
        "language_agreement": "agree", "text_extracted": True,
        "scope": "country:sn", "subject": "agriculture",
    })
    document.transition(AcquisitionStatus.FETCHED, "HTTP 200.")
    return document.transition(AcquisitionStatus.PARSED, "Texte extrait.")


# ----------------------------------------------------------------------
# Les quasi-doublons
# ----------------------------------------------------------------------

def test_deux_textes_identiques_apres_normalisation_le_sont():
    """La casse, la ponctuation et les espaces ne distinguent pas deux documents."""
    assert normalize("Le  MIL, en 2024.") == normalize("le mil en 2024")
    assert compare("Le  MIL, en 2024.", "le mil en 2024")["verdict"] == "identical"


def test_un_quasi_doublon_est_repere_sans_etre_confondu_avec_un_doublon():
    """
    Trois mots changés ne font pas un nouveau document ; ils font une version.
    Les deux demandent des actions différentes.
    """
    verdict = compare(TEXTE, PRESQUE)

    assert verdict["verdict"] == "near"
    assert 0.8 <= verdict["similarity"] < 1.0


def test_deux_documents_differents_ne_sont_pas_des_doublons():
    """La contrepartie : un seuil trop bas mettrait en quarantaine deux rapports légitimes."""
    assert compare(TEXTE, AUTRE)["verdict"] == "distinct"


def test_la_mesure_est_symetrique():
    """Une mesure asymétrique ferait dépendre le verdict de l'ordre d'arrivée."""
    assert similarity(TEXTE, PRESQUE) == similarity(PRESQUE, TEXTE)


def test_un_texte_vide_ne_ressemble_a_rien():
    """Sinon deux extractions ratées seraient « le même document »."""
    assert similarity("", TEXTE) == 0.0


def test_tous_les_proches_sont_rendus_pas_seulement_le_premier():
    """Un seuil franchi deux fois n'est pas la même information qu'une fois."""
    corpus = [
        {"id": "a", "text": PRESQUE},
        {"id": "b", "text": TEXTE + " Un paragraphe de conclusion a été ajouté."},
        {"id": "c", "text": AUTRE},
    ]

    doublons = find_duplicates(TEXTE, corpus)

    assert len(doublons["near"]) == 2
    assert set(entree["id"] for entree in doublons["near"]) == {"a", "b"}


def test_un_mot_change_partout_passe_sous_le_seuil_et_c_est_mesure():
    """
    La limite réelle de la mesure, constatée plutôt que supposée : remplacer
    « Kaolack » par « Fatick » dans un texte court où le mot revient trois fois
    donne 0,79 — **sous** le seuil de 0,80. Deux rapports régionaux distincts
    sont donc bien vus comme distincts, ce qui est le comportement voulu, mais un
    document simplement relocalisé passerait aussi. C'est écrit ici pour que le
    seuil se règle sur une mesure et non sur une impression.
    """
    score = similarity(TEXTE, TEXTE.replace("Kaolack", "Fatick"))

    assert 0.75 < score < 0.80
    assert compare(TEXTE, TEXTE.replace("Kaolack", "Fatick"))["verdict"] == "distinct"


def test_le_rapport_nomme_ce_que_la_mesure_ne_voit_pas():
    """Une traduction du même document a une similarité nulle, et c'est écrit."""
    rapport = dedup_report()

    assert rapport["symmetric"] is True
    assert any("traduction" in ligne for ligne in rapport["not_detected"])


# ----------------------------------------------------------------------
# Le pouvoir borné de chaque contrôle
# ----------------------------------------------------------------------

def test_un_rang_de_decouverte_refuse_le_document():
    """`TIER_D` est une piste, jamais une source."""
    document = _parsed(source_tier="TIER_D_DISCOVERY_ONLY")

    assert check_authority(document)["verdict"] == REFUS


def test_un_rang_replie_met_en_quarantaine_sans_refuser():
    """Un rang que personne n'a relu ne doit pas donner d'autorité en silence."""
    verdict = check_authority(_parsed(), tier_defaulted=True)

    assert verdict["verdict"] == QUARANTAINE
    assert "relu" in verdict["reason"]


def test_la_pertinence_ne_refuse_jamais():
    """
    Le contrôle le plus tentant à durcir. Les marqueurs de sujet sont un signal
    faible ; leur donner le pouvoir de refuser viderait la base des documents que
    le registre n'a pas su décrire.
    """
    verdict = check_relevance(AUTRE, ["agriculture"])

    assert verdict["verdict"] == QUARANTAINE
    assert verdict["verdict"] != REFUS
    assert "ne refuse jamais" in verdict["reason"] or "pas à refuser" in verdict["reason"]


def test_une_licence_inconnue_degrade_au_lieu_de_bloquer():
    """
    Sinon les meilleures sources seraient les premières écartées : une institution
    publie rarement une licence lisible par une machine.
    """
    assert check_licence(_parsed())["verdict"] == OK
    assert check_licence(_parsed(license_or_usage_status="unknown"))["verdict"] == QUARANTAINE


def test_une_date_absente_met_en_quarantaine_et_ne_refuse_pas():
    """Un document officiel non daté reste un document officiel."""
    verdict = check_date(_parsed(publication_date="unknown"))

    assert verdict["verdict"] == QUARANTAINE


def test_un_doublon_exact_refuse_un_quasi_doublon_met_en_quarantaine():
    """Les deux verdicts sont différents parce que les deux actions le sont."""
    corpus = [{"id": "existant", "text": TEXTE}]

    assert check_duplicate(TEXTE, corpus)["verdict"] == REFUS
    assert check_duplicate(PRESQUE, corpus)["verdict"] == QUARANTAINE
    assert check_duplicate(AUTRE, corpus)["verdict"] == OK


# ----------------------------------------------------------------------
# L'agrégation
# ----------------------------------------------------------------------

def test_un_document_complet_passe_les_dix_controles():
    """
    La contrepartie de tous les refus. Sans ce test, dix contrôles qui arrêtent
    tout auraient l'air très sûrs.
    """
    document = _parsed()

    rapport = evaluate(document, TEXTE, declared_subjects=["agriculture"])

    assert rapport["verdict"] == OK, rapport["reasons"]
    assert document.status is AcquisitionStatus.VERIFIED
    assert len(rapport["passed"]) == 10


def test_un_seul_refus_suffit_a_refuser_le_document():
    """Le verdict d'ensemble est le maximum, pas la moyenne."""
    document = _parsed(source_tier="TIER_D_DISCOVERY_ONLY")

    rapport = evaluate(document, TEXTE, declared_subjects=["agriculture"])

    assert rapport["verdict"] == REFUS
    assert document.status is AcquisitionStatus.REJECTED


def test_une_quarantaine_ne_devient_pas_un_refus():
    """Une lacune n'est pas une faute : elle attend une personne."""
    document = _parsed(publication_date="unknown")

    rapport = evaluate(document, TEXTE, declared_subjects=["agriculture"])

    assert rapport["verdict"] == QUARANTAINE
    assert document.status is AcquisitionStatus.QUARANTINED
    assert any("Date de publication inconnue" in raison for raison in rapport["reasons"])


def test_un_desaccord_avec_la_base_est_rapporte_jamais_resolu():
    """Aucun gagnant n'est désigné : écraser un fait validé est la façon dont une base pourrit."""
    document = _parsed()
    base = [{
        "id": "existant", "scope": "country:sn", "subject": "agriculture",
        "content": TEXTE.replace("une hausse", "aucune hausse"),
    }]

    rapport = evaluate(document, TEXTE, corpus=base, declared_subjects=["agriculture"])

    contradiction = [c for c in rapport["checks"] if c["check"] == "contradiction"][0]
    assert contradiction["verdict"] == QUARANTAINE
    assert "jamais résolu" in contradiction["reason"]
    assert "winner" not in str(rapport)


def test_un_document_non_analyse_n_est_pas_evalue():
    """Les contrôles se placent entre l'extraction et le verdict, pas ailleurs."""
    document = AcquiredDocument(source_url="https://x.sn/a.pdf")

    rapport = evaluate(document, TEXTE)

    assert rapport["evaluated"] is False
    assert document.status is AcquisitionStatus.DISCOVERED


def test_les_raisons_disent_quoi_corriger():
    """Un document arrêté sans raison lisible oblige à relire le code."""
    document = _parsed(content_hash="unknown", license_or_usage_status="unknown")

    rapport = evaluate(document, TEXTE, declared_subjects=["agriculture"])

    assert rapport["reasons"], "Un verdict sans raison"
    assert document.history[-1]["reason"].startswith("Refusé")


@pytest.mark.parametrize("controle", [
    "authority", "integrity", "provenance", "duplicate", "date",
    "language", "relevance", "extraction", "contradiction", "licence",
])
def test_les_dix_controles_sont_tous_declares_avec_leur_pouvoir(controle):
    """Le rapport se vérifie sans lire le code, et il en compte bien dix."""
    rapport = quality_report()

    assert controle in rapport["checks"]
    assert len(rapport["checks"]) == 10
    assert rapport["unknown_goes_to"] == "quarantine"
