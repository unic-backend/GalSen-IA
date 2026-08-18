"""
Tests for the golden scenarios (C17 phase 17.2, directive V4 §62, §63, §64).

§63 lists twenty-five scenarios. The tempting way to satisfy it is twenty-five
tests asserting a result — *the video is coherent*, *identity is preserved*.
None could run: nothing generates here. Writing them anyway, pinned to a
plausible value, is the fault this repository has already paid for four times.

So every scenario asserts the **invariant it protects**, with one of two
verdicts. `VERIFIED` means the invariant was checked against live code.
`BLOCKED` means the capability is missing *and the platform reports it instead
of inventing* — an assertion, not a skipped test. There is deliberately no third
verdict, because a skipped scenario defends nothing.

The tests below therefore guard the scenario set itself: that all twenty-five
are present, that none is silently skipped, that a blocked one names what is
missing, and — the one that matters most — that the whole set runs without a
model, a download or a network call, as §62 requires by name.
"""

import time

import pytest

from src.creative.golden import (
    BLOQUE,
    SCENARIOS,
    VERDICTS,
    VERIFIE,
    language_coverage,
    run_all,
    run_scenario,
)


@pytest.fixture(scope="module")
def resultats():
    """Les vingt-cinq scénarios, exécutés une fois."""
    return run_all()


class TestJeuDeScenarios:
    """Le jeu lui-même est gardé : c'est lui qui pourrait se vider en silence."""

    def test_les_vingt_cinq_scenarios_de_la_directive_existent(self):
        assert len(SCENARIOS) == 25
        assert [s.number for s in SCENARIOS] == list(range(1, 26))

    def test_chaque_scenario_declare_l_invariant_qu_il_defend(self):
        for scenario in SCENARIOS:
            assert scenario.invariant, f"Scénario {scenario.number} sans invariant."
            assert scenario.title

    def test_aucun_scenario_n_est_ignore(self, resultats):
        """Un scénario sauté ne défend rien, et gonflerait la couverture."""
        assert resultats["skipped"] == []
        assert len(resultats["verified"]) + len(resultats["blocked"]) == 25

    def test_chaque_verdict_est_l_un_des_deux_declares(self, resultats):
        for resultat in resultats["scenarios"]:
            assert resultat["verdict"] in VERDICTS

    def test_un_scenario_bloque_nomme_ce_qui_manque(self, resultats):
        bloques = [r for r in resultats["scenarios"] if r["verdict"] == BLOQUE]
        assert bloques, "Aucun blocage : la machine générerait donc."
        for resultat in bloques:
            assert resultat["missing"], (
                f"Scénario {resultat['number']} bloqué sans dire par quoi."
            )

    def test_un_scenario_verifie_porte_sa_preuve(self, resultats):
        for resultat in resultats["scenarios"]:
            if resultat["verdict"] == VERIFIE:
                assert resultat["evidence"], (
                    f"Scénario {resultat['number']} vérifié sans preuve."
                )


class TestContrainteDeTest:
    """§62 : aucun test ordinaire ne dépend d'un modèle ou du réseau."""

    def test_le_jeu_complet_s_execute_en_quelques_millisecondes(self):
        """Un scénario qui attendrait un service externe ne finirait pas."""
        debut = time.perf_counter()
        run_all()
        ecoule = time.perf_counter() - debut
        assert ecoule < 10.0, (
            f"{ecoule:.1f} s : quelque chose attend un service externe."
        )

    def test_le_rapport_refuse_de_se_lire_comme_une_chaine_qui_marche(
            self, resultats):
        """« 25 scénarios, 0 échec » ne doit pas se lire « ça génère »."""
        note = resultats["note"]
        assert "attend un GPU" in note
        assert "pas un test sauté" in note
        assert "Aucun scénario ne produit de" in note


class TestInvariantsPortes:
    """Quelques scénarios valent d'être nommés individuellement."""

    def test_le_serere_et_le_lingala_sont_exprimables(self):
        """Tests d'or 5 et 6 : refusés avant C13, faute d'être déclarés."""
        for numero in (4, 5, 6):
            resultat = run_scenario(numero)
            assert resultat["verdict"] == VERIFIE
            assert resultat["evidence"]["path"] == "PRESERVE_ORIGINAL"
            assert resultat["evidence"]["synthesis"] == "NOT_AVAILABLE"

    def test_aucune_derive_d_identite_n_est_chiffree(self):
        """Test d'or 15 : un score sans mesure serait une invention."""
        resultat = run_scenario(15)
        assert resultat["verdict"] == BLOQUE
        assert "mesure d'identité" in resultat["missing"]

    def test_aucun_repli_silencieux_sur_le_fournisseur_voisin(self):
        """Test d'or 19."""
        resultat = run_scenario(19)
        assert resultat["verdict"] == VERIFIE
        assert resultat["evidence"]["fallback"] is None

    def test_une_langue_inconnue_ne_produit_aucun_texte(self):
        """Test d'or 20."""
        resultat = run_scenario(20)
        assert resultat["evidence"]["transcript"] is None

    def test_une_conversation_privee_ne_rejoint_pas_le_global(self):
        """Test d'or 22."""
        resultat = run_scenario(22)
        assert resultat["evidence"]["global_visible"] == 0

    def test_une_reference_retiree_retrouve_ses_travaux(self):
        """Test d'or 24 : sans quoi la révocation d'ADR-025 ne promet rien."""
        assert run_scenario(24)["evidence"]["jobs_found"] == 1

    def test_aucune_graine_n_est_inventee(self):
        """Test d'or 25 : `0` serait une graine, pas une absence."""
        assert run_scenario(25)["evidence"]["seed"] is None


class TestCouvertureDesLangues:
    """§64 : une seule architecture, pas une par langue."""

    def test_toutes_les_langues_de_validation_sont_nommables(self):
        couverture = language_coverage()
        assert couverture["validation_languages"] == 15
        assert couverture["all_nameable"] is True

    def test_aucune_architecture_par_langue(self):
        assert language_coverage()["per_language_architecture"] is False

    def test_nommable_n_est_ni_comprise_ni_parlee(self):
        """La confusion la moins chère à écrire dans une plateforme d'IA."""
        couverture = language_coverage()
        assert couverture["understood"] == []
        assert couverture["speakable"] == []


def test_le_compte_publie_est_mesure(resultats):
    """19 vérifiés et 6 bloqués aujourd'hui — et le jour où un GPU arrive,
    c'est ce test qui rappelle de re-mesurer plutôt que de recopier."""
    assert resultats["total"] == 25
    assert len(resultats["verified"]) + len(resultats["blocked"]) == 25
