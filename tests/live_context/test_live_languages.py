"""
Tests de la couche langues (L07.2, ADR-033, §10 et §11).

Les tests qui comptent sont `TestAucuneTraductionN_EstFabriquee` et
`TestZeroBasculeN_EstPasZero` — l'une est interdite par §10, l'autre est la
manière la plus discrète de transformer une absence de mesure en fait.
"""

import pytest

import src.live_context.languages as languages
from src.creative.voice.scene import AudioSegment
from src.live_context.languages import (
    BASE_DE_CONFIANCE,
    MODULES_D_IDENTIFICATION_AUDIO,
    audio_language_identification_state,
    language_observation,
    language_observations,
    languages_report,
    languages_view,
    live_switching,
    transcript_observation,
    translation_observation,
)
from src.live_context.state import ABSENT, DECLARE, INCONNU, MESURE

_AUDIO = "/tmp/reunion.wav"


def _seg(segment_id: str, start: float, end: float, **kwargs) -> AudioSegment:
    return AudioSegment(segment_id=segment_id, start=start, end=end,
                        original_audio_path=_AUDIO, **kwargs)


class TestTroisCasTroisStatuts:
    """Une langue affirmée n'est pas une langue mesurée."""

    def test_sans_langue_l_observation_est_inconnue(self):
        observation = language_observation(_seg("s1", 0, 1))

        assert observation.status == INCONNU
        assert observation.value is None

    def test_une_langue_sans_confiance_est_declaree(self):
        observation = language_observation(_seg("s1", 0, 1, language="wo"))

        assert observation.status == DECLARE
        assert observation.confidence is None

    def test_une_langue_avec_confiance_est_mesuree(self):
        observation = language_observation(
            _seg("s1", 0, 1, language="wo", language_confidence=0.9))

        assert observation.status == MESURE
        assert observation.confidence == 0.9

    def test_la_confiance_porte_toujours_sa_base(self):
        observation = language_observation(
            _seg("s1", 0, 1, language="fr", language_confidence=0.3))

        assert observation.confidence_basis == BASE_DE_CONFIANCE

    def test_une_confiance_faible_est_rendue_telle_quelle(self):
        """Une langue identifiée à 0,3 rapportée comme un fait ferait traduire
        depuis la mauvaise langue."""
        observation = language_observation(
            _seg("s1", 0, 1, language="fr", language_confidence=0.3))

        assert "LOW_CONFIDENCE" in observation.detail

    def test_l_inconnue_nomme_ce_qui_manque(self, monkeypatch):
        monkeypatch.setattr(languages, "_module_present", lambda nom: False)

        observation = language_observation(_seg("s1", 0, 1))

        assert "importable" in observation.detail

    def test_une_observation_par_segment(self):
        segments = [_seg("s1", 0, 1, language="wo"), _seg("s2", 1, 2)]

        assert len(language_observations(segments)) == 2


class TestAucuneTraductionN_EstFabriquee:
    """§10 : ne jamais fabriquer une traduction."""

    def test_une_traduction_demandee_rend_une_absence(self):
        observation = translation_observation(_seg("s1", 0, 1, language="wo"),
                                              "fr")

        assert observation.status == ABSENT
        assert observation.value is None

    def test_l_absence_nomme_la_langue_demandee_et_la_raison(self):
        observation = translation_observation(_seg("s1", 0, 1), "en")

        assert "en" in observation.detail
        assert "table certifiée" in observation.detail

    def test_le_rapport_declare_qu_aucune_traduction_n_existe(self):
        assert languages_report()["translation_available"] is False


class TestAucuneTranscriptionN_EstApproximee:
    """L'invariant est hérité d'AudioSegment, pas revérifié."""

    def test_sans_transcription_l_observation_est_inconnue(self):
        observation = transcript_observation(_seg("s1", 0, 1))

        assert observation.status == INCONNU
        assert "ABSENT" in observation.detail

    def test_une_transcription_mesuree_est_mesuree(self):
        segment = _seg("s1", 0, 1, transcript="bonjour",
                       transcript_source="MEASURED")

        assert transcript_observation(segment).status == MESURE

    def test_un_texte_sans_source_mesuree_est_refuse_en_amont(self):
        from src.creative.voice.scene import VoiceSceneRefused

        with pytest.raises(VoiceSceneRefused, match="dans la bouche"):
            _seg("s1", 0, 1, transcript="peut-être ceci")


