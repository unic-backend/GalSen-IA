"""
Tests de l'état de contexte live (L05.1, ADR-033, §6 et §13).

Les tests qui comptent sont `TestAbsentN_EstPasInconnu` — c'est la distinction
dont dépend l'utilité du rapport pour un opérateur — et `TestAucunArbitrage`.
"""

import pytest

from src.live_context.state import (
    ABSENT,
    DECLARE,
    INCONNU,
    MESURE,
    MODALITES,
    STATUTS,
    LiveContextState,
    Observation,
    ObservationRefused,
    absent,
    state_report,
    unknown,
)


def _obs(**kwargs) -> Observation:
    defauts = dict(subject="speaker", status=MESURE, modality="audio",
                   value="SPEAKER_01")
    defauts.update(kwargs)
    return Observation(**defauts)


class TestDeclaration:
    """Ce qui est refusé à la construction."""

    def test_une_observation_sans_sujet_est_refusee(self):
        with pytest.raises(ObservationRefused, match="ne se recoupe"):
            _obs(subject="   ")

    def test_un_statut_inconnu_est_refuse(self):
        with pytest.raises(ObservationRefused, match="non déclaré"):
            _obs(status="PRESQUE_SUR")

    def test_une_modalite_inconnue_est_refusee(self):
        with pytest.raises(ObservationRefused, match="non déclarée"):
            _obs(modality="telepathie")

    def test_les_quatre_statuts_sont_declares(self):
        assert STATUTS == (MESURE, DECLARE, INCONNU, ABSENT)


class TestAbsentN_EstPasInconnu:
    """L'un est mesuré et ne changera pas ; l'autre attend une mesure."""

    def test_absent_et_inconnu_sont_deux_statuts(self):
        assert ABSENT != INCONNU

    def test_une_absence_sans_constat_est_refusee(self):
        """« Absent » sans constat est une supposition."""
        with pytest.raises(ObservationRefused, match="supposition"):
            absent("microphone", "audio", "   ")

    def test_une_absence_porte_comment_elle_a_ete_etablie(self):
        observation = absent("microphone", "audio", "/dev/snd cherché, absent")

        assert observation.status == ABSENT
        assert "/dev/snd" in observation.detail

    def test_un_inconnu_n_exige_pas_de_constat(self):
        """Ne pas savoir n'a pas à se justifier ; ne pas avoir, si."""
        assert unknown("language", "audio").status == INCONNU

    def test_un_statut_sans_valeur_refuse_une_valeur(self):
        for statut in (INCONNU, ABSENT):
            with pytest.raises(ObservationRefused, match="on ne connaît pas"):
                _obs(status=statut, value="quelque chose")

    def test_measured_sans_valeur_est_refuse(self):
        with pytest.raises(ObservationRefused, match="ne mesure rien"):
            _obs(value=None)

    def test_ni_absent_ni_inconnu_ne_sont_connus(self):
        assert absent("m", "audio", "constaté").is_known is False
        assert unknown("l", "audio").is_known is False
        assert _obs().is_known is True


class TestConfiance:
    """Un chiffre sans méthode se comporte comme une mesure sans en être une."""

    def test_la_confiance_est_absente_par_defaut(self):
        assert _obs().confidence is None

    def test_une_confiance_sans_base_est_refusee(self):
        with pytest.raises(ObservationRefused, match="sans base"):
            _obs(confidence=0.9)

    def test_une_base_sans_confiance_est_refusee(self):
        with pytest.raises(ObservationRefused, match="soit les deux"):
            _obs(confidence_basis="au jugé")

    def test_une_confiance_hors_bornes_est_refusee(self):
        with pytest.raises(ObservationRefused, match="hors de"):
            _obs(confidence=1.5, confidence_basis="x")

    def test_une_confiance_avec_sa_base_passe(self):
        observation = _obs(confidence=0.8,
                           confidence_basis="deux modalités concordantes")

        assert observation.confidence == 0.8


