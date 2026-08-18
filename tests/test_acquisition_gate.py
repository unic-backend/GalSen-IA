"""
Décider, faire approuver, puis récupérer — dans cet ordre (ADR-021, étape 4).

Les trois pièces existaient déjà ; rien ne garantissait l'ordre, et un ordre non
garanti n'est pas un ordre. Ces tests gardent les trois impossibilités :
récupérer sans avoir décidé, récupérer sans accord, et réutiliser un accord
donné pour autre chose.

Aucune requête réseau : le récupérateur est injecté. Ce qui est mesuré ici est
le portillon, pas le transport — celui-ci a ses propres tests.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.acquisition.gate import (  # noqa: E402
    CollectionBatch,
    GateRefused,
    acquire,
    gate_report,
    plan_batch,
    submit_batch,
)
from src.acquisition.record import AcquisitionStatus  # noqa: E402
from src.approval_engine.approval_manager import ApprovalManagerImpl  # noqa: E402
from src.approval_engine.types import ApprovalRequest  # noqa: E402

ANSD = "https://www.ansd.sn/rapport-2024.pdf"
ANSD_BIS = "https://www.ansd.sn/annuaire-2023.pdf"
HORS_REGISTRE = "https://blog-inconnu.example/note.pdf"


class _Portillon:
    """Un contexte minimal qui dépose de vraies demandes dans un vrai gestionnaire."""

    def __init__(self, manager: ApprovalManagerImpl) -> None:
        self.manager = manager

    def submit_approval(self, action, description, metadata):
        """Dépose la demande et retourne son identifiant."""
        return self.manager.submit(ApprovalRequest(
            agent_id="acquisition", request_id=None, action=action,
            description=description, metadata=metadata,
        ))


@pytest.fixture
def manager(monkeypatch, tmp_path):
    """Un gestionnaire d'approbations isolé, en mémoire."""
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "in-memory")
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    return ApprovalManagerImpl()


@pytest.fixture
def contexte(manager):
    """Le contexte qui porte le portillon."""
    return _Portillon(manager)


class _Recuperateur:
    """Un récupérateur qui compte ses appels — pour prouver qu'il n'est pas appelé."""

    def __init__(self) -> None:
        self.appels = []

    def __call__(self, url, **_):
        self.appels.append(url)
        from src.acquisition.fetcher import FetchResult
        return FetchResult(
            url=url, status=200, body=b"%PDF-1.4 test", content_type="application/pdf",
            size=13,
        )


# ----------------------------------------------------------------------
# Décider avant de demander
# ----------------------------------------------------------------------

def test_la_decision_est_prise_url_par_url_avant_toute_requete():
    """
    Décider après avoir téléchargé rend la décision décorative : la requête est
    déjà arrivée chez quelqu'un.
    """
    lot = plan_batch([ANSD, HORS_REGISTRE], robots_txt="")

    assert lot.urls == [ANSD]
    assert len(lot.refused) == 1
    assert "non inscrit" in lot.refused[0]["reason"]


def test_un_lot_melangeant_deux_sources_est_refuse():
    """
    Une approbation porte sur une source, sinon la personne qui approuve ne sait
    pas ce qu'elle approuve.
    """
    with pytest.raises(GateRefused) as echec:
        plan_batch([ANSD, "https://www.isra.sn/guide.pdf"], robots_txt="")

    assert "plusieurs sources" in str(echec.value)


def test_un_lot_vide_n_a_rien_a_faire_approuver():
    """Zéro document n'est pas un lot."""
    with pytest.raises(GateRefused):
        plan_batch([], robots_txt="")


def test_un_lot_sans_candidat_retenu_ne_produit_pas_d_approbation(contexte):
    """Une approbation sans objet serait une approbation réutilisable."""
    lot = plan_batch([HORS_REGISTRE], robots_txt="")

    with pytest.raises(GateRefused) as echec:
        submit_batch(contexte, lot)

    assert "rien à approuver" in str(echec.value)


def test_une_seule_demande_est_deposee_pour_tout_le_lot(contexte, manager):
    """Trente demandes se cliquent sans être lues ; une se lit."""
    lot = plan_batch([ANSD, ANSD_BIS], robots_txt="")
    identifiant = submit_batch(contexte, lot)

    assert manager.count() == 1
    demande = manager.get(identifiant)
    assert demande.metadata["count"] == 2
    assert demande.metadata["source"].startswith("ANSD")
    assert "2 document(s)" in demande.description


# ----------------------------------------------------------------------
# Rien ne part sans accord
# ----------------------------------------------------------------------

def test_recuperer_sans_avoir_demande_l_accord_leve_et_n_appelle_rien(manager):
    """Le test central de l'étape : aucune requête n'est envoyée dans ce cas."""
    lot = plan_batch([ANSD], robots_txt="")
    recuperateur = _Recuperateur()

    with pytest.raises(GateRefused) as echec:
        acquire(lot, manager, allowed_content_types=["pdf"], fetch_fn=recuperateur)

    assert "Aucune approbation" in str(echec.value)
    assert recuperateur.appels == [], "Une requête est partie sans approbation"


