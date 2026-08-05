"""
Tests unitaires pour la persistance SQLite des moteurs de modèles et de
connaissances (Phase 4, ADR-005).

Couvre pour chaque store :
- Opérations CRUD : save, get, update, delete
- Sémantique des versions (save/update ne font jamais régresser une version)
- list_items avec tous les filtres, l'ordre et la limite
- cleanup (models) / cleanup_old_versions (knowledge)
- Persistance à travers une réouverture du fichier
- Fonctionnement en :memory: et création automatique des dossiers
- Aller-retour de sérialisation (enums, dates, JSON, priorité)
- Concurrence (verrou + PRAGMA busy_timeout)

Et le branchement des moteurs (GALSEN_STORAGE_BACKEND) :
- Sélection du backend SQLite via la variable d'environnement
- Backend en mémoire par défaut
- Injection explicite d'un store prioritaire
- GALSEN_DATA_DIR évite toute pollution du dépôt pendant les tests
"""

import os
import sys
import threading
import datetime

import pytest

# S'assurer que le chemin d'importation est correct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from storage.sqlite_model_store import SQLiteModelStore
from storage.sqlite_knowledge_store import SQLiteKnowledgeStore
from storage.paths import default_sqlite_path

from model_engine.types import ModelItem, ModelType, ModelPriority, ModelStatus
from model_engine.model_manager import ModelManagerImpl

from knowledge_engine.types import (
    KnowledgeItem,
    KnowledgeSource,
    KnowledgeType,
    ContentType,
    Language,
    SourceCategory,
    KnowledgePriority,
)
from knowledge_engine.knowledge_manager import KnowledgeManagerImpl


# --------------------------------------------------------------------------
# Fabriques d'éléments de test
# --------------------------------------------------------------------------

def _make_model(model_id="model-1", model_type=ModelType.LOCAL_OLLAMA,
                provider="ollama", name="Test Model", version="1.0",
                priority=ModelPriority.MEDIUM, status=ModelStatus.ACTIVE,
                context_window=4096, **kwargs) -> ModelItem:
    """Crée un modèle de test avec des valeurs par défaut stables."""
    return ModelItem(
        model_id=model_id,
        model_type=model_type,
        provider=provider,
        name=name,
        version=version,
        priority=priority,
        status=status,
        context_window=context_window,
        supported_features=kwargs.pop("supported_features", ["chat", "vision"]),
        metadata=kwargs.pop("metadata", {"tag": "dev"}),
        **kwargs,
    )


def _make_knowledge(content="Le Sénégal est un pays d'Afrique de l'Ouest.",
                    knowledge_type=KnowledgeType.FACT,
                    content_type=ContentType.TEXT,
                    language=Language.FR,
                    tags=None,
                    categories=None,
                    source_category=SourceCategory.OFFICIAL,
                    confidence=0.9,
                    priority=KnowledgePriority.P1,
                    source=None,
                    created_at=None,
                    updated_at=None) -> KnowledgeItem:
    """Crée une connaissance de test avec des valeurs par défaut stables."""
    if source is None:
        source = KnowledgeSource(
            id="src-001",
            type="file",
            location="/tmp/test.txt",
            source_category=source_category,
            title="Document de référence",
            author="Ministère",
            url="https://exemple.gouv.sn/ref",
            citation="Rapport officiel 2024",
            retrieved_at=datetime.datetime.now(datetime.timezone.utc),
        )
    kwargs = {}
    if created_at is not None:
        kwargs["created_at"] = created_at
    if updated_at is not None:
        kwargs["updated_at"] = updated_at
    return KnowledgeItem(
        content=content,
        knowledge_type=knowledge_type,
        content_type=content_type,
        language=language,
        tags=tags or ["afrique", "senegal"],
        categories=categories or ["geographie"],
        source=source,
        confidence=confidence,
        priority=priority,
        metadata={"source_ref": "doc-2024"},
        relations=["r1", "r2"],
        **kwargs,
    )


