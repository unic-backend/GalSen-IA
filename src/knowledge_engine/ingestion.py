"""
Ingestion de documents vers la base de connaissances (VOLET 28, ch. 01).

Deux moteurs existaient sans se rencontrer. `TextFileLoader` charge **un fichier
entier en un seul élément de connaissance** : un document de cinquante pages
devient un bloc que la recherche note une fois et qu'une citation désigne en
entier — ce qui revient à ne rien citer. Pendant ce temps,
`src/document_intelligence_engine/simple_chunker.py` découpe correctement, avec
recouvrement, sans être jamais appelé depuis les connaissances.

Ce module les branche l'un sur l'autre. Il n'ajoute pas de troisième chargeur et
pas de troisième découpeur : c'est exactement le défaut que ce dépôt a trouvé
huit fois en vingt-cinq VOLETs.

Trois règles portent la conception :

1. **Un bloc porte sa provenance.** Fichier, position dans le document, hachage
   du fichier. Sans cela, une réponse ne peut pas citer sa source, et une
   connaissance sans source est une affirmation sans auteur.
2. **Rien n'est ingéré sans source déclarée.** Le titre et la catégorie de source
   sont exigés, parce que ce sont eux qui permettront plus tard de dire *d'où*
   vient une réponse.
3. **Une ingestion rejouée ne duplique pas.** L'identifiant d'un bloc est déduit
   du hachage du fichier et de sa position : réingérer le même fichier met à
   jour, il n'empile pas.
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.document_intelligence_engine.simple_chunker import SimpleChunker
from src.document_intelligence_engine.types import DocumentItem, DocumentType

from .scope import KnowledgeScope, KnowledgeSubject, parse_subject
from .types import (
    ContentType,
    KnowledgeDomain,
    KnowledgeItem,
    KnowledgeSource,
    KnowledgeStatus,
    Language,
    SourceCategory,
)

logger = logging.getLogger(__name__)

# Taille de bloc. Assez grand pour qu'un paragraphe garde son sens, assez petit
# pour qu'une citation désigne un passage et non un chapitre.
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 200

# Extensions lues directement en texte. Les autres formats passent par les
# chargeurs du moteur documentaire, qui savent les ouvrir.
EXTENSIONS_TEXTE = {".txt", ".md", ".markdown", ".rst"}

# Entrées non textuelles (VOLET 32). Une photo de parcelle et un message vocal
# sont deux des façons les plus naturelles de s'adresser à cette plateforme dans
# son pays ; elles n'entraient nulle part.
EXTENSIONS_IMAGE = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
EXTENSIONS_AUDIO = {".wav", ".mp3", ".m4a", ".ogg", ".opus", ".flac", ".webm"}


@dataclass
class IngestionReport:
    """Ce qu'une ingestion a produit, et ce qu'elle a refusé."""

    source_path: str
    chunks: int = 0
    knowledge_ids: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    # Ce que l'ingestion a appris en chemin : modèle de transcription utilisé,
    # OCR absent, moteur de vision indisponible. Ni erreurs ni rejets — des
    # faits que l'opérateur doit connaître pour interpréter ce qui est entré.
    notes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le rapport."""
        return {
            "source": self.source_path,
            "chunks": self.chunks,
            "knowledge_ids": self.knowledge_ids,
            "skipped": self.skipped,
            "errors": self.errors,
            "notes": self.notes,
            "ingested": len(self.knowledge_ids),
        }


