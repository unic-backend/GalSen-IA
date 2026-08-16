"""
Tests for the provider research record (directive V4, §37-§40).

What is pinned is not the content of the survey — that changes every month by
design. It is the discipline that keeps the survey from drifting in one
direction: a repository licence quietly becoming a permission, a README figure
quietly becoming a measurement, an article quietly becoming a licence.
"""

import pytest
import yaml

from src.creative.research import (
    AUCUNE,
    AUTORITATIF,
    COMMERCIAL_AUTORISE,
    INCONNU,
    NON_MESURE,
    SECONDAIRE,
    ResearchRefused,
    executable_here,
    license_matrix,
    load_research,
    research_report,
)


def _ecrire(tmp_path, candidats):
    """Écrit un dossier de recherche jetable."""
    chemin = tmp_path / "providers.yaml"
    chemin.write_text(
        yaml.safe_dump({"version": "1.0", "researched_on": "2026-08-16",
                        "candidates": candidats}, allow_unicode=True),
        encoding="utf-8",
    )
    return str(chemin)


# --------------------------------------------------------------------------
# Le dossier réel du dépôt
# --------------------------------------------------------------------------


def test_le_dossier_du_depot_se_charge_et_respecte_ses_propres_regles():
    dossier = load_research()
    assert dossier["candidates"]
    assert dossier["researched_on"] == "2026-08-16"


def test_les_licences_de_depot_sont_lues_a_leur_source():
    matrice = license_matrix()
    # Une preuve autoritative nomme son URL ; le chargeur refuse le contraire.
    assert matrice["authoritative_repository_licenses"] >= 8


def test_aucune_permission_commerciale_n_est_accordee_sans_preuve():
    matrice = license_matrix()
    for ligne in matrice["rows"]:
        if ligne["commercial_status"] == COMMERCIAL_AUTORISE:
            assert ligne["repository_license_evidence"] == AUTORITATIF
            assert ligne["weight_license_evidence"] == AUTORITATIF


def test_les_licences_de_poids_sont_majoritairement_inconnues_et_c_est_mesure():
    # `huggingface.co` n'a aucune route depuis ce conteneur : les conditions
    # des poids n'ont pas pu être lues, et le dossier le dit au lieu de
    # recopier la licence du dépôt.
    matrice = license_matrix()
    assert len(matrice["unknown"]["weight_license"]) >= 7
    assert "huggingface" in matrice["note"]


def test_une_licence_non_osi_est_rapportee_restreinte():
    ligne = [entree for entree in license_matrix()["rows"]
             if entree["id"] == "hunyuanvideo"][0]
    assert ligne["commercial_status"] == "RESTRICTED"
    # La restriction vient du texte de la licence, pas d'un résumé.
    assert "EUROPEAN UNION" in ligne["restrictions"]


def test_le_copyleft_est_signale_comme_une_question_d_architecture():
    dossier = load_research()
    seed = [c for c in dossier["candidates"] if c["id"] == "seed-vc"][0]
    assert seed["repository_license"] == "GPL-3.0"
    assert "COPYLEFT" in seed["repository_license_note"]


def test_aucun_candidat_n_est_executable_ici():
    execution = executable_here()
    assert execution["executable"] == []
    assert execution["gpu_state"] == "UNAVAILABLE"


def test_qualite_et_latence_ne_sont_jamais_recopiees():
    for entree in load_research()["candidates"]:
        for champ in ("quality", "latency"):
            assert entree.get(champ, NON_MESURE) in (NON_MESURE, INCONNU,
                                                     "NOT_APPLICABLE")


# --------------------------------------------------------------------------
# Les règles, éprouvées sur des dossiers construits pour les casser
# --------------------------------------------------------------------------


def test_une_preuve_autoritative_sans_source_est_refusee(tmp_path):
    chemin = _ecrire(tmp_path, [{
        "id": "faux", "repository_license": "Apache-2.0",
        "repository_license_evidence": AUTORITATIF,
    }])
    with pytest.raises(ResearchRefused) as erreur:
        load_research(chemin)
    assert "sans source" in str(erreur.value)


