"""
Chargeur OCR pour le moteur d'intelligence documentaire GalSen IA.
"""

import os
from .document_loader_factory import BaseDocumentLoader
from .types import DocumentItem, DocumentType
import logging

logger = logging.getLogger(__name__)


class OCRLoader(BaseDocumentLoader):
    """Chargeur pour effectuer l'OCR sur des images."""

    # Extensions supportées (formats d'image courants)
    supported_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif']

    def load(self, source: str, **kwargs) -> DocumentItem:
        """
        Effectue l'OCR sur une image et retourne un DocumentItem.

        Args:
            source: Chemin vers le fichier image
            **kwargs: Options supplémentaires (lang, config, etc.)

        Returns:
            DocumentItem représentant le résultat de l'OCR
        """
        if not os.path.isfile(source):
            raise FileNotFoundError(f"Fichier non trouvé: {source}")

        try:
            from PIL import Image
            import pytesseract
        except ImportError:
            message = (
                "Pillow et pytesseract est requis pour charger l'OCR. "
                "Installez-le avec: pip install Pillow pytesseract"
            )
            logger.error(message)
            raise ImportError(message)

        # Ouvrir l'image
        image = Image.open(source)

        # Obtenir les paramètres OCR
        lang = kwargs.get('lang', 'eng')  # Langue par défaut: anglais
        config = kwargs.get('config', '')  # Configuration Tesseract additionnelle

        # Effectuer l'OCR
        try:
            text = pytesseract.image_to_string(image, lang=lang, config=config)
        except Exception as e:
            logger.error(f"Erreur lors de l'OCR sur {source}: {e}")
            raise

        # Extraire les métadonnées de l'image
        stat = os.stat(source)
        width, height = image.size
        mode = image.mode
        image_format = image.format

        metadata = {
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "source": os.path.abspath(source),
            "filename": os.path.basename(source),
            "extension": os.path.splitext(source)[1],
            "image_width": width,
            "image_height": height,
            "image_mode": mode,
            "image_format": image_format,
            "ocr_language": lang,
            "ocr_config": config
        }

        # Utiliser le nom du fichier comme titre
        title = os.path.splitext(os.path.basename(source))[0]

        # Créer l'élément de document
        document = DocumentItem(
            document_id="",
            document_type=DocumentType.TXT,  # Le résultat de l'OCR est du texte
            title=title,
            content=text,
            metadata=metadata
        )

        return document

    def supports_type(self, document_type: str) -> bool:
        """Vérifie si le chargeur supporte le type de document donné."""
        # L'OCR prend des images et produit du texte, donc nous soutenons les types d'image
        image_types = ['image/png', 'image/jpeg', 'image/tiff', 'image/bmp', 'image/gif']
        return document_type in image_types