def test_une_demande_en_attente_ne_suffit_pas(contexte, manager):
    """« Déposée » n'est pas « accordée » — et la différence est tout le portillon."""
    lot = plan_batch([ANSD], robots_txt="")
    submit_batch(contexte, lot)
    recuperateur = _Recuperateur()

    with pytest.raises(GateRefused) as echec:
        acquire(lot, manager, allowed_content_types=["pdf"], fetch_fn=recuperateur)

    assert "pending" in str(echec.value)
    assert recuperateur.appels == []


def test_une_demande_refusee_ne_recupere_rien(contexte, manager):
    """Un refus humain est un refus, pas un avis."""
    lot = plan_batch([ANSD], robots_txt="")
    manager.reject(submit_batch(contexte, lot), reason="Licence à vérifier.")
    recuperateur = _Recuperateur()

    with pytest.raises(GateRefused):
        acquire(lot, manager, allowed_content_types=["pdf"], fetch_fn=recuperateur)

    assert recuperateur.appels == []


def test_une_approbation_ne_couvre_pas_un_lot_modifie(contexte, manager):
    """
    Sans l'empreinte, « approuver trois documents de l'ANSD » autoriserait
    n'importe quoi : il suffirait d'ajouter une URL après l'accord.
    """
    lot = plan_batch([ANSD], robots_txt="")
    manager.approve(submit_batch(contexte, lot), decided_by="proprietaire")

    elargi = plan_batch([ANSD, ANSD_BIS], robots_txt="")
    elargi.approval_id = lot.approval_id
    recuperateur = _Recuperateur()

    with pytest.raises(GateRefused) as echec:
        acquire(elargi, manager, allowed_content_types=["pdf"], fetch_fn=recuperateur)

    assert "ne porte pas sur ce lot" in str(echec.value)
    assert recuperateur.appels == []


def test_une_approbation_introuvable_est_dite_comme_telle(manager):
    """Un identifiant inventé ne devient pas un accord."""
    lot = plan_batch([ANSD], robots_txt="")
    lot.approval_id = "approval-qui-n-existe-pas"

    with pytest.raises(GateRefused) as echec:
        acquire(lot, manager, allowed_content_types=["pdf"], fetch_fn=_Recuperateur())

    assert "introuvable" in str(echec.value)


# ----------------------------------------------------------------------
# Le chemin nominal
# ----------------------------------------------------------------------

def test_un_lot_approuve_est_recupere_et_chaque_document_avance(contexte, manager):
    """La contrepartie de tous les refus : le chemin nominal doit exister."""
    lot = plan_batch([ANSD, ANSD_BIS], robots_txt="")
    manager.approve(submit_batch(contexte, lot), decided_by="proprietaire")
    recuperateur = _Recuperateur()

    rapport = acquire(lot, manager, allowed_content_types=["pdf"], fetch_fn=recuperateur)

    assert rapport["fetched"] == 2
    assert sorted(recuperateur.appels) == sorted([ANSD, ANSD_BIS])
    for document in lot.documents:
        assert document.status is AcquisitionStatus.FETCHED
        assert document.content_hash != "unknown"
        assert document.provenance["approval_id"] == lot.approval_id
        # La date de récupération se pose ici, au moment où le document arrive.
        # Elle fait partie de la provenance minimale : sans elle, aucun document
        # n'atteignait `VERIFIED`, et seul un passage de bout en bout l'a montré.
        assert document.retrieval_date != "unknown"


def test_le_lot_porte_ce_que_le_registre_sait_deja(contexte):
    """
    L'institution, le rang et le pays viennent du registre, jamais du document —
    c'est la règle qui rend « ceci est officiel » vérifiable.
    """
    lot = plan_batch([ANSD], robots_txt="")
    document = lot.documents[0]

    assert document.institution.startswith("ANSD")
    assert document.source_tier == "TIER_A_PRIMARY_OFFICIAL"
    assert document.country == "SN"
    assert document.license_or_usage_status == "reference_only", "Licence inconnue"


def test_un_echec_de_recuperation_refuse_le_document_avec_sa_raison(contexte, manager):
    """Un document arrêté sans motif serait une panne du pipeline, pas un verdict."""
    from src.acquisition.fetcher import FetchRefused

    lot = plan_batch([ANSD], robots_txt="")
    manager.approve(submit_batch(contexte, lot), decided_by="proprietaire")

    def _refuse(url, **_):
        raise FetchRefused("Réponse HTTP 503.")

    rapport = acquire(lot, manager, allowed_content_types=["pdf"], fetch_fn=_refuse)

    assert rapport["fetched"] == 0
    assert rapport["failed"][0]["reason"] == "Réponse HTTP 503."
    assert lot.documents[0].status is AcquisitionStatus.REJECTED


def test_le_rapport_du_portillon_ne_declare_aucune_source_activee():
    """
    Mesure, pas déclaration : tant que personne n'a activé de source, le
    portillon n'a rien à ouvrir.
    """
    rapport = gate_report()

    assert rapport["enabled_sources"] == []
    assert rapport["acquirable_sources"] == []
    assert rapport["approval_scope"] == "un lot, une source, une licence"


def test_une_empreinte_ne_depend_pas_de_l_ordre_de_decouverte():
    """Deux découvertes du même lot doivent donner le même accord."""
    premier = plan_batch([ANSD, ANSD_BIS], robots_txt="")
    second = plan_batch([ANSD_BIS, ANSD], robots_txt="")

    assert premier.fingerprint == second.fingerprint
    assert premier.fingerprint != CollectionBatch("ANSD", "cc-by").fingerprint