def test_un_inconnu_sans_raison_est_refuse(tmp_path):
    chemin = _ecrire(tmp_path, [{
        "id": "faux", "repository_license": INCONNU,
        "repository_license_evidence": AUCUNE,
    }])
    with pytest.raises(ResearchRefused) as erreur:
        load_research(chemin)
    # « On ne sait pas » et « on n'a pas regardé » appellent des actions
    # différentes.
    assert "sans raison" in str(erreur.value)


def test_une_permission_commerciale_deduite_est_refusee(tmp_path):
    chemin = _ecrire(tmp_path, [{
        "id": "faux",
        "repository_license": "Apache-2.0",
        "repository_license_evidence": AUTORITATIF,
        "repository_license_source": "https://exemple/LICENSE",
        "weight_license": INCONNU,
        "weight_license_evidence": AUCUNE,
        "weight_license_reason": "non lue",
        "dataset_license": INCONNU,
        "dataset_license_reason": "non lue",
        "commercial_status": COMMERCIAL_AUTORISE,
    }])
    with pytest.raises(ResearchRefused) as erreur:
        load_research(chemin)
    assert "permissif n'est pas une permission" in str(erreur.value)


def test_une_source_secondaire_ne_rend_pas_un_champ_autoritatif(tmp_path):
    # Un article résumant une licence n'est pas la licence (§67). Le niveau
    # est conservé tel quel, et la permission commerciale reste refusée.
    chemin = _ecrire(tmp_path, [{
        "id": "faux",
        "repository_license": "Apache-2.0",
        "repository_license_evidence": SECONDAIRE,
        "weight_license": "Apache-2.0",
        "weight_license_evidence": SECONDAIRE,
        "dataset_license": INCONNU,
        "dataset_license_reason": "non lue",
        "commercial_status": COMMERCIAL_AUTORISE,
    }])
    with pytest.raises(ResearchRefused):
        load_research(chemin)


def test_une_mesure_sans_mesureur_est_refusee(tmp_path):
    chemin = _ecrire(tmp_path, [{
        "id": "faux",
        "repository_license": "MIT", "repository_license_evidence": AUTORITATIF,
        "repository_license_source": "https://exemple/LICENSE",
        "weight_license": INCONNU, "weight_license_reason": "non lue",
        "dataset_license": INCONNU, "dataset_license_reason": "non lue",
        "latency": "45 s",
    }])
    with pytest.raises(ResearchRefused) as erreur:
        load_research(chemin)
    # Un chiffre repris d'un README est la revendication d'un projet.
    assert "revendication d'un projet" in str(erreur.value)


def test_une_mesure_avec_son_mesureur_est_acceptee(tmp_path):
    chemin = _ecrire(tmp_path, [{
        "id": "faux",
        "repository_license": "MIT", "repository_license_evidence": AUTORITATIF,
        "repository_license_source": "https://exemple/LICENSE",
        "weight_license": INCONNU, "weight_license_reason": "non lue",
        "dataset_license": INCONNU, "dataset_license_reason": "non lue",
        "latency": "45 s",
        "latency_measured_by": "banc de mesure interne, 2026-08-16, 5 échantillons",
    }])
    assert load_research(chemin)["candidates"][0]["latency"] == "45 s"


def test_un_identifiant_en_double_est_refuse(tmp_path):
    entree = {"id": "faux", "repository_license": INCONNU,
              "repository_license_reason": "non lue",
              "weight_license": INCONNU, "weight_license_reason": "non lue",
              "dataset_license": INCONNU, "dataset_license_reason": "non lue"}
    chemin = _ecrire(tmp_path, [entree, dict(entree)])
    with pytest.raises(ResearchRefused) as erreur:
        load_research(chemin)
    assert "double" in str(erreur.value)


def test_le_rapport_nomme_ce_qu_il_refuse():
    rapport = research_report()
    refus = " ".join(rapport["does_not"]).lower()
    assert "choisir un fournisseur" in refus
    assert "popularité" in refus
    assert len(rapport["candidates"]) == 9
