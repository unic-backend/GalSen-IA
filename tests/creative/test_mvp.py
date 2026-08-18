"""
Tests for the vertical slice (C17 phase 17.3, directive V4 §65, §66, §72).

The slice walks §65's thirteen stages and reports what actually happened. Two
properties are what these tests defend, and both are about a count that could
quietly start lying.

**The final count cannot read as a success.** Seven stages happen, six do not,
and `produced_video` is False. A slice that reported "13/13 stages walked" would
be true and misleading; a slice that dropped the unreached stages from the total
would be neither.

**Nothing is invented for a stage the caller did not feed.** No audio means no
transcript and no speakers — not an empty scene that looks processed. No speaker
mapping means the unassigned speakers are *named*, never attached to the nearest
entity.
"""

import pytest

from src.creative.mvp import (
    BLOQUE,
    ETAPES,
    ISSUES,
    NON_ATTEINT,
    NON_MESURABLE,
    OK,
    run_slice,
    slice_report,
)
from src.creative.voice.scene import AudioSegment


def _segments():
    """Une alternance wolof → français chez un même locuteur."""
    return [
        AudioSegment("s1", 0.0, 2.0, "/tmp/a.wav", language="wo",
                     language_confidence=0.9, speaker_id="sp1"),
        AudioSegment("s2", 2.0, 3.0, "/tmp/a.wav", language="fr",
                     language_confidence=0.9, speaker_id="sp1"),
    ]


@pytest.fixture(scope="module")
def tranche():
    """La tranche complète, exécutée une fois avec voix et référence."""
    return run_slice("une scène dans une boutique à Dakar",
                     audio_segments=_segments(), references={"sp1": "awa"})


class TestParcours:
    """Les treize étapes de §65, toutes parcourues, aucune sautée."""

    def test_les_treize_etapes_sont_parcourues(self, tranche):
        assert [e["stage"] for e in tranche["stages"]] == list(ETAPES)
        assert tranche["total"] == 13

    def test_chaque_issue_est_l_une_des_quatre_declarees(self, tranche):
        for etape in tranche["stages"]:
            assert etape["outcome"] in ISSUES

    def test_chaque_etape_dit_ce_qui_s_est_passe(self, tranche):
        for etape in tranche["stages"]:
            assert etape["detail"], f"{etape['stage']} sans explication."

    def test_les_six_premieres_etapes_aboutissent(self, tranche):
        """Toute l'orchestration est en place ; c'est la génération qui manque."""
        debut = tranche["stages"][:6]
        assert all(e["outcome"] == OK for e in debut), (
            f"Orchestration incomplète : {[e['stage'] for e in debut if e['outcome'] != OK]}"
        )


class TestStyle:
    """§46 : le style est posé s'il est nommé, jamais choisi sinon."""

    def test_un_style_nomme_traverse_la_tranche(self):
        etape = run_slice("une scène en style anime")["stages"][0]
        assert etape["evidence"]["style"] == "anime"

    def test_sans_style_nomme_aucun_n_est_choisi(self):
        etape = run_slice("une scène à Dakar")["stages"][0]
        assert etape["evidence"]["style"] is None


class TestLeCompteNePeutPasMentir:
    """Un compte final lisible comme un succès serait le vrai défaut."""

    def test_aucune_video_n_est_produite(self, tranche):
        assert tranche["produced_video"] is False

    def test_la_video_finale_figure_dans_le_total(self, tranche):
        """La retirer du total ferait paraître la chaîne complète."""
        finale = tranche["stages"][-1]
        assert finale["stage"] == "final_video"
        assert finale["outcome"] == NON_ATTEINT

    def test_les_etapes_non_atteintes_ne_sont_pas_comptees_comme_franchies(
            self, tranche):
        comptes = tranche["counts"]
        assert comptes[OK] < tranche["total"]
        assert comptes[NON_ATTEINT] > 0

    def test_la_note_dit_que_rien_n_a_ete_simule(self, tranche):
        assert "aucune n'a été simulée" in tranche["note"]

    def test_le_premier_blocage_dur_est_nomme(self, tranche):
        assert tranche["first_hard_block"] == "video_generation"


class TestRienNEstInvente:
    """Ce que l'appelant n'a pas fourni reste vide, et l'étape le dit."""

    def test_sans_audio_la_voix_est_bloquee_pas_vide(self):
        tranche = run_slice("une scène")
        voix = [e for e in tranche["stages"]
                if e["stage"] == "voice_understanding"][0]
        assert voix["outcome"] == BLOQUE
        assert "rien ici ne peut en produire" in voix["detail"]

    def test_sans_audio_il_n_y_a_rien_a_preserver(self):
        tranche = run_slice("une scène")
        audio = [e for e in tranche["stages"]
                 if e["stage"] == "original_audio"][0]
        assert audio["outcome"] == NON_ATTEINT

    def test_un_locuteur_sans_entite_est_nomme_pas_rattache(self):
        """Le rattacher au plus proche inventerait une identité."""
        tranche = run_slice("une scène", audio_segments=_segments())
        mise_en_correspondance = [e for e in tranche["stages"]
                                  if e["stage"] == "reference_entity_mapping"][0]
        assert mise_en_correspondance["evidence"]["unassigned"] == ["sp1"]

    def test_l_audio_d_origine_ne_depend_d_aucun_fournisseur(self, tranche):
        """La seule étape qu'une absence de travail satisfait (§22)."""
        audio = [e for e in tranche["stages"]
                 if e["stage"] == "original_audio"][0]
        assert audio["outcome"] == OK
        assert audio["evidence"]["path"] == "PRESERVE_ORIGINAL"

    def test_l_identite_n_est_pas_notee_faute_de_mesure(self, tranche):
        verification = [e for e in tranche["stages"]
                        if e["stage"] == "identity_verification"][0]
        assert verification["outcome"] == NON_MESURABLE
        assert verification["evidence"]["not_measurable"] > 0

    def test_la_continuite_sans_plans_rendus_n_est_pas_un_pass(self, tranche):
        continuite = [e for e in tranche["stages"]
                      if e["stage"] == "continuity"][0]
        assert continuite["outcome"] == NON_MESURABLE
        assert "jamais un `PASS` par défaut" in continuite["detail"]


class TestRapport:
    """Ce que la tranche refuse est lisible sans l'exécuter."""

    def test_les_refus_sont_ecrits(self):
        refus = " ".join(slice_report()["refuses"])
        assert "Sauter une étape bloquée" in refus
        assert "se lire comme un succès" in refus

    def test_le_scenario_de_la_directive_est_situe(self):
        """§66 : ce qui relève de l'orchestration, et ce qui attend un GPU."""
        assert "attend un GPU" in slice_report()["note"]


def test_la_tranche_ne_depend_d_aucun_service_externe():
    """§62 : aucun test ordinaire n'attend un modèle ou le réseau."""
    import time
    debut = time.perf_counter()
    run_slice("une scène", audio_segments=_segments())
    assert time.perf_counter() - debut < 10.0
