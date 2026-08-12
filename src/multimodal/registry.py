"""
Le point unique où l'on demande un transcripteur (VOLET 32).

Même forme que le registre d'embeddings (ADR-015), et pour la même raison : sans
point unique, chaque appelant construirait le sien, et deux composants
finiraient par transcrire avec deux modèles différents sans que personne le voie.

`active_transcriber()` retourne **None** quand aucun transcripteur ne peut
travailler. C'est l'état normal d'une installation sans Whisper, et l'appelant
doit alors refuser le fichier audio **en le disant**, jamais le traiter comme
un texte vide.
"""

import os
import threading
from typing import Any, Dict, Optional

from .interfaces import TranscriptionProvider
from .whisper_provider import WhisperTranscriber

ENABLED_VARIABLE = "GALSEN_TRANSCRIPTION_ENABLED"

_verrou = threading.RLock()
_fournisseur: Optional[TranscriptionProvider] = None
_force: bool = False


def _desactive() -> bool:
    """Indique si l'exploitant a coupé la transcription explicitement."""
    return os.getenv(ENABLED_VARIABLE, "").strip().lower() in ("false", "0", "no")


def set_transcriber(fournisseur: Optional[TranscriptionProvider]) -> None:
    """
    Impose un transcripteur, ou rend la main au choix par défaut avec `None`.

    Sert à un déploiement qui sert son propre modèle, et aux tests, qui peuvent
    ainsi exercer tout le chemin — ingestion, provenance, refus — sans
    télécharger plusieurs gigaoctets de poids.
    """
    global _fournisseur, _force
    with _verrou:
        _fournisseur = fournisseur
        _force = fournisseur is not None


def reset_transcriber() -> None:
    """Oublie le transcripteur retenu ; le prochain appel le redécouvrira."""
    global _fournisseur, _force
    with _verrou:
        _fournisseur = None
        _force = False


def active_transcriber() -> Optional[TranscriptionProvider]:
    """
    Retourne le transcripteur utilisable, ou None s'il n'y en a pas.

    Returns:
        Le fournisseur, ou None — l'état normal d'une installation sans Whisper.
        Un `None` n'est pas une panne : c'est l'information dont l'appelant a
        besoin pour refuser proprement un fichier audio.
    """
    global _fournisseur
    with _verrou:
        # La coupure de l'exploitant est vérifiée **avant** le fournisseur
        # imposé. L'inverse laissait un appel programmatique rétablir une
        # capacité que l'exploitant a explicitement coupée — un interrupteur
        # qu'un composant peut contourner n'est pas un interrupteur.
        if _desactive():
            return None
        if _force and _fournisseur is not None:
            return _fournisseur
        if _fournisseur is None:
            candidat = WhisperTranscriber()
            if not candidat.is_available():
                return None
            _fournisseur = candidat
        return _fournisseur


def transcription_status() -> Dict[str, Any]:
    """
    Décrit l'état de la transcription, pour `/health` et les rapports.

    Returns:
        L'état du fournisseur retenu, ou le motif pour lequel il n'y en a pas.
        Jamais un état vide : « pas de transcription » est une réponse, et elle
        doit dire pourquoi.
    """
    if _desactive():
        return {
            "available": False,
            "reason": "disabled",
            "detail": f"{ENABLED_VARIABLE} est à false : les fichiers audio sont refusés.",
        }

    with _verrou:
        fournisseur = _fournisseur if _force else None
    if fournisseur is None:
        fournisseur = WhisperTranscriber()

    etat = fournisseur.check_availability().to_dict()
    etat["reference"] = "VOLET 32"
    return etat