class TestZeroBasculeN_EstPasZero:
    """`None` dit que personne n'a mesuré ; `0` affirme une seule langue."""

    def test_sans_langue_le_compte_de_bascules_vaut_none(self):
        resultat = live_switching([_seg("s1", 0, 1), _seg("s2", 1, 2)])

        assert resultat["live"]["switch_count"] is None
        assert resultat["live"]["state"] == "NOT_MEASURED"

    def test_l_absence_de_mesure_porte_sa_raison_et_sa_couverture(self):
        resultat = live_switching([_seg("s1", 0, 1)])

        assert resultat["live"]["reason"].strip()
        assert resultat["live"]["coverage"] == "0/1 segment(s) étiqueté(s)"

    def test_deux_langues_alternees_sont_comptees(self):
        segments = [_seg("s1", 0, 1, language="wo"),
                    _seg("s2", 1, 2, language="fr"),
                    _seg("s3", 2, 3, language="wo")]

        resultat = live_switching(segments)

        assert resultat["live"]["switch_count"] == 2
        assert resultat["live"]["languages"] == ["fr", "wo"]
        assert resultat["live"]["state"] == "MEASURED"

    def test_un_etiquetage_partiel_est_dit_partiel(self):
        segments = [_seg("s1", 0, 1, language="wo"), _seg("s2", 1, 2)]

        assert live_switching(segments)["live"]["state"] == "PARTIAL"

    def test_le_rapport_reutilise_est_rendu_tel_quel(self):
        from src.creative.language.switching import switching_report

        segments = [_seg("s1", 0, 1, language="wo"),
                    _seg("s2", 1, 2, language="fr")]

        assert (live_switching(segments)["switching"]
                == switching_report(segments))


class TestIdentificationMesuree:
    """L'identification de langue sur l'audio est sondée, jamais supposée."""

    def test_les_modules_cherches_sont_declares(self):
        etat = audio_language_identification_state()

        assert etat["modules_searched"] == list(MODULES_D_IDENTIFICATION_AUDIO)

    def test_un_document_n_est_pas_de_la_parole(self):
        """`acquisition/language.py` existe et ne couvre pas l'audio."""
        etat = audio_language_identification_state()

        assert "document" in etat["document_identification"]
        assert "parole" in etat["document_identification"]

    def test_une_identification_absente_porte_sa_raison(self, monkeypatch):
        monkeypatch.setattr(languages, "_module_present", lambda nom: False)

        etat = audio_language_identification_state()

        assert etat["state"] == "ABSENT"
        assert etat["reason"].strip()

    def test_un_module_present_rend_l_etat_disponible(self, monkeypatch):
        monkeypatch.setattr(languages, "_module_present",
                            lambda nom: nom == "whisper")

        etat = audio_language_identification_state()

        assert etat["state"] == "AVAILABLE"
        assert etat["modules_found"] == ["whisper"]


class TestVue:
    """Aucune langue dominante, aucune langue de fichier."""

    def test_aucune_langue_dominante_n_est_calculee(self):
        segments = [_seg("s1", 0, 9, language="wo"),
                    _seg("s2", 9, 10, language="fr")]

        vue = languages_view(segments)

        assert vue["dominant_language"] is None
        assert vue["dominant_language_reason"].strip()

    def test_les_segments_sans_langue_sont_comptes(self):
        vue = languages_view([_seg("s1", 0, 1, language="wo"),
                              _seg("s2", 1, 2)])

        assert vue["segments_without_language"] == 1

    def test_la_vue_porte_les_observations_et_l_identification(self):
        vue = languages_view([_seg("s1", 0, 1)])

        assert len(vue["observations"]) == 1
        assert "identification" in vue


class TestRapport:
    """Le rapport dit ce qui est réutilisé et ce qui est refusé."""

    def test_les_modules_reutilises_sont_nommes(self):
        reutilises = " ".join(languages_report()["reused"])

        assert "switching.py" in reutilises
        assert "scene.py" in reutilises

    def test_les_regles_qui_comptent_sont_ecrites(self):
        regles = " ".join(languages_report()["rules"])

        assert "Aucune traduction n'est fabriquée" in regles
        assert "Aucune langue dominante" in regles
