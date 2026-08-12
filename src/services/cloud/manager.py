"""
Gestionnaire du service Cloud — adaptateur sur le service de fichiers (ADR-016).

Ce service **ne stocke plus rien lui-même**. Il traduit les routes `/cloud/*`,
dépréciées, vers le service de fichiers, qui est le chemin d'écriture unique de
la plateforme.

## Pourquoi les quatre magasins cloud ont disparu

ADR-016 a mesuré que `file` et `cloud` étaient une même conception écrite deux
fois : mêmes routes, même interface de magasin méthode pour méthode, même
gestionnaire. Les backends `filesystem` et `s3` — la seule chose que le service
cloud avait de plus — sont passés sous le service de fichiers. Il ne restait
donc que la duplication.

## Ce que `provider` valait, et ce qu'il vaut maintenant

`CloudFileItem.provider` était **une déclaration de l'appelant, jamais
vérifiée**. Mesuré avant ce changement : un téléversement avec `provider="s3"`
sur une plateforme configurée en mémoire enregistrait `s3`, et `/cloud/stats`
rapportait `by_provider: {"s3": 1}` pour un fichier qui vivait en RAM.

Le champ reste dans la réponse — la route est dépréciée, pas modifiée — mais il
porte désormais **le magasin qui détient réellement les octets**. Un appelant
qui demande `s3` sur une plateforme en `filesystem` obtient `local` : c'est un
changement de valeur, et c'est la fin d'une valeur fausse.

`CloudFileItem` n'est plus un type stocké. C'est la **forme de réponse** des
routes dépréciées, construite à la demande depuis un `FileItem`.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from src.services.file.manager import FileManagerImpl

from .interfaces import CloudManager
from .types import CloudFileCategory, CloudFileItem, CloudProvider, CloudSyncResult

logger = logging.getLogger(__name__)

# Le magasin qui détient les octets → le fournisseur annoncé. Seul `s3` est un
# fournisseur distant ; tout le reste est local à la machine, et le dire
# autrement serait reproduire le champ faux qu'on retire.
FOURNISSEUR_PAR_MAGASIN = {
    "S3FileStore": CloudProvider.S3,
    "FileSystemFileStore": CloudProvider.LOCAL,
    "SQLiteFileStore": CloudProvider.LOCAL,
    "InMemoryFileStore": CloudProvider.LOCAL,
}

ANCIENNE_VARIABLE = "GALSEN_CLOUD_BACKEND"


def _infer_category(content_type: str) -> CloudFileCategory:
    """Déduit la catégorie d'un fichier depuis son type MIME."""
    type_map: Dict[str, CloudFileCategory] = {
        "application/pdf": CloudFileCategory.DOCUMENT,
        "application/msword": CloudFileCategory.DOCUMENT,
        "application/vnd.openxmlformats-officedocument": CloudFileCategory.DOCUMENT,
        "text/plain": CloudFileCategory.DOCUMENT,
        "text/html": CloudFileCategory.DOCUMENT,
        "text/csv": CloudFileCategory.DATA,
        "application/json": CloudFileCategory.DATA,
        "application/xml": CloudFileCategory.DATA,
        "image/": CloudFileCategory.IMAGE,
        "video/": CloudFileCategory.VIDEO,
        "audio/": CloudFileCategory.AUDIO,
        "application/zip": CloudFileCategory.ARCHIVE,
        "application/x-tar": CloudFileCategory.ARCHIVE,
        "application/gzip": CloudFileCategory.ARCHIVE,
    }

    for prefix, category in type_map.items():
        if content_type.startswith(prefix):
            return category
    return CloudFileCategory.OTHER


