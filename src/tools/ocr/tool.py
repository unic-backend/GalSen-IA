"""
Outil de reconnaissance optique de caractères (OCR) pour GalSen IA.

Fournit une interface pour extraire du texte à partir d'images en utilisant
le moteur OCR Tesseract via pytesseract.

Opérations disponibles : `extract_text` (extraire le texte d'une image).

Exemple:
    tool.execute("extract_text", "path/to/image.png")
    tool.execute("extract_text", "path/to/image.jpg", lang="fra")
"""

import logging
from typing import Any, Dict, Union

from src.tool.base import BaseTool

logger = logging.getLogger(__name__)

# These will be set to the actual classes if dependencies are available
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:  # pragma: no cover
    OCR_AVAILABLE = False
    Image = None  # type: ignore
    pytesseract = None  # type: ignore


class OCRTool(BaseTool):
    """
    Outil d'accès aux fonctionnalités OCR pour GalSen IA.

    Opérations disponibles : `extract_text` (extraire le texte d'une image).

    Exemple:
        tool.execute("extract_text", "path/to/image.png")
        tool.execute("extract_text", "path/to/image.jpg", lang="fra")
    """

    def __init__(self, config: dict = None):
        """
        Initialise l'outil OCR.

        Args:
            config: Configuration avec les clés optionnelles :
                - `lang`: langue par défaut pour l'OCR (ex: 'eng', 'fra') (défaut: 'eng')
                - `tesseract_cmd`: chemin complet vers l'exécutable tesseract
                                 (si non défini, utilise la variable d'environnement PATH)
        """
        super().__init__(config)
        self.default_lang = self.config.get("lang", "eng")
        self.tesseract_cmd = self.config.get("tesseract_cmd", None)
        if self.tesseract_cmd and OCR_AVAILABLE:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        logger.debug(
            f"OCRTool initialisé avec langue par défaut {self.default_lang}"
        )

    def _check_availability(self):
        """Vérifie que les dépendances OCR sont disponibles."""
        if not OCR_AVAILABLE:
            raise ImportError(
                "Les bibliothèques 'Pillow' et 'pytesseract' sont nécessaires pour l'outil OCR. "
                "Veuillez les installer avec : pip install pillow pytesseract"
            )

    def _op_extract_text(
        self, image_path: Union[str, bytes], **kwargs
    ) -> Dict[str, Any]:
        """
        Extrait le texte d'une image donnée.

        Args:
            image_path: Chemin vers le fichier image ou données binaires de l'image.
            **kwargs: Options supplémentaires :
                - `lang`: langue à utiliser pour l'OCR (surcharge la configuration par défaut)
                - `config`: chaîne de configuration supplémentaire passée à tesseract

        Returns:
            Dictionnaire contenant le texte extrait et des métadonnées :
            {
                "text": str,          # Texte extrait
                "lang": str,          # Langue utilisée
                "confidence": float,  # Confiance moyenne (0-100) si disponible, sinon None
                "boxes": list,        # Boîtes de délimitation par mot (optionnel)
            }

        Raises:
            FileNotFoundError: Si le fichier image n'existe pas.
            ValueError: Si l'argument image_path est invalide.
            RuntimeError: Si l'OCR échoue.
        """
        self._check_availability()

        # Charger l'image
        if isinstance(image_path, str):
            try:
                img = Image.open(image_path)
            except FileNotFoundError:
                raise FileNotFoundError(f"Fichier image introuvable: {image_path}")
            except Exception as e:
                raise ValueError(f"Impossible d'ouvrir l'image {image_path}: {e}")
        elif isinstance(image_path, bytes):
            # Charger à partir des bytes
            try:
                import io
                img = Image.open(io.BytesIO(image_path))
            except Exception as e:
                raise ValueError(f"Impossible de charger l'image depuis des bytes: {e}")
        else:
            raise TypeError(
                "image_path doit être une chaîne de caractères (chemin) ou des bytes"
            )

        # Options OCR
        lang = kwargs.get("lang", self.default_lang)
        config = kwargs.get("config", "")

        try:
            # Extraire le texte
            text = pytesseract.image_to_string(img, lang=lang, config=config)

            # Optionally get detailed data including bounding boxes and confidence
            data = pytesseract.image_to_data(
                img, lang=lang, config=config, output_type=pytesseract.Output.DICT
            )
            # Calculate average confidence (excluding -1 entries)
            confs = [int(conf) for conf in data["conf"] if int(conf) != -1]
            avg_confidence = sum(confs) / len(confs) if confs else None

            # Optionally return boxes (we could include them if needed)
            boxes = []
            if "left" in data:
                for i in range(len(data["text"])):
                    if int(data["conf"][i]) != -1:  # only confident entries
                        boxes.append(
                            {
                                "text": data["text"][i],
                                "left": data["left"][i],
                                "top": data["top"][i],
                                "width": data["width"][i],
                                "height": data["height"][i],
                                "conf": int(data["conf"][i]),
                            }
                        )

            result = {
                "text": text,
                "lang": lang,
                "confidence": avg_confidence,
                "boxes": boxes,
            }
            logger.debug(f"OCR terminé sur {image_path if isinstance(image_path, str) else 'bytes'} (lang={lang})")
            return result
        except Exception as e:  # pragma: no cover
            logger.error(f"Erreur lors de l'OCR sur {image_path}: {e}")
            raise RuntimeError(f"Échec de l'OCR : {e}")

    def available_operations(self) -> list[str]:
        """Retourne la liste des opérations prises en charge."""
        return ["extract_text"]

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur l'outil OCR.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération.

        Raises:
            ValueError: Opération inconnue.
        """
        if not args:
            raise ValueError("Une opération est requise (extract_text)")

        operation = str(args[0]).lower()
        operation_args = args[1:]

        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. "
                f"Opérations disponibles: {', '.join(self.available_operations())}"
            )

        return handler(*operation_args, **kwargs)