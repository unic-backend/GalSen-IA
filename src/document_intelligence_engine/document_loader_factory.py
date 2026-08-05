"""
Usine de chargeurs de documents pour le moteur d'intelligence documentaire GalSen IA.
"""

import abc
import logging
import mimetypes
import os
from typing import List, Optional

from .interfaces import DocumentLoader
from .types import DocumentItem


class BaseDocumentLoader(DocumentLoader, metaclass=abc.ABCMeta):
    """
    Classe de base pour tous les chargeurs de documents.

    Elle hérite du contrat `DocumentLoader` et ajoute la convention commune à
    tous les chargeurs concrets : la liste des extensions prises en charge.
    """

    # Extensions de fichiers prises en charge par le chargeur (à surcharger)
    supported_extensions: List[str] = []

    @abc.abstractmethod
    def load(self, source: str, **kwargs) -> DocumentItem:
        """Charge un document à partir d'une source et retourne un DocumentItem."""

    @abc.abstractmethod
    def supports_type(self, document_type: str) -> bool:
        """Vérifie si le chargeur supporte un type de document donné."""

    def supports_extension(self, extension: str) -> bool:
        """Vérifie si le chargeur supporte une extension de fichier donnée."""
        return extension.lower() in self.supported_extensions


class DocumentLoaderFactory:
    """Usine pour créer le chargeur approprié selon le type de document ou l'extension de fichier."""

    # Extensions traitées comme du texte brut quand aucun chargeur spécialisé ne répond
    _TEXT_FALLBACK_EXTENSIONS = frozenset({'.txt', '.md', '.csv', '.html', '.htm', '.json'})

    def __init__(self, register_defaults: bool = True):
        """
        Initialise l'usine.

        Args:
            register_defaults: Enregistre les chargeurs livrés avec le moteur.
                Passer False permet de construire une usine vide pour les tests
                ou pour un ensemble de chargeurs entièrement personnalisé.
        """
        self._loaders: List[DocumentLoader] = []
        self._logger = logging.getLogger(__name__)
        if register_defaults:
            self._register_default_loaders()

    def _register_default_loaders(self) -> None:
        """
        Enregistre les chargeurs par défaut.

        Les imports sont faits ici, et non en tête de module, car chaque chargeur
        importe `BaseDocumentLoader` depuis ce module : un import au niveau du
        module créerait un cycle.
        """
        from .txt_loader import TXTLoader
        from .markdown_loader import MarkdownLoader
        from .csv_loader import CSVLoader
        from .html_loader import HTMLLoader
        from .json_loader import JSONLoader
        from .pdf_loader import PDFLoader
        from .docx_loader import DOCXLoader
        from .xlsx_loader import XLSXLoader
        from .pptx_loader import PPTXLoader
        from .ocr_loader import OCRLoader

        for loader_class in (
            TXTLoader, MarkdownLoader, CSVLoader, HTMLLoader, JSONLoader,
            PDFLoader, DOCXLoader, XLSXLoader, PPTXLoader, OCRLoader,
        ):
            self.register_loader(loader_class())

    def register_loader(self, loader: DocumentLoader) -> None:
        """Enregistre un chargeur dans l'usine."""
        self._loaders.append(loader)
        self._logger.debug(f"Chargeur enregistré: {loader.__class__.__name__}")

    def get_loader_for_file(self, file_path: str) -> Optional[DocumentLoader]:
        """Retourne le chargeur approprié pour un fichier donné."""
        if not os.path.isfile(file_path):
            self._logger.warning(f"Fichier non trouvé: {file_path}")
            return None

        mime_type, _ = mimetypes.guess_type(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()

        # Un chargeur est retenu s'il reconnaît le type MIME ou l'extension du fichier
        for loader in self._loaders:
            if mime_type and loader.supports_type(mime_type):
                return loader
            if isinstance(loader, BaseDocumentLoader) and loader.supports_extension(file_ext):
                return loader

        # Aucun chargeur spécialisé : on retombe sur le texte brut pour les formats textuels
        if file_ext in self._TEXT_FALLBACK_EXTENSIONS:
            from .txt_loader import TXTLoader
            return TXTLoader()

        return None

    def get_loader_for_type(self, document_type: str) -> Optional[DocumentLoader]:
        """Retourne le chargeur approprié pour un type de document donné."""
        for loader in self._loaders:
            if loader.supports_type(document_type):
                return loader
        return None

    def load_document(self, source: str, **kwargs) -> DocumentItem:
        """Charge un document en utilisant le chargeur approprié."""
        if not os.path.isfile(source):
            # Les sources distantes (URL, base de données) relèveront de chargeurs dédiés
            raise NotImplementedError(f"Chargement depuis {source} non encore implémenté")

        loader = self.get_loader_for_file(source)
        if loader is None:
            raise ValueError(f"Aucun chargeur trouvé pour le fichier: {source}")

        return loader.load(source, **kwargs)


# Instance partagée, pratique pour les appelants qui n'ont pas besoin de configuration
_factory = DocumentLoaderFactory()


def get_factory() -> DocumentLoaderFactory:
    """Retourne l'instance partagée de l'usine de chargeurs."""
    return _factory
