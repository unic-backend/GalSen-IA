"""
Le contrat d'un transcripteur (VOLET 32, ch. 01).

Une règle domine toutes les autres ici : **un transcripteur indisponible le dit ;
il ne rend jamais de texte.**

Ailleurs dans la plateforme, une capacité manquante rend une liste vide et le
service continue. Une transcription inventée est d'une autre nature : elle met
des mots dans la bouche de quelqu'un. Elle sera citée, mémorisée, peut-être
utilisée pour décider. C'est la forme la plus dommageable que puisse prendre la
fabrication que ce dépôt refuse — et la seule qui puisse nuire à une personne
nommée.

La confiance est donc rendue avec le texte, et une transcription peu sûre reste
peu sûre : l'appelant doit pouvoir la traiter comme une hypothèse.
"""

import abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TranscriptionUnavailable(Enum):
    """Pourquoi un transcripteur ne peut pas travailler."""

    MISSING_DEPENDENCY = "missing_dependency"
    MODEL_NOT_LOADED = "model_not_loaded"
    UNSUPPORTED_FORMAT = "unsupported_format"
    DISABLED = "disabled"


@dataclass
class TranscriptionResult:
    """Ce qu'une transcription a produit."""

    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    duration_seconds: Optional[float] = None
    segments: List[Dict[str, Any]] = field(default_factory=list)
    model_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat, sans champ vide inutile."""
        donnees: Dict[str, Any] = {"text": self.text, "model_name": self.model_name}
        for champ in ("language", "confidence", "duration_seconds"):
            valeur = getattr(self, champ)
            if valeur is not None:
                donnees[champ] = valeur
        if self.segments:
            donnees["segments"] = self.segments
        return donnees


@dataclass(frozen=True)
class TranscriptionProviderInfo:
    """État d'un transcripteur, et ce qu'il faut faire s'il ne répond pas."""

    provider_id: str
    model_name: str
    available: bool
    reason: Optional[TranscriptionUnavailable] = None
    detail: Optional[str] = None
    languages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'état pour `/health` et les rapports d'ingestion."""
        donnees: Dict[str, Any] = {
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "available": self.available,
        }
        if self.reason is not None:
            donnees["reason"] = self.reason.value
        if self.detail:
            donnees["detail"] = self.detail
        if self.languages:
            donnees["languages"] = self.languages
        return donnees


class TranscriptionProvider(abc.ABC):
    """Fournisseur de transcription parole vers texte."""

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Identifiant stable du fournisseur."""

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Modèle servi, inscrit avec chaque transcription."""

    @abc.abstractmethod
    def check_availability(self) -> TranscriptionProviderInfo:
        """Retourne l'état du fournisseur, sans lever."""

    @abc.abstractmethod
    def transcribe(self, chemin: str, language: Optional[str] = None) -> TranscriptionResult:
        """
        Transcrit un fichier audio.

        Args:
            chemin: Fichier audio à transcrire.
            language: Langue attendue, si elle est connue. La laisser à None
                fait détecter la langue — utile ici, où une même phrase mêle
                souvent français et wolof.

        Returns:
            Le texte, sa langue et la confiance du modèle.

        Raises:
            RuntimeError: Si le fournisseur est indisponible. Lever est correct :
                rendre une chaîne vide se confondrait avec « la personne n'a
                rien dit », et rendre un texte plausible serait pire encore.
        """

    def is_available(self) -> bool:
        """Indique si le fournisseur peut transcrire maintenant."""
        return self.check_availability().available
