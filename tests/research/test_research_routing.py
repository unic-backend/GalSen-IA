"""
Tests du routage de recherche et de son repli (R05, STEP 5).

Les tests qui comptent sont `TestTroisRefusDistincts` — installer un paquet ne
lève pas un refus juridique — et `TestAucuneSubstitution`, qui vérifie que le
repli change de fournisseur et jamais de capacité.
"""

import pytest

from src.research.providers import DISPONIBLE
from src.research.routing import (
    AUCUN_FOURNISSEUR,
    CHOISI,
    INCONNU,
    ISSUES,
    NON_VERIFIABLE,
    REFUSE,
    TOUS_BLOQUES,
    ResearchNeed,
    RoutingRefused,
    declared_capabilities,
    execute_with_fallback,
    route,
    routing_report,
)


class TestDemande:
    """Ce qui est refusé à la construction d'une demande."""

    def test_une_capacite_inventee_est_refusee(self):
        """Sinon « aucun fournisseur » masquerait une faute dans la demande."""
        with pytest.raises(RoutingRefused, match="non déclarée"):
            ResearchNeed(capability="telepathie")

    def test_une_latence_maximale_negative_est_refusee(self):
        with pytest.raises(RoutingRefused, match="impossible"):
            ResearchNeed(capability="web_search", max_latency_ms=-1)

    def test_une_demande_minimale_suffit(self):
        besoin = ResearchNeed(capability="web_search")

        assert besoin.commercial is False
        assert besoin.allow_hosted_services is True


class TestRoutage:
    """Ce que le routeur choisit, et ce qu'il rend en cas d'échec."""

    def test_la_recherche_web_est_servie_par_la_plateforme(self):
        decision = route(ResearchNeed("web_search"))

        assert decision["decision"] == CHOISI
        assert decision["provider_id"] == "existing_galsen_research"

    def test_chaque_candidat_examine_est_rendu(self):
        """Ne rendre que le gagnant empêche de comprendre les perdants."""
        decision = route(ResearchNeed("web_search"))

        assert len(decision["considered"]) == 3
        assert all("refusals" in e for e in decision["considered"])

    def test_l_ordre_est_declare_comme_etant_celui_de_declaration(self):
        assert route(ResearchNeed("web_search"))["ordering"] == "declaration"

    def test_le_plan_de_repli_contient_les_admis(self):
        plan = route(ResearchNeed("web_search"))["plan"]

        assert plan[0] == "existing_galsen_research"


class TestTroisRefusDistincts:
    """Trois refus, parce qu'ils ne se corrigent pas de la même façon."""

    def test_une_capacite_que_personne_ne_sert_rend_no_provider(self, monkeypatch):
        import src.research.routing as routage

        monkeypatch.setattr(routage, "providers_serving", lambda c: [])
        decision = routage.route(ResearchNeed("academic_search"))

        assert decision["decision"] == AUCUN_FOURNISSEUR
        assert decision["plan"] == []

    def test_une_capacite_declaree_mais_non_installee_rend_all_blocked(self):
        """arXiv n'est servi que par un candidat, et il n'est pas installé."""
        decision = route(ResearchNeed("academic_search"))

        assert decision["decision"] == TOUS_BLOQUES
        assert decision["considered"]

    def test_une_regle_qui_interdit_rend_refused(self):
        """Installer quelque chose ne lèvera pas ce refus."""
        decision = route(ResearchNeed("web_search", carries_personal_data=True))

        assert decision["decision"] == REFUSE

    def test_les_trois_refus_ne_disent_pas_la_meme_chose(self):
        bloque = route(ResearchNeed("academic_search"))
        refuse = route(ResearchNeed("web_search", carries_personal_data=True))

        assert bloque["decision"] != refuse["decision"]
        assert bloque["reason"] != refuse["reason"]

    def test_aucune_capacite_voisine_n_est_proposee(self, monkeypatch):
        import src.research.routing as routage

        monkeypatch.setattr(routage, "providers_serving", lambda c: [])
        decision = routage.route(ResearchNeed("academic_search"))

        assert "voisine" in decision["reason"]
        assert decision["provider_id"] is None


class TestRegles:
    """Commercial, données personnelles, services hébergés."""

    def test_une_demande_commerciale_ecarte_un_droit_non_etabli(self):
        decision = route(ResearchNeed("reddit_search", commercial=True))
        motifs = [r["criterion"] for e in decision["considered"]
                  for r in e["refusals"]]

        assert "commercial" in motifs

    def test_une_donnee_personnelle_vers_une_destination_inconnue_est_refusee(self):
        decision = route(ResearchNeed("web_search", carries_personal_data=True))
        motifs = [r["criterion"] for e in decision["considered"]
                  for r in e["refusals"]]

        assert "personal_data" in motifs

    def test_exclure_les_services_heberges_ecarte_meme_le_fournisseur_interne(self):
        """La recherche web de la plateforme atteint duckduckgo.com."""
        decision = route(ResearchNeed("web_search", allow_hosted_services=False))

        assert decision["decision"] == REFUSE


