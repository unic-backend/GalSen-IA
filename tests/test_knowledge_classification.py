"""
Tests de la classification des connaissances (VOLET 05, chapitre 02).

Le chapitre classe la connaissance selon cinq axes : source, fiabilité,
sensibilité, audience et statut. Ces tests couvrent les deux axes ajoutés en
phase 2.2 — sensibilité et statut — dans les deux magasins.
"""

import pytest

from src.knowledge_engine.types import (
    KnowledgeItem, KnowledgeSensitivity, KnowledgeStatus,
)
from src.knowledge_engine.knowledge_store import InMemoryKnowledgeStore
from src.storage.sqlite_knowledge_store import SQLiteKnowledgeStore


def test_defauts_ne_protegent_ni_ne_valident():
    """Sans déclaration, une connaissance est publique et en brouillon."""
    item = KnowledgeItem(content="Le Sénégal compte 14 régions.")
    assert item.sensitivity is KnowledgeSensitivity.PUBLIC
    assert item.status is KnowledgeStatus.DRAFT


def test_les_statuts_couvrent_les_deux_chapitres():
    """Un seul axe porte la progression des chapitres 02 et 04."""
    valeurs = {s.value for s in KnowledgeStatus}
    # Chapitre 02 : Draft, Reviewed, Approved, Archived.
    assert {"draft", "reviewed", "approved", "archived"}.issubset(valeurs)
    # Chapitre 04 : Under Review et Deprecated en plus ; « Verified » = REVIEWED.
    assert {"under_review", "deprecated"}.issubset(valeurs)
    assert "verified" not in valeurs


def test_filtres_sensibilite_et_statut_en_memoire():
    """Le magasin mémoire filtre sur les deux axes, par enum comme par valeur."""
    store = InMemoryKnowledgeStore()
    id_public = store.save(KnowledgeItem(
        content="Horaires d'ouverture publiés.",
        sensitivity=KnowledgeSensitivity.PUBLIC,
        status=KnowledgeStatus.APPROVED,
    ))
    id_secret = store.save(KnowledgeItem(
        content="Grille salariale interne.",
        sensitivity=KnowledgeSensitivity.CONFIDENTIAL,
        status=KnowledgeStatus.UNDER_REVIEW,
    ))

    assert [k.id for k in store.list_items(sensitivity=KnowledgeSensitivity.CONFIDENTIAL)] == [id_secret]
    assert [k.id for k in store.list_items(status="approved")] == [id_public]
    assert store.count(sensitivity=KnowledgeSensitivity.RESTRICTED) == 0


def test_classification_persiste_et_filtre_en_sqlite(tmp_path):
    """Sensibilité et statut survivent à un aller-retour SQLite."""
    db = str(tmp_path / "knowledge.sqlite")
    store = SQLiteKnowledgeStore(db_path=db)
    identifiant = store.save(KnowledgeItem(
        content="Contrat cadre signé.",
        sensitivity=KnowledgeSensitivity.RESTRICTED,
        status=KnowledgeStatus.ARCHIVED,
    ))
    store.close()

    relu = SQLiteKnowledgeStore(db_path=db)
    item = relu.get(identifiant)
    assert item.sensitivity is KnowledgeSensitivity.RESTRICTED
    assert item.status is KnowledgeStatus.ARCHIVED
    assert [k.id for k in relu.list_items(status=KnowledgeStatus.ARCHIVED)] == [identifiant]
    assert relu.list_items(sensitivity=KnowledgeSensitivity.PUBLIC) == []
    relu.close()


def test_base_anterieure_relit_les_defauts(tmp_path):
    """Une base sans les colonnes de classification n'invente ni protection ni validation."""
    db = str(tmp_path / "ancienne.sqlite")
    store = SQLiteKnowledgeStore(db_path=db)
    identifiant = store.save(KnowledgeItem(
        content="Écrite avant la classification.",
        sensitivity=KnowledgeSensitivity.CONFIDENTIAL,
        status=KnowledgeStatus.APPROVED,
    ))
    store.close()

    anciennes = [c for c in SQLiteKnowledgeStore._COLUMNS if c not in ("sensitivity", "status")]
    import sqlite3
    with sqlite3.connect(db) as conn:
        conn.execute(f"CREATE TABLE ancienne AS SELECT {', '.join(anciennes)} FROM knowledge_items")
        conn.execute("DROP TABLE knowledge_items")
        conn.execute("ALTER TABLE ancienne RENAME TO knowledge_items")

    migre = SQLiteKnowledgeStore(db_path=db)
    item = migre.get(identifiant)
    assert item.content == "Écrite avant la classification."
    assert item.sensitivity is KnowledgeSensitivity.PUBLIC
    assert item.status is KnowledgeStatus.DRAFT
    migre.close()


def test_contenu_reecrit_repart_en_brouillon():
    """Une nouvelle version n'hérite pas de l'approbation de la précédente."""
    approuve = KnowledgeItem(
        content="Première rédaction.",
        sensitivity=KnowledgeSensitivity.INTERNAL,
        status=KnowledgeStatus.APPROVED,
    )
    suivante = approuve.update_content("Rédaction corrigée.")
    assert suivante.status is KnowledgeStatus.DRAFT
    # La sensibilité, elle, tient au sujet et non à la rédaction : elle est conservée.
    assert suivante.sensitivity is KnowledgeSensitivity.INTERNAL


@pytest.mark.parametrize("enumeration, inconnu", [
    (KnowledgeSensitivity, "secret_defense"),
    (KnowledgeStatus, "verified"),
])
def test_axes_fermes(enumeration, inconnu):
    """Les deux axes sont fermés : une valeur hors liste est refusée."""
    with pytest.raises(ValueError):
        enumeration(inconnu)
