"""
Connecteur de stockage sur disque local.

Propriétaire, côté plateforme, de l'endroit où vivent les fichiers téléversés.
Aujourd'hui le service de fichiers les garde en mémoire : ils disparaissent au
redémarrage. Ce connecteur donne un endroit durable où les écrire.

Le disque local est le premier fournisseur, pas le seul visé : un connecteur S3
ou MinIO se branchera derrière le même contrat, sans que l'appelant change
(ADR-007). C'est aussi le seul qui fonctionne sans compte ni réseau, ce qui en
fait le défaut raisonnable pour une installation au Sénégal où la connectivité
n'est pas acquise.

Toute clé est résolue puis vérifiée contre le répertoire racine avant le moindre
accès : ni `..`, ni chemin absolu, ni lien symbolique ne permettent d'en sortir —
la même discipline que l'outil système de fichiers.
"""

import logging
import os
import shutil
import time
from typing import Any, Dict, List, Optional

from .interfaces import Connector
from .types import ConnectorCheck, ConnectorDescription, ConnectorKind, ConnectorStatus

logger = logging.getLogger(__name__)


class StorageAccessError(RuntimeError):
    """Levée quand une clé sort du répertoire autorisé ou qu'un objet est absent."""


class LocalDiskStorageConnector(Connector):
    """
    Connecteur de stockage d'objets sur le disque local.

    Exemple:
        stockage = LocalDiskStorageConnector()
        if stockage.is_configured():
            stockage.put("rapports/2026/aout.pdf", donnees)
    """

    CONNECTOR_ID = "storage_local_disk"

    ROOT_VARIABLE = "GALSEN_FILE_STORAGE_DIR"
    REQUIRED_VARIABLES = [ROOT_VARIABLE]

    def __init__(self, root: Optional[str] = None) -> None:
        """
        Initialise le connecteur.

        Args:
            root: Répertoire racine du stockage. À défaut, la variable
                `GALSEN_FILE_STORAGE_DIR`. Sans l'un ni l'autre, le connecteur
                se déclare non configuré plutôt que d'écrire quelque part au
                hasard.
        """
        self._explicit_root = root

    @property
    def connector_id(self) -> str:
        """Identifiant stable du connecteur."""
        return self.CONNECTOR_ID

    @property
    def kind(self) -> ConnectorKind:
        """Catégorie : stockage."""
        return ConnectorKind.STORAGE

    def describe(self) -> ConnectorDescription:
        """Décrit le connecteur et la variable qu'il consulte."""
        return ConnectorDescription(
            connector_id=self.CONNECTOR_ID,
            kind=ConnectorKind.STORAGE,
            summary=(
                "Stockage d'objets sur le disque local. La vérification contrôle "
                "que la racine existe et accepte l'écriture, sans y laisser de fichier."
            ),
            environment_variables=[self.ROOT_VARIABLE],
            operations=["check", "put", "get", "delete", "exists", "list_keys", "usage"],
            owner="plateforme",
        )

    def root(self) -> Optional[str]:
        """Retourne la racine configurée, résolue, ou None si aucune ne l'est."""
        brut = self._explicit_root or self._read_environment(self.ROOT_VARIABLE)
        return os.path.realpath(brut) if brut else None

    def is_configured(self) -> bool:
        """Indique si une racine est déclarée, sans toucher au disque."""
        return self.root() is not None

    def check(self) -> ConnectorCheck:
        """
        Vérifie que la racine existe et accepte l'écriture.

        Le test d'écriture crée puis supprime un fichier temporaire : sans lui,
        un répertoire en lecture seule passerait pour opérationnel jusqu'au
        premier téléversement.
        """
        racine = self.root()
        if racine is None:
            return self._not_configured([self.ROOT_VARIABLE])

        debut = time.time()
        try:
            os.makedirs(racine, exist_ok=True)
            temoin = os.path.join(racine, f".galsen-ecriture-{os.getpid()}")
            with open(temoin, "wb") as fichier:
                fichier.write(b"ok")
            os.remove(temoin)
        except PermissionError as erreur:
            return self._resultat(
                ConnectorStatus.UNAUTHORIZED,
                f"Écriture refusée dans {racine} : {erreur}",
                debut,
            )
        except OSError as erreur:
            return self._resultat(
                ConnectorStatus.UNREACHABLE,
                f"Racine de stockage inutilisable ({racine}) : {type(erreur).__name__}: {erreur}",
                debut,
            )

        return self._resultat(
            ConnectorStatus.READY, f"Stockage opérationnel dans {racine}.", debut
        )

    # ------------------------------------------------------------------
    # Opérations de stockage
    # ------------------------------------------------------------------
    def put(self, key: str, data: bytes) -> Dict[str, Any]:
        """
        Écrit un objet.

        Args:
            key: Clé de l'objet, relative à la racine (`rapports/2026/aout.pdf`)
            data: Contenu binaire

        Returns:
            La clé et la taille écrite.

        Raises:
            StorageAccessError: Si le stockage n'est pas configuré ou si la clé
                sort du répertoire autorisé.
        """
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("Le contenu doit être fourni en octets.")

        chemin = self._resolve(key)
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, "wb") as fichier:
            fichier.write(data)

        logger.info("Objet écrit : %s (%d octets)", key, len(data))
        return {"key": self._relative(chemin), "size": len(data)}

    def get(self, key: str) -> bytes:
        """
        Lit un objet.

        Raises:
            StorageAccessError: Si l'objet est absent ou hors du répertoire autorisé.
        """
        chemin = self._resolve(key)
        if not os.path.isfile(chemin):
            raise StorageAccessError(f"Objet introuvable : {key}")
        with open(chemin, "rb") as fichier:
            return fichier.read()

    def exists(self, key: str) -> bool:
        """Indique si un objet existe, sans le lire."""
        return os.path.isfile(self._resolve(key))

    def delete(self, key: str) -> bool:
        """Supprime un objet ; retourne False s'il était absent."""
        chemin = self._resolve(key)
        if not os.path.isfile(chemin):
            return False
        os.remove(chemin)
        logger.info("Objet supprimé : %s", key)
        return True

    def list_keys(self, prefix: str = "") -> List[str]:
        """
        Liste les clés stockées, éventuellement filtrées par préfixe.

        Returns:
            Les clés triées, exprimées relativement à la racine.
        """
        racine = self._require_root()
        cles: List[str] = []
        for repertoire, _, fichiers in os.walk(racine):
            for nom in fichiers:
                if nom.startswith(".galsen-ecriture-"):
                    continue  # témoin de vérification, jamais un objet stocké
                cle = self._relative(os.path.join(repertoire, nom))
                if cle.startswith(prefix):
                    cles.append(cle)
        return sorted(cles)

    def usage(self) -> Dict[str, Any]:
        """Retourne le nombre d'objets et la place occupée."""
        racine = self._require_root()
        cles = self.list_keys()
        total = sum(os.path.getsize(os.path.join(racine, cle)) for cle in cles)
        return {
            "root": racine,
            "objects": len(cles),
            "total_bytes": total,
            "total_mb": round(total / (1024 * 1024), 2),
        }

    def clear(self) -> int:
        """
        Supprime tous les objets et retourne le nombre supprimé.

        La racine elle-même est conservée : la vider ne doit pas la faire
        disparaître, ni emporter ce qui l'entoure.
        """
        racine = self._require_root()
        supprimes = 0
        for cle in self.list_keys():
            os.remove(os.path.join(racine, cle))
            supprimes += 1

        for nom in os.listdir(racine):
            chemin = os.path.join(racine, nom)
            if os.path.isdir(chemin):
                shutil.rmtree(chemin, ignore_errors=True)
        return supprimes

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _require_root(self) -> str:
        """Retourne la racine, ou lève si le stockage n'est pas configuré."""
        racine = self.root()
        if racine is None:
            raise StorageAccessError(
                "Stockage non configuré : renseignez "
                f"{self.ROOT_VARIABLE} avec un répertoire de destination."
            )
        os.makedirs(racine, exist_ok=True)
        return racine

    def _resolve(self, key: str) -> str:
        """
        Résout une clé en chemin absolu, confiné à la racine.

        Raises:
            StorageAccessError: Si la clé est vide ou sort de la racine. Une clé
                vient souvent d'une requête : elle doit être traitée comme une
                entrée hostile.
        """
        racine = self._require_root()

        if not isinstance(key, str) or not key.strip():
            raise StorageAccessError("La clé doit être une chaîne non vide.")

        candidat = os.path.join(racine, key)
        # realpath résout les liens symboliques : sans cela, un lien pourrait
        # pointer hors de la racine tout en semblant s'y trouver
        resolu = os.path.realpath(candidat)

        if resolu != racine and not resolu.startswith(racine + os.sep):
            raise StorageAccessError(
                f"Accès refusé : la clé '{key}' sort du répertoire de stockage."
            )
        return resolu

    def _relative(self, chemin_absolu: str) -> str:
        """Exprime un chemin relativement à la racine, en séparateurs POSIX."""
        return os.path.relpath(chemin_absolu, self._require_root()).replace(os.sep, "/")

    def _resultat(self, statut: ConnectorStatus, detail: str, debut: float) -> ConnectorCheck:
        """Construit le résultat d'une vérification en mesurant sa durée."""
        return ConnectorCheck(
            connector_id=self.CONNECTOR_ID,
            kind=ConnectorKind.STORAGE,
            status=statut,
            detail=detail,
            latency_ms=(time.time() - debut) * 1000,
        )
