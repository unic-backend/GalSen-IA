"""
Tests de l'assistance live (L08, ADR-033, §19 et §20).

Le test qui compte est `TestJamaisSurUnInconnu` : une suggestion tirée d'une
inconnue se lit comme un conseil et non comme une donnée, donc elle est plus
convaincante qu'une valeur fausse — et plus dangereuse.

`TestRienN_EstReconstruit` vérifie la deuxième promesse du volet : le
`NudgeEngine` du §20 est `src/proactive/`, et il n'est pas réécrit.
"""

import pytest

from src.live_context.assistance import (
    DETECTEURS_LIVE,
    AssistanceRefused,
    assistance_report,
    capacites_manquantes,
    conflits_de_contexte,
    live_scan,
    rien_de_mesure,
    run_live_detector,
)
from src.live_context.state import (
    MESURE,
    LiveContextState,
    Observation,
    absent,
    unknown,
)
from src.proactive.journal import SuggestionJournal


def _obs(**kwargs) -> Observation:
    defauts = dict(subject="speaker", status=MESURE, modality="audio",
                   value="SPEAKER_01")
    defauts.update(kwargs)
    return Observation(**defauts)


@pytest.fixture
def carnet(tmp_path) -> SuggestionJournal:
    """Un journal isolé — jamais celui du répertoire de données du dépôt."""
    return SuggestionJournal(path=str(tmp_path / "journal.jsonl"))


class TestJamaisSurUnInconnu:
    """Une suggestion tirée d'une inconnue est un conseil sans mesure."""

    def test_un_inconnu_ne_produit_aucune_suggestion_de_capacite(self):
        etat = LiveContextState("s1").add(unknown("language", "audio"))

        assert capacites_manquantes(etat) == []

    def test_un_inconnu_ne_declenche_pas_de_conflit(self):
        etat = LiveContextState("s1").add(_obs(value="A"),
                                          unknown("speaker", "audio"))

        assert conflits_de_contexte(etat) == []

    def test_un_etat_entierement_connu_ne_declenche_pas_rien_de_mesure(self):
        etat = LiveContextState("s1").add(_obs())

        assert rien_de_mesure(etat) == []

    def test_un_etat_vide_ne_signale_rien(self):
        """Une session qui n'a pas commencé n'a rien à signaler."""
        assert rien_de_mesure(LiveContextState("s1")) == []

    def test_toute_suggestion_porte_ses_preuves(self, carnet):
        etat = LiveContextState("s1").add(
            absent("diarization", "audio", "pyannote introuvable"))

        for suggestion in live_scan(etat, journal=carnet)["observations"]:
            assert suggestion["evidence"]


class TestConflits:
    """Le désaccord est rendu à un humain, jamais enterré."""

    def test_un_conflit_produit_une_suggestion(self):
        etat = LiveContextState("s1").add(_obs(value="A", provider="p1"),
                                          _obs(value="B", provider="p2"))

        suggestions = conflits_de_contexte(etat)

        assert len(suggestions) == 1
        assert "ne concordent pas" in suggestions[0].finding

    def test_la_preuve_nomme_les_valeurs_et_les_fournisseurs(self):
        etat = LiveContextState("s1").add(_obs(value="A", provider="p1"),
                                          _obs(value="B", provider="p2"))

        preuve = conflits_de_contexte(etat)[0].evidence

        assert preuve["providers"] == ["p1", "p2"]
        assert len(preuve["values"]) == 2

    def test_l_action_proposee_ne_tranche_pas_a_la_place_de_l_humain(self):
        etat = LiveContextState("s1").add(_obs(value="A", provider="p1"),
                                          _obs(value="B", provider="p2"))

        suggestion = conflits_de_contexte(etat)[0]

        assert suggestion.decided_by == "operator"
        assert "n'arbitre pas" in suggestion.suggested_action

    def test_deux_observations_concordantes_ne_disent_rien(self):
        etat = LiveContextState("s1").add(_obs(provider="p1"),
                                          _obs(provider="p2"))

        assert conflits_de_contexte(etat) == []


class TestCapacitesManquantes:
    """Un ABSENT est adressé à l'opérateur, avec son constat."""

    def test_une_absence_produit_une_suggestion(self):
        etat = LiveContextState("s1").add(
            absent("diarization", "audio", "pyannote introuvable"))

        suggestions = capacites_manquantes(etat)

        assert len(suggestions) == 1
        assert "pyannote" in suggestions[0].finding

    def test_le_meme_sujet_absent_deux_fois_ne_dit_qu_une_chose(self):
        etat = LiveContextState("s1").add(
            absent("diarization", "audio", "constat 1"),
            absent("diarization", "audio", "constat 2"))

        assert len(capacites_manquantes(etat)) == 1

    def test_la_suggestion_est_informative_pas_bloquante(self):
        etat = LiveContextState("s1").add(absent("screen", "screen", "DISPLAY vide"))

        assert capacites_manquantes(etat)[0].priority == "for_information"


