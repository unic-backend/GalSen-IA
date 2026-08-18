"""
L'audit et les approbations survivent au redémarrage (backlog P2 — ADR-005).

Les deux vivaient en mémoire du processus, alors que les cinq autres services
avaient déjà leur magasin. Ce qu'ils portent est pourtant ce qu'on vient
chercher **après** :

- un journal d'audit qui disparaît au redémarrage ne sert à rien le jour d'un
  incident — et ce jour-là, le service a souvent redémarré ;
- une demande d'approbation perdue, c'est une modification qui attend une
  décision que plus personne ne peut prendre, ou une décision **déjà accordée**
  qui s'évapore et qu'un agent redemande.

Depuis le VOLET 31, toute écriture de code passe par ce portillon : sa
persistance n'est plus un confort.

Ces tests vérifient les deux magasins **et** leur équivalence avec la version
mémoire : deux implémentations d'un même contrat qui divergent est le défaut que
ce dépôt a déjà trouvé trois fois.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.approval_engine.approval_store import InMemoryApprovalStore  # noqa: E402
from src.approval_engine.types import ApprovalRequest, ApprovalStatus  # noqa: E402
from src.audit_engine.audit_store import InMemoryAuditStore  # noqa: E402
from src.audit_engine.types import AuditEvent, AuditEventType, AuditStatus  # noqa: E402
from src.storage.sqlite_approval_store import SQLiteApprovalStore  # noqa: E402
from src.storage.sqlite_audit_store import SQLiteAuditStore  # noqa: E402


@pytest.fixture
def journal(tmp_path):
    """Journal d'audit sur disque, pour pouvoir le rouvrir."""
    chemin = str(tmp_path / "audit.sqlite")
    magasin = SQLiteAuditStore(chemin)
    yield magasin, chemin
    magasin.close()


@pytest.fixture
def portillon(tmp_path):
    """Magasin d'approbations sur disque."""
    chemin = str(tmp_path / "approvals.sqlite")
    magasin = SQLiteApprovalStore(chemin)
    yield magasin, chemin
    magasin.close()


def _evenement(**kwargs) -> AuditEvent:
    """Construit un événement d'audit."""
    defauts = {
        "event_type": AuditEventType.REQUEST,
        "action": "workflow:run",
        "agent_id": "planner",
        "request_id": "req_1",
        "status": AuditStatus.SUCCESS,
    }
    return AuditEvent(**{**defauts, **kwargs})


# ----------------------------------------------------------------------
# Le journal survit
# ----------------------------------------------------------------------

def test_le_journal_survit_a_un_redemarrage(journal):
    """Le fait qui justifie ce travail."""
    magasin, chemin = journal
    magasin.save(_evenement(detail="clé révoquée"))
    magasin.close()

    rouvert = SQLiteAuditStore(chemin)
    try:
        evenements = rouvert.list_events()
        assert len(evenements) == 1
        assert evenements[0].detail == "clé révoquée"
    finally:
        rouvert.close()


def test_un_evenement_garde_tous_ses_champs(journal):
    """Les neuf champs de l'audit doivent traverser la sérialisation."""
    magasin, _ = journal
    identifiant = magasin.save(_evenement(
        model_id="samp-1", confidence=0.82, execution_time_seconds=1.25,
        knowledge_sources=[{"title": "Guide", "id": "kn1"}],
        metadata={"workflow_id": "default"}, user_request="Analyser la parcelle",
    ))

    relu = magasin.get(identifiant)

    assert relu.model_id == "samp-1"
    assert relu.confidence == 0.82
    assert relu.execution_time_seconds == 1.25
    assert relu.knowledge_sources == [{"title": "Guide", "id": "kn1"}]
    assert relu.metadata == {"workflow_id": "default"}
    assert relu.event_type is AuditEventType.REQUEST
    assert relu.status is AuditStatus.SUCCESS


def test_les_filtres_rendent_la_meme_chose_que_la_version_memoire(journal):
    """
    Deux implémentations d'un contrat qui divergent : le défaut trouvé trois
    fois dans ce dépôt. Les filtres sont traduits en SQL ici et appliqués en
    Python là ; ils doivent répondre pareil.
    """
    sqlite_store, _ = journal
    memoire = InMemoryAuditStore()

    evenements = [
        _evenement(agent_id="planner", status=AuditStatus.SUCCESS, timestamp=100.0),
        _evenement(agent_id="coder", status=AuditStatus.FAILURE, timestamp=200.0),
        _evenement(agent_id="coder", status=AuditStatus.SUCCESS, timestamp=300.0),
    ]
    for evenement in evenements:
        sqlite_store.save(evenement)
        memoire.save(evenement)

    for filtres in (
        {"agent_id": "coder"},
        {"status": AuditStatus.FAILURE},
        {"agent_id": "coder", "status": AuditStatus.SUCCESS},
        {"since": 200.0},
        {"until": 200.0},
    ):
        attendus = {e.id for e in memoire.list_events(**filtres)}
        obtenus = {e.id for e in sqlite_store.list_events(**filtres)}
        assert obtenus == attendus, f"divergence sur {filtres}"


def test_un_filtre_inconnu_est_refuse(journal):
    """
    Ignorer un filtre inconnu rendrait plus de lignes que demandé, ce qu'un
    lecteur de journal lirait comme une absence de filtre.
    """
    magasin, _ = journal

    with pytest.raises(ValueError, match="inconnu"):
        magasin.list_events(champ_qui_nexiste_pas="x")


