"""
Tests for the two audio-video architectures (C15 phase 15.2, directive V4 §43).

Two properties carry these tests.

**Neither architecture wins by default.** §43 says not to assume one is
universally superior, so `compare_pipelines` returns `recommended: None` and
`choose_pipeline` refuses to pick when both are feasible and no measured
criterion was given. A default here would install a preference nobody would
ever re-discuss.

**A's audio stage can need no provider at all.** When the person's recording is
kept (§22), there is nothing to generate and nothing to route. Treating audio as
a mandatory-provider stage would declare A blocked where it is not, and push
towards B in exactly the case where B — which regenerates the voice — is the
wrong answer.
"""

import pytest

from src.creative.pipelines import (
    BLOQUE,
    PIPELINE_A,
    PIPELINE_B,
    REALISABLE,
    SANS_FOURNISSEUR,
    PipelineRefused,
    choose_pipeline,
    compare_pipelines,
    pipelines_report,
    plan_pipeline,
)
from src.creative.providers import (
    AUCUN,
    CHOISI,
    CreativeProvider,
    LicenceRecord,
    ProviderRegistry,
)
from src.creative.routing import NON_CLASSE, RoutingRefused


def _fournisseur(identifiant, taches, **champs):
    """Un fournisseur déclaré, licence vérifiée."""
    base = {
        "provider_id": identifiant,
        "tasks": frozenset(taches),
        "input_modalities": ("text", "audio"),
        "output_modalities": ("video",),
        "licence": LicenceRecord(
            repository="MIT", weights="MIT", commercial="ALLOWED",
            verified_from="https://example.invalid/LICENSE"),
        "runs_locally": True,
    }
    base.update(champs)
    return CreativeProvider(**base)


def _registre(*fournisseurs):
    registre = ProviderRegistry()
    for fournisseur in fournisseurs:
        registre.register(fournisseur)
    return registre


def _pour_a(**champs):
    """De quoi rendre l'architecture composée réalisable."""
    return (
        _fournisseur("video", {"text_to_video"}, **champs),
        _fournisseur("levres", {"lip_sync"},
                     capability_status={"lip_sync": "SUPPORTED"}, **champs),
    )


def _pour_b(**champs):
    """De quoi rendre l'architecture native réalisable."""
    return (_fournisseur(
        "natif", {"audio_to_video"},
        capability_status={"audio_output": "SUPPORTED",
                           "lip_sync": "SUPPORTED"},
        **champs),)


class TestPlanification:
    """Chaque architecture dit où elle s'arrête, pas seulement qu'elle s'arrête."""

    def test_l_audio_d_origine_ne_demande_aucun_fournisseur(self):
        """La seule étape qu'une absence de travail satisfait (§22)."""
        plan = plan_pipeline(_registre(*_pour_a()), PIPELINE_A)
        audio = [e for e in plan["stages"] if e["stage"] == "audio"][0]
        assert audio["state"] == SANS_FOURNISSEUR
        assert audio["provider_id"] is None
        assert plan["state"] == REALISABLE

    def test_une_voix_synthetique_demande_un_fournisseur_absent(self):
        """Rien ne fait de la synthèse vocale dans ce dépôt."""
        plan = plan_pipeline(_registre(*_pour_a()), PIPELINE_A,
                             preserve_original_audio=False)
        assert plan["state"] == BLOQUE
        assert plan["first_block"] == "audio"

    def test_la_preservation_est_le_defaut(self):
        assert plan_pipeline(_registre(*_pour_a()),
                             PIPELINE_A)["preserves_original_audio"] is True

    def test_l_architecture_native_ne_preserve_jamais(self):
        """Elle régénère la voix par construction."""
        plan = plan_pipeline(_registre(*_pour_b()), PIPELINE_B)
        assert plan["preserves_original_audio"] is False

    def test_le_premier_blocage_est_nomme(self):
        plan = plan_pipeline(ProviderRegistry(), PIPELINE_A)
        assert plan["state"] == BLOQUE
        assert plan["first_block"] == "video_generation"

    def test_l_architecture_native_exige_une_capacite_audio_declaree(self):
        """Le son produit avec l'image est l'argument de B : il se déclare."""
        muet = _fournisseur("muet", {"audio_to_video"})
        plan = plan_pipeline(_registre(muet), PIPELINE_B,
                             need=None)
        # Rien n'est déclaré : c'est `UNKNOWN`, donc pas un refus.
        assert plan["state"] == REALISABLE
        refus = _fournisseur("refuse", {"audio_to_video"},
                             capability_status={"audio_output": "UNSUPPORTED"})
        assert plan_pipeline(_registre(refus), PIPELINE_B)["state"] == BLOQUE

    def test_sans_synchronisation_l_etape_disparait_de_a(self):
        plan = plan_pipeline(
            _registre(_fournisseur("video", {"text_to_video"})),
            PIPELINE_A, needs_lip_sync=False)
        assert [e["stage"] for e in plan["stages"]] == ["video_generation",
                                                        "audio"]
        assert plan["state"] == REALISABLE

    def test_une_architecture_inconnue_est_refusee(self):
        with pytest.raises(PipelineRefused):
            plan_pipeline(ProviderRegistry(), "MAGIE")