class TestCritereNonVerifiable:
    """UNKNOWN n'est pas UNMET — la règle centrale."""

    def test_une_latence_non_mesuree_n_ecarte_pas(self):
        decision = route(ResearchNeed("web_search", max_latency_ms=100))

        assert decision["decision"] == CHOISI

    def test_une_latence_non_mesuree_est_rapportee(self):
        decision = route(ResearchNeed("web_search", max_latency_ms=100))
        retenu = next(e for e in decision["considered"]
                      if e["provider_id"] == decision["provider_id"])

        assert retenu["unverifiable"]
        assert retenu["unverifiable"][0]["verdict"] == NON_VERIFIABLE

    def test_non_mesure_n_est_pas_lent(self):
        decision = route(ResearchNeed("web_search", max_latency_ms=1))
        retenu = next(e for e in decision["considered"]
                      if e["provider_id"] == decision["provider_id"])

        assert retenu["admitted"] is True
        assert "pas lent" in retenu["unverifiable"][0]["reason"]

    def test_refus_et_non_verifiables_sont_deux_listes(self):
        decision = route(ResearchNeed("academic_search", max_latency_ms=100))

        for examen in decision["considered"]:
            assert "refusals" in examen and "unverifiable" in examen


class TestAucuneSubstitution:
    """Le repli change de fournisseur, jamais de capacité."""

    def test_tous_les_fournisseurs_en_echec_rendent_unknown(self):
        def tombe(_):
            raise RuntimeError("panne")

        resultat = execute_with_fallback(ResearchNeed("web_search"), tombe)

        assert resultat["status"] == INCONNU
        assert resultat["result"] is None

    def test_l_echec_de_chaque_essai_est_conserve(self):
        def tombe(_):
            raise RuntimeError("panne")

        resultat = execute_with_fallback(ResearchNeed("web_search"), tombe)

        assert resultat["attempts"]
        assert all(a["ok"] is False for a in resultat["attempts"])
        assert "panne" in resultat["attempts"][0]["error"]

    def test_un_essai_reussi_nomme_son_fournisseur(self):
        resultat = execute_with_fallback(
            ResearchNeed("web_search"), lambda p: f"servi par {p.provider_id}")

        assert resultat["status"] == CHOISI
        assert resultat["served_by"] == "existing_galsen_research"
        assert "servi par" in resultat["result"]

    def test_un_echec_precedent_reste_visible_apres_un_succes(self):
        """Savoir que le premier est tombé est ce qui permet de le réparer."""
        appels = {"n": 0}

        def une_fois_sur_deux(fournisseur):
            appels["n"] += 1
            if appels["n"] == 1:
                raise RuntimeError("première panne")
            return "ok"

        import src.research.routing as routage
        besoin = ResearchNeed("web_search")
        decision = routage.route(besoin)
        if len(decision["plan"]) < 2:
            pytest.skip("un seul fournisseur admis : le repli n'est pas "
                        "testable de bout en bout aujourd'hui")
        resultat = routage.execute_with_fallback(besoin, une_fois_sur_deux)

        assert resultat["status"] == CHOISI
        assert resultat["attempts"][0]["ok"] is False

    def test_un_routage_impossible_rend_unknown_sans_essayer(self):
        appelé = {"oui": False}

        def ne_doit_pas_etre_appele(_):
            appelé["oui"] = True
            return "x"

        resultat = execute_with_fallback(ResearchNeed("academic_search"),
                                         ne_doit_pas_etre_appele)

        assert resultat["status"] == INCONNU
        assert appelé["oui"] is False


class TestRapport:
    """Le rapport dit ce qui est tenu, et ce qui est mesuré aujourd'hui."""

    def test_le_rapport_couvre_toutes_les_capacites(self):
        rapport = routing_report()

        assert set(rapport["by_capability"]) == set(declared_capabilities())

    def test_la_plupart_des_capacites_sont_bloquees_ici(self):
        decisions = [v["decision"]
                     for v in routing_report()["by_capability"].values()]

        assert decisions.count(TOUS_BLOQUES) >= 8
        assert decisions.count(CHOISI) >= 1

    def test_aucun_critere_n_est_classable_aujourd_hui(self):
        assert routing_report()["rankable_criteria"] == []

    def test_le_vocabulaire_est_celui_declare(self):
        assert routing_report()["outcomes"] == list(ISSUES)
        assert routing_report()["unverified_result"] == INCONNU

    def test_le_fournisseur_interne_est_le_seul_disponible(self):
        decision = route(ResearchNeed("web_search"))
        disponibles = [e["provider_id"] for e in decision["considered"]
                       if e["health_state"] == DISPONIBLE]

        assert disponibles == ["existing_galsen_research"]