class TestRienDeMesure:
    """Le silence se lirait comme « tout va bien »."""

    def test_un_etat_sans_rien_de_connu_le_dit(self):
        etat = LiveContextState("s1").add(unknown("language", "audio"),
                                          absent("screen", "screen", "vide"))

        suggestions = rien_de_mesure(etat)

        assert len(suggestions) == 1
        assert suggestions[0].priority == "blocking"

    def test_la_preuve_compte_les_inconnues_et_les_absences(self):
        etat = LiveContextState("s1").add(unknown("language", "audio"),
                                          absent("screen", "screen", "vide"))

        preuve = rien_de_mesure(etat)[0].evidence

        assert preuve["unknown"] == 1
        assert preuve["absent"] == 1
        assert preuve["absent_subjects"] == ["screen"]

    def test_une_seule_observation_connue_suffit_a_le_taire(self):
        etat = LiveContextState("s1").add(unknown("language", "audio"), _obs())

        assert rien_de_mesure(etat) == []


class TestDetecteurs:
    """Un détecteur muet et un détecteur cassé ne se confondent pas."""

    def test_les_trois_detecteurs_sont_declares(self):
        assert len(DETECTEURS_LIVE) == 3

    def test_un_detecteur_non_declare_est_refuse(self):
        with pytest.raises(AssistanceRefused, match="non déclaré"):
            run_live_detector("devinette", LiveContextState("s1"))

    def test_un_detecteur_muet_rend_ok_avec_une_liste_vide(self):
        resultat = run_live_detector("context_conflict", LiveContextState("s1"))

        assert resultat["status"] == "ok"
        assert resultat["observations"] == []

    def test_une_panne_est_rapportee_pas_cachee(self, monkeypatch):
        import src.live_context.assistance as assistance

        def casse(_state):
            raise RuntimeError("sonde en panne")

        monkeypatch.setitem(assistance._FONCTIONS, "context_conflict", casse)

        resultat = run_live_detector("context_conflict", LiveContextState("s1"))

        assert resultat["status"] == "failed"
        assert "sonde en panne" in resultat["reason"]

    def test_un_scan_rapporte_les_detecteurs_en_panne(self, monkeypatch, carnet):
        import src.live_context.assistance as assistance

        def casse(_state):
            raise RuntimeError("sonde en panne")

        monkeypatch.setitem(assistance._FONCTIONS, "context_conflict", casse)

        resultat = live_scan(LiveContextState("s1"), journal=carnet)

        assert len(resultat["detectors_failed"]) == 1


class TestRienN_EstReconstruit:
    """§20 décrit `src/proactive/`, qui existe déjà."""

    def test_le_module_declare_ne_rien_reconstruire(self):
        rapport = assistance_report()

        assert rapport["builds_nudge_engine"] is False
        assert rapport["builds_journal"] is False
        assert rapport["uses_cooldown_timer"] is False

    def test_le_journal_reutilise_est_celui_de_proactive(self, carnet, tmp_path):
        etat = LiveContextState("s1").add(absent("screen", "screen", "vide"))

        live_scan(etat, journal=carnet)

        assert (tmp_path / "journal.jsonl").exists()

    def test_une_suggestion_ecartee_ne_revient_pas(self, carnet):
        etat = LiveContextState("s1").add(absent("screen", "screen", "vide"))
        premier = capacites_manquantes(etat)[0]
        carnet.dismiss(premier)

        resultat = live_scan(etat, journal=carnet)

        assert all(s["id"] != premier.id for s in resultat["observations"])
        assert resultat["silenced"] >= 1

    def test_une_suggestion_ecartee_revient_si_les_preuves_changent(self, carnet):
        """C'est l'empreinte des preuves, pas le temps, qui la fait revenir."""
        avant = LiveContextState("s1").add(absent("screen", "screen", "vide"))
        carnet.dismiss(capacites_manquantes(avant)[0])
        apres = LiveContextState("s1").add(
            absent("screen", "screen", "DISPLAY=:0 mais serveur injoignable"))

        resultat = live_scan(apres, journal=carnet)

        assert any(s["source"] == "live_context.missing_capability"
                   for s in resultat["observations"])

    def test_les_modules_reutilises_sont_nommes(self):
        reutilises = " ".join(assistance_report()["reused"])

        assert "proactive/journal.py" in reutilises
        assert "proactive/observations.py" in reutilises


class TestRienN_Agit:
    """Aucune action, aucune parole dans la session, aucune écriture mémoire."""

    def test_un_scan_declare_n_avoir_rien_fait(self, carnet):
        resultat = live_scan(LiveContextState("s1"), journal=carnet)

        assert resultat["acted"] is False
        assert resultat["spoke_in_session"] is False

    def test_chaque_suggestion_nomme_qui_decide(self, carnet):
        etat = LiveContextState("s1").add(_obs(value="A", provider="p1"),
                                          _obs(value="B", provider="p2"))

        for suggestion in live_scan(etat, journal=carnet)["observations"]:
            assert suggestion["decided_by"] in ("operator", "owner")

    def test_le_scan_porte_la_session(self, carnet):
        assert live_scan(LiveContextState("s42"),
                         journal=carnet)["session_id"] == "s42"

    def test_les_regles_qui_comptent_sont_ecrites(self):
        regles = " ".join(assistance_report()["rules"])

        assert "ne repose jamais sur un UNKNOWN" in regles
        assert "quand ses preuves changent, jamais quand" in regles
