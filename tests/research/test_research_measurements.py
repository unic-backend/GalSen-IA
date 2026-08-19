"""
Tests du relevé de mesures (R10, STEP 13 et 14).

Le test qui compte est `test_les_mesures_impossibles_rendent_not_measured` :
une colonne vide qui rend `0` se lit comme une mesure.
"""

from src.research.measurements import (
    NON_MESURE,
    cache_hit_rate,
    machine,
    measurements_report,
    orchestration_overhead,
    transparency_report,
)


class TestMesuresPossibles:
    """Ce qui peut honnêtement être mesuré ici."""

    def test_le_surcout_d_orchestration_est_chiffre(self):
        surcout = orchestration_overhead()

        assert surcout["route_web_search_ms"] > 0
        assert surcout["generate_queries_ms"] >= 0

    def test_toutes_les_operations_declarees_sont_mesurees(self):
        surcout = orchestration_overhead()

        assert len(surcout) == 7
        assert all(isinstance(v, float) for v in surcout.values())

    def test_le_taux_de_cache_est_declare_synthetique(self):
        """Un taux mesuré sur des clés qu'on vient d'écrire ne dit rien de
        l'usage."""
        taux = cache_hit_rate(entries=10)

        assert taux["synthetic"] is True
        assert "synthétique" in taux["note"]

    def test_le_cache_distingue_present_et_absent(self):
        taux = cache_hit_rate(entries=10)

        assert taux["hits_on_written"] == 10
        assert taux["hits_on_absent"] == 0

    def test_la_machine_est_mesuree(self):
        etat = machine()

        assert etat["cpu_cores"] != NON_MESURE
        assert etat["gpu"] == NON_MESURE


class TestMesuresImpossibles:
    """Une mesure impossible rend NOT_MEASURED, jamais zéro."""

    def test_les_mesures_impossibles_rendent_not_measured(self):
        rapport = measurements_report()

        assert rapport["not_measured_count"] == 5
        for entree in rapport["not_measured"]:
            assert entree["state"] == NON_MESURE

    def test_chaque_impossibilite_porte_sa_raison(self):
        for entree in measurements_report()["not_measured"]:
            assert entree["reason"].strip()

    def test_la_latence_de_recherche_n_est_pas_mesuree(self):
        noms = {e["measurement"] for e in measurements_report()["not_measured"]}

        assert "search_latency" in noms
        assert "fallback_rate" in noms

    def test_aucune_amelioration_n_est_revendiquee(self):
        regles = " ".join(measurements_report()["rules"])

        assert "Aucune amélioration" in regles


class TestTransparence:
    """STEP 14 : le fournisseur reste un détail d'implémentation."""

    def test_aucun_point_d_entree_n_expose_un_fournisseur(self):
        rapport = transparency_report()

        assert rapport["provider_is_an_implementation_detail"] is True
        assert rapport["exposing_a_provider"] == {}

    def test_les_trois_points_d_entree_sont_inspectes(self):
        rapport = transparency_report()

        assert set(rapport["entry_points"]) == {
            "run_pipeline", "route", "execute_with_fallback"}

    def test_run_pipeline_prend_une_question_pas_un_fournisseur(self):
        parametres = transparency_report()["entry_points"]["run_pipeline"]

        assert "question" in parametres
        assert "capability" in parametres

    def test_le_fournisseur_retenu_reste_rendu_dans_le_resultat(self):
        """Un détail d'implémentation n'est pas un secret : la provenance en
        a besoin."""
        from src.research.routing import ResearchNeed, route

        assert "provider_id" in route(ResearchNeed("web_search"))
