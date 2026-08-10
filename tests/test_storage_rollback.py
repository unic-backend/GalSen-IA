"""
Tests de compatibilité descendante des bases SQLite (VOLET 03, chapitre 05).

Le chapitre exige un retour arrière rapide qui **préserve l'intégrité des
données**. Pour cette plateforme, le retour arrière consiste à redéployer une
image antérieure sur les mêmes fichiers SQLite : la question n'est donc pas « le
code revient-il en arrière » — Docker s'en charge — mais « la base écrite par la
version récente reste-t-elle lisible par la précédente ».

Elle l'est parce que les migrations sont **additives** et que les lectures
nomment leurs colonnes. Ces tests le prouvent dans les deux sens plutôt que de
l'affirmer.
"""

import sqlite3

import pytest

from src.knowledge_engine.types import (
    KnowledgeDomain, KnowledgeItem, KnowledgeSensitivity, KnowledgeStatus,
)
from src.storage.sqlite_knowledge_store import SQLiteKnowledgeStore

# Colonnes ajoutées par le VOLET 05 : une version antérieure les ignore.
COLONNES_RECENTES = ("domain", "sensitivity", "status")


@pytest.fixture
def base(tmp_path):
    """Chemin d'une base neuve, propre à un test."""
    return str(tmp_path / "knowledge.sqlite")


def test_une_version_anterieure_lit_une_base_recente(base):
    """Retour arrière : l'ancien code lit ses colonnes, ignore celles qu'il ignore."""
    magasin = SQLiteKnowledgeStore(db_path=base)
    identifiant = magasin.save(KnowledgeItem(
        content="Écrite par la version récente, avec sa classification.",
        domain=KnowledgeDomain.LEGAL,
        sensitivity=KnowledgeSensitivity.CONFIDENTIAL,
        status=KnowledgeStatus.APPROVED,
    ))
    magasin.close()

    # Une version antérieure sélectionne explicitement les colonnes qu'elle connaît.
    anciennes = [c for c in SQLiteKnowledgeStore._COLUMNS if c not in COLONNES_RECENTES]
    with sqlite3.connect(base) as conn:
        ligne = conn.execute(
            f"SELECT {', '.join(anciennes)} FROM knowledge_items WHERE id = ?", (identifiant,)
        ).fetchone()

    assert ligne is not None
    assert dict(zip(anciennes, ligne))["id"] == identifiant


def test_une_version_recente_lit_une_base_anterieure(base):
    """Roulement avant : les colonnes absentes sont ajoutées, les lignes conservées."""
    magasin = SQLiteKnowledgeStore(db_path=base)
    identifiant = magasin.save(KnowledgeItem(content="Écrite avant la migration."))
    magasin.close()

    anciennes = [c for c in SQLiteKnowledgeStore._COLUMNS if c not in COLONNES_RECENTES]
    with sqlite3.connect(base) as conn:
        conn.execute(f"CREATE TABLE ancienne AS SELECT {', '.join(anciennes)} FROM knowledge_items")
        conn.execute("DROP TABLE knowledge_items")
        conn.execute("ALTER TABLE ancienne RENAME TO knowledge_items")

    migre = SQLiteKnowledgeStore(db_path=base)
    relu = migre.get(identifiant)
    assert relu is not None and relu.content == "Écrite avant la migration."
    migre.close()


def test_un_aller_retour_ne_perd_aucune_ligne(base):
    """Migrer, revenir, remigrer : le contenu traverse les trois états."""
    magasin = SQLiteKnowledgeStore(db_path=base)
    identifiants = [
        magasin.save(KnowledgeItem(content=f"Connaissance numéro {i} sur le fleuve."))
        for i in range(5)
    ]
    magasin.close()

    # Retour arrière simulé : la table perd les colonnes récentes.
    anciennes = [c for c in SQLiteKnowledgeStore._COLUMNS if c not in COLONNES_RECENTES]
    with sqlite3.connect(base) as conn:
        conn.execute(f"CREATE TABLE ancienne AS SELECT {', '.join(anciennes)} FROM knowledge_items")
        conn.execute("DROP TABLE knowledge_items")
        conn.execute("ALTER TABLE ancienne RENAME TO knowledge_items")

    # Re-roulement avant : la migration additive les remet.
    remigre = SQLiteKnowledgeStore(db_path=base)
    assert remigre.count() == 5
    for identifiant in identifiants:
        assert remigre.get(identifiant) is not None
    remigre.close()


def test_la_migration_n_efface_ni_ne_renomme_une_colonne(base):
    """Une migration additive ne détruit rien : c'est ce qui rend le retour possible."""
    magasin = SQLiteKnowledgeStore(db_path=base)
    magasin.close()

    with sqlite3.connect(base) as conn:
        colonnes_avant = {r[1] for r in conn.execute("PRAGMA table_info(knowledge_items)")}

    # Ré-ouvrir déclenche la migration : elle ne doit qu'ajouter.
    encore = SQLiteKnowledgeStore(db_path=base)
    encore.close()
    with sqlite3.connect(base) as conn:
        colonnes_apres = {r[1] for r in conn.execute("PRAGMA table_info(knowledge_items)")}

    assert colonnes_avant <= colonnes_apres
    assert set(SQLiteKnowledgeStore._COLUMNS) <= colonnes_apres