class CloudManagerImpl(CloudManager):
    """Façade des routes `/cloud/*`, servie par le service de fichiers."""

    def __init__(self, files: Optional[FileManagerImpl] = None) -> None:
        """
        Args:
            files: Service de fichiers à utiliser ; un nouveau sinon.
        """
        self._logger = logging.getLogger(f"{__name__}.CloudManagerImpl")
        self._files = files if files is not None else FileManagerImpl()
        self._avertir_ancienne_variable()

    def _avertir_ancienne_variable(self) -> None:
        """
        Signale `GALSEN_CLOUD_BACKEND`, qui ne sélectionne plus rien.

        L'ignorer en silence serait le défaut que ce dépôt traque partout
        ailleurs : un opérateur ayant écrit `filesystem` là croirait ses
        fichiers sur disque alors qu'ils seraient en mémoire.
        """
        if os.getenv(ANCIENNE_VARIABLE, "").strip():
            self._logger.error(
                "%s n'a plus d'effet (ADR-016) : le service de fichiers choisit le "
                "magasin. Déclarer GALSEN_FILE_BACKEND à la place.",
                ANCIENNE_VARIABLE,
            )

    @property
    def provider(self) -> CloudProvider:
        """Retourne le fournisseur qui détient réellement les octets."""
        return FOURNISSEUR_PAR_MAGASIN.get(
            type(self._files._store).__name__, CloudProvider.LOCAL
        )

    def _en_element_cloud(self, fichier) -> CloudFileItem:
        """
        Présente un fichier sous la forme attendue par les routes `/cloud/*`.

        Args:
            fichier: `FileItem` ou `FileSummary` du service de fichiers.
        """
        return CloudFileItem(
            id=fichier.id,
            name=fichier.name,
            content_type=fichier.content_type,
            size=fichier.size,
            provider=self.provider,
            category=_infer_category(fichier.content_type),
            uploaded_by=fichier.uploaded_by,
            metadata=dict(fichier.metadata),
            created_at=fichier.created_at,
            updated_at=fichier.updated_at,
        )

    def upload(
        self,
        name: str,
        content_type: str,
        data: bytes,
        provider: CloudProvider = CloudProvider.LOCAL,
        uploaded_by: Optional[str] = None,
        max_size: int = 100 * 1024 * 1024,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CloudSyncResult:
        """
        Téléverse un fichier par le service de fichiers.

        `provider` est accepté pour ne pas casser les appelants de la route
        dépréciée, et **ignoré** : le magasin qui détient les octets est décidé
        par la configuration (`GALSEN_FILE_BACKEND`), pas par l'appelant.
        Enregistrer sa demande revenait à enregistrer une croyance.
        """
        if provider is not None and provider != self.provider:
            self._logger.info(
                "Fournisseur « %s » demandé et ignoré : les octets vont dans %s "
                "(ADR-016).",
                getattr(provider, "value", provider), self.provider.value,
            )

        resultat = self._files.upload_file(
            name=name.strip() if isinstance(name, str) else name,
            content_type=content_type,
            data=data,
            uploaded_by=uploaded_by,
            metadata=metadata,
            max_size=max_size,
        )
        if not resultat.success:
            # `FileUploadResult` nomme son champ `error` ; le traduire ici évite
            # de rendre un message vide sur un refus, ce qui laisserait
            # l'appelant sans la raison.
            return CloudSyncResult(False, resultat.error or "Téléversement refusé.")
        return CloudSyncResult(
            True,
            f"Fichier '{name}' téléversé avec succès.",
            file_id=resultat.file_id,
        )

    def get_file(self, file_id: str) -> Optional[CloudFileItem]:
        """Retourne les métadonnées d'un fichier."""
        fichier = self._files.get_file(file_id)
        return self._en_element_cloud(fichier) if fichier is not None else None

    def download(self, file_id: str) -> Optional[bytes]:
        """Retourne le contenu d'un fichier, ou None s'il est absent."""
        fichier = self._files.get_file(file_id)
        return fichier.data if fichier is not None else None

    def list_files(
        self,
        limit: int = 100,
        offset: int = 0,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> List[CloudFileItem]:
        """
        Retourne les fichiers filtrés.

        Le filtre `provider` porte sur le magasin actif : tous les fichiers y
        sont, ou aucun. Il filtrait auparavant sur une valeur déclarée à
        l'envoi, donc sur ce que l'appelant avait cru.
        """
        if provider is not None and provider != self.provider.value:
            return []

        resumes = self._files.list_files(
            limit=limit, offset=offset, uploaded_by=uploaded_by,
        )
        elements = [self._en_element_cloud(resume) for resume in resumes]
        if category is not None:
            elements = [e for e in elements if e.category.value == category]
        return elements

    def delete(self, file_id: str) -> bool:
        """Supprime un fichier ; retourne False s'il est absent."""
        return self._files.delete_file(file_id)

    def update_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """Met à jour les métadonnées d'un fichier ; False s'il est absent."""
        return self._files.update_metadata(file_id, metadata)

    def stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques, dans la forme attendue par `/cloud/stats`.

        `by_provider` ne compte plus des déclarations d'appelants : tous les
        fichiers sont dans le magasin actif, et c'est ce qu'il annonce.
        """
        etat = self._files.stats()
        if not etat:
            # Le service de fichiers rend un dictionnaire vide quand son magasin
            # est en panne. Rendre « zéro fichier » ici dirait qu'il n'y en a
            # pas, alors que personne n'a pu compter.
            return {}

        total = etat.get("total", 0)
        return {
            "total": total,
            "total_size": etat.get("total_size", 0),
            "by_category": self._par_categorie(),
            "by_provider": {self.provider.value: total} if total else {},
        }

    def _par_categorie(self) -> Dict[str, int]:
        """Compte les fichiers par catégorie cloud, déduite du type MIME."""
        comptes: Dict[str, int] = {}
        for resume in self._files.list_files(limit=10_000):
            categorie = _infer_category(resume.content_type).value
            comptes[categorie] = comptes.get(categorie, 0) + 1
        return comptes

    def clear(self) -> int:
        """Supprime tous les fichiers et retourne le nombre supprimé."""
        return self._files.clear()
