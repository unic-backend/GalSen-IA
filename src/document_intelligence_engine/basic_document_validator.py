"""
Validateur de documents pour le moteur d'intelligence documentaire GalSen IA.
"""

from typing import List, Optional, Tuple

from .interfaces import DocumentValidator
from .types import DocumentItem, DocumentStatus, DocumentType


class DocumentValidatorImpl(DocumentValidator):
    """
    Validateur d'intégrité des documents.

    Il vérifie qu'un document est exploitable par la suite de la chaîne de
    traitement : champs obligatoires renseignés, types cohérents et taille
    compatible avec les limites de la plateforme.
    """

    # Taille maximale du contenu textuel accepté, en caractères (~50 Mo)
    DEFAULT_MAX_CONTENT_LENGTH = 50 * 1024 * 1024

    def __init__(self, max_content_length: Optional[int] = None):
        """
        Initialise le validateur.

        Args:
            max_content_length: Longueur maximale du contenu, None pour la
                valeur par défaut de la plateforme
        """
        self._max_content_length = (
            max_content_length if max_content_length is not None
            else self.DEFAULT_MAX_CONTENT_LENGTH
        )

    def validate(self, document: DocumentItem) -> Tuple[bool, List[str]]:
        """
        Valide un document.

        Args:
            document: Document à valider

        Returns:
            Tuple (document valide, liste des erreurs constatées)
        """
        errors: List[str] = []

        if not document.title or not document.title.strip():
            errors.append("Le titre du document ne peut pas être vide")

        if not document.content:
            errors.append("Le contenu du document ne peut pas être vide")
        elif len(document.content) > self._max_content_length:
            errors.append(
                f"Le contenu dépasse la taille maximale autorisée "
                f"({len(document.content)} > {self._max_content_length} caractères)"
            )

        if not isinstance(document.document_type, DocumentType):
            errors.append("Type de document invalide")

        if not isinstance(document.status, DocumentStatus):
            errors.append("Statut de document invalide")

        if document.version < 1:
            errors.append("Le numéro de version doit être au moins 1")

        # Un document ne peut pas être sa propre version précédente
        if document.parent_id and document.parent_id == document.document_id:
            errors.append("Un document ne peut pas être son propre parent")

        return not errors, errors
