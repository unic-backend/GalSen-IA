"""
Tests unitaires pour le service Cloud.

Couvre :
- CloudFileItem, CloudSyncResult, CloudStats — désormais la **forme de réponse**
  des routes dépréciées `/cloud/*`, plus un type stocké (ADR-016)
- CloudManagerImpl : upload, validation, inférence de catégorie, dégradation gracieuse

Les tests de `InMemoryCloudStore` ont disparu avec lui : le service ne stocke
plus rien. Le contrat de magasin est couvert par `test_services.py` et
`test_file_backends.py`, sur le magasin réellement utilisé. Ce que ce
changement apporte de neuf est dans `test_cloud_adapter.py`.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestCloudTypes:
    """Vérifie les modèles de données du cloud."""

    def test_generate_file_id_prefix(self):
        """L'identifiant de fichier doit commencer par 'cloud_'."""
        from src.services.cloud import generate_cloud_file_id
        fid = generate_cloud_file_id()
        assert fid.startswith("cloud_")
        assert len(fid) > 10

    def test_file_item_defaults(self):
        """Un CloudFileItem doit avoir des valeurs par défaut cohérentes."""
        from src.services.cloud import CloudFileItem, CloudProvider, CloudFileCategory
        item = CloudFileItem(name="test.txt", content_type="text/plain", size=100)
        assert item.provider == CloudProvider.LOCAL
        assert item.category == CloudFileCategory.OTHER
        assert item.path is None
        assert item.uploaded_by is None
        assert item.metadata == {}
        assert item.id.startswith("cloud_")

    def test_file_item_to_dict(self):
        """to_dict() doit inclure tous les champs obligatoires."""
        from src.services.cloud import CloudFileItem
        item = CloudFileItem(
            name="doc.pdf", content_type="application/pdf", size=2048,
            provider="s3", path="/docs/doc.pdf", uploaded_by="user1",
            metadata={"project": "GalSen"},
        )
        d = item.to_dict()
        assert d["id"] == item.id
        assert d["name"] == "doc.pdf"
        assert d["content_type"] == "application/pdf"
        assert d["size"] == 2048
        assert d["provider"] == "s3"
        assert d["category"] == "other"
        assert d["path"] == "/docs/doc.pdf"
        assert d["uploaded_by"] == "user1"
        assert d["metadata"]["project"] == "GalSen"
        assert "created_at" in d
        assert "updated_at" in d

    def test_file_item_to_dict_minimal(self):
        """to_dict() sans champs optionnels ne doit pas les inclure."""
        from src.services.cloud import CloudFileItem
        item = CloudFileItem(name="f.txt", content_type="text/plain", size=50)
        d = item.to_dict()
        assert "path" not in d
        assert "uploaded_by" not in d
        assert "metadata" not in d

    def test_file_item_from_mapping(self):
        """from_mapping() doit reconstruire un CloudFileItem depuis un dict."""
        from src.services.cloud import CloudFileItem
        original = CloudFileItem(
            name="doc.pdf", content_type="application/pdf", size=2048,
            provider="s3", path="/docs/doc.pdf", uploaded_by="user1",
        )
        d = original.to_dict()
        restored = CloudFileItem.from_mapping(d)
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.provider.value == "s3"

    def test_file_item_from_mapping_string_provider(self):
        """from_mapping() doit accepter un provider sous forme de chaîne."""
        from src.services.cloud import CloudFileItem, CloudProvider
        restored = CloudFileItem.from_mapping({
            "name": "f.txt", "content_type": "text/plain", "size": 50,
            "provider": "gcs",
        })
        assert restored.provider == CloudProvider.GCS

    def test_file_item_from_mapping_invalid_provider_defaults_local(self):
        """Un provider invalide dans from_mapping() doit être remplacé par LOCAL."""
        from src.services.cloud import CloudFileItem, CloudProvider
        restored = CloudFileItem.from_mapping({
            "name": "f.txt", "content_type": "text/plain", "size": 50,
            "provider": "unknown",
        })
        assert restored.provider == CloudProvider.LOCAL

    def test_file_item_from_mapping_string_category(self):
        """from_mapping() doit accepter une catégorie sous forme de chaîne."""
        from src.services.cloud import CloudFileItem, CloudFileCategory
        restored = CloudFileItem.from_mapping({
            "name": "f.txt", "content_type": "text/plain", "size": 50,
            "category": "document",
        })
        assert restored.category == CloudFileCategory.DOCUMENT

    def test_file_item_from_mapping_invalid_category_defaults_other(self):
        """Une catégorie invalide dans from_mapping() doit être remplacée par OTHER."""
        from src.services.cloud import CloudFileItem, CloudFileCategory
        restored = CloudFileItem.from_mapping({
            "name": "f.txt", "content_type": "text/plain", "size": 50,
            "category": "unknown",
        })
        assert restored.category == CloudFileCategory.OTHER

    def test_sync_result_defaults(self):
        """CloudSyncResult doit accepter les champs minimaux."""
        from src.services.cloud import CloudSyncResult
        r = CloudSyncResult(True, "Uploadé")
        assert r.success is True
        assert r.message == "Uploadé"
        assert r.file_id is None

    def test_cloud_stats_creation(self):
        """CloudStats doit stocker les compteurs."""
        from src.services.cloud import CloudStats
        stats = CloudStats(total=5, total_size=10000, by_category={"document": 3}, by_provider={"local": 5})
        assert stats.total == 5
        assert stats.total_size == 10000