class DocumentIngestor:
    """
    Découpe un document et le verse dans la base de connaissances.

    Exemple:
        ingestor = DocumentIngestor(knowledge_manager)
        rapport = ingestor.ingest_file(
            "docs/architecture/overview.md",
            title="Architecture GalSen IA",
            source_category=SourceCategory.P1_OFFICIAL,
        )
    """

    def __init__(
        self,
        knowledge_manager,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ):
        """
        Args:
            knowledge_manager: Moteur de connaissances recevant les blocs.
            chunk_size: Taille maximale d'un bloc, en caractères.
            overlap: Recouvrement entre blocs, pour ne pas couper une idée en deux.
        """
        self._knowledge = knowledge_manager
        self._chunker = SimpleChunker(chunk_size=chunk_size, overlap=overlap)

    def ingest_file(
        self,
        chemin: str,
        title: str,
        source_category: SourceCategory,
        domain: KnowledgeDomain = KnowledgeDomain.UNSPECIFIED,
        scope: Any = "global",
        subject: Any = KnowledgeSubject.UNSPECIFIED,
        author: Optional[str] = None,
        url: Optional[str] = None,
        tags: Optional[List[str]] = None,
        language: Language = Language.FR,
        status: KnowledgeStatus = KnowledgeStatus.DRAFT,
    ) -> IngestionReport:
        """
        Ingère un fichier, un bloc de connaissance par passage.

        Args:
            chemin: Fichier à ingérer.
            title: Titre du document — exigé : il apparaîtra dans les citations.
            source_category: Fiabilité de la source (P1 à P4) — exigée pour la
                même raison ; une connaissance sans provenance déclarée ne peut
                pas être pondérée par `retrieve_reliable`.
            domain: Domaine de connaissance de la plateforme.
            scope: D'où cette connaissance vaut — `global` ou `country:sn`
                (VOLET 35). **Le défaut est mondial** : un document sénégalais
                non déclaré comme tel n'est pas rangé au Sénégal par charité.
            subject: De quoi elle parle — `agriculture`, `law`, `health`…
                Une portée ou un sujet malformé **refuse l'ingestion** plutôt que
                de retomber sur une valeur par défaut, qui rendrait le document
                introuvable par l'axe sur lequel on le cherchera.
            author: Auteur ou institution.
            url: Adresse de la source, si elle en a une.
            tags: Étiquettes appliquées à chaque bloc.
            language: Langue du document.
            status: Statut initial. **`DRAFT` par défaut, à dessein** : un
                document ingéré n'est pas une connaissance approuvée, et le faire
                entrer directement en `APPROVED` viderait de son sens le cycle
                de vie du VOLET 05.

        Returns:
            Le rapport d'ingestion.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            ValueError: Si le titre est vide.
            ScopeRefused: Si la portée ou le sujet sont malformés.
        """
        # Les deux axes sont résolus **avant** toute lecture de fichier : une
        # portée fautive doit refuser l'ingestion, pas la laisser écrire cent
        # blocs qu'il faudrait ensuite retrouver pour les corriger.
        portee = str(KnowledgeScope.parse(scope))
        sujet = parse_subject(subject)

        if not title or not title.strip():
            raise ValueError(
                "Un titre est exigé : il apparaîtra dans les citations, et une "
                "connaissance sans provenance lisible est une affirmation sans auteur."
            )
        if not os.path.isfile(chemin):
            raise FileNotFoundError(f"Fichier introuvable : {chemin}")

        rapport = IngestionReport(source_path=chemin)
        texte = self._lire(chemin, rapport)
        if texte is None:
            return rapport
        if not texte.strip():
            rapport.skipped.append("fichier vide")
            return rapport

        empreinte = self._empreinte(chemin)
        blocs = self._decouper(texte, chemin)
        rapport.chunks = len(blocs)

        for position, bloc in enumerate(blocs):
            if not bloc.strip():
                continue
            item = self._construire(
                bloc=bloc, position=position, total=len(blocs), chemin=chemin,
                empreinte=empreinte, title=title, source_category=source_category,
                domain=domain, scope=portee, subject=sujet,
                author=author, url=url, tags=tags or [],
                language=language, status=status,
            )
            try:
                rapport.knowledge_ids.append(self._knowledge.add_knowledge(item))
            except Exception as erreur:
                # Un bloc refusé ne doit pas emporter le document entier ; il
                # doit en revanche apparaître, sinon l'ingestion mentirait par
                # omission sur ce qu'elle a réellement versé.
                rapport.errors.append(f"bloc {position} : {erreur}")

        logger.info(
            "Ingestion de %s : %d bloc(s), %d versé(s), %d refusé(s).",
            chemin, rapport.chunks, len(rapport.knowledge_ids), len(rapport.errors),
        )
        return rapport

    def ingest_directory(
        self,
        repertoire: str,
        source_category: SourceCategory,
        motif: str = "*.md",
        **communs,
    ) -> List[IngestionReport]:
        """
        Ingère tous les fichiers d'un répertoire correspondant à un motif.

        Le titre de chaque document est son nom de fichier quand aucun n'est
        fourni : c'est faible, mais c'est vrai, et cela vaut mieux qu'un titre
        inventé.

        Args:
            repertoire: Répertoire à parcourir, récursivement.
            source_category: Fiabilité de la source.
            motif: Motif de fichiers, au sens de `pathlib.Path.rglob`.
            **communs: Arguments passés à `ingest_file`.

        Returns:
            Un rapport par fichier.
        """
        from pathlib import Path

        rapports = []
        for fichier in sorted(Path(repertoire).rglob(motif)):
            rapports.append(
                self.ingest_file(
                    str(fichier),
                    title=communs.pop("title", None) or fichier.stem.replace("-", " "),
                    source_category=source_category,
                    **communs,
                )
            )
        return rapports

    # ------------------------------------------------------------------
    # Interne
    # ------------------------------------------------------------------

    def _lire(self, chemin: str, rapport: IngestionReport) -> Optional[str]:
        """Lit un fichier ; passe par le moteur documentaire pour les formats riches."""
        extension = os.path.splitext(chemin)[1].lower()

        if extension in EXTENSIONS_AUDIO:
            return self._transcrire(chemin, rapport)
        if extension in EXTENSIONS_IMAGE:
            return self._decrire_image(chemin, rapport)

        if extension in EXTENSIONS_TEXTE:
            try:
                with open(chemin, "r", encoding="utf-8") as fichier:
                    return fichier.read()
            except (OSError, UnicodeDecodeError) as erreur:
                rapport.errors.append(f"lecture impossible : {erreur}")
                return None

        try:
            from src.document_intelligence_engine.document_loader_factory import (
                DocumentLoaderFactory,
            )

            document = DocumentLoaderFactory().load(chemin)
            return getattr(document, "content", None) or ""
        except Exception as erreur:
            # Les formats riches dépendent de bibliothèques optionnelles
            # (PyPDF2, python-docx…). Leur absence est une information, pas une
            # panne : le fichier est écarté en le disant.
            rapport.errors.append(f"format non pris en charge ici : {erreur}")
            return None

    def _transcrire(self, chemin: str, rapport: IngestionReport) -> Optional[str]:
        """
        Transcrit un fichier audio, ou refuse en le disant (VOLET 32).

        Sans transcripteur, le fichier est **écarté**. Le traiter comme un
        document vide serait le pire des deux mondes : la base gagnerait une
        entrée sans contenu, et l'opérateur croirait le message enregistré.
        """
        from src.multimodal.registry import active_transcriber, transcription_status

        transcripteur = active_transcriber()
        if transcripteur is None:
            etat = transcription_status()
            rapport.skipped.append(
                f"audio non transcrit : {etat.get('detail', 'aucun transcripteur disponible')}"
            )
            return None

        try:
            resultat = transcripteur.transcribe(chemin)
        except Exception as erreur:
            rapport.errors.append(f"transcription impossible : {erreur}")
            return None

        if not resultat.text.strip():
            # Un audio inaudible n'est pas un document vide : le dire évite
            # d'inscrire un silence comme s'il était une connaissance.
            rapport.skipped.append("transcription vide : rien d'audible dans le fichier")
            return None

        rapport.notes.append({
            "kind": "transcription",
            "model": resultat.model_name,
            "language": resultat.language,
            "confidence": resultat.confidence,
        })
        return resultat.text

    def _decrire_image(self, chemin: str, rapport: IngestionReport) -> Optional[str]:
        """
        Décrit une image par le moteur de vision, et lit son texte si l'OCR existe.

        Le moteur de vision (OpenCV, Pillow) tourne réellement : dimensions,
        qualité, couleurs dominantes, classification. L'OCR dépend de
        `pytesseract`, souvent absent — son absence retire le texte, pas
        l'analyse.

        Ce qui est versé est une **description mesurée**, jamais une description
        rédigée : « image 1920×1080, nette, dominante verte » est vrai et
        vérifiable ; « une parcelle de mil en bonne santé » serait inventé.
        """
        analyse = self._analyser_image(chemin, rapport)
        texte_ocr = self._lire_texte_image(chemin, rapport)

        morceaux = []
        if analyse:
            morceaux.append(analyse)
        if texte_ocr:
            morceaux.append(f"Texte lu dans l'image :\n{texte_ocr}")

        if not morceaux:
            rapport.skipped.append(
                "image non exploitable : ni analyse ni texte n'ont pu être produits"
            )
            return None
        return "\n\n".join(morceaux)

    def _analyser_image(self, chemin: str, rapport: IngestionReport) -> Optional[str]:
        """Retourne une description factuelle de l'image, ou None."""
        try:
            from PIL import Image

            with Image.open(chemin) as image:
                largeur, hauteur = image.size
                mode = image.mode
                format_ = image.format
        except Exception as erreur:
            rapport.errors.append(f"image illisible : {erreur}")
            return None

        details = [
            f"Image {format_ or 'inconnue'} de {largeur}×{hauteur} pixels, mode {mode}."
        ]

        # Le moteur de vision est optionnel ici : son absence retire des mesures,
        # elle n'empêche pas l'image d'entrer avec ce qu'on sait d'elle.
        try:
            from src.integration.engine_registry import get_shared_registry
            from src.vision_intelligence_engine.types import ImageItem

            vision = get_shared_registry().try_get("vision")
            if vision is not None:
                with open(chemin, "rb") as fichier:
                    item = ImageItem(image_id=os.path.basename(chemin), data=fichier.read())
                resultats = vision.analyze_image(item)
                for cle in ("quality", "colors", "classification"):
                    valeur = resultats.get(cle)
                    if isinstance(valeur, dict) and not valeur.get("error"):
                        details.append(f"{cle} : {valeur}")
        except Exception as erreur:
            rapport.notes.append({"kind": "vision", "unavailable": str(erreur)})

        return "\n".join(details)

    def _lire_texte_image(self, chemin: str, rapport: IngestionReport) -> Optional[str]:
        """Lit le texte d'une image par OCR, ou rapporte son indisponibilité."""
        try:
            import pytesseract
            from PIL import Image

            with Image.open(chemin) as image:
                texte = pytesseract.image_to_string(image, lang="fra")
        except ImportError:
            rapport.notes.append({
                "kind": "ocr",
                "unavailable": "pytesseract n'est pas installé : l'image entre sans son texte.",
            })
            return None
        except Exception as erreur:
            rapport.notes.append({"kind": "ocr", "unavailable": str(erreur)})
            return None
        return texte.strip() or None

    def _decouper(self, texte: str, chemin: str) -> List[str]:
        """Découpe via le découpeur du moteur documentaire, jamais un troisième."""
        document = DocumentItem(
            document_id=f"ingest:{os.path.basename(chemin)}",
            content=texte,
            title=os.path.basename(chemin),
            document_type=DocumentType.TXT,
        )
        return [bloc.content for bloc in self._chunker.chunk(document)]

    @staticmethod
    def _empreinte(chemin: str) -> str:
        """Hachage du fichier, pour qu'une réingestion mette à jour au lieu d'empiler."""
        condensat = hashlib.sha256()
        with open(chemin, "rb") as fichier:
            for morceau in iter(lambda: fichier.read(65536), b""):
                condensat.update(morceau)
        return condensat.hexdigest()

    def _construire(
        self, bloc: str, position: int, total: int, chemin: str, empreinte: str,
        title: str, source_category: SourceCategory, domain: KnowledgeDomain,
        scope: str, subject: KnowledgeSubject,
        author: Optional[str], url: Optional[str], tags: List[str],
        language: Language, status: KnowledgeStatus,
    ) -> KnowledgeItem:
        """Construit un élément de connaissance portant sa provenance."""
        source = KnowledgeSource(
            id=f"{empreinte[:12]}:{position}",
            type="file",
            location=chemin,
            hash=empreinte,
            source_category=source_category,
            title=title,
            author=author,
            url=url,
            citation=f"{title}, passage {position + 1}/{total} ({os.path.basename(chemin)})",
        )
        item = KnowledgeItem(
            content=bloc,
            content_type=ContentType.TEXT,
            language=language,
            domain=domain,
            scope=scope,
            subject=subject,
            status=status,
            tags=list(tags),
            source=source,
        )
        # L'identifiant est déduit du fichier et de la position : réingérer le
        # même document met à jour les mêmes blocs au lieu d'en créer de nouveaux.
        item.id = f"kn{empreinte[:12]}p{position:04d}"
        item.metadata.update({
            "chunk_index": position,
            "chunk_total": total,
            "file_hash": empreinte,
            "file_name": os.path.basename(chemin),
        })
        return item
