"""
Tests unitaires pour le module de stockage persistant de GalSen IA.

Couvre :
- SQLiteMemoryStore avec base de données en mémoire (:memory:)
- Opérations CRUD : save, get, update, delete
- Listage avec filtres : memory_type, user_id, session_id, agent_id, tags, status
- Pagination : limit, offset
- clear() avec filtres
- cleanup_expired()
- Sérialisation/désérialisation des MemoryItem
- Cas limites : entité inexistante, champs JSON, tags

Conforme à ADR-005 : les tests utilisent une base :memory: pour l'isolation.
"""

import os
import sys
import time

import pytest

# S'assurer que le chemin d'importation est correct
# La racine du dépôt doit être importable : convention unique `src.<module>`.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.storage.sqlite_store import SQLiteMemoryStore
from src.storage.base_repository import BaseRepository
from src.memory_engine.types import MemoryItem, MemoryType, MemoryPriority, MemoryStatus
from src.memory_engine.interfaces import MemoryStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store():
    """Crée un magasin SQLite en mémoire pour les tests.

    Avec ``cache=shared``, toutes les connexions :memory: partagent la
    même base. On nettoie avant chaque test pour garantir l'isolation.
    Une connexion persistante maintient la base en vie entre les appels.
    """
    s = SQLiteMemoryStore(db_path=":memory:")
    s.clear()
    yield s
    s.close()


@pytest.fixture
def sample_item():
    """Crée un MemoryItem de test."""
    return MemoryItem(
        content="Ceci est un contenu de test en français.",
        memory_type=MemoryType.SHORT_TERM,
        user_id="user-123",
        session_id="session-abc",
        agent_id="agent-researcher",
        tags=["test", "unitaire"],
        priority=MemoryPriority.MEDIUM,
        status=MemoryStatus.ACTIVE,
        metadata={"source": "test", "langue": "fr"},
    )


@pytest.fixture
def sample_item_long_term():
    """Crée un MemoryItem de type LONG_TERM."""
    return MemoryItem(
        content="Mémoire à long terme.",
        memory_type=MemoryType.LONG_TERM,
        user_id="user-456",
        session_id="session-def",
        tags=["important", "persistant"],
        priority=MemoryPriority.HIGH,
    )


# ---------------------------------------------------------------------------
# Tests : interface BaseRepository
# ---------------------------------------------------------------------------


class TestBaseRepository:
    """Vérifie que BaseRepository est une classe abstraite."""

    def test_base_repository_est_abstraite(self):
        """BaseRepository ne peut pas être instanciée directement."""
        with pytest.raises(TypeError):
            BaseRepository()  # type: ignore

    def test_base_repository_definit_save(self):
        """BaseRepository expose la méthode save."""
        assert hasattr(BaseRepository, "save")
        assert callable(getattr(BaseRepository, "save"))

    def test_base_repository_definit_get(self):
        """BaseRepository expose la méthode get."""
        assert hasattr(BaseRepository, "get")
        assert callable(getattr(BaseRepository, "get"))

    def test_base_repository_definit_update(self):
        """BaseRepository expose la méthode update."""
        assert hasattr(BaseRepository, "update")
        assert callable(getattr(BaseRepository, "update"))

    def test_base_repository_definit_delete(self):
        """BaseRepository expose la méthode delete."""
        assert hasattr(BaseRepository, "delete")
        assert callable(getattr(BaseRepository, "delete"))

    def test_base_repository_definit_list_items(self):
        """BaseRepository expose la méthode list_items."""
        assert hasattr(BaseRepository, "list_items")
        assert callable(getattr(BaseRepository, "list_items"))

    def test_base_repository_definit_clear(self):
        """BaseRepository expose la méthode clear."""
        assert hasattr(BaseRepository, "clear")
        assert callable(getattr(BaseRepository, "clear"))

    def test_base_repository_definit_count(self):
        """BaseRepository expose la méthode count."""
        assert hasattr(BaseRepository, "count")
        assert callable(getattr(BaseRepository, "count"))

    def test_base_repository_definit_exists(self):
        """BaseRepository expose la méthode exists."""
        assert hasattr(BaseRepository, "exists")
        assert callable(getattr(BaseRepository, "exists"))


