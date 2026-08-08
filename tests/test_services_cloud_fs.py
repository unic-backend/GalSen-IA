"""
Tests unitaires pour FileSystemCloudStore et S3CloudStore.

Couvre :
- FileSystemCloudStore : CRUD, persistence, filtrage, métadonnées
- S3CloudStore : import, structure (sans connexion réelle)
"""

import os
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestFileSystemCloudStore:
    """Vérifie le stockage cloud persistant sur le système de fichiers."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.cloud import FileSystemCloudStore, CloudFileItem, CloudProvider, CloudFileCategory
        # Créer un répertoire temporaire pour les tests
        self.tmpdir = tempfile.mkdtemp(prefix="galsen_cloud_test_")
        self.store = FileSystemCloudStore(data_dir=self.tmpdir)
        self.file_a = CloudFileItem(
            name="doc.pdf", content_type="application/pdf", size=2048,
            provider=CloudProvider.S3, category=CloudFileCategory.DOCUMENT,
            uploaded_by="user1",
        )
        self.file_b = CloudFileItem(
            name="photo.jpg", content_type="image/jpeg", size=102400,
            provider=CloudProvider.LOCAL, category=CloudFileCategory.IMAGE,
            uploaded_by="user1",
        )

    def teardown_method(self):
        """Nettoie les fichiers temporaires."""
        import shutil
        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def test_save_creates_file_on_disk(self):
        """save() doit créer un fichier sur le disque."""
        fid = self.store.save(self.file_a, b"contenu pdf")
        file_path = os.path.join(self.tmpdir, "files", fid)
        assert os.path.exists(file_path)
        with open(file_path, "rb") as f:
            assert f.read() == b"contenu pdf"

    def test_save_and_get(self):
        """save() puis get() doivent retourner le même fichier."""
        fid = self.store.save(self.file_a, b"data")
        retrieved = self.store.get(fid)
        assert retrieved is not None
        assert retrieved.name == "doc.pdf"

    def test_save_and_get_data(self):
        """save() puis get_data() doivent retourner les données."""
        data = b"contenu persistant"
        fid = self.store.save(self.file_a, data)
        assert self.store.get_data(fid) == data

    def test_save_duplicate_raises(self):
        """save() d'un identifiant existant doit lever ValueError."""
        self.store.save(self.file_a, b"data")
        with pytest.raises(ValueError, match="existe déjà"):
            self.store.save(self.file_a, b"other")

    def test_get_missing_returns_none(self):
        """get() d'un identifiant inconnu doit retourner None."""
        assert self.store.get("nonexistent") is None

    def test_get_data_missing_returns_none(self):
        """get_data() d'un identifiant inconnu doit retourner None."""
        assert self.store.get_data("nonexistent") is None

    def test_list_files_ordered_by_recency(self):
        """list_files() doit trier du plus récent au plus ancien."""
        self.store.save(self.file_b, b"b")
        time.sleep(0.01)
        self.store.save(self.file_a, b"a")
        files = self.store.list_files(limit=10)
        assert len(files) == 2
        assert files[0].name == "doc.pdf"  # plus récent

    def test_list_files_filter_provider(self):
        """list_files() doit filtrer par fournisseur."""
        self.store.save(self.file_a, b"a")  # S3
        self.store.save(self.file_b, b"b")  # LOCAL
        s3_files = self.store.list_files(limit=10, provider="s3")
        assert len(s3_files) == 1

    def test_delete(self):
        """delete() doit supprimer le fichier ET les données."""
        fid = self.store.save(self.file_a, b"data")
        file_path = os.path.join(self.tmpdir, "files", fid)
        assert os.path.exists(file_path)
        assert self.store.delete(fid)
        assert self.store.get(fid) is None
        assert not os.path.exists(file_path)

    def test_delete_missing(self):
        """delete() d'un fichier inconnu doit retourner False."""
        assert not self.store.delete("nonexistent")

    def test_update_metadata(self):
        """update_metadata() doit persister les métadonnées."""
        fid = self.store.save(self.file_a, b"data")
        assert self.store.update_metadata(fid, {"projet": "GalSen"})
        retrieved = self.store.get(fid)
        assert retrieved.metadata["projet"] == "GalSen"

    def test_stats(self):
        """stats() doit retourner des statistiques correctes."""
        self.store.save(self.file_a, b"a")  # size=2048
        self.store.save(self.file_b, b"b")  # size=102400
        stats = self.store.stats()
        assert stats["total"] == 2
        assert stats["total_size"] == 2048 + 102400

    def test_clear(self):
        """clear() doit tout supprimer."""
        self.store.save(self.file_a, b"a")
        self.store.save(self.file_b, b"b")
        assert self.store.clear() == 2
        assert self.store.count() == 0

    def test_persistence_across_reload(self):
        """Les données doivent survivre à une re-création du store."""
        fid = self.store.save(self.file_a, b"donnees persistees")
        # Créer un nouveau store pointant sur le même répertoire
        from src.services.cloud import FileSystemCloudStore
        store2 = FileSystemCloudStore(data_dir=self.tmpdir)
        retrieved = store2.get(fid)
        assert retrieved is not None
        assert retrieved.name == "doc.pdf"
        assert store2.get_data(fid) == b"donnees persistees"

    def test_persistence_metadata_across_reload(self):
        """Les métadonnées mises à jour doivent survivre au rechargement."""
        fid = self.store.save(self.file_a, b"data")
        self.store.update_metadata(fid, {"version": "2.0"})
        from src.services.cloud import FileSystemCloudStore
        store2 = FileSystemCloudStore(data_dir=self.tmpdir)
        retrieved = store2.get(fid)
        assert retrieved.metadata["version"] == "2.0"

    def test_count_with_filters(self):
        """count() doit retourner le nombre correct."""
        assert self.store.count() == 0
        self.store.save(self.file_a, b"a")
        assert self.store.count() == 1

    def test_list_with_limit_and_offset(self):
        """list_files() doit respecter limite et offset."""
        self.store.save(self.file_a, b"a")
        self.store.save(self.file_b, b"b")
        assert len(self.store.list_files(limit=1)) == 1
        assert len(self.store.list_files(limit=10, offset=1)) == 1


class TestS3CloudStore:
    """Vérifie la structure de S3CloudStore (sans connexion réelle)."""

    def test_import_and_init(self):
        """S3CloudStore doit s'importer et s'initialiser sans boto3."""
        from src.services.cloud import S3CloudStore
        store = S3CloudStore(data_dir=tempfile.mkdtemp())
        assert store._bucket == "galsen-ia-cloud"

    def test_save_without_boto3_raises_io_error(self):
        """save() sans boto3 doit lever une IOError claire."""
        from src.services.cloud import S3CloudStore
        store = S3CloudStore(data_dir=tempfile.mkdtemp())
        with pytest.raises((IOError, OSError)):
            store.save(self._make_item(), b"data")

    def _make_item(self):
        from src.services.cloud import CloudFileItem
        return CloudFileItem(name="test.txt", content_type="text/plain", size=4)