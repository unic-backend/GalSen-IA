"""
Tests du pipeline de recherche et du cache (R07.2 et R08, STEP 7, 11, 15).

Les tests qui comptent sont `TestAucuneRequeteElargie` — une question élargie
par la plateforme ramène des sources sur un sujet voisin présentées comme
répondant à la question posée — et `TestAucuneReponseFabriquee`.
"""

import time

import pytest

from src.creative.mvp import BLOQUE, NON_ATTEINT, NON_MESURABLE, OK
from src.research.cache import (
    GENRES,
    ResearchCache,
    ResearchCacheRefused,
    research_key,
)
from src.research.pipeline import (
    ETAPES,
    PipelineRefused,
    generate_queries,
    pipeline_report,
    run_pipeline,
    separation_report,
)
from src.research.routing import INCONNU
from src.research.sources import normalize


def _recherche(_provider, query):
    """Une recherche injectée, déterministe et hors réseau."""
    return [{"url": f"https://exemple.test/{len(query)}", "title": query[:12]}]


class TestAucuneRequeteElargie:
    """La question part telle qu'écrite."""

    def test_sans_facette_il_y_a_une_requete_verbatim(self):
        assert generate_queries("qui a écrit ceci ?") == ["qui a écrit ceci ?"]

    def test_les_facettes_fournies_sont_les_seules_ajoutees(self):
        requetes = generate_queries("galsen ia", ("2026", "sénégal"))

        assert requetes == ["galsen ia", "galsen ia 2026", "galsen ia sénégal"]

    def test_aucun_synonyme_n_est_devine(self):
        requetes = generate_queries("plaquiste")

        assert requetes == ["plaquiste"]

    def test_une_facette_vide_est_ignoree(self):
        assert generate_queries("x", ("", "  ")) == ["x"]

    def test_une_facette_en_double_n_ajoute_rien(self):
        assert generate_queries("x", ("y", "y")) == ["x", "x y"]

    def test_une_question_vide_est_refusee(self):
        with pytest.raises(PipelineRefused, match="ne se planifie pas"):
            generate_queries("   ")


class TestChaineArretee:
    """Le premier blocage dur arrête la chaîne, et la suite le dit."""

    def test_sans_fonction_de_recherche_l_etape_bloque(self):
        resultat = run_pipeline("une question")
        recherche = next(e for e in resultat["steps"] if e["step"] == "search")

        assert recherche["outcome"] == BLOQUE
        assert "ne joint pas le réseau" in recherche["detail"]

    def test_ce_qui_suit_un_blocage_n_est_pas_compte_comme_franchi(self):
        resultat = run_pipeline("une question")

        assert resultat["first_block"] == "search"
        assert resultat["counts"]["not_reached"] >= 7

    def test_les_treize_etapes_sont_toujours_parcourues(self):
        resultat = run_pipeline("une question")

        assert [e["step"] for e in resultat["steps"]] == list(ETAPES)

    def test_un_routage_impossible_n_atteint_pas_la_recherche(self):
        resultat = run_pipeline("une question", capability="academic_search")
        recherche = next(e for e in resultat["steps"] if e["step"] == "search")

        assert recherche["outcome"] == NON_ATTEINT
        assert resultat["first_block"] == "provider_routing"


class TestChaineVivante:
    """Avec une recherche injectée, la chaîne avance et dit où elle s'arrête."""

    def test_les_sources_sont_normalisees(self):
        resultat = run_pipeline("une question", search=_recherche)

        assert len(resultat["sources"]) == 1
        assert resultat["sources"][0]["provider"] == "existing_galsen_research"

    def test_le_recoupement_a_lieu(self):
        resultat = run_pipeline("q", facets=("a", "bb"), search=_recherche)

        assert resultat["corroboration"]["distinct_sources"] == 3

    def test_le_raisonnement_bloque_faute_de_modele(self):
        resultat = run_pipeline("une question", search=_recherche)
        raisonnement = next(e for e in resultat["steps"]
                            if e["step"] == "galsen_reasoning")

        assert raisonnement["outcome"] == BLOQUE
        assert "n'en simule aucun" in raisonnement["detail"]

    def test_la_confiance_n_est_pas_chiffree(self):
        resultat = run_pipeline("une question", search=_recherche)
        confiance = next(e for e in resultat["steps"]
                         if e["step"] == "confidence")

        assert confiance["outcome"] == NON_MESURABLE
        assert confiance["evidence"]["confidence"] is None

    def test_une_recherche_qui_echoue_bloque_sans_lever(self):
        def tombe(_p, _q):
            raise RuntimeError("panne réseau")

        resultat = run_pipeline("une question", search=tombe)
        recherche = next(e for e in resultat["steps"] if e["step"] == "search")

        assert recherche["outcome"] == BLOQUE
        assert "panne réseau" in recherche["detail"]

    def test_un_resultat_sans_url_est_refuse_et_compte(self):
        resultat = run_pipeline("une question",
                                search=lambda p, q: [{"title": "sans url"}])
        normalisation = next(e for e in resultat["steps"]
                             if e["step"] == "source_normalization")

        assert normalisation["outcome"] == BLOQUE
        assert normalisation["evidence"]["refused"]


