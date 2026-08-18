"""
Stockage des fichiers sur S3 ou compatible (ADR-016).

Backend `s3` du service de fichiers : les métadonnées dans l'index JSON local
tenu par `IndexedFileStore`, les octets dans un seau S3 (AWS S3, MinIO,
DigitalOcean Spaces…).

L'index reste local **à dessein** : lister par appels S3 coûte un appel réseau
par page et facture chaque listage, alors que la question « quels fichiers
existent » est posée en boucle. Le prix de ce choix est que l'index et le seau
peuvent diverger ; `get` le dit au lieu de rendre un fichier vide.

Configuration :

| Variable | Rôle |
|----------|------|
| `CLOUD_S3_BUCKET` | Nom du seau |
| `CLOUD_S3_ACCESS_KEY`, `CLOUD_S3_SECRET_KEY` | Identifiants |
| `CLOUD_S3_ENDPOINT` | Point d'entrée (MinIO et compatibles) |
| `CLOUD_S3_REGION` | Région, `us-east-1` par défaut |

Les identifiants ne sont **jamais** écrits en dur : ce sont des variables
d'environnement, comme toute donnée secrète du projet.

`boto3` est importé paresseusement : la plateforme démarre sans lui, et un envoi
vers un S3 injoignable rapporte une vraie erreur plutôt que de retomber en
silence sur la mémoire — un fichier « déposé » en RAM serait pire que l'échec.
"""

import logging
import os
from typing import Any, Dict, Optional

from src.storage.paths import data_dir

from .store_indexed import IndexedFileStore

logger = logging.getLogger(__name__)

SOUS_REPERTOIRE = "files-s3"
PREFIXE_CLE = "files/"


class S3FileStore(IndexedFileStore):
    """Magasin de fichiers dont les octets sont des objets S3."""

    def __init__(
        self,
        bucket: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        region: Optional[str] = None,
        data_directory: Optional[str] = None,
    ) -> None:
        """
        Args:
            bucket: Seau S3 ; `CLOUD_S3_BUCKET` sinon.
            access_key: Clé d'accès ; `CLOUD_S3_ACCESS_KEY` sinon.
            secret_key: Clé secrète ; `CLOUD_S3_SECRET_KEY` sinon.
            endpoint: Point d'entrée compatible S3 ; `CLOUD_S3_ENDPOINT` sinon.
            region: Région ; `CLOUD_S3_REGION` sinon.
            data_directory: Répertoire de l'index local.
        """
        self._bucket = bucket or os.environ.get("CLOUD_S3_BUCKET", "galsen-ia-files")
        self._access_key = access_key or os.environ.get("CLOUD_S3_ACCESS_KEY", "")
        self._secret_key = secret_key or os.environ.get("CLOUD_S3_SECRET_KEY", "")
        self._endpoint = endpoint or os.environ.get("CLOUD_S3_ENDPOINT", "")
        self._region = region or os.environ.get("CLOUD_S3_REGION", "us-east-1")
        self._s3 = None
        super().__init__(data_directory or os.path.join(data_dir(), SOUS_REPERTOIRE))

    def _client(self):
        """Retourne le client S3, importé et construit à la première demande."""
        if self._s3 is None:
            import boto3

            arguments: Dict[str, Any] = {
                "region_name": self._region,
                "aws_access_key_id": self._access_key or None,
                "aws_secret_access_key": self._secret_key or None,
            }
            if self._endpoint:
                arguments["endpoint_url"] = self._endpoint
            self._s3 = boto3.client("s3", **arguments)
        return self._s3

    def _cle(self, file_id: str) -> str:
        """Retourne la clé S3 des octets d'un fichier."""
        return f"{PREFIXE_CLE}{self._verifier_identifiant(file_id)}"

    def _write_blob(self, file_id: str, data: bytes, content_type: str) -> None:
        """Dépose les octets dans le seau."""
        try:
            self._client().put_object(
                Bucket=self._bucket,
                Key=self._cle(file_id),
                Body=data,
                ContentType=content_type,
            )
        except Exception as erreur:  # boto3 lève des types qui lui sont propres
            raise IOError(
                f"Impossible d'envoyer {file_id} vers le seau « {self._bucket} » : {erreur}"
            ) from erreur

    def _read_blob(self, file_id: str) -> Optional[bytes]:
        """Récupère les octets depuis le seau, ou None s'ils sont introuvables."""
        try:
            reponse = self._client().get_object(Bucket=self._bucket, Key=self._cle(file_id))
            return reponse["Body"].read()
        except Exception as erreur:
            logger.warning("Lecture S3 impossible pour %s : %s", file_id, erreur)
            return None

    def _delete_blob(self, file_id: str) -> None:
        """
        Supprime les octets du seau.

        Le magasin S3 d'origine ne faisait rien de tel dans `clear()` : il vidait
        son index local et rapportait N fichiers supprimés pendant que les N
        objets restaient dans le seau, facturés et lisibles par qui a la clé.
        """
        try:
            self._client().delete_object(Bucket=self._bucket, Key=self._cle(file_id))
        except Exception as erreur:
            logger.warning("Suppression S3 impossible pour %s : %s", file_id, erreur)
