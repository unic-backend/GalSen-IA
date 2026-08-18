"""
Chargeur de fichiers PDF pour le moteur d'intelligence documentaire GalSen IA.
"""

import os
from .document_loader_factory import BaseDocumentLoader
from .types import DocumentItem, DocumentType
import logging

logger = logging.getLogger(__name__)


class PDFLoader(BaseDocumentLoader):
    """Chargeur pour les fichiers PDF (.pdf)."""

    # Extensions supportées
    supported_extensions = ['.pdf']

    def load(self, source: str, **kwargs) -> DocumentItem:
        """
        Charge un fichier PDF et retourne un DocumentItem.

        Args:
            source: Chemin vers le fichier PDF
            **kwargs: Options supplémentaires (pages, etc.)

        Returns:
            DocumentItem représentant le fichier chargé
        """
        if not os.path.isfile(source):
            raise FileNotFoundError(f"Fichier non trouvé: {source}")

        try:
            try:
                import pypdf as PyPDF2  # successeur maintenu de PyPDF2
            except ImportError:
                import PyPDF2
        except ImportError:
            logger.error("PyPDF2 est requis pour charger les fichiers PDF. Installez-le avec: pip install PyPDF2")
            raise ImportError("PyPDF2 est requis pour charger les fichiers PDF. Installez-le avec: pip install PyPDF2")

        # Extraire le texte du PDF
        text_content = ""
        with open(source, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text_content += page.extract_text() + "\n"

        # Extraire les métadonnées du PDF
        metadata = {
            "size": os.path.getsize(source),
            "created": os.path.getctime(source),
            "modified": os.path.getmtime(source),
            "source": os.path.abspath(source),
            "filename": os.path.basename(source),
            "extension": ".pdf",
            "page_count": num_pages
        }

        # Essayer d'obtenir les métadonnées du PDF
        if pdf_reader.metadata:
            pdf_meta = pdf_reader.metadata
            if pdf_meta.author:
                metadata["author"] = pdf_meta.author
            if pdf_meta.creator:
                metadata["creator"] = pdf_meta.creator
            if pdf_meta.producer:
                metadata["producer"] = pdf_meta.producer
            if pdf_meta.creation_date:
                metadata["creation_date"] = str(pdf_meta.creation_date)
            if pdf_meta.modification_date:
                metadata["modification_date"] = str(pdf_meta.modification_date)
            if pdf_meta.title:
                metadata["title"] = pdf_meta.title
            if pdf_meta.subject:
                metadata["subject"] = pdf_meta.subject
            if hasattr(pdf_meta, 'keywords') and pdf_meta.keywords:
                metadata["keywords"] = pdf_meta.keywords

        # Utiliser le titre du PDF ou le nom du fichier
        title = metadata.get("title") or os.path.splitext(os.path.basename(source))[0]

        # Créer l'élément de document
        document = DocumentItem(
            document_id="",
            document_type=DocumentType.PDF,
            title=title,
            content=text_content.strip(),
            metadata=metadata
        )

        return document

    def supports_type(self, document_type: str) -> bool:
        """Vérifie si le chargeur supporte le type de document donné."""
        return document_type in [DocumentType.PDF.value, 'application/pdf']