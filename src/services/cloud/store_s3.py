"""
Stockage S3/Minio pour le service Cloud.

Fournit `S3CloudStore`, une implémentation du contrat `CloudStore` qui
stocke les fichiers sur un bucket S3 compatible (AWS S3, Minio, DigitalOcean
Spaces, etc.).

Les métadonnées sont conservées dans un index mémoire + fichier JSON local
pour éviter les appels S3 coûteux en listing.

Configuration par variables d'environnement :
- CLOUD_S3_ENDPOINT : URL du endpoint S3 (optionnel, défaut : AWS)
- CLOUD_S3_REGION : région (défaut : us-east-1)
- CLOUD_S3_BUCKET : nom du bucket (défaut : galsen-ia-cloud)
- CLOUD_S3_ACCESS_KEY : clé d'accès
- CLOUD_S3_SECRET_KEY : clé secrète
- CLOUD_S3_DATA_DIR : répertoire local pour l'index (défaut : data/cloud-s3)

```python
store = S3CloudStore(
    bucket="mon-bucket",
    access_key="xxx", secret_key="yyy",
    endpoint="https://minio.example.com",
)
manager = CloudManagerImpl(store=store)
```

Référence : VOLET 02, Chapitre 09 (Integration).
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from .interfaces import CloudStore
from .types import CloudFileItem

logger = logging.getLogger(__name__)


class S3CloudStore(CloudStore):
    """
    Stockage cloud via S3/Minio.

    Les données binaires sont stockées dans un bucket S3. Les métadonnées
    sont persistées localement dans un fichier JSON. Nécessite boto3.
    """

    def __init__(
        self,
        bucket: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        region: Optional[str] = None,
        data_dir: Optional[str] = None,
    ) -> None:
        self._bucket = bucket or os.environ.get("CLOUD_S3_BUCKET", "galsen-ia-cloud")
        self._access_key = access_key or os.environ.get("CLOUD_S3_ACCESS_KEY", "")
        self._secret_key = secret_key or os.environ.get("CLOUD_S3_SECRET_KEY", "")
        self._endpoint = endpoint or os.environ.get("CLOUD_S3_ENDPOINT", "")
        self._region = region or os.environ.get("CLOUD_S3_REGION", "us-east-1")
        self._data_dir = data_dir or os.environ.get("CLOUD_S3_DATA_DIR", "data/cloud-s3")
        self._index_path = os.path.join(self._data_dir, "index.json")
        self._lock = threading.RLock()
        self._items: Dict[str, CloudFileItem] = {}
        self._order: List[str] = []
        self._s3 = None

        os.makedirs(self._data_dir, exist_ok=True)
        self._load_index()

    def _get_s3(self):
        """Retourne le client S3 (import lazy de boto3)."""
        if self._s3 is None:
            import boto3
            kwargs: Dict[str, Any] = {
                "region_name": self._region,
                "aws_access_key_id": self._access_key or None,
                "aws_secret_access_key": self._secret_key or None,
            }
            if self._endpoint:
                kwargs["endpoint_url"] = self._endpoint
            self._s3 = boto3.client("s3", **kwargs)
            self._ensure_bucket()
        return self._s3

    def _ensure_bucket(self) -> None:
        """Crée le bucket s'il n'existe pas."""
        try:
            self._s3.head_bucket(Bucket=self._bucket)
        except Exception:
            try:
                if self._region == "us-east-1":
                    self._s3.create_bucket(Bucket=self._bucket)
                else:
                    self._s3.create_bucket(
                        Bucket=self._bucket,
                        CreateBucketConfiguration={"LocationConstraint": self._region},
                    )
            except Exception as e:
                logger.warning("Impossible de créer le bucket '%s' : %s", self._bucket, e)

    def _load_index(self) -> None:
        """Charge l'index depuis le disque."""
        try:
            if os.path.exists(self._index_path):
                with open(self._index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._order = data.get("order", [])
                for item_data in data.get("items", []):
                    item = CloudFileItem.from_mapping(item_data)
                    self._items[item.id] = item
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Impossible de charger l'index S3 : %s", e)

    def _save_index(self) -> None:
        """Sauvegarde l'index sur le disque."""
        try:
            data = {
                "order": self._order,
                "items": [item.to_dict() for item in self._items.values()],
            }
            with open(self._index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error("Impossible de sauvegarder l'index S3 : %s", e)

    def _s3_key(self, file_id: str) -> str:
        """Retourne la clé S3 pour un identifiant."""
        return f"files/{file_id}"

    def save(self, item: CloudFileItem, data: bytes) -> str:
        """Enregistre un fichier sur S3 et dans l'index local."""
        with self._lock:
            if item.id in self._items:
                raise ValueError(f"Le fichier cloud {item.id} existe déjà.")

            # Upload vers S3
            try:
                s3 = self._get_s3()
                s3.put_object(
                    Bucket=self._bucket,
                    Key=self._s3_key(item.id),
                    Body=data,
                    ContentType=item.content_type,
                    Metadata={"name": item.name, "id": item.id},
                )
            except Exception as e:
                raise IOError(f"Impossible d'uploader vers S3 : {e}")

            # Mettre à jour l'index local
            self._items[item.id] = item
            self._order.append(item.id)
            self._save_index()

            return item.id

    def get(self, file_id: str) -> Optional[CloudFileItem]:
        """Retourne un fichier cloud par identifiant."""
        with self._lock:
            return self._items.get(file_id)

    def get_data(self, file_id: str) -> Optional[bytes]:
        """Télécharge les données depuis S3."""
        with self._lock:
            if file_id not in self._items:
                return None
            try:
                s3 = self._get_s3()
                response = s3.get_object(Bucket=self._bucket, Key=self._s3_key(file_id))
                return response["Body"].read()
            except Exception as e:
                logger.warning("Impossible de télécharger %s depuis S3 : %s", file_id, e)
                return None

    def _matches(
        self,
        item: CloudFileItem,
        provider: Optional[str],
        category: Optional[str],
        uploaded_by: Optional[str],
    ) -> bool:
        if provider is not None and item.provider.value != provider:
            return False
        if category is not None and item.category.value != category:
            return False
        if uploaded_by is not None and item.uploaded_by != uploaded_by:
            return False
        return True

    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> List[CloudFileItem]:
        """Retourne les fichiers filtrés (depuis l'index local)."""
        with self._lock:
            matched: List[CloudFileItem] = []
            for item_id in reversed(self._order):
                item = self._items[item_id]
                if self._matches(item, provider, category, uploaded_by):
                    matched.append(item)
            return matched[offset:offset + limit]

    def delete(self, file_id: str) -> bool:
        """Supprime un fichier de S3 et de l'index local."""
        with self._lock:
            if file_id not in self._items:
                return False

            try:
                s3 = self._get_s3()
                s3.delete_object(Bucket=self._bucket, Key=self._s3_key(file_id))
            except Exception as e:
                logger.warning("Impossible de supprimer %s de S3 : %s", file_id, e)

            del self._items[file_id]
            self._order = [fid for fid in self._order if fid != file_id]
            self._save_index()
            return True

    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        with self._lock:
            item = self._items.get(file_id)
            if item is None:
                return False
            item.metadata.update(metadata)
            item.updated_at = time.time()
            self._save_index()
            return True

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._order)
            total_size = sum(item.size for item in self._items.values())
            by_category: Dict[str, int] = {}
            by_provider: Dict[str, int] = {}
            for item in self._items.values():
                c = item.category.value
                by_category[c] = by_category.get(c, 0) + 1
                p = item.provider.value
                by_provider[p] = by_provider.get(p, 0) + 1
            return {"total": total, "total_size": total_size, "by_category": by_category, "by_provider": by_provider}

    def clear(self) -> int:
        with self._lock:
            count = len(self._order)
            self._items.clear()
            self._order.clear()
            try:
                if os.path.exists(self._index_path):
                    os.remove(self._index_path)
            except OSError:
                pass
            return count

    def count(self) -> int:
        with self._lock:
            return len(self._order)

    def total_size(self) -> int:
        with self._lock:
            return sum(item.size for item in self._items.values())