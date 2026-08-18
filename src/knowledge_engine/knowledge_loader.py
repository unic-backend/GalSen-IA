"""
Chargeur de connaissances pour divers formats de fichiers et sources.
"""

from typing import List
from .types import KnowledgeItem, KnowledgeSource, ContentType, Language
from .interfaces import KnowledgeLoader
import os
import json
import csv
import html
from datetime import datetime
import hashlib


class BaseKnowledgeLoader(KnowledgeLoader):
    """Chargeur de base avec fonctionnalités communes."""

    def _create_knowledge_item(self, content: str, source: KnowledgeSource,
                               content_type: ContentType = ContentType.TEXT,
                               language: Language = Language.FR,
                               knowledge_type: str = "FACT") -> KnowledgeItem:
        """Crée un objet KnowledgeItem à partir du contenu."""
        # Déterminer le type de connaissance basé sur le contenu (simplifié)
        from .types import KnowledgeType
        try:
            kt = KnowledgeType[knowledge_type.upper()]
        except KeyError:
            kt = KnowledgeType.FACT

        item = KnowledgeItem(
            content=content,
            knowledge_type=kt,
            content_type=content_type,
            language=language,
            source=source
        )
        return item

    def _compute_file_hash(self, filepath: str) -> str:
        """Calcule le hash SHA256 d'un fichier."""
        hash_sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()


class TextFileLoader(BaseKnowledgeLoader):
    """Chargeur pour les fichiers texte simples (.txt, .md, etc)."""

    def load_from_source(self, source: KnowledgeSource) -> List[KnowledgeItem]:
        """Charge un fichier texte."""
        if source.type != "file":
            raise ValueError(f"Source type '{source.type}' not supported by TextFileLoader")
        if not os.path.isfile(source.location):
            raise FileNotFoundError(f"File not found: {source.location}")

        # Déterminer le type de contenu basé sur l'extension
        ext = os.path.splitext(source.location)[1].lower()
        if ext == ".md":
            content_type = ContentType.MARKDOWN
        elif ext == ".html" or ext == ".htm":
            content_type = ContentType.HTML
        else:
            content_type = ContentType.TEXT

        # Détecter la langue (simple: anglais par défaut, sinon français si contient certains mots)
        language = Language.FR  # défaut pour GalSen IA

        with open(source.location, 'r', encoding='utf-8') as f:
            content = f.read()

        # Nettoyer le contenu HTML si nécessaire
        if content_type == ContentType.HTML:
            # Suppression très basique des balises HTML (pour un vrai projet, utiliser BeautifulSoup)
            import re
            content = re.sub('<[^<]+?>', '', content)
            content = html.unescape(content)

        item = self._create_knowledge_item(
            content=content,
            source=source,
            content_type=content_type,
            language=language
        )
        # Ajouter le hash du fichier comme métadonnée
        item.metadata["file_hash"] = self._compute_file_hash(source.location)
        item.metadata["file_size"] = os.path.getsize(source.location)
        return [item]

    def supports_type(self, content_type: str) -> bool:
        """Vérifie si ce chargeur supporte un type de contenu."""
        supported = [ContentType.TEXT.value, ContentType.MARKDOWN.value, ContentType.HTML.value]
        return content_type in supported