def test_la_recherche_textuelle_trouve_dans_le_detail(journal):
    """Un incident se cherche par ce qu'on en sait : un mot, pas un identifiant."""
    magasin, _ = journal
    magasin.save(_evenement(detail="Tentative avec une clé révoquée"))
    magasin.save(_evenement(detail="Sauvegarde terminée"))

    trouves = magasin.search_events("révoquée")

    assert len(trouves) == 1
    assert "révoquée" in trouves[0].detail


def test_le_journal_est_rendu_du_plus_recent_au_plus_ancien(journal):
    """On ouvre un journal pour voir ce qui vient de se passer."""
    magasin, _ = journal
    magasin.save(_evenement(action="vieux", timestamp=100.0))
    magasin.save(_evenement(action="récent", timestamp=200.0))

    assert [e.action for e in magasin.list_events()] == ["récent", "vieux"]


# ----------------------------------------------------------------------
# Les approbations survivent
# ----------------------------------------------------------------------

def test_une_demande_survit_a_un_redemarrage(portillon):
    """Une décision accordée qui s'évapore ferait redemander ce qui l'était déjà."""
    magasin, chemin = portillon
    identifiant = magasin.submit(ApprovalRequest(
        agent_id="coder", request_id="req_1", action="code_edit",
        description="corrige le calcul",
    ))
    magasin.approve(identifiant, reason="revu", decided_by="awa")
    magasin.close()

    rouvert = SQLiteApprovalStore(chemin)
    try:
        relue = rouvert.get(identifiant)
        assert relue.status == ApprovalStatus.APPROVED.value
        assert relue.decided_by == "awa"
        assert relue.decided_at is not None
    finally:
        rouvert.close()


def test_une_demande_deja_decidee_ne_se_redecide_pas(portillon):
    """
    Le filtre de statut est dans l'`UPDATE` : deux décisions concurrentes ne
    peuvent pas toutes deux réussir. Vérifier puis écrire laisserait une fenêtre
    où une demande serait approuvée **et** rejetée.
    """
    magasin, _ = portillon
    identifiant = magasin.submit(ApprovalRequest(
        agent_id="coder", request_id="req_1", action="code_edit",
    ))

    assert magasin.approve(identifiant, decided_by="awa") is True
    assert magasin.reject(identifiant, decided_by="moussa") is False
    assert magasin.get(identifiant).decided_by == "awa"


def test_la_file_d_attente_se_lit_par_le_debut(portillon):
    """Une file se traite dans l'ordre d'arrivée — c'est aussi l'ordre du magasin mémoire."""
    magasin, _ = portillon
    premiere = magasin.submit(ApprovalRequest(
        agent_id="a", request_id="r", action="x", created_at=100.0,
    ))
    seconde = magasin.submit(ApprovalRequest(
        agent_id="b", request_id="r", action="y", created_at=200.0,
    ))

    assert [d.id for d in magasin.list_pending()] == [premiere, seconde]
    # `list_requests` reste, elle, du plus récent au plus ancien.
    assert [d.id for d in magasin.list_requests()] == [seconde, premiere]


def test_les_filtres_d_approbation_suivent_la_version_memoire(portillon):
    """Même contrat, mêmes réponses."""
    sqlite_store, _ = portillon
    memoire = InMemoryApprovalStore()

    demandes = [
        ApprovalRequest(agent_id="coder", request_id="req_1", action="code_edit"),
        ApprovalRequest(agent_id="security", request_id="req_1", action="scan"),
        ApprovalRequest(agent_id="coder", request_id="req_2", action="code_edit"),
    ]
    for demande in demandes:
        sqlite_store.submit(demande)
        memoire.submit(demande)

    for filtres in ({"agent_id": "coder"}, {"request_id": "req_1"},
                    {"status": ApprovalStatus.PENDING.value}):
        attendus = {d.id for d in memoire.list_requests(**filtres)}
        obtenus = {d.id for d in sqlite_store.list_requests(**filtres)}
        assert obtenus == attendus, f"divergence sur {filtres}"


def test_l_etat_distingue_l_attente_du_total(portillon):
    """« Combien attendent une décision » est la seule question posée en boucle."""
    magasin, _ = portillon
    accordee = magasin.submit(ApprovalRequest(agent_id="a", request_id="r", action="x"))
    magasin.submit(ApprovalRequest(agent_id="b", request_id="r", action="y"))
    magasin.approve(accordee)

    etat = magasin.stats()

    assert etat["total_requests"] == 2
    assert etat["pending"] == 1


# ----------------------------------------------------------------------
# Le choix du magasin suit ADR-005
# ----------------------------------------------------------------------

def test_les_gestionnaires_suivent_le_backend_declare(tmp_path, monkeypatch):
    """`GALSEN_STORAGE_BACKEND=sqlite` doit suffire, comme pour les cinq autres."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
    from src.approval_engine.approval_manager import ApprovalManagerImpl
    from src.audit_engine.audit_manager import AuditManagerImpl

    assert type(AuditManagerImpl()._store).__name__ == "SQLiteAuditStore"
    assert type(ApprovalManagerImpl()._store).__name__ == "SQLiteApprovalStore"


def test_le_defaut_reste_la_memoire(tmp_path, monkeypatch):
    """Le défaut du projet reste `in-memory` (ADR-005) : rien ne change sans décision."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)
    from src.approval_engine.approval_manager import ApprovalManagerImpl
    from src.audit_engine.audit_manager import AuditManagerImpl

    assert type(AuditManagerImpl()._store).__name__ == "InMemoryAuditStore"
    assert type(ApprovalManagerImpl()._store).__name__ == "InMemoryApprovalStore"
