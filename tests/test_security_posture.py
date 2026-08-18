"""
Le modèle de sécurité, mesuré (VOLET 34, ch. 13).

Deux moitiés, et la même exigence dans les deux :

1. **`posture()`** — elle doit *mesurer*, pas recopier ce qu'un document
   affirme. Le test qui compte fait varier la configuration réelle et vérifie
   que la mesure change avec elle.
2. **`list_checkpoints()`** — elle doit distinguer ce qui se défait de ce qui ne se
   défait pas. Une décision d'approbation et une sauvegarde ne s'annulent pas ;
   les présenter comme réversibles serait la promesse la plus coûteuse de tout
   le VOLET.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.security.checkpoints import describe, list_checkpoints, undo  # noqa: E402
from src.security.posture import SECTIONS, posture, summary  # noqa: E402
from src.storage.roots import VARIABLE  # noqa: E402


@pytest.fixture
def racine_inscriptible(tmp_path, monkeypatch):
    """Une racine déclarée en écriture, avec un fichier dedans."""
    dossier = tmp_path / "documents"
    dossier.mkdir()
    (dossier / "rapport.pdf").write_text("contenu", encoding="utf-8")
    monkeypatch.setenv(VARIABLE, f"documents:{dossier}:rw")
    return dossier


# ----------------------------------------------------------------------
# 1. La posture se mesure
# ----------------------------------------------------------------------


def test_toutes_les_sections_sont_rapportees():
    """Une section absente se lirait « rien à signaler »."""
    mesure = posture()

    assert set(mesure["sections"]) == set(SECTIONS)
    for nom, section in mesure["sections"].items():
        assert "state" in section, f"section « {nom} » sans état"
        assert "gaps" in section, f"section « {nom} » sans failles rapportées"


def test_la_posture_suit_la_configuration_reelle(monkeypatch, racine_inscriptible):
    """
    Le test central : la mesure doit changer quand la configuration change.
    Une posture recopiée d'un document resterait identique.
    """
    avec = posture()["sections"]["filesystem"]
    monkeypatch.delenv(VARIABLE, raising=False)
    sans = posture()["sections"]["filesystem"]

    assert avec["writable_roots"] == 1
    assert avec["state"] == "confined"
    assert sans["declared_roots"] == 0
    assert sans["state"] == "no_roots"


def test_une_racine_inscriptible_est_rapportee_comme_une_faille(racine_inscriptible):
    """
    Ce n'est pas une erreur de configuration — c'est une capacité, et une
    capacité d'écriture sur le disque de quelqu'un se dit.
    """
    section = posture()["sections"]["filesystem"]

    assert section["gaps"]
    assert "documents" in section["gaps"][0]


def test_les_failles_du_bac_a_sable_viennent_du_module_pas_d_une_reecriture():
    """
    Deux formulations d'une même limite divergent, et c'est la plus rassurante
    qui survit. La posture reprend `NON_GARANTI` tel quel.
    """
    from src.sandbox.policy import NON_GARANTI

    assert posture()["sections"]["execution"]["gaps"] == list(NON_GARANTI)


def test_le_terminal_rapporte_sa_liste_blanche_et_l_absence_de_shell():
    section = posture()["sections"]["execution"]

    assert section["shell"] is False
    assert "python3" in section["allowed_commands"]
    assert "bash" not in section["allowed_commands"]


def test_l_exposition_mcp_rapporte_ce_qui_ne_sort_pas():
    section = posture()["sections"]["exposure"]

    assert section["anonymous_calls"] is False
    for retenu in ("terminal", "gui", "screen", "filesystem"):
        assert retenu in section["withheld_tools"]


def test_un_magasin_en_memoire_est_rapporte_comme_une_perte_au_redemarrage(monkeypatch):
    """Le portillon et l'audit en mémoire ne survivent pas, et cela se dit."""
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "in-memory")

    sections = posture()["sections"]

    assert sections["approval"]["persistent"] is False
    assert sections["approval"]["gaps"]
    assert sections["audit"]["gaps"]


