"""
L'enregistrement d'un document candidat et sa machine à états (ADR-021, étape 2).

Ce que ces tests gardent : un document découvert **n'est pas** une connaissance,
il ne le devient qu'au bout d'un chemin dont chaque pas porte sa raison, et la
seule sortie de quarantaine passe par une personne.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.acquisition import (  # noqa: E402
    STATUTS_TERMINAUX,
    TRANSITIONS,
    AcquiredDocument,
    AcquisitionRefused,
    AcquisitionStatus,
    acquisition_report,
)
from src.acquisition.record import HUMAIN, INCONNU, PROVENANCE_MINIMALE  # noqa: E402

URL = "https://www.ansd.sn/rapport-2024.pdf"


def _candidat(**champs) -> AcquiredDocument:
    """Un candidat fraîchement découvert."""
    return AcquiredDocument(source_url=URL, **champs)


def _jusqu_a_parsed(document: AcquiredDocument) -> AcquiredDocument:
    """Avance un candidat jusqu'à `PARSED`, chaque pas motivé."""
    document.transition(AcquisitionStatus.FETCHED, "HTTP 200, 412 ko.")
    return document.transition(AcquisitionStatus.PARSED, "18 pages extraites.")


# ----------------------------------------------------------------------
# La machine à états
# ----------------------------------------------------------------------

def test_un_candidat_commence_decouvert_et_sa_trace_commence_avec_lui():
    """Aucun état sans trace : l'état initial est consigné, pas supposé."""
    document = _candidat()

    assert document.status is AcquisitionStatus.DISCOVERED
    assert len(document.history) == 1
    assert document.history[0]["to"] == "DISCOVERED"


def test_un_candidat_sans_url_n_est_pas_un_candidat():
    """Il n'y a rien à acquérir, et rien à tracer."""
    with pytest.raises(AcquisitionRefused):
        AcquiredDocument(source_url="   ")


def test_le_chemin_complet_va_de_la_decouverte_a_l_ingestion():
    """La contrepartie de tous les refus : le chemin nominal doit exister."""
    document = _jusqu_a_parsed(_candidat())
    document.transition(AcquisitionStatus.VERIFIED, "Provenance complète, aucun doublon.")
    document.transition(AcquisitionStatus.INGESTED, "Manifeste approuvé le 2026-08-13.")

    assert document.status is AcquisitionStatus.INGESTED
    assert [pas["to"] for pas in document.history] == [
        "DISCOVERED", "FETCHED", "PARSED", "VERIFIED", "INGESTED",
    ]


def test_un_saut_d_etape_est_refuse():
    """
    Une machine à états qui accepte n'importe quel saut ne mesure rien : ingérer
    depuis `DISCOVERED` contournerait la totalité des contrôles.
    """
    with pytest.raises(AcquisitionRefused) as echec:
        _candidat().transition(AcquisitionStatus.INGESTED, "Raccourci.")

    assert "interdite" in str(echec.value)


def test_aucune_transition_sans_raison():
    """Un document arrêté sans motif est une panne du pipeline, pas un verdict."""
    with pytest.raises(AcquisitionRefused) as echec:
        _candidat().transition(AcquisitionStatus.FETCHED, "   ")

    assert "sans raison" in str(echec.value)


@pytest.mark.parametrize("terminal", sorted(STATUTS_TERMINAUX, key=lambda s: s.value))
def test_un_statut_terminal_ne_se_reprend_pas(terminal):
    """`REJECTED` et `INGESTED` se relisent ; aucun ne se reprend."""
    assert TRANSITIONS[terminal] == frozenset()


def test_un_refus_est_terminal_et_porte_sa_raison():
    """Le refus est la moitié utile du pipeline : il doit rester lisible."""
    document = _candidat().transition(
        AcquisitionStatus.REJECTED, "robots.txt interdit /rapports/."
    )

    assert document.is_terminal is True
    assert document.history[-1]["reason"] == "robots.txt interdit /rapports/."
    with pytest.raises(AcquisitionRefused):
        document.transition(AcquisitionStatus.FETCHED, "Nouvelle tentative.")


# ----------------------------------------------------------------------
# La quarantaine — le seul endroit où l'automate ne décide pas
# ----------------------------------------------------------------------

def test_le_pipeline_ne_sort_pas_un_document_de_quarantaine():
    """
    C'est la propriété centrale de l'étape : la quarantaine est ce que la mesure
    n'a pas su trancher. Un automate qui s'en sort seul l'aurait tranchée.
    """
    document = _jusqu_a_parsed(_candidat()).transition(
        AcquisitionStatus.QUARANTINED, "Motif suspect repéré dans le texte."
    )

    with pytest.raises(AcquisitionRefused) as echec:
        document.transition(AcquisitionStatus.VERIFIED, "Ça a l'air d'aller.")

    assert "personne" in str(echec.value)


