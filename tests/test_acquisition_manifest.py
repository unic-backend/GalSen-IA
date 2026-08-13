"""
De document vérifié à entrée de manifeste — proposée, jamais appliquée (ADR-021, étape 9).

L'étape la plus facile à rater : appeler `ingest_file()` sur un document
`VERIFIED` aurait été simple, et le portillon de l'étape 4 n'aurait plus servi
qu'à autoriser une requête HTTP. Ces tests gardent la frontière.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.acquisition.manifest import (  # noqa: E402
    BROUILLON,
    ManifestRefused,
    manifest_report,
    propose,
    propose_batch,
    to_yaml,
)
from src.acquisition.record import AcquiredDocument, AcquisitionStatus  # noqa: E402

ANSD = "ANSD — Agence nationale de la statistique et de la démographie"


def _verifie(**champs) -> AcquiredDocument:
    """Un document mené jusqu'à `VERIFIED`, comme le pilote en produira."""
    valeurs = {
        "institution": ANSD,
        "source_tier": "TIER_A_PRIMARY_OFFICIAL",
        "retrieval_date": "2026-08-13T10:00:00+00:00",
        "content_hash": "a" * 64,
        "license_or_usage_status": "reference_only",
        "publication_date": "2024-03-15",
        "document_title": "Annuaire statistique 2024",
        "language": "fr",
    }
    valeurs.update(champs)
    document = AcquiredDocument(source_url="https://www.ansd.sn/annuaire-2024.pdf", **valeurs)
    document.provenance["language_detection"] = {"language": "fr", "reviewed": True}
    document.transition(AcquisitionStatus.FETCHED, "HTTP 200.")
    document.transition(AcquisitionStatus.PARSED, "Texte extrait.")
    return document.transition(AcquisitionStatus.VERIFIED, "Les dix contrôles passent.")


# ----------------------------------------------------------------------
# Ce qui n'est jamais fait
# ----------------------------------------------------------------------

def test_la_proposition_n_ecrit_rien_et_ne_cree_aucune_connaissance():
    """
    Le test qui justifie ce module. Une acquisition qui écrit dans la base sans
    relecture ferait du portillon une simple autorisation de requête HTTP.
    """
    proposition = propose(_verifie())

    assert proposition["applied"] is False
    assert proposition["requires_human_confirmation"] is True
    assert proposition["entry"]["status"] == BROUILLON
    assert manifest_report()["writes_files"] is False
    assert manifest_report()["creates_knowledge"] is False


@pytest.mark.parametrize("statut", [
    AcquisitionStatus.DISCOVERED,
    AcquisitionStatus.FETCHED,
    AcquisitionStatus.QUARANTINED,
])
def test_seul_un_document_verifie_se_propose(statut):
    """
    Proposer pour un document en quarantaine ferait entrer par la proposition ce
    que les contrôles ont retenu.
    """
    document = AcquiredDocument(source_url="https://www.ansd.sn/x.pdf")
    if statut is not AcquisitionStatus.DISCOVERED:
        document.transition(AcquisitionStatus.FETCHED, "HTTP 200.")
    if statut is AcquisitionStatus.QUARANTINED:
        document.transition(AcquisitionStatus.QUARANTINED, "Licence inconnue.")

    with pytest.raises(ManifestRefused) as echec:
        propose(document)

    assert "VERIFIED" in str(echec.value)


# ----------------------------------------------------------------------
# D'où vient chaque champ
# ----------------------------------------------------------------------

def test_l_autorite_vient_du_registre_jamais_du_document():
    """
    Un document qui se déclare officiel ne gagne rien à le dire : la catégorie,
    la portée et le sujet sont lus dans le registre, sur le nom de l'institution.
    """
    entree = propose(_verifie())["entry"]

    assert entree["author"] == ANSD
    assert entree["source_category"] == "government"
    assert entree["scope"] == "country:sn"
    assert entree["subject"] == "economics"


def test_une_institution_absente_du_registre_ne_recoit_aucune_autorite():
    """Faute d'entrée, les champs d'autorité restent vides plutôt que devinés."""
    entree = propose(_verifie(institution="Organisation inconnue"))["entry"]

    assert entree["source_category"] is None
    assert entree["scope"] is None
    assert entree["subject"] is None


