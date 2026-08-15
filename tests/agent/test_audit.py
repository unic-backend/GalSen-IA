"""
Le journal des actions autonomes (phase 6).

Une réparation que personne ne peut reconstituer après coup est une réparation
en laquelle personne ne peut avoir confiance. Ces tests gardent les trois
propriétés qui rendent ce journal utile :

1. **Aucun secret n'y entre** — l'expurgation est celle de
   `src/security/redaction.py`, jamais une seconde liste qui divergerait.
2. **Les compteurs survivent à l'oubli des entrées** : un dépôt actif ne doit
   pas finir par annoncer « aucune réparation ».
3. **Une panne d'écriture n'emporte pas l'action observée** : un journal qui
   casse la réparation qu'il regarde serait pire que pas de journal.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.agent.audit import ACTIONS, AuditJournal  # noqa: E402
from src.agent.audit.journal import ENTREES_CONSERVEES  # noqa: E402
from src.agent.health import observability  # noqa: E402


@pytest.fixture
def journal():
    """Un journal en mémoire, sans écriture disque."""
    return AuditJournal(persist=False)


# ----------------------------------------------------------------------
# 1. Aucun secret
# ----------------------------------------------------------------------

def test_une_cle_d_api_est_expurgee(journal):
    """Le journal est lu par des humains et archivé : rien de sensible n'y entre."""
    journal.record(
        "command", target="deploy", metadata={"api_key": "sk-très-secret-123"},
    )

    detail = journal.entries()[0]["detail"]

    assert "sk-très-secret-123" not in detail
    assert "***" in detail


@pytest.mark.parametrize("cle", [
    "password", "token", "secret", "authorization", "private_key",
])
def test_les_champs_sensibles_courants_sont_expurges(journal, cle):
    """La liste vient de `src/security/redaction.py`, pas d'ici."""
    journal.record("command", target="x", metadata={cle: "valeur-sensible"})

    assert "valeur-sensible" not in journal.entries()[0]["detail"]


def test_le_contexte_non_sensible_est_conserve(journal):
    """Tout expurger rendrait le journal inutile."""
    journal.record("test", target="pytest", metadata={"cible": "tests/agent"})

    assert "tests/agent" in journal.entries()[0]["detail"]


# ----------------------------------------------------------------------
# 2. Ce qui est consigné, et ce qui est refusé
# ----------------------------------------------------------------------

def test_une_action_non_declaree_est_refusee(journal):
    """Un nom inventé au vol rendrait le journal illisible."""
    with pytest.raises(ValueError) as refus:
        journal.record("danser")

    assert "non déclarée" in str(refus.value)


def test_les_actions_couvrent_le_cycle_de_reparation():
    """Une étape sans action déclarée serait invisible dans le journal."""
    for attendue in ("read", "write", "command", "patch", "test",
                     "branch", "merge", "rollback", "failure", "diagnosis"):
        assert attendue in ACTIONS


def test_les_entrees_se_filtrent_par_incident(journal):
    """C'est ainsi qu'on relit une réparation et pas le bruit d'à côté."""
    journal.record("read", incident_id="inc-1", target="a.py")
    journal.record("read", incident_id="inc-2", target="b.py")

    trouvees = journal.entries(incident_id="inc-1")

    assert len(trouvees) == 1
    assert trouvees[0]["target"] == "a.py"


def test_les_empreintes_sont_conservees(journal):
    """« Le fichier n'a pas changé » est une affirmation ; un SHA-256 est une preuve."""
    journal.record("write", target="x.py", hashes={"before": "aaa", "after": "bbb"})

    assert journal.entries()[0]["hashes"] == {"before": "aaa", "after": "bbb"}


# ----------------------------------------------------------------------
# 3. Les compteurs survivent à l'oubli
# ----------------------------------------------------------------------

def test_les_compteurs_survivent_a_l_eviction(journal):
    """Sinon un dépôt actif finirait par annoncer « aucune réparation »."""
    for _ in range(ENTREES_CONSERVEES + 25):
        journal.record("read", target="x.py")

    rapport = journal.journal_report()

    assert rapport["entries"] == ENTREES_CONSERVEES
    assert rapport["forgotten"] == 25
    assert rapport["by_action"]["read"] == ENTREES_CONSERVEES + 25


def test_le_rapport_dit_ses_regles(journal):
    """Un journal dont on ignore les garanties ne se lit pas."""
    regles = " ".join(journal.journal_report()["rules"])

    assert "Aucun secret" in regles
    assert "consigne" in regles


# ----------------------------------------------------------------------
# 4. La persistance ne fait jamais tomber l'action
# ----------------------------------------------------------------------

def test_une_ecriture_impossible_n_interrompt_pas_la_consignation(tmp_path):
    """Un journal qui casse la réparation qu'il observe serait pire que rien."""
    interdit = tmp_path / "fichier-existant"
    interdit.write_text("x", encoding="utf-8")
    # Un chemin dont le parent est un fichier : `makedirs` échouera.
    journal = AuditJournal(path=str(interdit / "sous" / "journal.jsonl"))

    journal.record("read", target="x.py")

    assert journal.entries()[0]["target"] == "x.py"
    assert journal.journal_report()["persisted_to"] is None


def test_le_journal_ecrit_reellement_sur_disque(tmp_path):
    """La persistance existe : elle n'est pas seulement annoncée."""
    chemin = tmp_path / "audit" / "journal.jsonl"
    journal = AuditJournal(path=str(chemin))

    journal.record("patch", incident_id="inc-9", target="src/x.py")

    with open(chemin, encoding="utf-8") as fichier:
        ligne = json.loads(fichier.readline())
    assert ligne["incident_id"] == "inc-9"
    assert ligne["action"] == "patch"


# ----------------------------------------------------------------------
# 5. L'observabilité tirée du journal
# ----------------------------------------------------------------------

def test_l_observabilite_compte_ce_qui_s_est_passe(journal):
    """Tentatives, annulations, catégories : les chiffres qui disent l'utilité."""
    journal.record("diagnosis", incident_id="inc-1", detail="ZeroDivisionError → division_by_zero")
    journal.record("write", incident_id="inc-1", target="src/x.py")
    journal.record("rollback", incident_id="inc-1", target="auto-patch/inc-1")

    mesures = observability(journal)

    assert mesures["incidents"] == 1
    assert mesures["rollbacks"] == 1
    assert mesures["failure_categories"]["division_by_zero"] == 1


def test_aucune_moyenne_n_est_calculee_sans_incident(journal):
    """Une moyenne sur zéro réparation serait un chiffre inventé."""
    mesures = observability(journal)

    assert mesures["attempts_per_incident"] is None
    assert "inventé" in mesures["note"]