class TestCloudManager:
    """Vérifie le gestionnaire cloud (best-effort)."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from src.services.cloud import CloudManagerImpl
        self.manager = CloudManagerImpl()

    def test_upload(self):
        """upload() doit retourner un résultat positif."""
        result = self.manager.upload(
            name="test.txt", content_type="text/plain", data=b"contenu",
        )
        assert result.success
        assert result.file_id is not None
        # Un seul stockage, un seul espace d'identifiants : le préfixe est
        # celui du service de fichiers (ADR-016).
        assert result.file_id.startswith("file_")

    def test_upload_and_download(self):
        """upload() puis download() doivent retourner les mêmes données."""
        data = b"contenu du fichier"
        result = self.manager.upload(
            name="doc.txt", content_type="text/plain", data=data,
        )
        downloaded = self.manager.download(result.file_id)
        assert downloaded == data

    def test_upload_and_get_file(self):
        """upload() puis get_file() doivent retourner le même fichier."""
        result = self.manager.upload(
            name="report.pdf", content_type="application/pdf", data=b"%PDF-1.4",
            uploaded_by="admin",
        )
        item = self.manager.get_file(result.file_id)
        assert item is not None
        assert item.name == "report.pdf"
        assert item.content_type == "application/pdf"
        assert item.size == 8
        assert item.uploaded_by == "admin"

    def test_upload_empty_name(self):
        """upload() avec un nom vide doit échouer."""
        result = self.manager.upload(
            name="", content_type="text/plain", data=b"data",
        )
        assert not result.success
        assert "nom" in result.message.lower()

    def test_upload_empty_data(self):
        """upload() avec des données vides doit échouer."""
        result = self.manager.upload(
            name="test.txt", content_type="text/plain", data=b"",
        )
        assert not result.success
        assert "vide" in result.message.lower()

    def test_upload_exceeds_max_size(self):
        """upload() avec des données trop volumineuses doit échouer."""
        result = self.manager.upload(
            name="big.txt", content_type="text/plain", data=b"x" * 100,
            max_size=50,
        )
        assert not result.success
        assert "taille" in result.message.lower()

    def test_upload_with_all_fields(self):
        """upload() doit accepter tous les champs optionnels."""
        from src.services.cloud import CloudProvider
        result = self.manager.upload(
            name="full.txt", content_type="text/plain", data=b"data",
            provider=CloudProvider.S3, uploaded_by="admin",
            metadata={"env": "production"},
        )
        assert result.success
        item = self.manager.get_file(result.file_id)
        # `provider` était une déclaration de l'appelant, jamais vérifiée : ce
        # fichier vit en mémoire du processus, et la plateforme répondait « s3 ».
        # Il porte désormais le magasin qui détient réellement les octets.
        assert item.provider.value == "local"
        assert item.uploaded_by == "admin"
        assert item.metadata["env"] == "production"

    def test_download_missing(self):
        """download() d'un fichier inconnu doit retourner None."""
        assert self.manager.download("nonexistent") is None

    def test_get_file_missing(self):
        """get_file() d'un fichier inconnu doit retourner None."""
        assert self.manager.get_file("nonexistent") is None

    def test_list_files(self):
        """list_files() doit retourner les fichiers uploadés."""
        self.manager.upload(name="a.txt", content_type="text/plain", data=b"a")
        self.manager.upload(name="b.txt", content_type="text/plain", data=b"b")
        files = self.manager.list_files()
        assert len(files) == 2

    def test_list_files_filter_provider(self):
        """
        list_files(provider=...) porte sur le magasin actif.

        Le filtre triait auparavant des valeurs déclarées à l'envoi : deux
        fichiers du même magasin ressortaient sous deux fournisseurs différents
        selon ce que l'appelant avait écrit.
        """
        from src.services.cloud import CloudProvider
        self.manager.upload(name="a.txt", content_type="text/plain", data=b"a")
        self.manager.upload(name="b.txt", content_type="text/plain", data=b"b",
                            provider=CloudProvider.S3)

        assert len(self.manager.list_files(provider="local")) == 2
        assert self.manager.list_files(provider="s3") == []

    def test_list_files_filter_category(self):
        """list_files(category=...) doit filtrer."""
        self.manager.upload(name="doc.pdf", content_type="application/pdf", data=b"%PDF")
        self.manager.upload(name="img.jpg", content_type="image/jpeg", data=b"JPEG")
        images = self.manager.list_files(category="image")
        assert len(images) == 1
        assert images[0].name == "img.jpg"

    def test_list_files_filter_uploaded_by(self):
        """list_files(uploaded_by=...) doit filtrer."""
        self.manager.upload(name="a.txt", content_type="text/plain", data=b"a",
                            uploaded_by="user1")
        self.manager.upload(name="b.txt", content_type="text/plain", data=b"b",
                            uploaded_by="user2")
        user1_files = self.manager.list_files(uploaded_by="user1")
        assert len(user1_files) == 1

    def test_delete(self):
        """delete() doit supprimer un fichier."""
        result = self.manager.upload(name="del.txt", content_type="text/plain", data=b"data")
        assert self.manager.delete(result.file_id)
        assert self.manager.get_file(result.file_id) is None

    def test_delete_missing(self):
        """delete() d'un fichier inconnu doit retourner False sans erreur."""
        assert not self.manager.delete("nonexistent")

    def test_update_metadata(self):
        """update_metadata() doit modifier les métadonnées."""
        result = self.manager.upload(name="meta.txt", content_type="text/plain", data=b"data")
        assert self.manager.update_metadata(result.file_id, {"key": "value"})
        item = self.manager.get_file(result.file_id)
        assert item.metadata["key"] == "value"

    def test_update_metadata_missing(self):
        """update_metadata() d'un fichier inconnu doit retourner False sans erreur."""
        assert not self.manager.update_metadata("nonexistent", {})

    def test_stats(self):
        """stats() doit retourner des statistiques cohérentes."""
        self.manager.upload(name="a.txt", content_type="text/plain", data=b"hello")
        self.manager.upload(name="b.txt", content_type="text/plain", data=b"world")
        stats = self.manager.stats()
        assert stats["total"] == 2
        assert stats["total_size"] == 5 + 5

    def test_clear(self):
        """clear() doit tout supprimer."""
        self.manager.upload(name="a.txt", content_type="text/plain", data=b"a")
        assert self.manager.clear() == 1
        assert len(self.manager.list_files()) == 0

    def test_store_failure_graceful(self):
        """
        Une panne du stockage ne doit pas faire tomber le service.

        Le magasin est désormais celui du service de fichiers : la panne est
        injectée là, et la dégradation gracieuse doit traverser les deux façades.
        """
        from src.services.file.interfaces import FileStore
        from src.services.file.manager import FileManagerImpl

        broken_store = MagicMock(spec=FileStore)
        for operation in ("save", "get", "get_by_name", "list_files", "delete",
                          "update_metadata", "stats", "clear", "count", "total_size"):
            getattr(broken_store, operation).side_effect = RuntimeError(
                "Stockage indisponible")
        manager = type(self.manager)(files=FileManagerImpl(store=broken_store))

        result = manager.upload(name="test.txt", content_type="text/plain", data=b"data")
        assert not result.success

        assert manager.get_file("any") is None
        assert manager.download("any") is None
        assert manager.list_files() == []
        assert manager.delete("any") is False
        assert manager.update_metadata("any", {}) is False
        assert manager.stats() == {}
        assert manager.clear() == 0

    def test_infer_category_pdf(self):
        """_infer_category() doit classifier application/pdf en DOCUMENT."""
        from src.services.cloud.manager import _infer_category
        from src.services.cloud import CloudFileCategory
        assert _infer_category("application/pdf") == CloudFileCategory.DOCUMENT
        assert _infer_category("application/msword") == CloudFileCategory.DOCUMENT
        assert _infer_category("text/plain") == CloudFileCategory.DOCUMENT
        assert _infer_category("text/html") == CloudFileCategory.DOCUMENT

    def test_infer_category_image(self):
        """_infer_category() doit classifier image/* en IMAGE."""
        from src.services.cloud.manager import _infer_category
        from src.services.cloud import CloudFileCategory
        assert _infer_category("image/png") == CloudFileCategory.IMAGE
        assert _infer_category("image/jpeg") == CloudFileCategory.IMAGE
        assert _infer_category("image/gif") == CloudFileCategory.IMAGE

    def test_infer_category_video(self):
        """_infer_category() doit classifier video/* en VIDEO."""
        from src.services.cloud.manager import _infer_category
        from src.services.cloud import CloudFileCategory
        assert _infer_category("video/mp4") == CloudFileCategory.VIDEO
        assert _infer_category("video/x-matroska") == CloudFileCategory.VIDEO

    def test_infer_category_audio(self):
        """_infer_category() doit classifier audio/* en AUDIO."""
        from src.services.cloud.manager import _infer_category
        from src.services.cloud import CloudFileCategory
        assert _infer_category("audio/mpeg") == CloudFileCategory.AUDIO
        assert _infer_category("audio/ogg") == CloudFileCategory.AUDIO

    def test_infer_category_data(self):
        """_infer_category() doit classifier text/csv, application/json, application/xml en DATA."""
        from src.services.cloud.manager import _infer_category
        from src.services.cloud import CloudFileCategory
        assert _infer_category("text/csv") == CloudFileCategory.DATA
        assert _infer_category("application/json") == CloudFileCategory.DATA
        assert _infer_category("application/xml") == CloudFileCategory.DATA

    def test_infer_category_archive(self):
        """_infer_category() doit classifier les archives en ARCHIVE."""
        from src.services.cloud.manager import _infer_category
        from src.services.cloud import CloudFileCategory
        assert _infer_category("application/zip") == CloudFileCategory.ARCHIVE
        assert _infer_category("application/x-tar") == CloudFileCategory.ARCHIVE
        assert _infer_category("application/gzip") == CloudFileCategory.ARCHIVE

    def test_infer_category_unknown(self):
        """_infer_category() doit retourner OTHER pour les types inconnus."""
        from src.services.cloud.manager import _infer_category
        from src.services.cloud import CloudFileCategory
        assert _infer_category("application/octet-stream") == CloudFileCategory.OTHER
        assert _infer_category("text/calendar") == CloudFileCategory.OTHER