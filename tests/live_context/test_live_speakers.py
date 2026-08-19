"""
Tests de la couche locuteurs (L07.1, ADR-033, §9).

Les tests qui comptent sont `TestAucunLocuteurN_EstInvente` et
`TestZeroTourN_ExistePas` — les deux fabrications que §9 rend faciles.

**Aucun test n'épingle l'absence de `pyannote` sur cette machine** : ce serait un
test qui échouerait sur le portable d'un développeur qui l'a installé. Ce qui
est vérifié est le comportement quand la diarisation manque, produit en
remplaçant la sonde.
"""

import pytest

import src.live_context.speakers as speakers
from src.creative.voice.scene import AudioSegment
from src.live_context.speakers import (
    MODULES_DE_DIARISATION,
    SOURCES_D_IDENTITE,
    SpeakerRefused,
    diarization_observation,
    diarization_state,
    known_speakers,
    speaker_observation,
    speaker_observations,
    speakers_report,
    speakers_view,
    turn_taking,
)
from src.live_context.state import ABSENT, DECLARE, INCONNU, MESURE

_AUDIO = "/tmp/reunion.wav"


def _seg(segment_id: str, start: float, end: float,
         speaker_id=None) -> AudioSegment:
    return AudioSegment(segment_id=segment_id, start=start, end=end,
                        original_audio_path=_AUDIO, speaker_id=speaker_id)


class TestSourcesDIdentite:
    """Trois sources, et une seule est une mesure."""

    def test_seule_la_diarisation_est_une_mesure(self):
        assert SOURCES_D_IDENTITE["DIARIZATION"] == MESURE
        assert SOURCES_D_IDENTITE["CHANNEL"] == DECLARE
        assert SOURCES_D_IDENTITE["DECLARED_BY_USER"] == DECLARE

    def test_une_source_inconnue_est_refusee(self):
        with pytest.raises(SpeakerRefused, match="non déclarée"):
            speaker_observation(_seg("s1", 0, 1, "A"), source="devinette")

    def test_la_vue_refuse_aussi_une_source_inconnue(self):
        with pytest.raises(SpeakerRefused, match="non déclarée"):
            speakers_view([], source="devinette")


class TestUnCanalN_EstPasUnLocuteur:
    """Un canal dit d'où vient le son, pas qui parle."""

    def test_une_identite_de_canal_est_declaree_pas_mesuree(self):
        observation = speaker_observation(_seg("s1", 0, 1, "local"),
                                          source="CHANNEL")

        assert observation.status == DECLARE

    def test_le_sujet_distingue_le_canal_du_locuteur(self):
        canal = speaker_observation(_seg("s1", 0, 1, "local"), source="CHANNEL")
        locuteur = speaker_observation(_seg("s1", 0, 1, "A"))

        assert canal.subject != locuteur.subject
        assert canal.subject == "speaker_channel"

    def test_le_detail_dit_pourquoi(self):
        observation = speaker_observation(_seg("s1", 0, 1, "local"),
                                          source="CHANNEL")

        assert "pas qui parle" in observation.detail

    def test_une_declaration_utilisateur_a_son_propre_sujet(self):
        observation = speaker_observation(_seg("s1", 0, 1, "Awa"),
                                          source="DECLARED_BY_USER")

        assert observation.subject == "speaker_declared"
        assert observation.status == DECLARE


class TestAucunLocuteurN_EstInvente:
    """SPEAKER_1 découpé au hasard a la forme d'une diarisation, pas le contenu."""

    def test_un_segment_sans_locuteur_rend_inconnu(self):
        observation = speaker_observation(_seg("s1", 0, 1))

        assert observation.status == INCONNU
        assert observation.value is None

    def test_l_inconnue_nomme_ce_qui_manque(self, monkeypatch):
        monkeypatch.setattr(speakers, "_module_present", lambda nom: False)

        observation = speaker_observation(_seg("s1", 0, 1))

        assert "importable" in observation.detail

    def test_le_module_n_expose_aucune_fonction_de_numerotation(self):
        exposees = [n for n in dir(speakers) if not n.startswith("_")]

        assert not any("number" in n or "assign" in n or "label" in n
                       for n in exposees)

    def test_les_locuteurs_connus_ne_comptent_que_les_etiquetes(self):
        segments = [_seg("s1", 0, 1, "A"), _seg("s2", 1, 2), _seg("s3", 2, 3, "A")]

        assert known_speakers(segments) == ["A"]

    def test_aucun_locuteur_etiquete_donne_un_compte_nul_pas_zero(self):
        vue = speakers_view([_seg("s1", 0, 1), _seg("s2", 1, 2)])

        assert vue["speaker_count"] is None
        assert vue["unlabelled_segments"] == 2

    def test_une_observation_par_segment_sans_fusion(self):
        segments = [_seg("s1", 0, 1, "A"), _seg("s2", 1, 2, "A")]

        assert len(speaker_observations(segments)) == 2


