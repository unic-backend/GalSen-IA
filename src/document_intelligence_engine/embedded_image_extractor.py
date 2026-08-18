"""
Extracteur d'images pour le moteur d'intelligence documentaire GalSen IA.
"""

import logging
import os
import re
import zipfile
from typing import Any, Dict, List

from .interfaces import DocumentImageExtractor
from .types import DocumentItem, DocumentType


class ImageExtractorImpl(DocumentImageExtractor):
    """
    Extracteur des images d'un document.

    La méthode d'extraction dépend du format :

    - DOCX, XLSX, PPTX : ce sont des archives ZIP, les images sont lues
      directement dans le dossier `media` de l'archive, sans dépendance externe.
    - PDF : les images sont énumérées via PyPDF2 lorsque la bibliothèque est
      disponible.
    - HTML, Markdown : les images sont des références externes, on retourne les
      URL déclarées dans le contenu.
    - TXT, CSV : ces formats ne portent pas d'image, la liste est vide.

    Les données binaires ne sont chargées que si l'appelant les demande, afin de
    ne pas saturer la mémoire sur les documents volumineux.
    """

    # Dossier des médias dans chaque format OOXML
    _OOXML_MEDIA_PREFIXES = {
        DocumentType.DOCX: "word/media/",
        DocumentType.XLSX: "xl/media/",
        DocumentType.PPTX: "ppt/media/",
    }

    _HTML_IMAGE_PATTERN = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
    _MARKDOWN_IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)')

    def __init__(self):
        """Initialise l'extracteur d'images."""
        self._logger = logging.getLogger(__name__)

    def extract_images(self, document: DocumentItem, **kwargs) -> List[Dict[str, Any]]:
        """
        Extrait les images d'un document.

        Args:
            document: Document à analyser
            **kwargs: `include_data` (False par défaut) pour joindre les octets
                de chaque image extraite d'une archive OOXML

        Returns:
            Liste d'images décrites par leur nom, leur format et leur origine
        """
        include_data = kwargs.get('include_data', False)

        if document.document_type in self._OOXML_MEDIA_PREFIXES:
            return self._extract_from_ooxml(document, include_data)
        if document.document_type == DocumentType.PDF:
            return self._extract_from_pdf(document)
        if document.document_type == DocumentType.HTML:
            # Le chargeur HTML ne conserve que le texte : les balises <img> ne sont
            # visibles que dans le fichier d'origine
            return self._extract_references(self._raw_html(document), self._HTML_IMAGE_PATTERN, group=1)
        if document.document_type == DocumentType.MARKDOWN:
            return self._extract_references(document.content, self._MARKDOWN_IMAGE_PATTERN, group=2)

        # TXT et CSV ne contiennent pas d'image : la liste vide est la bonne réponse
        return []

    def _source_path(self, document: DocumentItem) -> str:
        """Retourne le chemin du fichier source, ou une chaîne vide s'il est inconnu."""
        source = document.metadata.get("source", "")
        return source if source and os.path.isfile(source) else ""

    def _extract_from_ooxml(self, document: DocumentItem, include_data: bool) -> List[Dict[str, Any]]:
        """Lit les images stockées dans une archive Office (DOCX, XLSX, PPTX)."""
        source = self._source_path(document)
        if not source:
            self._logger.warning(
                f"Fichier source indisponible pour {document.document_id}, "
                "extraction d'images impossible"
            )
            return []

        prefix = self._OOXML_MEDIA_PREFIXES[document.document_type]
        images: List[Dict[str, Any]] = []

        try:
            with zipfile.ZipFile(source) as archive:
                for entry in archive.infolist():
                    if not entry.filename.startswith(prefix) or entry.is_dir():
                        continue

                    image: Dict[str, Any] = {
                        "name": os.path.basename(entry.filename),
                        "format": os.path.splitext(entry.filename)[1].lstrip('.').lower(),
                        "size": entry.file_size,
                        "path_in_archive": entry.filename,
                        "origin": "embedded",
                    }
                    if include_data:
                        image["data"] = archive.read(entry.filename)

                    images.append(image)
        except (zipfile.BadZipFile, OSError) as error:
            self._logger.error(f"Lecture des images impossible dans {source}: {error}")
            return []

        return images

    def _extract_from_pdf(self, document: DocumentItem) -> List[Dict[str, Any]]:
        """Énumère les images d'un PDF à l'aide de PyPDF2."""
        source = self._source_path(document)
        if not source:
            return []

        try:
            try:
                import pypdf as PyPDF2  # successeur maintenu de PyPDF2
            except ImportError:
                import PyPDF2
        except ImportError:
            self._logger.warning(
                "PyPDF2 est absent : les images des PDF ne peuvent pas être extraites. "
                "Installez-le avec: pip install PyPDF2"
            )
            return []

        images: List[Dict[str, Any]] = []
        try:
            with open(source, 'rb') as pdf_file:
                reader = PyPDF2.PdfReader(pdf_file)
                for page_number, page in enumerate(reader.pages, start=1):
                    for image_file in page.images:
                        images.append({
                            "name": image_file.name,
                            "format": os.path.splitext(image_file.name)[1].lstrip('.').lower(),
                            "size": len(image_file.data),
                            "page": page_number,
                            "origin": "embedded",
                        })
        except Exception as error:
            # Un PDF corrompu ne doit pas interrompre le traitement du document
            self._logger.error(f"Extraction des images du PDF {source} échouée: {error}")
            return []

        return images

    def _raw_html(self, document: DocumentItem) -> str:
        """Relit le HTML d'origine du document, ou retourne son texte à défaut."""
        source = self._source_path(document)
        if not source:
            return document.content

        try:
            with open(source, 'r', encoding='utf-8', errors='replace') as html_file:
                return html_file.read()
        except OSError as error:
            self._logger.error(f"Relecture du fichier HTML {source} impossible: {error}")
            return document.content

    def _extract_references(
        self, content: str, pattern: re.Pattern, group: int
    ) -> List[Dict[str, Any]]:
        """Relève les images référencées par URL dans un contenu textuel."""
        images: List[Dict[str, Any]] = []

        for match in pattern.finditer(content):
            reference = match.group(group)
            images.append({
                "name": os.path.basename(reference.split('?')[0]) or reference,
                "format": os.path.splitext(reference.split('?')[0])[1].lstrip('.').lower(),
                "reference": reference,
                "origin": "reference",
            })

        return images