class TestEtat:
    """L'état est en ajout seul et ne conclut rien."""

    def test_un_etat_sans_session_est_refuse(self):
        with pytest.raises(ObservationRefused, match="ne se rattache"):
            LiveContextState("  ")

    def test_add_rend_un_nouvel_etat(self):
        avant = LiveContextState("s1")

        apres = avant.add(_obs())

        assert avant.observations == ()
        assert len(apres.observations) == 1

    def test_les_sujets_sont_tries(self):
        etat = LiveContextState("s1").add(
            _obs(subject="speaker"), _obs(subject="language", value="wo"))

        assert etat.subjects() == ["language", "speaker"]

    def test_by_subject_rend_tout_l_historique(self):
        """Rendre seulement la dernière ferait disparaître le désaccord."""
        etat = LiveContextState("s1").add(
            _obs(value="A", provider="p1"), _obs(value="B", provider="p2"))

        assert len(etat.by_subject("speaker")) == 2

    def test_latest_rend_la_plus_recente(self):
        etat = LiveContextState("s1").add(
            _obs(value="A", at=1.0), _obs(value="B", at=2.0))

        assert etat.latest("speaker").value == "B"

    def test_latest_sur_un_sujet_absent_rend_none(self):
        assert LiveContextState("s1").latest("inexistant") is None

    def test_les_comptes_couvrent_les_quatre_statuts(self):
        etat = LiveContextState("s1").add(
            _obs(), absent("m", "audio", "constaté"), unknown("l", "audio"))

        assert etat.counts() == {MESURE: 1, DECLARE: 0, INCONNU: 1, ABSENT: 1}


class TestAucunArbitrage:
    """Une moyenne effacerait exactement l'information qui compte."""

    def test_deux_valeurs_connues_font_un_conflit(self):
        etat = LiveContextState("s1").add(
            _obs(value="SPEAKER_01", provider="p1"),
            _obs(value="SPEAKER_02", provider="p2"))

        conflits = etat.conflicts()

        assert len(conflits) == 1
        assert conflits[0]["subject"] == "speaker"

    def test_le_conflit_nomme_les_fournisseurs(self):
        etat = LiveContextState("s1").add(
            _obs(value="A", provider="p1"), _obs(value="B", provider="p2"))

        assert etat.conflicts()[0]["providers"] == ["p1", "p2"]

    def test_un_conflit_n_est_jamais_resolu(self):
        etat = LiveContextState("s1").add(
            _obs(value="A", provider="p1"), _obs(value="B", provider="p2"))

        assert etat.conflicts()[0]["resolved"] is False

    def test_deux_fois_la_meme_valeur_n_est_pas_un_conflit(self):
        etat = LiveContextState("s1").add(
            _obs(value="A", provider="p1"), _obs(value="A", provider="p2"))

        assert etat.conflicts() == []

    def test_un_inconnu_ne_contredit_pas_une_mesure(self):
        """Ne pas savoir n'est pas être en désaccord."""
        etat = LiveContextState("s1").add(
            _obs(value="A"), unknown("speaker", "audio"))

        assert etat.conflicts() == []

    def test_l_etat_ne_promeut_rien(self):
        etat = LiveContextState("s1")
        for _ in range(10):
            etat = etat.add(_obs(value="A"))

        assert etat.as_dict()["promoted"] is False
        assert all(o.status == MESURE for o in etat.observations)


class TestRapport:
    """Le rapport dit ce qui est tenu."""

    def test_le_vocabulaire_est_celui_declare(self):
        rapport = state_report()

        assert rapport["statuses"] == list(STATUTS)
        assert rapport["modalities"] == list(MODALITES)

    def test_la_regle_qui_compte_est_ecrite(self):
        regles = " ".join(state_report()["rules"])

        assert "ABSENT n'est pas UNKNOWN" in regles
        assert "Aucun arbitrage" in regles

    def test_l_etat_se_serialise(self):
        etat = LiveContextState("s1").add(_obs())

        serialise = etat.as_dict()

        assert serialise["session_id"] == "s1"
        assert len(serialise["observations"]) == 1
