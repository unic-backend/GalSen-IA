"""
Découverte proactive : ce qu'elle remarque, et surtout quand elle se tait.

Dernière capacité absente du brief. Un assistant qui suggère est très facile à
écrire et très facile à rendre insupportable, et ces tests portent sur les trois
façons de rater :

1. **Suggérer sans mesure** — une observation sans preuve est refusée à la
   construction, pas filtrée plus tard.
2. **Répéter** — une observation écartée ne revient pas, *sauf* si la situation
   a changé. Les deux moitiés de cette phrase sont testées ; la seconde est
   celle qui distingue « se taire » de « cacher ».
3. **Agir** — rien n'est exécuté, et le scan le dit dans sa réponse.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.proactive.detectors import DETECTEURS, run_detector  # noqa: E402
from src.proactive.journal import SuggestionJournal  # noqa: E402
from src.proactive.observations import (  # noqa: E402
    PRIORITES,
    Observation,
    observation,
    sort_observations,
)
from src.proactive.scan import CADENCE_SECONDES, dismiss, due, scan  # noqa: E402


@pytest.fixture
def journal(tmp_path):
    """Un journal de suggestions vide, propre à chaque test."""
    return SuggestionJournal(path=str(tmp_path / "proactif.jsonl"))


def une_observation(finding="Trois fichiers sans test.", evidence=None) -> Observation:
    """Construit une observation valide."""
    return observation(
        source="untested_code",
        finding=finding,
        evidence=evidence or {"unreached": 3},
        suggested_action="Écrire un test qui les atteint.",
    )


# ----------------------------------------------------------------------
# 1. Une suggestion sans mesure n'existe pas
# ----------------------------------------------------------------------


def test_une_observation_sans_preuve_est_refusee():
    """Une suggestion qui ne renvoie à aucune mesure est une opinion."""
    with pytest.raises(ValueError) as erreur:
        observation(source="x", finding="ça pourrait aller mieux",
                    suggested_action="faire quelque chose")

    assert "preuve" in str(erreur.value)


def test_une_observation_sans_action_est_refusee():
    """Signaler sans dire quoi faire déplace la charge sur la personne."""
    with pytest.raises(ValueError):
        observation(source="x", finding="constat", evidence={"n": 1})


def test_une_priorite_inconnue_est_refusee():
    with pytest.raises(ValueError):
        observation(source="x", finding="c", evidence={"n": 1},
                    suggested_action="a", priority="urgentissime")


def test_les_observations_sont_triees_du_bloquant_a_l_informatif():
    informative = observation(source="a", finding="a", evidence={"n": 1},
                              suggested_action="a", priority="for_information")
    bloquante = observation(source="b", finding="b", evidence={"n": 1},
                            suggested_action="b", priority="blocking")

    triees = sort_observations([informative, bloquante])

    assert [o.priority for o in triees] == ["blocking", "for_information"]
    assert list(PRIORITES) == ["blocking", "worth_doing", "for_information"]


# ----------------------------------------------------------------------
# 2. Ne pas répéter — mais ne pas cacher non plus
# ----------------------------------------------------------------------


def test_l_identifiant_est_stable_pour_une_meme_situation():
    """Sinon écarter une suggestion ne servirait à rien : elle reviendrait sous un autre nom."""
    assert une_observation().id == une_observation().id


def test_l_empreinte_change_quand_les_preuves_changent():
    trois = une_observation(evidence={"unreached": 3})
    trois_cents = une_observation(evidence={"unreached": 300})

    assert trois.id == trois_cents.id
    assert trois.fingerprint != trois_cents.fingerprint


def test_une_observation_ecartee_ne_revient_pas(journal):
    obs = une_observation()
    journal.dismiss(obs, by="awa", reason="je sais")

    assert journal.is_dismissed(obs) is True
    assert journal.filter([obs]) == []


def test_une_observation_ecartee_revient_si_la_situation_a_change(journal):
    """
    La nuance qui distingue « se taire » de « cacher » : écarter « 3 fichiers
    sans test » ne doit pas masquer « 300 fichiers sans test » six mois plus tard.
    """
    journal.dismiss(une_observation(evidence={"unreached": 3}))

    aggravee = une_observation(evidence={"unreached": 300})

    assert journal.is_dismissed(aggravee) is False
    assert journal.filter([aggravee]) == [aggravee]


def test_la_derniere_decision_fait_foi(journal):
    """Quelqu'un peut écarter, puis reconsidérer."""
    obs = une_observation()
    journal.dismiss(obs)
    journal.dismiss(une_observation(evidence={"unreached": 9}))

    assert journal.is_dismissed(obs) is False


