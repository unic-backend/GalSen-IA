"""
Tests de la confidentialité, de la disponibilité et de la tranche verticale
(K07.2, ADR-031 décisions 3 à 5, §22).

Le test qui compte est `test_aucun_artefact_n_est_produit` : la tranche a le
droit de s'arrêter, pas celui de faire croire qu'elle est allée plus loin.
"""

import pytest

from src.creative.canvas.graph import CanvasGraph
from src.creative.canvas.privacy import (
    AUTORITAIRE,
    CONSERVEE,
    DESTINATION_INCONNUE,
    HOTE_TIERS,
    LOCAL_SEULEMENT,
    PrivacyRefused,
    ProviderPrivacyPolicy,
    may_send_personal_reference,
    privacy_report,
    unknown_policy,
)
from src.creative.canvas.readiness import BLOQUE, ETATS, PRET, graph_readiness, node_state
from src.creative.canvas.slice import ETAPES, run_canvas_slice, slice_report
from src.creative.mvp import BLOQUE as MVP_BLOQUE
from src.creative.mvp import OK as MVP_OK
from src.security.trust import TrustLevel


def _chaine() -> CanvasGraph:
    graphe = CanvasGraph()
    graphe.add_node("p", "prompt")
    graphe.add_node("i", "intent")
    graphe.add_node("v", "video_generation")
    graphe.connect("p", "text", "i", "text")
    graphe.connect("i", "intent", "v", "intent")
    return graphe


class TestPolitiqueDeConfidentialite:
    """Le seul type que les audits ont trouvé réellement absent."""

    def test_une_politique_sans_fournisseur_est_refusee(self):
        with pytest.raises(PrivacyRefused, match="ne s'applique"):
            ProviderPrivacyPolicy(provider_id="  ")

    def test_une_destination_non_declaree_est_refusee(self):
        with pytest.raises(PrivacyRefused, match="non déclarée"):
            ProviderPrivacyPolicy(provider_id="x", data_destination="ailleurs")

    def test_un_hote_tiers_sans_nom_est_refuse(self):
        """« ailleurs » n'est pas une réponse."""
        with pytest.raises(PrivacyRefused, match="ne se vérifie pas"):
            ProviderPrivacyPolicy(provider_id="x", data_destination=HOTE_TIERS)

    def test_une_preuve_sans_source_est_refusee(self):
        with pytest.raises(PrivacyRefused, match="ne se recoupe pas"):
            ProviderPrivacyPolicy(provider_id="x", evidence=AUTORITAIRE)

    def test_une_politique_complete_passe(self):
        politique = ProviderPrivacyPolicy(
            provider_id="x", data_destination=HOTE_TIERS, host="api.exemple.ai",
            retention=CONSERVEE, evidence=AUTORITAIRE,
            verified_from="https://exemple.ai/terms")

        assert politique.host == "api.exemple.ai"


class TestConfianceDerivee:
    """ADR-031 décision 3 : la destination décide, pas l'invocation."""

    def test_local_seulement_rend_tool(self):
        politique = ProviderPrivacyPolicy(provider_id="x",
                                          data_destination=LOCAL_SEULEMENT)

        assert politique.trust_level == TrustLevel.TOOL

    def test_un_hote_tiers_rend_external(self):
        politique = ProviderPrivacyPolicy(provider_id="x",
                                          data_destination=HOTE_TIERS,
                                          host="api.exemple.ai")

        assert politique.trust_level == TrustLevel.EXTERNAL

    def test_inconnu_retombe_du_cote_sur(self):
        """UNKNOWN n'est pas une permission : il rend EXTERNAL."""
        assert unknown_policy("x").trust_level == TrustLevel.EXTERNAL

    def test_le_rapport_ecrit_la_correspondance(self):
        correspondance = privacy_report()["trust_mapping"]

        assert correspondance[DESTINATION_INCONNUE] == TrustLevel.EXTERNAL.value
        assert correspondance[LOCAL_SEULEMENT] == TrustLevel.TOOL.value


class TestPorteDesDonneesPersonnelles:
    """Le visage de quelqu'un ne part pas chez un hôte non vérifié."""

    def test_une_destination_inconnue_refuse(self):
        verdict = may_send_personal_reference(unknown_policy("wan2.2"))

        assert verdict["allowed"] is False

    def test_le_refus_nomme_le_geste_qui_le_leve(self):
        verdict = may_send_personal_reference(unknown_policy("wan2.2"))

        assert "conditions" in verdict["reason"]
        assert "socket" in verdict["reason"]

    def test_local_seulement_autorise(self):
        politique = ProviderPrivacyPolicy(provider_id="x",
                                          data_destination=LOCAL_SEULEMENT)

        assert may_send_personal_reference(politique)["allowed"] is True

    def test_un_hote_tiers_sans_accord_explicite_refuse(self):
        politique = ProviderPrivacyPolicy(provider_id="x",
                                          data_destination=HOTE_TIERS,
                                          host="api.exemple.ai")

        assert may_send_personal_reference(politique)["allowed"] is False

    def test_un_hote_tiers_qui_l_accepte_autorise(self):
        politique = ProviderPrivacyPolicy(
            provider_id="x", data_destination=HOTE_TIERS,
            host="api.exemple.ai", accepts_personal_data=True)

        assert may_send_personal_reference(politique)["allowed"] is True