class TestAucuneReponseFabriquee:
    """Une réponse approchante serait pire que pas de réponse."""

    def test_la_reponse_est_toujours_absente(self):
        assert run_pipeline("q", search=_recherche)["answer"] is None

    def test_le_statut_est_unknown(self):
        assert run_pipeline("q", search=_recherche)["status"] == INCONNU

    def test_l_etape_reponse_n_est_jamais_ok(self):
        resultat = run_pipeline("q", search=_recherche)
        reponse = next(e for e in resultat["steps"] if e["step"] == "answer")

        assert reponse["outcome"] != OK


class TestRienN_EntreDansLaConnaissance:
    """STEP 7 : aucune insertion automatique."""

    def test_la_proposition_est_un_brouillon(self):
        resultat = run_pipeline("q", search=_recherche)

        assert resultat["knowledge_proposal"]["state"] == "DRAFT"
        assert resultat["knowledge_proposal"]["ingested"] is False

    def test_sans_source_il_n_y_a_pas_de_proposition(self):
        assert run_pipeline("q")["knowledge_proposal"] is None


class TestSeparation:
    """STEP 15 : la recherche ne devient pas une instruction créative."""

    def test_les_cinq_activites_restent_separees(self):
        rapport = separation_report()

        assert rapport["separated"] == ["UNDERSTANDING", "RESEARCH", "PLANNING",
                                        "CREATION", "EXECUTION"]

    def test_le_pipeline_ne_rend_jamais_d_intention_creative(self):
        assert "CreativeIntent" in separation_report()["pipeline_never_returns"]

    def test_le_resultat_ne_contient_aucune_intention_creative(self):
        resultat = run_pipeline("q", search=_recherche)

        assert "intent" not in resultat
        assert "creative_intent" not in resultat

    def test_le_vocabulaire_est_celui_de_mvp(self):
        assert pipeline_report()["shares_vocabulary_with"] == "creative/mvp.py"


class TestCleDeCache:
    """Ce que la clé doit distinguer."""

    def test_un_genre_inconnu_est_refuse(self):
        with pytest.raises(ResearchCacheRefused, match="non déclaré"):
            research_key("magie", "p", "web_search", "q")

    def test_une_cle_sans_capacite_est_refusee(self):
        with pytest.raises(ResearchCacheRefused, match="capacité"):
            research_key("search_results", "p", "", "q")

    def test_une_cle_sans_sujet_est_refusee(self):
        with pytest.raises(ResearchCacheRefused, match="ne distingue rien"):
            research_key("search_results", "p", "web_search", "  ")

    def test_deux_capacites_donnent_deux_cles(self):
        a = research_key("search_results", "p", "web_search", "q")
        b = research_key("search_results", "p", "academic_search", "q")

        assert a != b

    def test_deux_versions_donnent_deux_cles(self):
        a = research_key("search_results", "p", "web_search", "q", "1.0")
        b = research_key("search_results", "p", "web_search", "q", "2.0")

        assert a != b

    def test_les_genres_declares_sont_ceux_du_module(self):
        assert "search_results" in GENRES and "fetched_page" in GENRES


class TestFraicheur:
    """Aucune lecture ne rend la valeur sans sa fraîcheur."""

    def test_sans_seuil_la_fraicheur_est_inconnue(self):
        """Ne pas savoir n'est pas être frais."""
        cache = ResearchCache()
        cache.put_results("p", "web_search", "q", [1])

        lecture = cache.lookup("search_results", "p", "web_search", "q")

        assert lecture["hit"] is True
        assert lecture["freshness"] == "UNKNOWN"

    def test_aucun_seuil_n_est_pose_par_defaut(self):
        assert ResearchCache().stale_after_seconds is None

    def test_une_entree_recente_est_fraiche(self):
        cache = ResearchCache(stale_after_seconds=60)
        cache.put_results("p", "web_search", "q", [1])

        assert cache.lookup("search_results", "p", "web_search",
                            "q")["freshness"] == "FRESH"

    def test_une_entree_vieille_est_perimee_et_rendue_quand_meme(self):
        """§54 n'interdit pas de servir du périmé, mais de le taire."""
        cache = ResearchCache(stale_after_seconds=10)
        cache.put_results("p", "web_search", "q", ["valeur"])

        lecture = cache.lookup("search_results", "p", "web_search", "q",
                               now=time.time() + 100)

        assert lecture["freshness"] == "STALE"
        assert lecture["value"] == ["valeur"]

    def test_une_absence_est_un_echec_franc(self):
        assert ResearchCache().lookup("search_results", "p", "web_search",
                                      "absent")["hit"] is False

    def test_une_source_normalisee_se_range_sous_son_url(self):
        cache = ResearchCache()
        source = normalize({"url": "https://exemple.test/a"},
                           "web_search_mcp", "q", "web_page", "0.6.3")

        cache.put_source(source)
        lecture = cache.lookup("normalized_source", "web_search_mcp",
                               "web_page", "https://exemple.test/a", "0.6.3")

        assert lecture["hit"] is True

    def test_l_invalidation_est_un_acte(self):
        cache = ResearchCache()
        cache.put_results("p", "web_search", "q", [1])

        cache.invalidate("search_results", "p", "web_search", "q",
                         by="opérateur", reason="version changée")

        assert cache.lookup("search_results", "p", "web_search",
                            "q")["hit"] is False

    def test_le_rapport_nomme_le_mecanisme_emprunte(self):
        rapport = ResearchCache().report()

        assert rapport["mechanism"] == "creative.cache.CreativeCache"
        assert rapport["kinds"] == list(GENRES)