# --------------------------------------------------------------------------
# SQLiteModelStore
# --------------------------------------------------------------------------

class TestSQLiteModelStore:

    def test_crud_roundtrip(self, tmp_path):
        """save, get, update et delete fonctionnent."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        mid = store.save(_make_model())
        assert mid == "model-1"

        model = store.get(mid)
        assert model is not None
        assert model.name == "Test Model"
        assert model.provider == "ollama"
        assert model.model_type is ModelType.LOCAL_OLLAMA
        assert model.priority is ModelPriority.MEDIUM
        assert model.status is ModelStatus.ACTIVE
        assert model.supported_features == ["chat", "vision"]
        assert model.metadata == {"tag": "dev"}

        # update (même version : le store SQLite l'accepte comme la mémoire)
        model.name = "Renamed"
        assert store.update(model) is True
        assert store.get(mid).name == "Renamed"

        assert store.delete(mid) is True
        assert store.get(mid) is None
        assert store.delete(mid) is False

    def test_get_missing_returns_none(self, tmp_path):
        """get() retourne None pour un identifiant inconnu."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        assert store.get("inconnu") is None

    def test_update_missing_returns_false(self, tmp_path):
        """update() d'un modèle inexistant retourne False."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        assert store.update(_make_model()) is False

    def test_save_updates_timestamp(self, tmp_path):
        """save() renouvelle updated_at."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        store.save(_make_model(updated_at=100.0))
        stored = store.get("model-1")
        assert stored.updated_at > 100.0

    def test_list_items_orders_by_updated_at_desc(self, tmp_path):
        """list_items trie par updated_at décroissant."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        store.save(_make_model(model_id="old", updated_at=100.0))
        store.save(_make_model(model_id="new", updated_at=200.0))
        items = store.list_items()
        assert [m.model_id for m in items] == ["new", "old"]

    def test_list_items_filters(self, tmp_path):
        """Les filtres model_type, provider, status et priority fonctionnent."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        store.save(_make_model(model_id="a", model_type=ModelType.LOCAL_OLLAMA, provider="ollama", status=ModelStatus.ACTIVE, priority=ModelPriority.HIGH))
        store.save(_make_model(model_id="b", model_type=ModelType.OPENAI_GPT4, provider="openai", status=ModelStatus.INACTIVE, priority=ModelPriority.LOW))
        store.save(_make_model(model_id="c", model_type=ModelType.LOCAL_OLLAMA, provider="ollama", status=ModelStatus.MAINTENANCE, priority=ModelPriority.CRITICAL))

        # Les horodatages updated_at peuvent être égaux (même tick de clock) :
        # l'ordre SQLite n'est alors pas garanti, on trie donc la comparaison.
        assert sorted([m.model_id for m in store.list_items(model_type="local_ollama")]) == ["a", "c"]
        assert [m.model_id for m in store.list_items(provider="openai")] == ["b"]
        assert [m.model_id for m in store.list_items(status="active")] == ["a"]
        # Parité avec le store en mémoire : le filtre priority compare la valeur
        # (int), pas l'énum brute.
        assert [m.model_id for m in store.list_items(priority=ModelPriority.LOW.value)] == ["b"]

    def test_list_items_generic_attribute_filter(self, tmp_path):
        """Un filtre sur un attribut quelconque fonctionne (context_window)."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        store.save(_make_model(model_id="a", context_window=4096))
        store.save(_make_model(model_id="b", context_window=8192))
        assert [m.model_id for m in store.list_items(context_window=8192)] == ["b"]

    def test_list_items_unknown_filter_matches_nothing(self, tmp_path):
        """Un filtre inconnu ne retourne aucun résultat (parité mémoire)."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        store.save(_make_model())
        assert store.list_items(nope="x") == []

    def test_list_items_limit(self, tmp_path):
        """list_items limite le nombre de résultats."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        for i in range(5):
            store.save(_make_model(model_id=f"m{i}", updated_at=float(i)))
        assert len(store.list_items(limit=2)) == 2

    def test_cleanup_expired_removes_only_deprecated(self, tmp_path):
        """cleanup_expired supprime uniquement les modèles DEPRECATED."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        store.save(_make_model(model_id="ok", status=ModelStatus.ACTIVE))
        store.save(_make_model(model_id="dep", status=ModelStatus.DEPRECATED))
        store.save(_make_model(model_id="err", status=ModelStatus.ERROR))
        assert store.cleanup_expired() == 1
        remaining = [m.model_id for m in store.list_items()]
        assert sorted(remaining) == ["err", "ok"]

    def test_persistence_across_reopen(self, tmp_path):
        """Les données survivent à la fermeture et à la réouverture du fichier."""
        db_path = str(tmp_path / "persist.sqlite")
        store = SQLiteModelStore(db_path=db_path)
        store.save(_make_model(model_id="persist", metadata={"kept": True}))
        store.close()

        reopened = SQLiteModelStore(db_path=db_path)
        model = reopened.get("persist")
        assert model is not None
        assert model.metadata == {"kept": True}

    def test_memory_mode(self):
        """Le mode :memory: partagé fonctionne sans fichier."""
        store = SQLiteModelStore(db_path=":memory:")
        store.save(_make_model())
        assert store.get("model-1").name == "Test Model"

    def test_auto_creates_directory(self, tmp_path):
        """Le dossier parent est créé automatiquement."""
        db_path = str(tmp_path / "subdir" / "deep" / "models.sqlite")
        store = SQLiteModelStore(db_path=db_path)
        store.save(_make_model())
        assert os.path.isfile(db_path)
        assert store.get("model-1") is not None

    def test_concurrent_saves(self, tmp_path):
        """Plusieurs threads sauvegardent sans corruption ni verrou bloqué."""
        store = SQLiteModelStore(db_path=str(tmp_path / "models.sqlite"))
        errors = []

        def worker(index):
            try:
                for j in range(10):
                    store.save(_make_model(model_id=f"t{index}-{j}"))
            except Exception as exc:  # pragma: no cover - échec de test
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(store.list_items()) == 50


