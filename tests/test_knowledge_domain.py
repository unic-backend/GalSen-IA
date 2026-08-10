"""
Tests du domaine de connaissance (VOLET 05, chapitre 02 — organisation).

Le chapitre exige que la connaissance soit organisée avant d'être consommée :
le domaine est le premier niveau de cette organisation. Ces tests vérifient
qu'il est porté par l'élément, filtrable dans les deux magasins, persistant,
et qu'une base écrite avant son existence reste lisible.
"""

import sqlite3

import pytest

from src.knowledge_engine.types import KnowledgeDomain, KnowledgeItem
from src.knowledge_engine.knowledge_store import InMemoryKnowledgeStore
from src.storage.sqlite_knowledge_store import SQLiteKnowledgeStore


def _item(content: str, domain: KnowledgeDomain) -> KnowledgeItem:
    """Construit un élément de connaissance dans un domaine donné."""
    return KnowledgeItem(content=content, domain=domain)


def test_domaine_par_defaut_est_non_classe():
    """Un élément sans domaine explicite est « non classé », pas classé au hasard."""
    assert KnowledgeItem(content="Dakar est la capitale du Sénégal.").domain is KnowledgeDomain.UNSPECIFIED


def test_les_sept_domaines_du_chapitre_existent():
    """Les sept domaines nommés par le VOLET 05 sont déclarés, plus « non classé »."""
    attendus = {
        "business", "technical", "operational", "legal",
        "ai", "user_documentation", "project_documentation",
    }
    valeurs = {d.value for d in KnowledgeDomain}
    assert attendus.issubset(valeurs)
    assert valeurs - attendus == {"unspecified"}


def test_filtre_domaine_en_memoire():
    """Le magasin mémoire filtre par domaine, avec l'enum comme avec sa valeur."""
    store = InMemoryKnowledgeStore()
    id_legal = store.save(_item("Le code du travail sénégalais.", KnowledgeDomain.LEGAL))
    id_tech = store.save(_item("Le moteur tourne sur SQLite.", KnowledgeDomain.TECHNICAL))

    legal = store.list_items(domain=KnowledgeDomain.LEGAL)
    assert [k.id for k in legal] == [id_legal]

    tech = store.list_items(domain="technical")
    assert [k.id for k in tech] == [id_tech]

    assert store.count(domain=KnowledgeDomain.BUSINESS) == 0


def test_domaine_persiste_et_filtre_en_sqlite(tmp_path):
    """Le domaine survit à un aller-retour SQLite et reste filtrable."""
    db = str(tmp_path / "knowledge.sqlite")
    store = SQLiteKnowledgeStore(db_path=db)
    identifiant = store.save(_item("Le PIB du Sénégal.", KnowledgeDomain.BUSINESS))
    store.close()

    relu = SQLiteKnowledgeStore(db_path=db)
    assert relu.get(identifiant).domain is KnowledgeDomain.BUSINESS
    assert [k.id for k in relu.list_items(domain=KnowledgeDomain.BUSINESS)] == [identifiant]
    assert relu.list_items(domain=KnowledgeDomain.LEGAL) == []
    relu.close()


def test_base_anterieure_sans_colonne_domaine_reste_lisible(tmp_path):
    """Une base écrite avant l'ajout du domaine est migrée sans perdre ses lignes."""
    db = str(tmp_path / "ancienne.sqlite")
    store = SQLiteKnowledgeStore(db_path=db)
    identifiant = store.save(_item("Connaissance écrite avant le domaine.", KnowledgeDomain.AI))
    store.close()

    # Reconstruit la table telle qu'elle existait sans la colonne "domain".
    anciennes = [c for c in SQLiteKnowledgeStore._COLUMNS if c != "domain"]
    with sqlite3.connect(db) as conn:
        conn.execute(f"CREATE TABLE ancienne AS SELECT {', '.join(anciennes)} FROM knowledge_items")
        conn.execute("DROP TABLE knowledge_items")
        conn.execute("ALTER TABLE ancienne RENAME TO knowledge_items")
        assert "domain" not in {row[1] for row in conn.execute("PRAGMA table_info(knowledge_items)")}

    migre = SQLiteKnowledgeStore(db_path=db)
    relu = migre.get(identifiant)
    assert relu is not None
    assert relu.content == "Connaissance écrite avant le domaine."
    # La ligne antérieure n'avait pas de domaine : elle est « non classée », pas inventée.
    assert relu.domain is KnowledgeDomain.UNSPECIFIED

    # La base migrée accepte à nouveau un domaine explicite.
    nouvel_id = migre.save(_item("Écrite après la migration.", KnowledgeDomain.OPERATIONAL))
    assert migre.get(nouvel_id).domain is KnowledgeDomain.OPERATIONAL
    migre.close()


def test_nouvelle_version_conserve_le_domaine():
    """Mettre à jour le contenu ne reclasse pas la connaissance."""
    origine = _item("Première rédaction.", KnowledgeDomain.PROJECT_DOCUMENTATION)
    suivante = origine.update_content("Rédaction corrigée.")
    assert suivante.domain is KnowledgeDomain.PROJECT_DOCUMENTATION
    assert suivante.version == origine.version + 1


def test_domaine_inconnu_est_refuse():
    """Le domaine est fermé : une valeur hors liste ne peut pas être construite."""
    with pytest.raises(ValueError):
        KnowledgeDomain("agriculture")