class TestComparaison:
    """§43 : ne pas supposer qu'une architecture est supérieure."""

    def test_aucune_n_est_recommandee(self):
        comparaison = compare_pipelines(
            _registre(*_pour_a(), *_pour_b()))
        assert comparaison["feasible"] == [PIPELINE_A, PIPELINE_B]
        assert comparaison["recommended"] is None

    def test_la_difference_decisive_est_ecrite(self):
        difference = compare_pipelines(ProviderRegistry())["decisive_difference"]
        assert "conserver l'enregistrement" in difference[PIPELINE_A]
        assert "Régénère la voix" in difference[PIPELINE_B]

    def test_les_deux_plans_sont_rendus_meme_bloques(self):
        comparaison = compare_pipelines(ProviderRegistry())
        assert set(comparaison["plans"]) == {PIPELINE_A, PIPELINE_B}
        assert comparaison["feasible"] == []


class TestChoix:
    """Un choix n'a lieu que sur un critère mesuré."""

    def test_sans_critere_aucune_n_est_retenue(self):
        resultat = choose_pipeline(_registre(*_pour_a(), *_pour_b()))
        assert resultat["status"] == NON_CLASSE
        assert resultat["pipeline"] is None
        assert "supériorité universelle" in resultat["reason"]

    def test_une_seule_realisable_est_retenue_sans_critere(self):
        resultat = choose_pipeline(_registre(*_pour_b()))
        assert resultat["status"] == CHOISI
        assert resultat["pipeline"] == PIPELINE_B
        assert "rien à départager" in resultat["reason"]

    def test_aucune_realisable_dit_ou_chacune_s_arrete(self):
        resultat = choose_pipeline(ProviderRegistry())
        assert resultat["status"] == AUCUN
        for plan in resultat["comparison"]["plans"].values():
            assert plan["first_block"]

    def test_un_critere_mesure_departage(self):
        resultat = choose_pipeline(
            _registre(*_pour_a(cost_per_second=0.1),
                      *_pour_b(cost_per_second=0.9)),
            by="cost_per_second")
        # A : 0,1 (vidéo) + 0 (audio d'origine) + 0,1 (lèvres) = 0,2 < 0,9
        assert resultat["pipeline"] == PIPELINE_A
        assert resultat["totals"][PIPELINE_A] == pytest.approx(0.2)

    def test_une_etape_sans_chiffre_annule_le_departage(self):
        """Sommer ce qui existe ferait gagner la moins documentée."""
        resultat = choose_pipeline(
            _registre(_fournisseur("video", {"text_to_video"},
                                   cost_per_second=0.1),
                      _fournisseur("levres", {"lip_sync"},
                                   capability_status={"lip_sync": "SUPPORTED"}),
                      *_pour_b(cost_per_second=0.9)),
            by="cost_per_second")
        assert resultat["status"] == NON_CLASSE
        assert resultat["missing"] == [PIPELINE_A]

    def test_la_qualite_ne_departage_pas(self):
        with pytest.raises(RoutingRefused):
            choose_pipeline(_registre(*_pour_a(), *_pour_b()), by="quality")


class TestRapport:
    """Les règles se lisent sans lire le code."""

    def test_l_asymetrie_de_l_audio_est_nommee(self):
        regles = " ".join(pipelines_report()["rules"])
        assert "sans fournisseur" in regles
        assert "mauvais choix" in regles

    def test_les_trois_etats_sont_declares(self):
        assert set(pipelines_report()["states"]) == {
            REALISABLE, BLOQUE, SANS_FOURNISSEUR}
