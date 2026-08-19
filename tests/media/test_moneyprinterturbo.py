"""
Tests for the MoneyPrinterTurbo adapter (M06, ADR-030).

Three properties carry these tests, and each one guards a mistake that would be
easy to make and expensive to find.

**It must never be selectable as a video generator.** MoneyPrinterTurbo composes
stock footage; it generates nothing. Declaring `text_to_video` would let a router
pick it for "generate a scene with my friend" and return footage of a stranger —
the silent substitution `src/creative/routing.py` exists to refuse. The task is
`stock_assembly`, and the test asserts the negative as well as the positive.

**It must never return a plausible result.** `generate()` raises, exactly like
`wangp.generate()`, because a placeholder is indistinguishable from a
composition that silently failed.

**It must name every missing condition, not the first.** An operator who fixes
one blocker to discover the next makes three round trips instead of one.
"""

import pytest

from src.media.providers.base import TACHES
from src.media.providers.moneyprinterturbo import (
    BLOCAGES,
    CAPACITE_ATTENDUE,
    NON_INTEGRE,
    VARIABLE_URL,
    VARIABLES_MATERIEL,
    health,
    integration_report,
    is_available,
)
from src.media.providers.moneyprinterturbo import generate as mpt_generate


class TestDeclaration:
    """Ce qui est déclaré décide de ce qu'un routeur peut choisir."""

    def test_la_tache_est_l_assemblage_pas_la_generation(self):
        """Le cœur d'ADR-030 : deux actes, deux noms."""
        assert CAPACITE_ATTENDUE.tasks == frozenset({"stock_assembly"})
        assert "text_to_video" not in CAPACITE_ATTENDUE.tasks, (
            "Déclarer `text_to_video` ferait rendre des rushes d'un inconnu "
            "pour « génère une scène avec mon ami »."
        )

    def test_la_tache_est_bien_declaree_au_vocabulaire(self):
        assert "stock_assembly" in TACHES

    def test_aucun_gpu_n_est_exige(self):
        """Sa seule vraie supériorité ici, et elle se déclare."""
        assert CAPACITE_ATTENDUE.min_vram_gb is None, (
            "`0` laisserait croire qu'un besoin a été mesuré à zéro plutôt "
            "qu'inexistant."
        )
        assert integration_report()["needs_gpu"] is False

    def test_l_invocation_est_par_api(self):
        """`edge-tts` est LGPL-3.0 : lier n'est pas appeler (M03, ADR-024)."""
        assert integration_report()["invocation"] == "API"

    def test_l_etat_d_integration_reprend_le_vocabulaire_existant(self):
        assert NON_INTEGRE == "ADAPTER_ONLY"
        assert integration_report()["integration"] == NON_INTEGRE


class TestSante:
    """Un blocage sans geste de réparation fait chercher au mauvais endroit."""

    def test_les_trois_conditions_sont_rapportees_ensemble(self, monkeypatch):
        monkeypatch.delenv(VARIABLE_URL, raising=False)
        for nom in VARIABLES_MATERIEL:
            monkeypatch.delenv(nom, raising=False)
        etat = health()
        assert etat["available"] is False
        assert set(etat["missing"]) == {"service", "ffmpeg", "material"}

    def test_chaque_manque_porte_son_geste(self):
        for nom, texte in health()["actions"].items():
            assert texte and texte == BLOCAGES[nom]

    def test_declarer_un_service_retire_ce_manque_seul(self, monkeypatch):
        """Les conditions sont indépendantes : en réparer une ne ment pas."""
        monkeypatch.setenv(VARIABLE_URL, "http://localhost:8080")
        etat = health()
        assert "service" not in etat["missing"]
        assert etat["service_declared"] is True
        assert etat["available"] is False, (
            "Un service déclaré ne suffit pas : ffmpeg et le matériel manquent."
        )

    def test_declarer_une_banque_retire_ce_manque_seul(self, monkeypatch):
        monkeypatch.setenv(VARIABLES_MATERIEL[0], "true")
        assert "material" not in health()["missing"]

    def test_le_manque_ffmpeg_est_mesure_pas_suppose(self):
        """La sonde interroge l'outil ; ce dépôt a payé pour l'apprendre."""
        assert "ffmpeg" in health()["missing"]
        assert "n'encode rien" in BLOCAGES["ffmpeg"]

    def test_indisponible_tant_que_tout_n_est_pas_reuni(self):
        assert is_available() is False


class TestRefus:
    """Un bouchon est indiscernable d'une composition qui a échoué."""

    def test_generer_leve_toujours(self):
        with pytest.raises(NotImplementedError) as erreur:
            mpt_generate(request=None, output_path="/tmp/x.mp4")
        assert "ne peut pas servir" in str(erreur.value)

    def test_le_refus_enumere_ce_qui_manque(self):
        with pytest.raises(NotImplementedError) as erreur:
            mpt_generate(request=None, output_path="/tmp/x.mp4")
        message = str(erreur.value)
        for nom in ("service", "ffmpeg", "material"):
            assert nom in message

    def test_meme_tout_configure_rien_n_est_invente(self, monkeypatch):
        """Le chemin d'exécution n'existe pas ; le prétendre serait pire."""
        monkeypatch.setenv(VARIABLE_URL, "http://localhost:8080")
        monkeypatch.setenv(VARIABLES_MATERIEL[0], "true")
        monkeypatch.setattr(
            "src.media.providers.moneyprinterturbo._ffmpeg_utilisable",
            lambda: True)
        assert is_available() is True
        with pytest.raises(NotImplementedError) as erreur:
            mpt_generate(request=None, output_path="/tmp/x.mp4")
        assert "n'est pas écrit" in str(erreur.value)


class TestCeQuIlNEstPas:
    """§23 : ne pas supposer ce qu'il ne fait pas."""

    def test_le_rapport_dit_qu_il_ne_genere_pas(self):
        refus = " ".join(integration_report()["is_not"])
        assert "aucun modèle ne produit de pixel" in refus.lower()

    def test_ni_identite_ni_continuite_ni_camera(self):
        refus = " ".join(integration_report()["is_not"]).lower()
        for absent in ("identité", "continuité", "caméra", "labiale"):
            assert absent in refus

    def test_il_ne_remplace_pas_wangp(self):
        """§21 : le remplacement exige une preuve, et il n'y en a aucune."""
        assert any("wangp" in ligne.lower()
                   for ligne in integration_report()["is_not"])

    def test_les_droits_sur_la_sortie_restent_ouverts(self):
        ouvertes = integration_report()["open_questions"]
        assert "output_rights" in ouvertes
        assert "vendue" in ouvertes["output_rights"]

    def test_la_licence_du_tts_est_nommee(self):
        assert "LGPL-3.0" in integration_report()["open_questions"]["edge_tts_licence"]


def test_wangp_reste_intact():
    """§1 : rien d'existant n'est cassé par l'ajout."""
    from src.media.providers import wangp
    assert wangp.is_available() is False
    # Son exception nommée, pas `Exception` : un refus attrapé au large ne
    # distinguerait pas un refus délibéré d'une faute de frappe dans l'appel.
    with pytest.raises(wangp.WanGPUnavailable):
        wangp.generate(request=None, output_path="/tmp/y.mp4")
