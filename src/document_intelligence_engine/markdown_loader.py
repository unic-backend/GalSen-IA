"""
Chargeur de fichiers Markdown pour le moteur d'intelligence documentaire GalSen IA.
"""

import os
from .document_loader_factory import BaseDocumentLoader
from .types import DocumentItem, DocumentType
import logging

logger = logging.getLogger(__name__)

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False
    logger.warning("Bibliothèque 'markdown' non trouvée. Le chargeur Markdown traitera les fichiers comme du texte brut.")


class MarkdownLoader(BaseDocumentLoader):
    """Chargeur pour les fichiers Markdown (.md)."""

    # Extensions supportées
    supported_extensions = ['.md', '.markdown']

    def load(self, source: str, **kwargs) -> DocumentItem:
        """
        Charge un fichier Markdown et retourne un DocumentItem.

        Args:
            source: Chemin vers le fichier Markdown
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
                markdown_content = f.read()
        except UnicodeDecodeError:
            with open(source, 'r', encoding='latin-1') as f:
                markdown_content = f.read()

        # Convertir en HTML si la bibliothèque est disponible, sinon garder le texte brut
        if MARKDOWN_AVAILABLE:
            html_content = markdown.markdown(markdown_content)
            # Pour l'instant, nous stockons le contenu Markdown comme contenu principal
            # et nous pourrions stocker l'HTML dans les métadonnées
            content = markdown_content
            metadata_extra = {"html_content": html_content}
        else:
            content = markdown_content
            metadata_extra = {}

        # Extraire les métadonnées de base
        stat = os.stat(source)
        metadata = {
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "source": os.path.abspath(source),
            "filename": os.path.basename(source),
            "extension": os.path.splitext(source)[1]
        }
        metadata.update(metadata_extra)

        # Créer l'élément de document
        document = DocumentItem(
            document_id="",
            document_type=DocumentType.MARKDOWN,
            title=os.path.splitext(os.path.basename(source))[0],
            content=content,
            metadata=metadata
        )

        return document

    def supports_type(self, document_type: str) -> bool:
        """Vérifie si le chargeur supporte le type de document donné."""
        return document_type in [DocumentType.MARKDOWN.value, 'text/markdown']