"""
Tests de la couverture, de la corroboration et de l'état mesuré des flux
(L06.2, ADR-033 décision 3, §13).

Le test qui compte est `test_les_valeurs_ne_sont_pas_classees_par_nombre` :
classer par nombre de voix serait arbitrer sans le dire, et personne ne le
verrait.

**Aucun test n'épingle les capacités de cette machine.** Ce qui est vérifié est
la cohérence entre les modalités mesurées et les verdicts rendus.
"""

import src.live_context.capture as capture
from src.live_context.fusion import (
    FLUX,
    corroboration,
    fuse,
    fusion_report,
    stream_coverage,
    streams_possible_here,
)
from src.live_context.state import MESURE, LiveContextState, Observation, unknown


def _obs(**kwargs) -> Observation:
    defauts = dict(subject="speaker", status=MESURE, modality="audio",
                   value="SPEAKER_01")
    defauts.update(kwargs)
    return Observation(**defauts)


class TestCouverture:
    """Ce que chaque flux a apporté — sans score."""

    def test_les_neuf_flux_sont_rendus(self):
        assert set(stream_coverage({})["streams"]) == set(FLUX)

    def test_un_flux_ayant_apporte_est_couvert(self):
        couverture = stream_coverage({"audio": [_obs()]})["streams"]

        assert couverture["audio"]["covered"] is True
        assert couverture["audio"]["subjects"] == ["speaker"]

    def test_un_flux_muet_porte_sa_raison(self):
        couverture = stream_coverage({"screen": []})["streams"]

        assert couverture["screen"]["covered"] is False
        assert couverture["screen"]["reason"].strip()

    def test_non_branche_et_branche_muet_donnent_deux_raisons(self):
        couverture = stream_coverage({"screen": []})["streams"]

        assert couverture["screen"]["reason"] != couverture["audio"]["reason"]

    def test_aucun_score_de_couverture(self):
        couverture = stream_coverage({"audio": [_obs()]})

        assert couverture["score"] is None
        assert couverture["covered_count"] == 1
        assert couverture["declared_count"] == 9

    def test_la_couverture_ne_se_lit_pas_sur_l_etat_fusionne(self):
        """Déduire le flux d'une modalité attribuerait une transcription à `audio`."""
        contributions = {"transcript": [_obs(subject="line", modality="audio",
                                             value="bonjour")]}

        couverture = stream_coverage(contributions)["streams"]

        assert couverture["transcript"]["covered"] is True
        assert couverture["audio"]["covered"] is False


class TestCorroboration:
    """Le nombre de voix est un fait, jamais une décision."""

    def test_une_seule_valeur_n_est_pas_en_conflit(self):
        etat = fuse("s1", {"speakers": [_obs(provider="p1"),
                                        _obs(provider="p2")]})

        resultat = corroboration(etat, "speaker")

        assert resultat["distinct_values"] == 1
        assert resultat["in_conflict"] is False

    def test_les_modalites_concordantes_sont_nommees(self):
        etat = fuse("s1", {"speakers": [_obs(provider="p1"),
                                        _obs(modality="video", provider="p2")]})

        valeurs = corroboration(etat, "speaker")["values"]

        assert valeurs[0]["modalities"] == ["audio", "video"]
        assert valeurs[0]["observations"] == 2

    def test_les_valeurs_ne_sont_pas_classees_par_nombre(self):
        """Classer par nombre de voix serait arbitrer sans le dire."""
        etat = fuse("s1", {"speakers": [
            _obs(value="ZZZ", provider="p1"),
            _obs(value="ZZZ", provider="p2"),
            _obs(value="AAA", provider="p3"),
        ]})

        resultat = corroboration(etat, "speaker")

        assert resultat["ranked_by_count"] is False
        assert [v["value"] for v in resultat["values"]] == ["'AAA'", "'ZZZ'"]

    def test_aucune_confiance_n_est_calculee(self):
        """« Trois modalités concordent » est un fait ; 0.75 serait un chiffre sans base."""
        etat = fuse("s1", {"speakers": [_obs(provider=f"p{i}") for i in range(3)]})

        assert corroboration(etat, "speaker")["confidence"] is None

    def test_la_corroboration_ne_promeut_rien(self):
        etat = fuse("s1", {"speakers": [_obs(provider=f"p{i}") for i in range(5)]})

        assert corroboration(etat, "speaker")["promoted"] is False

    def test_un_inconnu_ne_compte_pas_comme_une_voix(self):
        etat = fuse("s1", {"speakers": [_obs(), unknown("speaker", "audio")]})

        assert corroboration(etat, "speaker")["values"][0]["observations"] == 1

    def test_un_sujet_jamais_observe_rend_zero_valeur(self):
        resultat = corroboration(LiveContextState("s1"), "inexistant")

        assert resultat["values"] == []
        assert resultat["in_conflict"] is False


class TestFluxPossiblesIci:
    """L'état mesuré des flux sur cette machine."""

    def test_chaque_flux_recoit_un_verdict(self):
        verdicts = streams_possible_here()["streams"]

        assert set(verdicts) == set(FLUX)
        assert all(v["verdict"] in ("POSSIBLE", "BLOCKED")
                   for v in verdicts.values())

    def test_les_comptes_couvrent_les_neuf_flux(self):
        mesure = streams_possible_here()

        assert mesure["possible_count"] + mesure["blocked_count"] == 9

    def test_un_flux_bloque_dit_pourquoi(self):
        for verdict in streams_possible_here()["streams"].values():
            if verdict["verdict"] == "BLOCKED":
                assert verdict["reason"].strip()

    def test_le_verdict_suit_les_modalites_mesurees(self, monkeypatch):
        monkeypatch.setattr(capture, "available_modalities", lambda: ["text"])

        verdicts = streams_possible_here()["streams"]

        assert verdicts["text"]["verdict"] == "POSSIBLE"
        assert verdicts["screen"]["verdict"] == "BLOCKED"
        assert verdicts["video"]["verdict"] == "BLOCKED"

    def test_possible_ne_veut_pas_dire_capture_live(self, monkeypatch):
        """`audio` peut venir d'un fichier téléversé, sans aucun microphone."""
        monkeypatch.setattr(capture, "available_modalities", lambda: ["audio"])
        monkeypatch.setattr(capture, "_sonde_microphone", lambda: (False, "absent"))

        assert streams_possible_here()["streams"]["audio"]["verdict"] == "POSSIBLE"
        assert capture.probe("microphone").is_known is False


class TestRapport:
    """Le rapport dit ce que la fusion refuse de faire."""

    def test_la_fusion_declare_ne_rien_resoudre(self):
        rapport = fusion_report()

        assert rapport["resolves_conflicts"] is False
        assert rapport["promotes"] is False

    def test_les_regles_qui_comptent_sont_ecrites(self):
        regles = " ".join(fusion_report()["rules"])

        assert "jamais une moyenne" in regles
        assert "Aucune promotion" in regles
        assert "ADR-033" in regles

    def test_le_rapport_porte_l_etat_mesure(self):
        rapport = fusion_report()

        assert "possible_here" in rapport
        assert set(rapport["modalities_per_stream"]) == set(FLUX)