# ---------------------------------------------------------------------------
# Tests : SQLiteMemoryStore — implémentation MemoryStore
# ---------------------------------------------------------------------------


class TestSQLiteMemoryStoreImplementsMemoryStore:
    """Vérifie que SQLiteMemoryStore implémente l'interface MemoryStore."""

    def test_est_sous_classe_de_memory_store(self):
        """SQLiteMemoryStore hérite de MemoryStore."""
        assert issubclass(SQLiteMemoryStore, MemoryStore)


# ---------------------------------------------------------------------------
# Tests : SQLiteMemoryStore — CRUD de base
# ---------------------------------------------------------------------------


class TestSQLiteMemoryStoreCRUD:
    """Tests des opérations CRUD fondamentales."""

    def test_save_retourne_id(self, store, sample_item):
        """save() retourne l'ID de l'élément sauvegardé."""
        item_id = store.save(sample_item)
        assert item_id == sample_item.id
        assert isinstance(item_id, str)
        assert len(item_id) > 0

    def test_save_et_get_cycle_complet(self, store, sample_item):
        """Un élément sauvegardé peut être récupéré avec get()."""
        store.save(sample_item)
        retrieved = store.get(sample_item.id)
        assert retrieved is not None
        assert retrieved.id == sample_item.id
        assert retrieved.content == sample_item.content

    def test_get_element_inexistant(self, store):
        """get() retourne None pour un ID inexistant."""
        result = store.get("id-inexistant")
        assert result is None

    def test_update_element_existant(self, store, sample_item):
        """update() modifie un élément existant."""
        store.save(sample_item)
        sample_item.content = "Contenu modifié."
        updated = store.update(sample_item)
        assert updated is True
        retrieved = store.get(sample_item.id)
        assert retrieved.content == "Contenu modifié."

    def test_update_element_inexistant(self, store, sample_item):
        """update() retourne False pour un élément inexistant."""
        result = store.update(sample_item)
        assert result is False

    def test_delete_element_existant(self, store, sample_item):
        """delete() supprime un élément existant."""
        store.save(sample_item)
        deleted = store.delete(sample_item.id)
        assert deleted is True
        assert store.get(sample_item.id) is None

    def test_delete_element_inexistant(self, store):
        """delete() retourne False pour un ID inexistant."""
        result = store.delete("id-inexistant")
        assert result is False

    def test_save_avec_contenu_json(self, store):
        """Le contenu de type dict est sérialisé et désérialisé correctement."""
        item = MemoryItem(
            content={"cle": "valeur", "nombre": 42},
            memory_type=MemoryType.KNOWLEDGE,
            tags=["données-structurées"],
        )
        store.save(item)
        retrieved = store.get(item.id)
        assert retrieved.content == {"cle": "valeur", "nombre": 42}

    def test_save_avec_metadonnees_complexes(self, store):
        """Les métadonnées JSON complexes sont préservées."""
        item = MemoryItem(
            content="Test métadonnées.",
            memory_type=MemoryType.SESSION,
            metadata={"nested": {"deep": [1, 2, 3]}, "flag": True},
        )
        store.save(item)
        retrieved = store.get(item.id)
        assert retrieved.metadata == {"nested": {"deep": [1, 2, 3]}, "flag": True}

    def test_save_avec_tags_vides(self, store):
        """Un élément avec tags vides est correctement géré."""
        item = MemoryItem(
            content="Sans tags.",
            memory_type=MemoryType.SHORT_TERM,
            tags=[],
        )
        store.save(item)
        retrieved = store.get(item.id)
        assert retrieved.tags == []


# ---------------------------------------------------------------------------
# Tests : SQLiteMemoryStore — list_items
# ---------------------------------------------------------------------------