class TestDisponibilite:
    """Nœud par nœud, sans note et sans booléen global."""

    def test_un_noeud_de_generation_est_bloque_ici(self):
        etat = node_state(_chaine(), "v")

        assert etat["state"] == BLOQUE
        assert etat["blocked_by"] != []

    def test_un_noeud_sans_fournisseur_est_pret(self):
        assert node_state(_chaine(), "p")["state"] == PRET

    def test_une_entree_requise_manquante_bloque_en_la_nommant(self):
        graphe = CanvasGraph()
        graphe.add_node("i", "intent")

        etat = node_state(graphe, "i")

        assert etat["state"] == BLOQUE
        assert any("text" in cause for cause in etat["blocked_by"])

    def test_le_graphe_ne_rend_aucune_note(self):
        rapport = graph_readiness(_chaine())

        assert rapport["score"] is None

    def test_le_graphe_ne_rend_aucun_booleen_global(self):
        rapport = graph_readiness(_chaine())

        assert not any(isinstance(v, bool) for v in rapport.values())

    def test_les_comptes_couvrent_les_quatre_etats(self):
        comptes = graph_readiness(_chaine())["counts"]

        assert set(comptes) == set(ETATS)

    def test_les_causes_sont_regroupees(self):
        """Une installation débloque plusieurs nœuds : les causes se comptent
        à part des nœuds."""
        rapport = graph_readiness(_chaine())

        assert len(rapport["blocking_reasons"]) <= rapport["counts"][BLOQUE] + 1


class TestTrancheVerticale:
    """§22 : la plus petite tranche, parcourue, qui rapporte ce qui a eu lieu."""

    def test_les_six_etapes_sont_parcourues(self):
        resultat = run_canvas_slice()

        assert [e["step"] for e in resultat["steps"]] == list(ETAPES)

    def test_aucun_artefact_n_est_produit(self):
        """La tranche a le droit de s'arrêter, pas de le cacher."""
        resultat = run_canvas_slice()

        assert resultat["produced_artifact"] is None

    def test_le_premier_blocage_dur_est_nomme(self):
        resultat = run_canvas_slice()

        assert resultat["first_block"] in ETAPES

    def test_aucun_compte_ne_se_lit_comme_un_succes(self):
        resultat = run_canvas_slice()

        assert "blocked" in resultat["counts"]
        assert resultat["counts"]["blocked"] > 0

    def test_le_plan_est_conforme_a_l_intention(self):
        resultat = run_canvas_slice()
        etape = next(e for e in resultat["steps"] if e["step"] == "shot")

        assert etape["outcome"] == MVP_OK
        assert etape["evidence"]["forbidden_present"] == []

    def test_l_etape_confidentialite_bloque_et_dit_pourquoi(self):
        resultat = run_canvas_slice()
        etape = next(e for e in resultat["steps"] if e["step"] == "privacy")

        assert etape["outcome"] == MVP_BLOQUE
        assert etape["evidence"]["personal_reference_allowed"] is False
        assert etape["evidence"]["trust_level"] == TrustLevel.EXTERNAL.value

    def test_la_remise_au_fournisseur_nomme_ce_qu_elle_ne_porte_pas(self):
        resultat = run_canvas_slice()
        etape = next(e for e in resultat["steps"] if e["step"] == "handover")

        assert "sensor_format" in etape["evidence"]["not_conveyed"]

    def test_le_vocabulaire_est_celui_de_mvp(self):
        """Deux mots pour un même état est la façon dont deux rapports
        finissent par se contredire."""
        rapport = slice_report()

        assert rapport["shares_vocabulary_with"] == "creative/mvp.py"
        assert MVP_OK in rapport["outcomes"]
        assert MVP_BLOQUE in rapport["outcomes"]

    def test_un_plan_qui_ne_repond_pas_a_l_intention_bloque_l_etape(self):
        """Le plan contient un lieu que cette intention n'a pas demandé, et il
        manque le style requis : l'étape le voit et bloque."""
        resultat = run_canvas_slice(required=(("style", "documentaire"),),
                                    forbidden=())
        etape = next(e for e in resultat["steps"] if e["step"] == "shot")

        assert etape["outcome"] == MVP_BLOQUE
        assert etape["evidence"]["verdict"] == "VIOLATES_INTENT"
        assert resultat["first_block"] == "shot"
