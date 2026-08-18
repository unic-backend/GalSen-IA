"""
Transcription locale par Whisper (VOLET 32, ch. 01 — ADR-014).

Le modèle tourne **sur cette machine**. Ce n'est pas un détail de performance :
un service de transcription hébergé recevrait la voix des utilisateurs — leur
timbre, leur langue, ce qu'ils disent chez eux. C'est un export plus intime
qu'une invite de texte, et ADR-014 l'exclut déjà pour la génération.

`faster-whisper` est préféré à `openai-whisper` pour une raison mesurable :
il fait tourner le même modèle sur CTranslate2, environ quatre fois plus vite sur
CPU et avec moins de mémoire. Sur les machines que ce projet vise réellement,
c'est la différence entre « utilisable » et « théorique ». L'implémentation de
référence reste acceptée si c'est elle qui est installée.

**Non vérifié dans l'environnement de développement** : la transcription réelle.
Les poids se téléchargent depuis Hugging Face, qui répond 403 à travers le
mandataire de cet environnement. Ce qui est vérifié, c'est que l'absence de la
bibliothèque est **rapportée** et non contournée — et c'est le comportement qui
compte tant que personne n'a installé le paquet.
"""

import logging
import os
from typing import List, Optional

from .interfaces import (
    TranscriptionProvider,
    TranscriptionProviderInfo,
    TranscriptionResult,
    TranscriptionUnavailable,
)

logger = logging.getLogger(__name__)

MODEL_VARIABLE = "GALSEN_WHISPER_MODEL"

# `small` est le compromis retenu : il comprend le français correctement et tient
# sur une machine modeste. `medium` et `large-v3` font mieux en wolof mais
# demandent plusieurs gigaoctets.
DEFAULT_MODEL = "small"

# Formats que les bibliothèques savent ouvrir. La liste sert à refuser tôt, avec
# un message utile, plutôt qu'à laisser échouer le décodage.
FORMATS = (".wav", ".mp3", ".m4a", ".ogg", ".opus", ".flac", ".webm", ".mp4")


class WhisperTranscriber(TranscriptionProvider):
    """Transcripteur local reposant sur `faster-whisper`, ou sur `whisper`."""

    def __init__(self, model_name: Optional[str] = None, device: str = "cpu"):
        """
        Args:
            model_name: Taille du modèle ; `GALSEN_WHISPER_MODEL` sinon.
            device: Appareil de calcul ; CPU par défaut, qui est ce dont dispose
                un déploiement ordinaire.
        """
        self._model_name = model_name or os.getenv(MODEL_VARIABLE, "").strip() or DEFAULT_MODEL
        self._device = device
        self._modele = None
        self._implementation: Optional[str] = None

    @property
    def provider_id(self) -> str:
        """Identifiant stable du fournisseur."""
        return "whisper_local"

    @property
    def model_name(self) -> str:
        """Modèle servi."""
        return self._model_name

    @staticmethod
    def _implementation_disponible() -> Optional[str]:
        """Retourne l'implémentation installée, ou None."""
        try:
            import faster_whisper  # noqa: F401

            return "faster-whisper"
        except ImportError:
            pass
        try:
            import whisper  # noqa: F401

            return "openai-whisper"
        except ImportError:
            return None

    def check_availability(self) -> TranscriptionProviderInfo:
        """Retourne l'état du fournisseur, sans jamais lever ni télécharger."""
        implementation = self._implementation_disponible()
        if implementation is None:
            return TranscriptionProviderInfo(
                provider_id=self.provider_id,
                model_name=self._model_name,
                available=False,
                reason=TranscriptionUnavailable.MISSING_DEPENDENCY,
                detail=(
                    "Aucune implémentation de Whisper n'est installée. "
                    "pip install -r requirements-audio.txt pour activer la "
                    "transcription locale (VOLET 32). Sans elle, un fichier "
                    "audio est refusé à l'ingestion plutôt que transcrit à vide."
                ),
            )

        return TranscriptionProviderInfo(
            provider_id=self.provider_id,
            model_name=self._model_name,
            available=True,
            detail=f"Implémentation : {implementation}.",
            # Whisper est multilingue ; ces trois-là sont celles qui comptent
            # pour ce projet, et le wolof n'est pas dans son jeu d'entraînement
            # — le VOLET 33 est la réponse à cela, pas une promesse ici.
            languages=["fr", "en", "ar"],
        )

    def supports(self, chemin: str) -> bool:
        """Indique si l'extension du fichier est prise en charge."""
        return os.path.splitext(chemin)[1].lower() in FORMATS

    def _charger(self):
        """Charge le modèle au premier usage."""
        if self._modele is not None:
            return self._modele

        implementation = self._implementation_disponible()
        if implementation == "faster-whisper":
            from faster_whisper import WhisperModel

            self._modele = WhisperModel(self._model_name, device=self._device, compute_type="int8")
        else:
            import whisper

            self._modele = whisper.load_model(self._model_name, device=self._device)
        self._implementation = implementation
        logger.info("Modèle Whisper chargé : %s (%s)", self._model_name, implementation)
        return self._modele

    def transcribe(self, chemin: str, language: Optional[str] = None) -> TranscriptionResult:
        """
        Transcrit un fichier audio.

        Args:
            chemin: Fichier audio.
            language: Langue attendue ; détectée si absente — utile ici, où une
                même phrase mêle souvent français et wolof.

        Returns:
            Le texte, sa langue et la confiance annoncée par le modèle.

        Raises:
            RuntimeError: Si la bibliothèque manque, si le fichier est absent ou
                si son format n'est pas pris en charge. Rendre une chaîne vide
                se confondrait avec « la personne n'a rien dit ».
        """
        if not os.path.isfile(chemin):
            raise RuntimeError(f"Fichier audio introuvable : {chemin}")
        if not self.supports(chemin):
            raise RuntimeError(
                f"Format non pris en charge : {os.path.splitext(chemin)[1]}. "
                f"Formats acceptés : {', '.join(FORMATS)}."
            )

        try:
            modele = self._charger()
        except ImportError as erreur:
            raise RuntimeError(
                "Transcription impossible : aucune implémentation de Whisper "
                "n'est installée (VOLET 32)."
            ) from erreur
        except Exception as erreur:
            raise RuntimeError(
                f"Transcription impossible : le modèle « {self._model_name} » "
                f"n'a pas pu être chargé ({erreur})."
            ) from erreur

        if self._implementation == "faster-whisper":
            segments, info = modele.transcribe(chemin, language=language)
            morceaux: List[dict] = [
                {"start": segment.start, "end": segment.end, "text": segment.text}
                for segment in segments
            ]
            return TranscriptionResult(
                text=" ".join(morceau["text"].strip() for morceau in morceaux).strip(),
                language=getattr(info, "language", language),
                # La probabilité de langue n'est pas une confiance de
                # transcription, mais c'est la seule mesure que le modèle rende.
                # La nommer ainsi serait exagéré : elle est reportée telle quelle.
                confidence=getattr(info, "language_probability", None),
                duration_seconds=getattr(info, "duration", None),
                segments=morceaux,
                model_name=self._model_name,
            )

        resultat = modele.transcribe(chemin, language=language)
        return TranscriptionResult(
            text=(resultat.get("text") or "").strip(),
            language=resultat.get("language", language),
            segments=resultat.get("segments", []),
            model_name=self._model_name,
        )