def test_l_identite_non_verifiee_reste_rapportee():
    """Une clé prouve une attribution, pas une personne (ADR-010, étape 2)."""
    section = posture()["sections"]["identity"]

    assert any("vérifi" in faille for faille in section["gaps"])


def test_aucune_note_globale_n_est_produite():
    """
    Une note ferait disparaître la faille qui compte derrière la moyenne de
    celles qui ne comptent pas.
    """
    mesure = posture()

    assert mesure["score"] is None
    assert "moyenne" in mesure["score_reason"]


def test_une_section_qui_echoue_est_dite_inconnue_et_non_omise(monkeypatch):
    """Une mesure ratée se dit ; l'omettre la ferait passer pour une garantie."""
    def casse():
        raise RuntimeError("module absent")

    monkeypatch.setitem(
        __import__("src.security.posture", fromlist=["_MESURES"])._MESURES,
        "exposure", casse,
    )

    section = posture()["sections"]["exposure"]

    assert section["state"] == "unknown"
    assert section["gaps"]


def test_le_resume_met_les_failles_en_premier():
    """C'est ce qu'on lit quand on n'a le temps de lire qu'une chose."""
    lignes = summary()

    assert lignes
    assert "non garanti" in lignes[0] or "Aucune faille" in lignes[0]


# ----------------------------------------------------------------------
# 2. Les points de reprise
# ----------------------------------------------------------------------


def test_une_operation_de_fichier_est_un_point_de_reprise_annulable(racine_inscriptible, tmp_path):
    from src.storage.reversible import ReversibleFiles
    from src.storage.roots import declared_roots

    journal = str(tmp_path / "operations.jsonl")
    fichiers = ReversibleFiles(declared_roots(), journal=journal)
    operation = fichiers.move("documents/rapport.pdf", "documents/archive/rapport.pdf",
                              raison="rangement")

    entrees = [
        entree for entree in fichiers.history()
        if entree.id == operation.id
    ]

    assert entrees and entrees[0].undone is False


def test_une_decision_d_approbation_n_est_jamais_reversible():
    """
    Une décision humaine a eu lieu : c'est un fait, pas un état. C'est son
    effet qui se défait, et il apparaît ailleurs dans la liste.
    """
    vue = list_checkpoints()

    decisions = [e for e in vue["checkpoints"] if e["origin"] == "approval"]
    assert all(entree["reversible"] is False for entree in decisions)


def test_il_n_y_a_pas_d_annulation_globale():
    """
    Un bouton unique laisserait croire que l'état de la machine se rembobine,
    alors que la moitié des lignes ne se défont pas.
    """
    vue = list_checkpoints()

    assert vue["global_undo"] is False
    assert "pas d'annulation globale" in vue["note"]


def test_annuler_ce_qui_n_est_pas_une_operation_de_fichier_est_refuse_avec_sa_raison():
    resultat = undo("appr_1234")

    assert resultat["status"] == "refused"
    assert "sauvegarde se restaure" in resultat["reason"]


def test_annuler_une_operation_inconnue_refuse_sans_lever(racine_inscriptible):
    resultat = undo("op_inexistante")

    assert resultat["status"] == "refused"
    assert resultat["reason"]


def test_une_origine_illisible_est_signalee_et_non_tue(monkeypatch):
    """Une origine muette se lirait « rien à défaire », le contraire du vrai."""
    import src.security.checkpoints as module

    def casse(limit):
        raise RuntimeError("journal illisible")

    monkeypatch.setattr(module, "_operations_de_fichiers", casse)

    vue = list_checkpoints()

    assert any(entree["origin"] == "file_operation" for entree in vue["unavailable"])
    assert "checkpoints" in vue


def test_describe_retrouve_un_point_de_reprise_par_identifiant():
    vue = list_checkpoints()
    if not vue["checkpoints"]:
        pytest.skip("Aucun point de reprise sur cette installation.")

    premier = vue["checkpoints"][0]

    assert describe(premier["id"])["id"] == premier["id"]


def test_describe_rend_none_pour_un_identifiant_inconnu():
    assert describe("op_qui_n_existe_pas") is None