def test_le_journal_conserve_le_constat_pas_seulement_l_identifiant(journal):
    """Relire un journal d'identifiants seuls ne dit pas ce qui a été écarté."""
    journal.dismiss(une_observation(), by="awa", reason="connu")

    entree = journal.history()[0]

    assert entree["finding"] == "Trois fichiers sans test."
    assert entree["by"] == "awa"


def test_une_ligne_corrompue_n_emporte_pas_le_journal(journal):
    journal.dismiss(une_observation())
    with open(journal.path, "a", encoding="utf-8") as fichier:
        fichier.write("{ceci n'est pas du json\n")

    assert len(journal.history()) == 1


def test_un_journal_absent_vaut_un_journal_vide(tmp_path):
    vide = SuggestionJournal(path=str(tmp_path / "jamais_ecrit.jsonl"))

    assert vide.history() == []
    assert vide.filter([une_observation()]) != []


# ----------------------------------------------------------------------
# 3. Le scan : ce qu'il rend, et ce qu'il ne fait pas
# ----------------------------------------------------------------------


def test_le_scan_n_execute_rien(journal):
    resultat = scan(journal=journal)

    assert resultat["acted"] is False
    assert "Aucune action" in resultat["note"]


def test_le_scan_tait_ce_qui_a_ete_ecarte(journal, monkeypatch):
    obs = une_observation()
    monkeypatch.setitem(DETECTEURS, "untested_code", lambda: [obs])
    journal.dismiss(obs)

    resultat = scan(journal=journal, detectors=["untested_code"])

    assert resultat["count"] == 0
    assert resultat["silenced"] == 1


def test_un_detecteur_en_panne_est_rapporte_et_non_confondu_avec_un_muet(journal, monkeypatch):
    """
    « Rien à signaler » et « je n'ai pas pu regarder » sont deux phrases
    différentes, et les confondre est la façon la plus simple de rater une
    dégradation.
    """
    def casse():
        raise RuntimeError("graphe illisible")

    monkeypatch.setitem(DETECTEURS, "untested_code", casse)

    resultat = scan(journal=journal, detectors=["untested_code"])

    assert resultat["count"] == 0
    assert resultat["detectors_failed"][0]["detector"] == "untested_code"
    assert "graphe illisible" in resultat["detectors_failed"][0]["reason"]


def test_un_detecteur_muet_est_le_cas_normal(journal, monkeypatch):
    monkeypatch.setitem(DETECTEURS, "untested_code", lambda: [])

    resultat = scan(journal=journal, detectors=["untested_code"])

    assert resultat["count"] == 0
    assert resultat["detectors_failed"] == []


def test_le_scan_reel_ne_leve_pas_et_rapporte_ses_detecteurs():
    """Sur l'état réel du dépôt : aucun détecteur ne doit tomber."""
    resultat = scan(record=False)

    assert resultat["detectors_run"] == len(DETECTEURS)
    assert resultat["detectors_failed"] == [], resultat["detectors_failed"]


def test_le_detecteur_de_modele_signale_l_absence_de_cerveau():
    """C1 est ouvert dans cet environnement : c'est la suggestion la plus rentable."""
    resultat = run_detector("model_availability")

    assert resultat["status"] == "ok"
    assert resultat["observations"]
    assert resultat["observations"][0].priority == "blocking"
    assert "ollama serve" in resultat["observations"][0].suggested_action


def test_un_detecteur_inconnu_ne_leve_pas():
    resultat = run_detector("detecteur_qui_n_existe_pas")

    assert resultat["status"] == "unknown"
    assert resultat["observations"] == []


# ----------------------------------------------------------------------
# 4. La cadence, et l'écart explicite
# ----------------------------------------------------------------------


def test_un_premier_passage_est_toujours_du():
    """Une plateforme qui n'a jamais regardé n'a rien à taire."""
    assert due(None) is True


def test_un_passage_recent_n_est_pas_du():
    maintenant = time.time()

    assert due(maintenant - 60, now=maintenant) is False


def test_la_cadence_ecoulee_rend_le_passage_du():
    maintenant = time.time()

    assert due(maintenant - CADENCE_SECONDES - 1, now=maintenant) is True


def test_ecarter_exige_l_empreinte(journal):
    """
    Sans elle, l'écart porterait sur le sujet en général plutôt que sur cette
    situation — c'est-à-dire qu'il cacherait l'aggravation.
    """
    resultat = dismiss("obs_123", "", journal=journal)

    assert resultat["status"] == "refused"


def test_ecarter_par_identifiant_fait_taire_l_observation(journal):
    obs = une_observation()

    dismiss(obs.id, obs.fingerprint, by="awa", journal=journal)

    assert journal.filter([obs]) == []
