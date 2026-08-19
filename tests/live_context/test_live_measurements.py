"""
Tests des mesures (L15.1, ADR-033, §33 et §45).

Le test qui compte est `test_aucune_latence_live_ne_vaut_zero` : zéro
affirmerait l'instantanéité, ce qui est exactement la prétention que §33
interdit.

**Aucun test n'épingle une durée.** Une assertion du genre « moins de 1 ms »
échouerait sur une machine chargée, et serait affaiblie plutôt que corrigée le
jour où elle échoue.
"""

from src.live_context.measurements import (
    LATENCES_IMPOSSIBLES,
    NON_MESURE,
    live_latencies,
    machine,
    measured_summary,
    measurements_report,
    realtime_claim,
    representation_cost,
)


class TestLatencesNonMesurees:
    """`None` dit que personne n'a mesuré ; zéro affirmerait l'instantanéité."""

    def test_aucune_latence_live_ne_vaut_zero(self):
        for mesure in live_latencies().values():
            assert mesure["value"] is None
            assert mesure["value"] != 0

    def test_chaque_latence_absente_porte_sa_raison(self):
        for mesure in live_latencies().values():
            assert mesure["state"] == NON_MESURE
            assert mesure["reason"].strip()

    def test_les_sept_latences_du_paragraphe_33_sont_nommees(self):
        assert set(live_latencies()) == set(LATENCES_IMPOSSIBLES)
        assert len(LATENCES_IMPOSSIBLES) == 6

    def test_la_latence_de_bout_en_bout_renvoie_a_la_chaine(self):
        raison = live_latencies()["end_to_end_latency_ms"]["reason"]

        assert "readiness" in raison


class TestCoutDeLaRepresentation:
    """Le coût de décider, pas celui de percevoir."""

    def test_chaque_operation_rend_une_duree(self):
        couts = representation_cost()

        assert couts
        for duree in couts.values():
            assert isinstance(duree, float)
            assert duree >= 0

    def test_les_operations_mesurees_sont_celles_de_la_representation(self):
        couts = representation_cost()

        assert "fuse_one_stream_ms" in couts
        assert "authorize_act_ms" in couts
        assert not any("transcription" in nom for nom in couts)

    def test_la_mesure_est_reproductible(self):
        """Deux appels rendent les mêmes clés, pas forcément les mêmes durées."""
        assert set(representation_cost()) == set(representation_cost())

    def test_le_rapport_compte_ce_qui_est_mesure_et_ce_qui_ne_l_est_pas(self):
        rapport = measurements_report()

        assert rapport["measured_count"] == len(representation_cost())
        assert rapport["not_measured_count"] == len(LATENCES_IMPOSSIBLES)


class TestAucunePretentionAuTempsReel:
    """Ni oui ni non."""

    def test_le_temps_reel_n_est_ni_affirme_ni_nie(self):
        revendication = realtime_claim()

        assert revendication["is_realtime"] is None
        assert revendication["state"] == NON_MESURE

    def test_ce_qui_trancherait_est_nomme(self):
        revendication = realtime_claim()

        assert len(revendication["what_would_settle_it"]) >= 3
        for element in revendication["what_would_settle_it"]:
            assert element.strip()

    def test_la_revendication_cite_l_etat_de_la_chaine(self):
        from src.live_context.readiness import readiness

        assert realtime_claim()["readiness_verdict"] == readiness()["state"]


class TestMachine:
    """Un chiffre sans la machine qui l'a produit ne se compare à rien."""

    def test_la_machine_est_rendue_avec_les_chiffres(self):
        details = machine()

        assert details["system"]
        assert details["python"]
        assert details["measured_at"] > 0

    def test_le_rapport_porte_la_machine(self):
        assert "machine" in measurements_report()


class TestResume:
    """Trois lignes, pour un rapport qui n'a pas la place du reste."""

    def test_le_resume_tient_en_trois_lignes(self):
        assert len(measured_summary()) == 3

    def test_le_resume_nomme_l_operation_la_plus_chere(self):
        resume = measured_summary()[0]

        assert "ms" in resume
        assert any(nom in resume for nom in representation_cost())

    def test_le_resume_ne_pretend_pas_au_temps_reel(self):
        assert "Aucune prétention au temps réel" in measured_summary()[2]

    def test_les_regles_qui_comptent_sont_ecrites(self):
        regles = " ".join(measurements_report()["rules"])

        assert "zéro affirmerait" in regles
        assert "n'est pas le goulot" in regles