class TestZeroTourN_ExistePas:
    """`None` dit que personne n'a compté ; `0` affirmerait que personne n'a parlé."""

    def test_sans_locuteur_les_tours_valent_none(self):
        resultat = turn_taking([_seg("s1", 0, 1), _seg("s2", 1, 2)])

        assert resultat["turns"] is None
        assert resultat["state"] == "NOT_MEASURED"

    def test_l_absence_de_mesure_porte_sa_raison_et_sa_couverture(self):
        resultat = turn_taking([_seg("s1", 0, 1)])

        assert resultat["reason"].strip()
        assert resultat["coverage"] == "0/1 segment(s) étiqueté(s)"

    def test_deux_locuteurs_alternes_font_trois_tours(self):
        segments = [_seg("s1", 0, 1, "A"), _seg("s2", 1, 2, "B"),
                    _seg("s3", 2, 3, "A")]

        resultat = turn_taking(segments)

        assert resultat["turns"] == 3
        assert resultat["state"] == "MEASURED"

    def test_deux_segments_du_meme_locuteur_font_un_seul_tour(self):
        segments = [_seg("s1", 0, 1, "A"), _seg("s2", 1, 2, "A")]

        resultat = turn_taking(segments)

        assert resultat["turns"] == 1
        assert resultat["boundaries"][0]["segments"] == 2
        assert resultat["boundaries"][0]["end"] == 2

    def test_un_etiquetage_partiel_est_dit_partiel(self):
        segments = [_seg("s1", 0, 1, "A"), _seg("s2", 1, 2)]

        resultat = turn_taking(segments)

        assert resultat["state"] == "PARTIAL"
        assert "ne couvrent pas tout" in resultat["reason"]

    def test_les_tours_suivent_le_temps_pas_l_ordre_recu(self):
        segments = [_seg("s2", 5, 6, "B"), _seg("s1", 0, 1, "A")]

        assert turn_taking(segments)["boundaries"][0]["speaker"] == "A"


class TestDiarisationMesuree:
    """L'état est mesuré, et sa raison n'est pas réécrite ici."""

    def test_les_modules_cherches_sont_declares(self):
        assert diarization_state()["modules_searched"] == list(MODULES_DE_DIARISATION)

    def test_la_raison_declaree_vient_du_moteur_voix(self):
        from src.creative.voice.scene import CAPACITES_EXTERNES

        assert (diarization_state()["declared_reason"]
                == CAPACITES_EXTERNES["speaker_diarization"])

    def test_une_diarisation_absente_donne_une_observation_absente(self, monkeypatch):
        monkeypatch.setattr(speakers, "_module_present", lambda nom: False)

        observation = diarization_observation()

        assert observation.status == ABSENT
        assert observation.value is None
        assert observation.detail.strip()

    def test_une_diarisation_presente_est_mesuree(self, monkeypatch):
        monkeypatch.setattr(speakers, "_module_present",
                            lambda nom: nom == "pyannote.audio")

        observation = diarization_observation()

        assert observation.status == MESURE
        assert observation.value == "pyannote.audio"


class TestAudioDOrigine:
    """§11 : l'enregistrement reste l'artefact source."""

    def test_le_chemin_voyage_avec_une_observation_connue(self):
        assert _AUDIO in speaker_observation(_seg("s1", 0, 1, "A")).detail

    def test_le_chemin_voyage_aussi_avec_une_inconnue(self):
        assert _AUDIO in speaker_observation(_seg("s1", 0, 1)).detail


class TestRapport:
    """Le rapport dit ce que la couche refuse de faire."""

    def test_le_module_declare_ne_pas_numeroter(self):
        assert speakers_report()["numbers_speakers"] is False

    def test_les_regles_qui_comptent_sont_ecrites(self):
        regles = " ".join(speakers_report()["rules"])

        assert "Aucune fonction ne numérote" in regles
        assert "Un canal n'est pas un locuteur" in regles
        assert "Zéro tour de parole n'existe pas" in regles

    def test_la_vue_porte_l_etat_de_la_diarisation(self):
        vue = speakers_view([_seg("s1", 0, 1, "A")])

        assert "diarization" in vue
        assert vue["identity_is_measured"] is True
