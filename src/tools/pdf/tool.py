"""
Outil d'extraction de texte PDF pour GalSen IA.

Fournit une interface pour extraire du texte à partir de fichiers PDF en utilisant
la bibliothèque PyPDF2.

Opérations disponibles : `extract_text` (extraire le texte d'un PDF).

Exemple:
    tool.execute("extract_text", "path/to/document.pdf")
    tool.execute("extract_text", "path/to/document.pdf", pages=[0, 1])  # première et deuxième pages
"""

import logging
from typing import Any, Dict, List, Union

from src.tool.base import BaseTool

logger = logging.getLogger(__name__)

# These will be set to the actual class if dependency is available
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:  # pragma: no cover
    PDF_AVAILABLE = False
    PyPDF2 = None  # type: ignore


class PDFTool(BaseTool):
    """
    Outil d'accès aux fonctionnalités PDF pour GalSen IA.

    Opérations disponibles : `extract_text` (extraire le texte d'un PDF).

    Exemple:
        tool.execute("extract_text", "path/to/document.pdf")
        tool.execute("extract_text", "path/to/document.pdf", pages=[0, 1])
    """

    def __init__(self, config: dict = None):
        """
        Initialise l'outil PDF.

        Args:
            config: Configuration avec les clés optionnelles :
                    Aucune configuration spécifique pour l'instant.
        """
        super().__init__(config)
        logger.debug("PDFTool initialisé.")

    def _check_availability(self):
        """Vérifie que la dépendance PyPDF2 est disponible."""
        if not PDF_AVAILABLE:
            raise ImportError(
                "La bibliothèque 'PyPDF2' est nécessaire pour l'outil PDF. "
                "Veuillez l'installer avec : pip install PyPDF2"
            )

    def _op_extract_text(
        self, file_path: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Extrait le texte d'un fichier PDF donné.

        Args:
            file_path: Chemin vers le fichier PDF.
            **kwargs: Options supplémentaires :
                - `pages`: liste d'indices de pages à extraire (0-based). Si None, toutes les pages sont extraites.

        Returns:
            Dictionnaire contenant :
                - "text": str, texte concatené des pages sélectionnées
                - "num_pages": int, nombre total de pages dans le PDF
                - "pages_extracted": list, indices des pages qui ont été extraites

        Raises:
            FileNotFoundError: Si le fichier PDF n'existe pas.
            ValueError: Si l'argument file_path n'est pas une chaîne de caractères valide.
            RuntimeError: Si l'extraction échoue.
        """
        self._check_availability()

        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("Le chemin du fichier doit être une chaîne non vide")

        try:
            with open(file_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                num_pages = len(pdf_reader.pages)

                pages_to_extract = kwargs.get("pages")
                if pages_to_extract is None:
                    pages_to_extract = list(range(num_pages))
                else:
                    # Ensure pages are integers and within range
                    pages_to_extract = [p for p in pages_to_extract if isinstance(p, int) and 0 <= p < num_pages]
                    if not pages_to_extract:
                        # If no valid pages, we could raise or return empty; we'll return empty.
                        pass

                text_parts = []
                for page_num in pages_to_extract:
                    page = pdf_reader.pages[page_num]
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                    except Exception as e:  # pragma: no cover
                        logger.warning(f"Impossible d'extraire le texte de la page {page_num}: {e}")

                extracted_text = "\n\n".join(text_parts)

                result = {
                    "text": extracted_text,
                    "num_pages": num_pages,
                    "pages_extracted": pages_to_extract,
                }
                logger.debug(f"Extraction PDF terminée: {file_path}, pages {pages_to_extract} sur {num_pages}")
                return result
        except FileNotFoundError:
            raise FileNotFoundError(f"Fichier PDF introuvable: {file_path}")
        except Exception as e:  # pragma: no cover
            logger.error(f"Erreur lors de l'extraction du PDF {file_path}: {e}")
            raise RuntimeError(f"Échec de l'extraction PDF : {e}")

    def available_operations(self) -> list[str]:
        """Retourne la liste des opérations prises en charge."""
        return ["extract_text"]

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur l'outil PDF.

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