# --------------------------------------------------------------------------
# SQLiteKnowledgeStore
# --------------------------------------------------------------------------

class TestSQLiteKnowledgeStore:

    def test_crud_roundtrip(self, tmp_path):
        """save, get, update et delete fonctionnent."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        kid = store.save(_make_knowledge())
        assert kid == _make_knowledge().id  # même contenu -> même ID déterministe

        item = store.get(kid)
        assert item is not None
        assert item.content == "Le Sénégal est un pays d'Afrique de l'Ouest."
        assert item.knowledge_type is KnowledgeType.FACT
        assert item.content_type is ContentType.TEXT
        assert item.language is Language.FR
        assert item.priority is KnowledgePriority.P1
        assert item.confidence == 0.9
        assert item.tags == ["afrique", "senegal"]
        assert item.categories == ["geographie"]
        assert item.metadata == {"source_ref": "doc-2024"}
        assert item.relations == ["r1", "r2"]
        assert item.source.id == "src-001"
        assert item.source.title == "Document de référence"
        assert item.source.source_category is SourceCategory.OFFICIAL

        # update
        item.version = item.version + 1
        assert store.update(item) is True
        assert store.get(kid).version == item.version

        assert store.delete(kid) is True
        assert store.get(kid) is None
        assert store.delete(kid) is False

    def test_get_missing_returns_none(self, tmp_path):
        """get() retourne None pour un identifiant inconnu."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        assert store.get("inconnu") is None

    def test_update_missing_returns_false(self, tmp_path):
        """update() d'une connaissance inexistante retourne False."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        assert store.update(_make_knowledge()) is False

    def test_save_generates_id_when_missing(self, tmp_path):
        """save() génère un ID stable à partir du contenu si absent."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        kid = store.save(_make_knowledge())
        assert kid.startswith("kn")
        assert kid == f"kn{_make_knowledge().compute_content_hash()[:12]}"

    def test_save_never_downgrades_version(self, tmp_path):
        """Une sauvegarde avec une version plus ancienne est ignorée."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        item = _make_knowledge()
        store.save(item)
        store.save(_make_knowledge(confidence=0.95))  # même contenu, même ID

        stored = store.get(item.id)
        assert stored.version == item.version
        assert stored.confidence == 0.9  # l'ancienne version n'a pas écrasé

    def test_update_requires_newer_version(self, tmp_path):
        """update() refuse une version inférieure ou égale."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        item = _make_knowledge()
        store.save(item)

        stale = _make_knowledge(confidence=0.99)
        assert stale.version == item.version
        assert store.update(stale) is False
        assert store.get(item.id).confidence == 0.9

    def test_list_items_preserves_insertion_order(self, tmp_path):
        """list_items retourne les éléments dans l'ordre de première sauvegarde."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        a = _make_knowledge(content="Première connaissance.")
        b = _make_knowledge(content="Deuxième connaissance.")
        c = _make_knowledge(content="Troisième connaissance.")
        store.save(a)
        store.save(b)
        store.save(c)
        assert [k.id for k in store.list_items()] == [a.id, b.id, c.id]

    def test_list_items_filters(self, tmp_path):
        """Les filtres de base (type, langue, source) fonctionnent."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        store.save(_make_knowledge(content="Fait en français.", knowledge_type=KnowledgeType.FACT, language=Language.FR))
        store.save(_make_knowledge(content="Procedure step.", knowledge_type=KnowledgeType.PROCEDURE, language=Language.EN, tags=["manuel", "procedure"]))
        store.save(_make_knowledge(content="Règle du service.", knowledge_type=KnowledgeType.RULE, language=Language.FR))

        assert len(store.list_items(knowledge_type="fact")) == 1
        assert len(store.list_items(content_type="text")) == 3
        assert len(store.list_items(language="fr")) == 2
        assert len(store.list_items(source_type="file")) == 3
        assert len(store.list_items(source_type="api")) == 0

    def test_list_items_tag_filters(self, tmp_path):
        """Les filtres tags acceptent une chaîne ou une liste."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        store.save(_make_knowledge(content="Avec tag Senegal.", tags=["senegal"]))
        store.save(_make_knowledge(content="Avec tag Afrique.", tags=["afrique"]))

        assert len(store.list_items(tags="senegal")) == 1
        assert len(store.list_items(tags=["senegal"])) == 1
        assert len(store.list_items(tags=["afrique", "senegal"])) == 0
        assert len(store.list_items(tags="absent")) == 0

    def test_list_items_category_filters(self, tmp_path):
        """Les filtres categories acceptent une chaîne ou une liste."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        store.save(_make_knowledge(content="Une", categories=["geographie"]))
        store.save(_make_knowledge(content="Deux", categories=["geographie", "histoire"]))

        assert len(store.list_items(categories="geographie")) == 2
        assert len(store.list_items(categories=["geographie", "histoire"])) == 1
        assert len(store.list_items(categories=["histoire"])) == 1

    def test_list_items_confidence_filters(self, tmp_path):
        """min_confidence et max_confidence bornent la confiance."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        store.save(_make_knowledge(content="Fiable.", confidence=0.95))
        store.save(_make_knowledge(content="Moyen.", confidence=0.5))

        assert len(store.list_items(min_confidence=0.8)) == 1
        assert len(store.list_items(max_confidence=0.6)) == 1
        assert len(store.list_items(min_confidence=0.4, max_confidence=0.6)) == 1

    def test_list_items_priority_filters(self, tmp_path):
        """priority, min_priority et max_priority fonctionnent."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        store.save(_make_knowledge(content="P1", priority=KnowledgePriority.P1))
        store.save(_make_knowledge(content="P2", priority=KnowledgePriority.P2))
        store.save(_make_knowledge(content="P4", priority=KnowledgePriority.P4))

        assert [k.content for k in store.list_items(priority=KnowledgePriority.P2)] == ["P2"]
        assert [k.content for k in store.list_items(priority=KnowledgePriority.P2.value)] == ["P2"]
        # "Au moins aussi fiable que P2" : on garde les priorités <= P2 (P1, P2)
        assert sorted(k.content for k in store.list_items(min_priority=KnowledgePriority.P2)) == ["P1", "P2"]
        # "Au plus aussi fiable que P2" : on garde les priorités >= P2 (P2, P4)
        assert sorted(k.content for k in store.list_items(max_priority=KnowledgePriority.P2)) == ["P2", "P4"]

    def test_list_items_source_category_filter(self, tmp_path):
        """Le filtre source_category accepte l'enum ou sa valeur."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        store.save(_make_knowledge(content="Officiel", source_category=SourceCategory.OFFICIAL))
        store.save(_make_knowledge(content="Sans source", source_category=None))

        assert [k.content for k in store.list_items(source_category=SourceCategory.OFFICIAL)] == ["Officiel"]
        assert [k.content for k in store.list_items(source_category="official")] == ["Officiel"]
        assert len(store.list_items(source_category=SourceCategory.OPINION)) == 0

    def test_list_items_created_after_filter(self, tmp_path):
        """Le filtre created_after compare les dates de création."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        marker = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
        store.save(_make_knowledge(content="Nouvelle", created_at=datetime.datetime(2031, 1, 1, tzinfo=datetime.timezone.utc)))
        store.save(_make_knowledge(content="Ancienne", created_at=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)))

        assert [k.content for k in store.list_items(created_after=marker.isoformat())] == ["Nouvelle"]

    def test_list_items_limit(self, tmp_path):
        """list_items limite le nombre de résultats."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        for i in range(5):
            store.save(_make_knowledge(content=f"Connaissance {i}"))
        assert len(store.list_items(limit=2)) == 2

    def test_unknown_filter_is_ignored(self, tmp_path):
        """Un filtre inconnu est ignoré (parité mémoire : match reste True)."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        store.save(_make_knowledge())
        assert len(store.list_items(nope="x")) == 1

    def test_count_with_filters(self, tmp_path):
        """count() respecte les filtres."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        store.save(_make_knowledge(content="FR", language=Language.FR))
        store.save(_make_knowledge(content="EN", language=Language.EN))
        assert store.count() == 2
        assert store.count(language="fr") == 1

    def test_cleanup_old_versions_returns_zero(self, tmp_path):
        """cleanup_old_versions ne supprime rien (une version par ID)."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        store.save(_make_knowledge())
        assert store.cleanup_old_versions() == 0
        assert store.count() == 1

    def test_persistence_across_reopen(self, tmp_path):
        """Les données survivent à la fermeture et à la réouverture du fichier."""
        db_path = str(tmp_path / "persist.sqlite")
        store = SQLiteKnowledgeStore(db_path=db_path)
        item = _make_knowledge(content="Connaissance persistée.")
        store.save(item)
        store.close()

        reopened = SQLiteKnowledgeStore(db_path=db_path)
        stored = reopened.get(item.id)
        assert stored is not None
        assert stored.content == "Connaissance persistée."
        assert stored.source.source_category is SourceCategory.OFFICIAL

    def test_memory_mode(self):
        """Le mode :memory: partagé fonctionne sans fichier."""
        store = SQLiteKnowledgeStore(db_path=":memory:")
        kid = store.save(_make_knowledge(content="En mémoire partagée."))
        assert store.get(kid).content == "En mémoire partagée."

    def test_auto_creates_directory(self, tmp_path):
        """Le dossier parent est créé automatiquement."""
        db_path = str(tmp_path / "subdir" / "deep" / "knowledge.sqlite")
        store = SQLiteKnowledgeStore(db_path=db_path)
        kid = store.save(_make_knowledge(content="Dans un sous-dossier."))
        assert os.path.isfile(db_path)
        assert store.get(kid) is not None

    def test_concurrent_saves(self, tmp_path):
        """Plusieurs threads sauvegardent sans corruption ni verrou bloqué."""
        store = SQLiteKnowledgeStore(db_path=str(tmp_path / "knowledge.sqlite"))
        errors = []

        def worker(index):
            try:
                for j in range(10):
                    store.save(_make_knowledge(content=f"T{index}-{j}"))
            except Exception as exc:  # pragma: no cover - échec de test
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(store.list_items()) == 50