class TestSQLiteMemoryStoreListItems:
    """Tests de la méthode list_items avec filtrage et pagination."""

    def test_list_items_retourne_tout(self, store, sample_item, sample_item_long_term):
        """list_items() sans filtre retourne tous les éléments."""
        store.save(sample_item)
        store.save(sample_item_long_term)
        result = store.list_items()
        assert len(result) == 2

    def test_list_items_filtre_memory_type(self, store, sample_item, sample_item_long_term):
        """list_items() filtre par memory_type."""
        store.save(sample_item)
        store.save(sample_item_long_term)
        result = store.list_items(memory_type=MemoryType.SHORT_TERM)
        assert len(result) == 1
        assert result[0].memory_type == MemoryType.SHORT_TERM

    def test_list_items_filtre_user_id(self, store, sample_item, sample_item_long_term):
        """list_items() filtre par user_id."""
        store.save(sample_item)
        store.save(sample_item_long_term)
        result = store.list_items(user_id="user-123")
        assert len(result) == 1
        assert result[0].user_id == "user-123"

    def test_list_items_filtre_session_id(self, store, sample_item, sample_item_long_term):
        """list_items() filtre par session_id."""
        store.save(sample_item)
        store.save(sample_item_long_term)
        result = store.list_items(session_id="session-abc")
        assert len(result) == 1
        assert result[0].session_id == "session-abc"

    def test_list_items_filtre_agent_id(self, store, sample_item, sample_item_long_term):
        """list_items() filtre par agent_id."""
        store.save(sample_item)
        store.save(sample_item_long_term)
        result = store.list_items(agent_id="agent-researcher")
        assert len(result) == 1
        assert result[0].agent_id == "agent-researcher"

    def test_list_items_filtre_status(self, store, sample_item):
        """list_items() filtre par status."""
        store.save(sample_item)
        result = store.list_items(status=MemoryStatus.ACTIVE)
        assert len(result) >= 1
        result_archived = store.list_items(status=MemoryStatus.ARCHIVED)
        assert len(result_archived) == 0

    def test_list_items_filtre_tags(self, store, sample_item, sample_item_long_term):
        """list_items() filtre par tags (doit contenir tous les tags spécifiés)."""
        store.save(sample_item)
        store.save(sample_item_long_term)
        result = store.list_items(tags=["test"])
        assert len(result) == 1
        result_multi = store.list_items(tags=["test", "unitaire"])
        assert len(result_multi) == 1
        # Aucun élément n'a à la fois "test" et "persistant"
        result_cross = store.list_items(tags=["test", "persistant"])
        assert len(result_cross) == 0

    def test_list_items_pagination_limit(self, store):
        """list_items() respecte le paramètre limit."""
        for i in range(10):
            item = MemoryItem(
                content=f"Item {i}",
                memory_type=MemoryType.SHORT_TERM,
            )
            store.save(item)
        result = store.list_items(limit=3)
        assert len(result) == 3

    def test_list_items_pagination_offset(self, store):
        """list_items() respecte le paramètre offset."""
        for i in range(5):
            item = MemoryItem(
                content=f"Item {i}",
                memory_type=MemoryType.SHORT_TERM,
            )
            store.save(item)
        all_items = store.list_items(limit=10)
        assert len(all_items) == 5
        result = store.list_items(limit=10, offset=2)
        assert len(result) == 3  # 5 - 2 = 3

    def test_list_items_combinaison_filtres(self, store, sample_item, sample_item_long_term):
        """list_items() avec plusieurs filtres combinés."""
        store.save(sample_item)
        store.save(sample_item_long_term)
        result = store.list_items(
            memory_type=MemoryType.SHORT_TERM,
            user_id="user-123",
        )
        assert len(result) == 1
        assert result[0].id == sample_item.id

    def test_list_items_vide(self, store):
        """list_items() retourne une liste vide quand le magasin est vide."""
        result = store.list_items()
        assert result == []


# ---------------------------------------------------------------------------
# Tests : SQLiteMemoryStore — clear
# ---------------------------------------------------------------------------


