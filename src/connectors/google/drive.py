"""
The Drive connector: listing and reading files, nothing else.

Same shape as Gmail, and for the same reasons — see `base.py`. What is specific
to a drive is that a *file* is not a message: it has a size, a type, and it can
be enormous. Two consequences are written into this module rather than left to
whoever calls it:

**A file's content is only read when asked for, and only up to a limit.**
Listing a drive returns metadata; downloading is a separate call. A connector
that quietly pulled every byte it listed would move gigabytes on someone's
behalf without them asking.

**A Google-native document is not a file to download.** A Doc or a Sheet has no
bytes to fetch — it must be exported to a format. This connector says so instead
of returning an empty body, which would read as « the document is empty ».
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..lifecycle import SubjectBinding
from ..safety import receive
from ..types import ConnectorKind
from .base import GoogleReadConnector

#: Nombre de fichiers listés par défaut, et plafond dur.
TAILLE_DE_PAGE_PAR_DEFAUT = 25
TAILLE_DE_PAGE_MAXIMALE = 100

#: Taille maximale d'un contenu accepté à la lecture, en octets. Au-delà, le
#: connecteur refuse **en le disant** : un fichier tronqué en silence se lit
#: comme un fichier entier.
TAILLE_MAXIMALE_OCTETS = 5 * 1024 * 1024

#: Les champs demandés au listage. Les nommer évite de ramener tout ce que
#: l'API sait dire d'un fichier, dont des choses que personne n'a demandées.
CHAMPS_DE_LISTAGE = "files(id,name,mimeType,size,modifiedTime),nextPageToken"

#: Préfixe des types Google natifs — Docs, Sheets, Slides. Ils n'ont pas
#: d'octets à télécharger.
PREFIXE_NATIF = "application/vnd.google-apps."


class DriveConnector(GoogleReadConnector):
    """Lecture des fichiers Drive d'une personne, pour elle seule."""

    CONNECTOR_ID = "google_drive"
    API_NAME = "drive"
    KIND = ConnectorKind.STORAGE
    SUMMARY = (
        "Lecture des fichiers Drive d'une personne. Ne téléverse rien, "
        "ne modifie rien, ne supprime rien."
    )
    OPERATIONS = ["list_files", "get_file", "download_file", "read_text"]

    def extra_refusals(self) -> List[str]:
        """Les refus propres au Drive."""
        return [
            "Téléverser, renommer, partager, supprimer — ce connecteur lit.",
            f"Lire un contenu au-delà de {TAILLE_MAXIMALE_OCTETS} octets, "
            "plutôt que de le tronquer en silence.",
            "Prétendre qu'un document Google natif est vide : il s'exporte.",
        ]

    # ------------------------------------------------------------------
    # Les requêtes
    # ------------------------------------------------------------------

    def list_files_request(
        self,
        binding: SubjectBinding,
        query: str = "",
        page_size: int = TAILLE_DE_PAGE_PAR_DEFAUT,
        page_token: str = "",
    ) -> Dict[str, Any]:
        """
        Construit la requête listant les fichiers du titulaire.

        Args:
            binding: Le lien à la personne.
            query: Une recherche Drive, telle quelle. Elle vient de la personne.
            page_size: Combien de fichiers, ramené au plafond si dépassé.
            page_token: La page suivante, quand il y en a une.

        Returns:
            La requête à envoyer.
        """
        parametres: Dict[str, Any] = {
            "pageSize": self._plafonner(
                page_size, TAILLE_DE_PAGE_PAR_DEFAUT, TAILLE_DE_PAGE_MAXIMALE
            ),
            "fields": CHAMPS_DE_LISTAGE,
        }
        if query:
            parametres["q"] = query
        if page_token:
            parametres["pageToken"] = page_token
        return self._requete(binding, "files", parametres)

    def get_file_request(
        self, binding: SubjectBinding, file_id: str
    ) -> Dict[str, Any]:
        """
        Construit la requête lisant les **métadonnées** d'un fichier.

        Séparée du téléchargement à dessein : savoir ce qu'est un fichier ne
        doit pas obliger à en rapatrier le contenu.

        Args:
            binding: Le lien à la personne.
            file_id: L'identifiant du fichier.

        Returns:
            La requête à envoyer.

        Raises:
            ValueError: Si l'identifiant est vide.
        """
        return self._requete(
            binding,
            f"files/{self._identifiant(file_id)}",
            {"fields": "id,name,mimeType,size,modifiedTime"},
        )

    def download_request(
        self, binding: SubjectBinding, file_id: str
    ) -> Dict[str, Any]:
        """
        Construit la requête rapatriant le contenu d'un fichier.

        Args:
            binding: Le lien à la personne.
            file_id: L'identifiant du fichier.

        Returns:
            La requête à envoyer.

        Raises:
            ValueError: Si l'identifiant est vide.
        """
        return self._requete(
            binding, f"files/{self._identifiant(file_id)}", {"alt": "media"}
        )

    @staticmethod
    def _identifiant(file_id: str) -> str:
        """Valide un identifiant de fichier."""
        if not (file_id or "").strip():
            raise ValueError("Identifiant de fichier vide : rien à lire.")
        return file_id.strip()

    # ------------------------------------------------------------------
    # Ce qui sort
    # ------------------------------------------------------------------

    def read_listing(
        self, binding: SubjectBinding, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Rend un listage exploitable, **noms enveloppés**.

        Un nom de fichier est du texte qu'un tiers a pu choisir — un fichier
        partagé s'appelle comme son auteur l'a voulu. Il traverse donc la même
        barrière que le contenu.

        Args:
            binding: Le lien à la personne.
            payload: La réponse du fournisseur.

        Returns:
            Les fichiers, et le jeton de page suivant s'il y en a un.

        Raises:
            ValueError: Si la réponse n'est pas exploitable.
        """
        if not isinstance(payload, dict):
            raise ValueError(
                f"Réponse de listage inattendue : {type(payload).__name__}."
            )

        fichiers = []
        for entree in payload.get("files", []) or []:
            identifiant = str((entree or {}).get("id") or "inconnu")
            fichiers.append({
                "file_id": identifiant,
                "name": receive(
                    self, str(entree.get("name") or ""),
                    origin=f"file:{identifiant}:name", subject=binding.subject,
                ).text,
                "mime_type": entree.get("mimeType"),
                "size": entree.get("size"),
                "modified_time": entree.get("modifiedTime"),
                "native_google_document": str(
                    entree.get("mimeType") or ""
                ).startswith(PREFIXE_NATIF),
            })

        return {"files": fichiers, "next_page_token": payload.get("nextPageToken")}

    def read_text(
        self,
        binding: SubjectBinding,
        file_id: str,
        content: Any,
        mime_type: str = "",
    ) -> Dict[str, Any]:
        """
        Rend le contenu d'un fichier, **enveloppé en donnée**.

        Args:
            binding: Le lien à la personne.
            file_id: L'identifiant du fichier.
            content: Le contenu rapatrié, texte ou octets.
            mime_type: Son type, quand il est connu.

        Returns:
            Le contenu enveloppé, ou le refus motivé.
        """
        if str(mime_type or "").startswith(PREFIXE_NATIF):
            return {
                "file_id": file_id,
                "body": None,
                "refused": (
                    f"Document Google natif ({mime_type}) : il n'a pas d'octets "
                    "à télécharger, il s'exporte vers un format. Rendre un "
                    "corps vide se lirait comme « le document est vide »."
                ),
            }

        octets = content if isinstance(content, (bytes, bytearray)) else (
            str(content or "").encode("utf-8")
        )
        if len(octets) > TAILLE_MAXIMALE_OCTETS:
            return {
                "file_id": file_id,
                "body": None,
                "refused": (
                    f"Contenu de {len(octets)} octets, au-delà de la limite de "
                    f"{TAILLE_MAXIMALE_OCTETS}. Refusé plutôt que tronqué : un "
                    "fichier coupé en silence se lit comme un fichier entier."
                ),
            }

        enveloppe = receive(
            self, octets.decode("utf-8", "replace"),
            origin=f"file:{file_id}", subject=binding.subject,
        )
        return {
            "file_id": file_id,
            "body": enveloppe.text,
            "suspicions": list(enveloppe.suspicions),
            "refused": None,
        }

    def drive_report(self, subject: Optional[str] = None) -> Dict[str, Any]:
        """Ce que ce connecteur est, et ce qu'il refuse d'être."""
        return self.connector_report(subject)