# --------------------------------------------------------------------------
# Branchement des moteurs sur SQLite (GALSEN_STORAGE_BACKEND)
# --------------------------------------------------------------------------

class TestEngineBackendSelection:

    def test_model_manager_uses_sqlite_when_env_set(self, tmp_path, monkeypatch):
        """GALSEN_STORAGE_BACKEND=sqlite branche le moteur de modèles sur SQLite."""
        monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
        monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
        manager = ModelManagerImpl()
        assert isinstance(manager._store, SQLiteModelStore)
        assert manager._store.db_path == str(tmp_path / "models.sqlite")

        manager.register_model(_make_model(model_id="sqlite-model"))
        models = manager.list_models(provider="ollama")
        assert [m.model_id for m in models] == ["sqlite-model"]
        assert manager.get_model("sqlite-model").name == "Test Model"
        assert manager.unregister_model("sqlite-model") is True

    def test_model_manager_defaults_to_in_memory(self, tmp_path, monkeypatch):
        """Sans variable d'environnement, le moteur de modèles reste en mémoire."""
        monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)
        monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
        manager = ModelManagerImpl()
        assert not isinstance(manager._store, SQLiteModelStore)

    def test_model_manager_explicit_store_wins(self, tmp_path, monkeypatch):
        """Un store injecté prime sur la variable d'environnement."""
        monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
        injected = SQLiteModelStore(db_path=str(tmp_path / "injected.sqlite"))
        manager = ModelManagerImpl(store=injected)
        assert manager._store is injected
        assert manager._store.db_path == str(tmp_path / "injected.sqlite")

    def test_knowledge_manager_uses_sqlite_when_env_set(self, tmp_path, monkeypatch):
        """GALSEN_STORAGE_BACKEND=sqlite branche le moteur de connaissances sur SQLite."""
        monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
        monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
        manager = KnowledgeManagerImpl()
        assert isinstance(manager.get_store(), SQLiteKnowledgeStore)
        assert manager.get_store().db_path == str(tmp_path / "knowledge.sqlite")

        item = _make_knowledge(content="Connaissance stockée en SQLite.")
        kid = manager.add_knowledge(item)
        retrieved = manager.get_knowledge(kid)
        assert retrieved is not None
        assert retrieved.content == "Connaissance stockée en SQLite."
        assert retrieved.priority is KnowledgePriority.P1

    def test_knowledge_manager_defaults_to_in_memory(self, tmp_path, monkeypatch):
        """Sans variable d'environnement, le moteur de connaissances reste en mémoire."""
        monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)
        monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
        manager = KnowledgeManagerImpl()
        assert not isinstance(manager.get_store(), SQLiteKnowledgeStore)

    def test_knowledge_manager_explicit_store_wins(self, tmp_path, monkeypatch):
        """Un store injecté prime sur la variable d'environnement."""
        monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
        injected = SQLiteKnowledgeStore(db_path=str(tmp_path / "injected.sqlite"))
        manager = KnowledgeManagerImpl(store=injected)
        assert manager.get_store() is injected
        assert manager.get_store().db_path == str(tmp_path / "injected.sqlite")

    def test_no_repo_pollution_with_defaults(self, tmp_path, monkeypatch):
        """Sans GALSEN_DATA_DIR, le défaut pointe vers le dossier 'data' configurable."""
        monkeypatch.delenv("GALSEN_DATA_DIR", raising=False)
        assert default_sqlite_path("models.sqlite") == os.path.join("data", "models.sqlite")