class TestSQLiteMemoryStoreClear:
    """Tests de la méthode clear."""

    def test_clear_total(self, store, sample_item, sample_item_long_term):
        """clear() sans filtre supprime tous les éléments."""
        store.save(sample_item)
        store.save(sample_item_long_term)
        count = store.clear()
        assert count == 2
        assert store.list_items() == []

    def test_clear_filtre_memory_type(self, store, sample_item, sample_item_long_term):
        """clear() avec filtre memory_type ne supprime que les éléments correspondants."""
        store.save(sample_item)
        store.save(sample_item_long_term)
        count = store.clear(memory_type=MemoryType.SHORT_TERM)
        assert count == 1
        remaining = store.list_items()
        assert len(remaining) == 1
        assert remaining[0].memory_type == MemoryType.LONG_TERM

    def test_clear_filtre_user_id(self, store, sample_item, sample_item_long_term):
        """clear() avec filtre user_id."""
        store.save(sample_item)
        store.save(sample_item_long_term)
        count = store.clear(user_id="user-456")
        assert count == 1
        remaining = store.list_items()
        assert len(remaining) == 1
        assert remaining[0].user_id == "user-123"

    def test_clear_magasin_vide(self, store):
        """clear() sur un magasin vide retourne 0."""
        count = store.clear()
        assert count == 0


# ---------------------------------------------------------------------------
# Tests : SQLiteMemoryStore — cleanup_expired
# ---------------------------------------------------------------------------


class TestSQLiteMemoryStoreCleanupExpired:
    """Tests de la méthode cleanup_expired."""

    def test_cleanup_supprime_elements_expires(self, store):
        """cleanup_expired() supprime les éléments dont expires_at est dépassé."""
        expired = MemoryItem(
            content="Élément expiré.",
            memory_type=MemoryType.SHORT_TERM,
            expires_at=time.time() - 3600,  # Expiré il y a 1 heure
        )
        store.save(expired)
        assert store.list_items() != []
        deleted = store.cleanup_expired()
        assert deleted == 1
        assert store.get(expired.id) is None

    def test_cleanup_conserve_elements_non_expires(self, store):
        """cleanup_expired() ne supprime pas les éléments non expirés."""
        valid = MemoryItem(
            content="Élément valide.",
            memory_type=MemoryType.SHORT_TERM,
            expires_at=time.time() + 3600,  # Expire dans 1 heure
        )
        store.save(valid)
        deleted = store.cleanup_expired()
        assert deleted == 0
        assert store.get(valid.id) is not None

    def test_cleanup_conserve_elements_sans_expiration(self, store, sample_item):
        """cleanup_expired() ne supprime pas les éléments sans date d'expiration."""
        store.save(sample_item)  # expires_at est None
        deleted = store.cleanup_expired()
        assert deleted == 0
        assert store.get(sample_item.id) is not None

    def test_cleanup_magasin_vide(self, store):
        """cleanup_expired() sur un magasin vide retourne 0."""
        deleted = store.cleanup_expired()
        assert deleted == 0


# ---------------------------------------------------------------------------
# Tests : SQLiteMemoryStore — cas limites et robustesse
# ---------------------------------------------------------------------------


