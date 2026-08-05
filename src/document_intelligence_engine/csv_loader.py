"""
Chargeur de fichiers CSV pour le moteur d'intelligence documentaire GalSen IA.
"""

import csv
import os
from .document_loader_factory import BaseDocumentLoader
from .types import DocumentItem, DocumentType
import logging

logger = logging.getLogger(__name__)


class CSVLoader(BaseDocumentLoader):
    """Chargeur pour les fichiers CSV (.csv)."""

    # Extensions supportées
    supported_extensions = ['.csv']

    def load(self, source: str, **kwargs) -> DocumentItem:
        """
        Charge un fichier CSV et retourne un DocumentItem.

        Args:
            source: Chemin vers le fichier CSV
            **kwargs: Options supplémentaires (delimiter, encoding, etc.)

        Returns:
            DocumentItem représentant le fichier chargé
        """
        if not os.path.isfile(source):
            raise FileNotFoundError(f"Fichier non trouvé: {source}")

        # Déterminer l'encodage (par défaut utf-8)
        encoding = kwargs.get('encoding', 'utf-8')
        delimiter = kwargs.get('delimiter', ',')

        try:
            with open(source, 'r', encoding=encoding, newline='') as f:
                # Lire l'en-tête
                sniffer = csv.Sniffer()
                sample = f.read(1024)
                f.seek(0)
                has_header = sniffer.has_header(sample)
                reader = csv.reader(f, delimiter=delimiter)

                if has_header:
                    headers = next(reader)
                else:
                    # Générer des en-têtes génériques
                    first_row = next(reader)
                    headers = [f"col_{i}" for i in range(len(first_row))]
                    # Remettre le pointeur au début car nous avons consommé la première ligne
                    f.seek(0)
                    reader = csv.reader(f, delimiter=delimiter)

                # Lire toutes les lignes restantes
                rows = list(reader)

                # Sans en-tête, la première ligne consommée plus haut est une
                # ligne de données: elle doit être réintégrée
                if not has_header:
                    rows = [first_row] + rows

        except UnicodeDecodeError:
            with open(source, 'r', encoding='latin-1', newline='') as f:
                reader = csv.reader(f, delimiter=delimiter)
                rows = list(reader)
                if not rows:
                    headers = []
                else:
                    # Supposer que la première ligne est l'en-tête
                    headers = rows[0]
                    rows = rows[1:]

        # Convertir les données en une représentation lisible
        # Nous allons créer un tableau simple en texte pour le contenu
        lines = []
        if headers:
            lines.append(",".join(headers))
        for row in rows:
            lines.append(",".join(str(cell) for cell in row))
        content = "\n".join(lines)

        # Extraire les métadonnées de base
        stat = os.stat(source)
        metadata = {
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "source": os.path.abspath(source),
            "filename": os.path.basename(source),
            "extension": os.path.splitext(source)[1],
            "rows": len(rows),
            "columns": len(headers) if headers else 0,
            "delimiter": delimiter,
            "has_header": True if headers else False  # Simplifié
        }

        # Créer l'élément de document
        document = DocumentItem(
            document_id="",
            document_type=DocumentType.CSV,
            title=os.path.splitext(os.path.basename(source))[0],
            content=content,
            metadata=metadata
        )

        return document

    def supports_type(self, document_type: str) -> bool:
        """Vérifie si le chargeur supporte le type de document donné."""
        return document_type == DocumentType.CSV.value