def test_la_langue_est_proposee_mais_marquee_comme_detectee():
    """
    Détectée n'est pas déclarée. La proposer sans le dire ferait passer une
    mesure pour une déclaration de l'éditeur.
    """
    proposition = propose(_verifie())

    assert proposition["entry"]["language"] == "fr"
    assert any("détectée" in ligne for ligne in proposition["uncertain"])


def test_une_langue_detectee_par_une_liste_non_relue_porte_sa_reserve():
    """La réserve voyage jusqu'à la proposition, pas seulement dans le détecteur."""
    document = _verifie(language="wo")
    document.provenance["language_detection"] = {"language": "wo", "reviewed": False}

    incertain = propose(document)["uncertain"]

    assert any("non relue par un locuteur" in ligne for ligne in incertain)


def test_une_langue_non_detectee_laisse_le_champ_vide_et_le_dit():
    """`unknown` n'est pas une langue : le champ reste vide, avec sa raison."""
    proposition = propose(_verifie(language="unknown"))

    assert proposition["entry"]["language"] is None
    assert any("non détectée" in ligne for ligne in proposition["uncertain"])


def test_une_date_absente_est_signalee_sans_empecher_la_proposition():
    """Un document officiel non daté reste un document officiel."""
    proposition = propose(_verifie(publication_date="unknown"))

    assert proposition["entry"]["publication_date"] is None
    assert any("publication_date" in ligne for ligne in proposition["uncertain"])
    assert proposition["status"] == "proposed"


def test_plusieurs_sujets_declares_laissent_le_choix_visible():
    """La source ANSD en déclare quatre : proposer le premier sans le dire serait un choix caché."""
    proposition = propose(_verifie())

    assert any("subject" in ligne and "déclare" in ligne for ligne in proposition["uncertain"])


# ----------------------------------------------------------------------
# Le lot
# ----------------------------------------------------------------------

def test_un_lot_dit_pourquoi_chaque_document_ecarte_l_est():
    """Un lot dont on ne sait pas dire ce qui n'a pas abouti n'a rien prouvé."""
    retenu = _verifie()
    ecarte = AcquiredDocument(source_url="https://www.ansd.sn/b.pdf")
    ecarte.transition(AcquisitionStatus.FETCHED, "HTTP 200.")
    ecarte.transition(AcquisitionStatus.QUARANTINED, "Quasi-doublon d'un élément détenu.")

    rapport = propose_batch([retenu, ecarte])

    assert rapport["proposed"] == 1
    assert rapport["applied"] is False
    assert rapport["excluded"][0]["status"] == "QUARANTINED"
    assert "Quasi-doublon" in rapport["excluded"][0]["reason"]


def test_le_rendu_porte_son_avertissement_en_tete():
    """Un fichier qui ressemble à un manifeste valide finit par être utilisé comme tel."""
    rendu = to_yaml(propose_batch([_verifie()])["entries"])

    assert rendu.startswith("# PROPOSITION")
    assert "Rien n'a été ingéré" in rendu
    assert "DRAFT" in rendu
    assert "annuaire-2024.pdf" in rendu


def test_ce_module_n_ingere_rien():
    """
    La frontière gardée par une absence : aucun appel d'ingestion, aucune
    écriture de fichier.
    """
    import ast

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "src", "acquisition", "manifest.py"), encoding="utf-8") as f:
        arbre = ast.parse(f.read())

    # Les noms sont cherchés dans l'arbre syntaxique, pas dans le texte : la
    # docstring **cite** `ingest_file()` pour dire qu'il n'est pas appelé, et un
    # test qui confond les deux garderait la prose au lieu du code.
    noms = {
        noeud.attr if isinstance(noeud, ast.Attribute) else noeud.id
        for noeud in ast.walk(arbre)
        if isinstance(noeud, (ast.Attribute, ast.Name))
    }

    for interdit in ("ingest_file", "DocumentIngestor", "open", "write_text"):
        assert interdit not in noms, f"Le module manifeste écrit via {interdit}"