class TestSQLiteMemoryStoreEdgeCases:
    """Tests des cas limites et de robustesse."""

    def test_save_remplace_element_meme_id(self, store, sample_item):
        """Sauvegarder un élément avec le même ID remplace l'existant (upsert)."""
        store.save(sample_item)
        sample_item.content = "Nouveau contenu."
        store.save(sample_item)
        retrieved = store.get(sample_item.id)
        assert retrieved.content == "Nouveau contenu."

    def test_contenu_avec_caracteres_speciaux(self, store):
        """Les caractères Unicode et spéciaux sont préservés."""
        content = " Wolof: ñ ë ŋ — Français: éèêëàù — Arabe: مرحبا "
        item = MemoryItem(
            content=content,
            memory_type=MemoryType.KNOWLEDGE,
            tags=["unicode", "テスト"],
        )
        store.save(item)
        retrieved = store.get(item.id)
        assert retrieved.content == content
        assert "テスト" in retrieved.tags

    def test_contenu_tres_long(self, store):
        """Un contenu volumineux est correctement sauvegardé et récupéré."""
        long_content = "A" * 100_000  # 100k caractères
        item = MemoryItem(
            content=long_content,
            memory_type=MemoryType.KNOWLEDGE,
        )
        store.save(item)
        retrieved = store.get(item.id)
        assert len(retrieved.content) == 100_000
        assert retrieved.content == long_content

    def test_operations_concurrentes_sur_meme_magasin(self, store):
        """Plusieurs opérations séquentielles sur le même magasin sont cohérentes."""
        ids = []
        for i in range(50):
            item = MemoryItem(content=f"Item {i}", memory_type=MemoryType.SHORT_TERM)
            store.save(item)
            ids.append(item.id)

        assert len(store.list_items(limit=100)) == 50

        for item_id in ids:
            assert store.get(item_id) is not None

    def test_type_memoire_differentes_valeurs(self, store):
        """Tous les types de mémoire sont correctement persistés."""
        content_map = {}
        for mem_type in MemoryType:
            item = MemoryItem(
                content=f"Contenu {mem_type.value}",
                memory_type=mem_type,
            )
            store.save(item)
            content_map[mem_type.value] = item.id

        for mem_type in MemoryType:
            item = store.get(content_map[mem_type.value])
            assert item is not None
            assert item.memory_type == mem_type

    def test_priorite_differentes_valeurs(self, store):
        """Toutes les priorités sont correctement persistées."""
        for priority in MemoryPriority:
            item = MemoryItem(
                content=f"Priorité {priority.value}",
                memory_type=MemoryType.SHORT_TERM,
                priority=priority,
            )
            store.save(item)
            retrieved = store.get(item.id)
            assert retrieved.priority == priority

    def test_status_differentes_valeurs(self, store):
        """Tous les statuts sont correctement persistés."""
        for status in MemoryStatus:
            item = MemoryItem(
                content=f"Statut {status.value}",
                memory_type=MemoryType.SHORT_TERM,
                status=status,
            )
            store.save(item)
            retrieved = store.get(item.id)
            assert retrieved.status == status


# ---------------------------------------------------------------------------
# Tests : SQLiteMemoryStore — persistence (fichier)
# ---------------------------------------------------------------------------


class TestSQLiteMemoryStoreFilePersistence:
    """Tests de persistance sur fichier (pas :memory:)."""

    def test_persistance_fichier_reel(self, tmp_path):
        """Les données survivent à la fermeture et réouverture du magasin."""
        db_path = str(tmp_path / "test_persist.sqlite")
        store1 = SQLiteMemoryStore(db_path=db_path)
        item = MemoryItem(content="Persistant.", memory_type=MemoryType.LONG_TERM)
        store1.save(item)

        # Fermer et rouvrir
        store2 = SQLiteMemoryStore(db_path=db_path)
        retrieved = store2.get(item.id)
        assert retrieved is not None
        assert retrieved.content == "Persistant."

    def test_fichier_cree_automatiquement(self, tmp_path):
        """Le fichier de base de données est créé automatiquement."""
        db_path = str(tmp_path / "subdir" / "auto_create.sqlite")
        store = SQLiteMemoryStore(db_path=db_path)
        item = MemoryItem(content="Création auto.", memory_type=MemoryType.SHORT_TERM)
        store.save(item)
        assert os.path.exists(db_path)


# ---------------------------------------------------------------------------
# Tests : exports du package storage
# ---------------------------------------------------------------------------


class TestStoragePackageExports:
    """Vérifie que le package storage exporte correctement ses classes."""

    def test_sqlite_memory_store_importable(self):
        """SQLiteMemoryStore est importable depuis le package."""
        from src.storage import SQLiteMemoryStore
        assert SQLiteMemoryStore is not None

    def test_base_repository_importable(self):
        """BaseRepository est importable depuis le package."""
        from src.storage import BaseRepository
        assert BaseRepository is not None