class JSONFileLoader(BaseKnowledgeLoader):
    """Chargeur pour les fichiers JSON."""

    def load_from_source(self, source: KnowledgeSource) -> List[KnowledgeItem]:
        """Charge un fichier JSON."""
        if source.type != "file":
            raise ValueError(f"Source type '{source.type}' not supported by JSONFileLoader")
        if not os.path.isfile(source.location):
            raise FileNotFoundError(f"File not found: {source.location}")

        with open(source.location, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Convertir le JSON en chaîne formatée pour le stockage
        content = json.dumps(data, indent=2, ensure_ascii=False)

        item = self._create_knowledge_item(
            content=content,
            source=source,
            content_type=ContentType.JSON
        )
        item.metadata["file_hash"] = self._compute_file_hash(source.location)
        return [item]

    def supports_type(self, content_type: str) -> bool:
        return content_type == ContentType.JSON.value


class CSVFileLoader(BaseKnowledgeLoader):
    """Chargeur pour les fichiers CSV."""

    def load_from_source(self, source: KnowledgeSource) -> List[KnowledgeItem]:
        """Charge un fichier CSV."""
        if source.type != "file":
            raise ValueError(f"Source type '{source.type}' not supported by CSVFileLoader")
        if not os.path.isfile(source.location):
            raise FileNotFoundError(f"File not found: {source.location}")

        rows = []
        with open(source.location, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        # Convertir en représentation lisible
        if not rows:
            content = "Empty CSV file"
        else:
            # Créer un tableau markdown simple
            headers = rows[0].keys()
            lines = []
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
            for row in rows:
                lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
            content = "\n".join(lines)

        item = self._create_knowledge_item(
            content=content,
            source=source,
            content_type=ContentType.CSV
        )
        item.metadata["file_hash"] = self._compute_file_hash(source.location)
        item.metadata["row_count"] = len(rows)
        return [item]

    def supports_type(self, content_type: str) -> bool:
        return content_type == ContentType.CSV.value


class WebPageLoader(BaseKnowledgeLoader):
    """Chargeur pour les pages web."""

    def load_from_source(self, source: KnowledgeSource) -> List[KnowledgeItem]:
        """Charge une page web."""
        if source.type not in ["url", "web"]:
            raise ValueError(f"Source type '{source.type}' not supported by WebPageLoader")
        try:
            import urllib.request
            from urllib.error import URLError
        except ImportError:
            raise ImportError("urllib module not available")

        try:
            with urllib.request.urlopen(source.location) as response:
                if hasattr(response, 'headers'):
                    charset = response.headers.get_content_charset()
                    if not charset:
                        charset = 'utf-8'
                else:
                    charset = 'utf-8'
                html_content = response.read().decode(charset)
        except URLError as e:
            raise ConnectionError(f"Failed to fetch URL {source.location}: {e}")

        # Extraire le texte de base (supprimer les balises HTML)
        import re
        text = re.sub('<[^<]+?>', '', html_content)
        text = html.unescape(text)

        item = self._create_knowledge_item(
            content=text,
            source=source,
            content_type=ContentType.HTML  # we stored processed text but origin HTML
        )
        item.metadata["url"] = source.location
        item.metadata["fetched_at"] = datetime.utcnow().isoformat()
        return [item]

    def supports_type(self, content_type: str) -> bool:
        # Le contenu HTML devient du texte après traitement, mais on accepte toute demande
        return True  # simplifié


class APIDatasourceLoader(BaseKnowledgeLoader):
    """Chargeur pour les API REST (simplifié)."""

    def load_from_source(self, source: KnowledgeSource) -> List[KnowledgeItem]:
        """Charge des données depuis une API REST."""
        if source.type != "api":
            raise ValueError(f"Source type '{source.type}' not supported by APIDatasourceLoader")
        try:
            import urllib.request
            import json
        except ImportError:
            raise ImportError("Required modules not available")

        # Supposons que l'URL est dans source.location et on attend du JSON
        try:
            with urllib.request.urlopen(source.location) as response:
                data = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            raise ConnectionError(f"Failed to fetch API {source.location}: {e}")

        # Convertir en texte lisible
        content = json.dumps(data, indent=2, ensure_ascii=False)

        item = self._create_knowledge_item(
            content=content,
            source=source,
            content_type=ContentType.JSON
        )
        item.metadata["api_url"] = source.location
        item.metadata["fetched_at"] = datetime.utcnow().isoformat()
        return [item]

    def supports_type(self, content_type: str) -> bool:
        return content_type == ContentType.JSON.value



class PDFLoader(BaseKnowledgeLoader):
    """Chargeur pour les fichiers PDF."""

    def load_from_source(self, source: KnowledgeSource) -> List[KnowledgeItem]:
        """Charge un fichier PDF."""
        if source.type != "file":
            raise ValueError(f"Source type '{source.type}' not supported by PDFLoader")
        if not os.path.isfile(source.location):
            raise FileNotFoundError(f"File not found: {source.location}")
        try:
            import PyPDF2
        except ImportError:
            raise ImportError("PyPDF2 is required for PDF loading. Install with: pip install PyPDF2")

        text_content = []
        with open(source.location, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text_content.append(page.extract_text())

        content = "\n\n".join(text_content)

        item = self._create_knowledge_item(
            content=content,
            source=source,
            content_type=ContentType.PDF
        )
        item.metadata["file_hash"] = self._compute_file_hash(source.location)
        item.metadata["page_count"] = len(reader.pages)
        return [item]

    def supports_type(self, content_type: str) -> bool:
        return content_type == ContentType.PDF.value


class DocxLoader(BaseKnowledgeLoader):
    """Chargeur pour les fichiers DOCX."""

    def load_from_source(self, source: KnowledgeSource) -> List[KnowledgeItem]:
        """Charge un fichier DOCX."""
        if source.type != "file":
            raise ValueError(f"Source type '{source.type}' not supported by DocxLoader")
        if not os.path.isfile(source.location):
            raise FileNotFoundError(f"File not found: {source.location}")
        try:
            import docx
        except ImportError:
            raise ImportError("python-docx is required for DOCX loading. Install with: pip install python-docx")

        doc = docx.Document(source.location)
        text_content = []
        for para in doc.paragraphs:
            text_content.append(para.text)

        content = "\n".join(text_content)

        item = self._create_knowledge_item(
            content=content,
            source=source,
            content_type=ContentType.DOCX
        )
        item.metadata["file_hash"] = self._compute_file_hash(source.location)
        return [item]

    def supports_type(self, content_type: str) -> bool:
        return content_type == ContentType.DOCX.value


class KnowledgeLoaderFactory:
    """Fabrique pour obtenir le chargeur approprié selon le type de source ou de contenu."""

    _loaders = [
        TextFileLoader(),
        JSONFileLoader(),
        CSVFileLoader(),
        WebPageLoader(),
        APIDatasourceLoader(),
        PDFLoader(),
        DocxLoader()
    ]

    @classmethod
    def get_loader_for_source(cls, source: KnowledgeSource) -> KnowledgeLoader:
        """Retourne un chargeur adapté à la source."""
        # Essayer de déterminer le type de contenu à partir de l'extension ou du type source
        if source.type == "file":
            ext = os.path.splitext(source.location)[1].lower()
            ext_to_type = {
                '.txt': ContentType.TEXT,
                '.md': ContentType.MARKDOWN,
                '.html': ContentType.HTML,
                '.htm': ContentType.HTML,
                '.json': ContentType.JSON,
                '.csv': ContentType.CSV,
                '.pdf': ContentType.PDF,
                '.docx': ContentType.DOCX
            }
            content_type = ext_to_type.get(ext, ContentType.TEXT)
        elif source.type in ["url", "web"]:
            content_type = ContentType.HTML  # sera traité comme HTML puis converti en texte
        elif source.type == "api":
            content_type = ContentType.JSON
        else:
            content_type = ContentType.TEXT  # défaut

        for loader in cls._loaders:
            if loader.supports_type(content_type.value):
                return loader
        # Si aucun chargeur spécifique, retourner le premier qui accepte le texte
        for loader in cls._loaders:
            if loader.supports_type(ContentType.TEXT.value):
                return loader
        raise ValueError(f"No loader found for content type {content_type}")

    @classmethod
    def load_from_source(cls, source: KnowledgeSource) -> List[KnowledgeItem]:
        """Charge des connaissances depuis une source en utilisant le chargeur approprié."""
        loader = cls.get_loader_for_source(source)
        return loader.load_from_source(source)