def test_une_personne_sort_un_document_de_quarantaine():
    """La contrepartie : la quarantaine est récupérable, sinon c'est un refus."""
    document = _jusqu_a_parsed(_candidat()).transition(
        AcquisitionStatus.QUARANTINED, "Langue détectée différente de la déclarée."
    )
    document.transition(
        AcquisitionStatus.VERIFIED, "Relu : document bilingue, déclaration corrigée.",
        actor=HUMAIN,
    )

    assert document.status is AcquisitionStatus.VERIFIED
    assert document.history[-1]["actor"] == HUMAIN


def test_le_pipeline_peut_refuser_un_document_en_quarantaine():
    """Refuser ne demande personne : c'est l'inverse qui est une décision."""
    document = _jusqu_a_parsed(_candidat()).transition(
        AcquisitionStatus.QUARANTINED, "Doublon proche d'un élément existant."
    )
    document.transition(AcquisitionStatus.REJECTED, "Doublon confirmé par empreinte.")

    assert document.status is AcquisitionStatus.REJECTED


def test_la_quarantaine_ne_mene_jamais_directement_a_l_ingestion():
    """Un document tiré de la quarantaine repasse par les contrôles, pas au-dessus."""
    assert AcquisitionStatus.INGESTED not in TRANSITIONS[AcquisitionStatus.QUARANTINED]


# ----------------------------------------------------------------------
# La provenance
# ----------------------------------------------------------------------

def test_tout_ce_qui_n_a_pas_ete_etabli_vaut_inconnu():
    """`unknown` n'est pas « sans importance » : c'est une lacune qui se transmet."""
    document = _candidat()

    assert document.publication_date == INCONNU
    assert document.license_or_usage_status == INCONNU
    assert "content_hash" in document.provenance_gaps()


def test_la_date_de_publication_n_est_jamais_la_date_de_recuperation():
    """
    Un document récupéré aujourd'hui n'est pas un document publié aujourd'hui.
    Une base qui confond les deux classe un décret de 1998 comme courant.
    """
    document = _candidat(retrieval_date="2026-08-13T10:00:00+00:00")

    assert document.publication_date == INCONNU
    assert document.publication_date != document.retrieval_date


def test_la_provenance_minimale_n_exige_pas_la_date_de_publication():
    """
    Un document officiel non daté reste un document officiel. L'exiger viderait
    le pilote ; il entre avec sa lacune, et la lacune se voit.
    """
    document = _candidat(
        institution="ANSD", source_tier="TIER_A_PRIMARY_OFFICIAL",
        retrieval_date="2026-08-13T10:00:00+00:00", content_hash="a" * 64,
        license_or_usage_status="reference_only",
    )

    assert "publication_date" not in PROVENANCE_MINIMALE
    assert document.provenance_is_sufficient() is True
    assert document.missing_for_trusted_layer() == []
    assert "publication_date" in document.provenance_gaps(), "La lacune a disparu du rapport"


def test_une_provenance_incomplete_dit_ce_qui_manque():
    """Un refus qui ne dit pas quoi corriger oblige à relire le code."""
    document = _candidat(institution="ANSD")

    assert document.provenance_is_sufficient() is False
    assert set(document.missing_for_trusted_layer()) == {
        "source_tier", "retrieval_date", "content_hash", "license_or_usage_status",
    }


# ----------------------------------------------------------------------
# Le rapport de lot
# ----------------------------------------------------------------------

def test_le_rapport_d_un_lot_sort_les_refus_avec_leur_raison():
    """Un lot dont on ne sait pas dire pourquoi chaque document s'est arrêté n'a rien prouvé."""
    refuse = AcquiredDocument(source_url="https://x.sn/a").transition(
        AcquisitionStatus.REJECTED, "Domaine non inscrit au registre."
    )
    en_quarantaine = _jusqu_a_parsed(AcquiredDocument(source_url="https://x.sn/b")).transition(
        AcquisitionStatus.QUARANTINED, "Licence inconnue."
    )

    rapport = acquisition_report([refuse, en_quarantaine])

    assert rapport["documents"] == 2
    assert rapport["by_status"]["REJECTED"] == 1
    assert rapport["rejected"][0]["reason"] == "Domaine non inscrit au registre."
    assert rapport["quarantined"][0]["reason"] == "Licence inconnue."
    assert len(rapport["insufficient_provenance"]) == 2


def test_un_lot_vide_est_un_lot_vide_et_le_dit():
    """Zéro document n'est pas un succès silencieux."""
    rapport = acquisition_report([])

    assert rapport["documents"] == 0
    assert rapport["by_status"]["INGESTED"] == 0


def test_ce_module_ne_touche_ni_le_reseau_ni_le_disque():
    """
    L'étape 2 tient un état, rien d'autre. La première requête sortante du projet
    est à l'étape 10, sous approbation — et ce test garde la frontière.
    """
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "src", "acquisition", "record.py"), encoding="utf-8") as f:
        source = f.read()

    for interdit in ("requests.", "urlopen", "httpx.", "open(", "subprocess"):
        assert interdit not in source, f"`record.py` atteint l'extérieur via {interdit}"
