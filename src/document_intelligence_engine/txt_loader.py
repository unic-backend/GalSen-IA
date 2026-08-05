"""
Chargeur de fichiers texte pour le moteur d'intelligence documentaire GalSen IA.
"""

import os
from .document_loader_factory import BaseDocumentLoader
from .types import DocumentItem, DocumentType
import logging

logger = logging.getLogger(__name__)


class TXTLoader(BaseDocumentLoader):
    """Chargeur pour les fichiers texte (.txt)."""

    # Extensions supportées
    supported_extensions = ['.txt']

    def load(self, source: str, **kwargs) -> DocumentItem:
        """
        Charge un fichier texte et retourne un DocumentItem.

        Args:
            source: Chemin vers le fichier texte
            **kwargs: Options supplémentaires (encoding, etc.)

        Returns:
            DocumentItem représentant le fichier chargé
        """
        if not os.path.isfile(source):
            raise FileNotFoundError(f"Fichier non trouvé: {source}")

        # Déterminer l'encodage (par défaut utf-8)
        encoding = kwargs.get('encoding', 'utf-8')

        try:
            with open(source, 'r', encoding=encoding) as f:
                content = f.read()
        except UnicodeDecodeError:
            # Essayer avec latin-1 comme fallback
            with open(source, 'r', encoding='latin-1') as f:
                content = f.read()

        # Extraire les métadonnées de base
        stat = os.stat(source)
        metadata = {
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "source": os.path.abspath(source),
            "filename": os.path.basename(source),
            "extension": os.path.splitext(source)[1],
            "line_count": len(content.splitlines()),
            "char_count": len(content)
        }

        # Utiliser le nom du fichier comme titre (sans extension)
        title = os.path.splitext(os.path.basename(source))[0]

        # Créer l'élément de document
        document = DocumentItem(
            document_id="",  # Sera généré par le store
            document_type=DocumentType.TXT,
            title=title,
            content=content,
            metadata=metadata
        )

        return document

    def supports_type(self, document_type: str) -> bool:
        """Vérifie si le chargeur supporte le type de document donné."""
        return document_type in [DocumentType.TXT.value, 'text/plain']