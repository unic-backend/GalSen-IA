"""
Chargeur de fichiers HTML pour le moteur d'intelligence documentaire GalSen IA.
"""

from html.parser import HTMLParser
import os
import re
from .document_loader_factory import BaseDocumentLoader
from .types import DocumentItem, DocumentType
import logging

logger = logging.getLogger(__name__)


class _HTMLTextExtractor(HTMLParser):
    """Classe interne pour extraire le texte brut du HTML."""

    # Balises dont le contenu n'est pas du texte lisible
    _IGNORED_TAGS = frozenset({"script", "style"})

    def __init__(self):
        # convert_charrefs=True décode automatiquement les entités HTML (&amp;, &eacute;...)
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        """Entre dans une balise: mémorise l'ouverture des balises à ignorer."""
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        """Sort d'une balise: referme le suivi des balises ignorées."""
        if tag in self._IGNORED_TAGS and self._ignored_depth > 0:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        """Accumule le texte, sauf s'il appartient à une balise ignorée."""
        if self._ignored_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        """Retourne le texte brut accumulé."""
        return ''.join(self._parts)


class HTMLLoader(BaseDocumentLoader):
    """Chargeur pour les fichiers HTML (.html, .htm)."""

    # Extensions supportées
    supported_extensions = ['.html', '.htm']

    def load(self, source: str, **kwargs) -> DocumentItem:
        """
        Charge un fichier HTML et retourne un DocumentItem.

        Args:
            source: Chemin vers le fichier HTML
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
                html_content = f.read()
        except UnicodeDecodeError:
            with open(source, 'r', encoding='latin-1') as f:
                html_content = f.read()

        # Extraire le texte brut du HTML
        parser = _HTMLTextExtractor()
        parser.feed(html_content)
        text_content = parser.get_text()

        # Essayer d'extraire le titre de la page
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        # À défaut de balise <title>, on retombe sur le nom du fichier sans extension
        title = title_match.group(1).strip() if title_match else os.path.splitext(os.path.basename(source))[0]
        # Nettoyer le titre des balises restantes et des espaces blancs
        title = re.sub(r'<[^>]+>', '', title)
        title = re.sub(r'\s+', ' ', title).strip()

        # Extraire les métadonnées de base
        stat = os.stat(source)
        metadata = {
            "size": stat.st_size,
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "source": os.path.abspath(source),
            "filename": os.path.basename(source),
            "extension": os.path.splitext(source)[1],
            "content_length": len(text_content)
        }

        # Créer l'élément de document
        document = DocumentItem(
            document_id="",
            document_type=DocumentType.HTML,
            title=title,
            content=text_content,
            metadata=metadata
        )

        return document

    def supports_type(self, document_type: str) -> bool:
        """Vérifie si le chargeur supporte le type de document donné."""
        return document_type in [DocumentType.HTML.value, 'text/html']