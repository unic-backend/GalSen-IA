"""
Chargeur de fichiers JSON pour le moteur d'intelligence documentaire GalSen IA.
"""

import json
import os
from .document_loader_factory import BaseDocumentLoader
from .types import DocumentItem, DocumentType
import logging

logger = logging.getLogger(__name__)


class JSONLoader(BaseDocumentLoader):
    """Chargeur pour les fichiers JSON (.json)."""

    # Extensions supportées
    supported_extensions = ['.json']

    def load(self, source: str, **kwargs) -> DocumentItem:
        """
        Charge un fichier JSON et retourne un DocumentItem.

        Args:
            source: Chemin vers le fichier JSON
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
                data = json.load(f)
        except UnicodeDecodeError:
            with open(source, 'r', encoding='latin-1') as f:
                data = json.load(f)

        # Convertir les données JSON en chaîne de caractères formatée
        # Nous utilisons une indentation raisonnable pour la lisibilité
        content = json.dumps(data, indent=2, ensure_ascii=False)

        # Le titre vient du nom du fichier, sauf si le JSON déclare explicitement un champ 'title'.
        # On n'utilise pas 'name' : dans la plupart des JSON métier c'est le nom d'une entité
        # (une personne, un produit), pas le titre du document.
        title = os.path.splitext(os.path.basename(source))[0]
        if isinstance(data, dict) and isinstance(data.get('title'), str):
            title = data['title']

        # Extraire les métadonnées de base
        stat = os.stat(source)
        metadata = {
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "source": os.path.abspath(source),
            "filename": os.path.basename(source),
            "extension": os.path.splitext(source)[1],
            "item_count": len(data) if isinstance(data, (list, dict)) else 1
        }

        # Créer l'élément de document
        document = DocumentItem(
            document_id="",
            document_type=DocumentType.TXT,  # Nous traitons le JSON comme du texte pour le contenu
            title=title,
            content=content,
            metadata=metadata
        )

        return document

    def supports_type(self, document_type: str) -> bool:
        """Vérifie si le chargeur supporte le type de document donné."""
        return document_type in ['application/json']