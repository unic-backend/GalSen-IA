"""
Understanding a recording without replacing it.

Directive §22 forbids the reflex pipeline — *audio → transcription → TTS →
generated voice* — and asks instead for *audio → understanding → video → lip
sync → **original audio***. §26 explains why the constraint bites hardest
exactly where it is least convenient: for under-resourced languages,
**understanding and generation are separate capabilities and the second is
usually missing or poor**. Wolof, Serer, Pulaar, Bambara, Diola are the
languages where a synthetic voice will be worst, and the languages where a
speaker's own recording carries the most that no model can reconstruct —
pronunciation, rhythm, hesitation, the pause before the word they chose.

Three structural consequences, and they are what this module is:

**The original path is never dropped.** `AudioSegment.original_audio_path` has
no default and no setter that clears it. §22's guarantee depends on the file
still being there at the end, so the structure makes losing it impossible rather
than discouraged.

**Language belongs to a segment, not a file** (§25). A single recording in Dakar
alternates Wolof and French inside one sentence. A file-level language field
forces a choice that is wrong for half the recording, and everything downstream
inherits it.

**A language may be understood and not speakable.** The two capabilities are
declared separately per language, so a gap is visible instead of being filled by
a bad voice. When understanding is uncertain, the answer is `UNKNOWN` or
`LOW_CONFIDENCE` and the recording is preserved (§33) — nothing invents a
translation, a meaning or a pronunciation.

Measured here: no ASR (`transcription` → `UNAVAILABLE`), no diarization, no
speech synthesis anywhere in this repository. So this module builds the pipeline
and **reports each stage's state**; it produces no transcript, no speaker
assignment and no voice. The stages that would fill them are named.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

from ...integration.degradation import DISPONIBLE
from ...media.core.capabilities import probe

#: Les langues déclarées par le moteur de sous-titres, réutilisées telles
#: quelles : deux tables de langues divergeraient au premier ajout.
from ...media.subtitles.cues import LANGUES  # noqa: E402  (import documenté)

#: Ce que la plateforme sait faire d'une langue. Les deux sont **séparées** :
#: comprendre le wolof et le parler sont deux capacités, et l'écosystème ne les
#: fournit pas ensemble.
COMPRENDRE = "UNDERSTOOD"
PARLER = "SPEAKABLE"

#: L'état d'une information linguistique (§33).
CONNU = "KNOWN"
CONFIANCE_FAIBLE = "LOW_CONFIDENCE"
INCONNU = "UNKNOWN"
ETATS_LINGUISTIQUES = (CONNU, CONFIANCE_FAIBLE, INCONNU)

#: Seuil sous lequel une identification de langue est rapportée en confiance
#: faible plutôt qu'en fait. Déclaré, donc discutable — et c'est le but : un
#: seuil caché se discute mal.
SEUIL_DE_CONFIANCE = 0.7

#: Les étapes de la chaîne §21, dans l'ordre, avec la capacité qui les porte.
#: Une étape sans capacité déclarée est une étape que ce dépôt réalise seul.
ETAPES = (
    ("audio_analysis", "audio_analysis"),
    ("language_identification", "transcription"),
    ("speaker_diarization", "speaker_diarization"),
    ("speech_segmentation", "transcription"),
    ("semantic_understanding", ""),
    ("emotion_prosody", "audio_analysis"),
    ("reference_entity_mapping", ""),
    ("entity_assignment", ""),
    ("scene_understanding", ""),
    ("timeline", ""),
    ("world_state", ""),
    ("director", ""),
    ("shot_planning", ""),
    ("video_generation", "gpu_compute"),
    ("original_audio", ""),
    ("lip_sync", "gpu_compute"),
    ("continuity", ""),
    ("identity_verification", "identity_verification"),
)

#: Les capacités que ce dépôt ne porte pas et qu'aucune sonde média ne couvre.
#: Nommées ici pour qu'une étape bloquée dise **quoi** installer.
CAPACITES_EXTERNES = {
    "speaker_diarization": (
        "Aucun module de séparation de locuteurs n'existe dans ce dépôt, et "
        "aucun n'est installable ici (pyannote exige `torch` et une "
        "acceptation de conditions sur Hugging Face)."
    ),
    "identity_verification": (
        "Aucune mesure d'identité (ADR-026) : les dimensions sont déclarées, "
        "aucune n'est mesurable sur cette machine."
    ),
}


class VoiceSceneRefused(ValueError):
    """Une scène vocale impossible à construire telle qu'elle est demandée."""


@dataclass(frozen=True)
class LanguageCapability:
    """
    Ce que la plateforme sait faire d'une langue — séparément.

    Attributes:
        code: Le code de langue.
        understood: Si la compréhension est possible.
        speakable: Si la génération vocale est possible.
        understanding_reason: Pourquoi, quand elle ne l'est pas.
        speaking_reason: Pourquoi, quand elle ne l'est pas.
    """

    code: str
    understood: bool = False
    speakable: bool = False
    understanding_reason: str = ""
    speaking_reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "code": self.code, "understood": self.understood,
            "speakable": self.speakable,
            "understanding_reason": self.understanding_reason,
            "speaking_reason": self.speaking_reason,
        }


@dataclass(frozen=True)
class AudioSegment:
    """
    Un passage parlé, et tout ce qu'on en sait — y compris rien.

    Attributes:
        segment_id: Son identité.
        start: Début, en secondes. **Mesuré**, jamais estimé.
        end: Fin, en secondes.
        original_audio_path: Le fichier d'origine. **Obligatoire** : la
            garantie de §22 tient à ce que ce fichier existe encore à la fin.
        language: La langue du **segment**, ou `None` si elle n'est pas connue.
        language_confidence: De 0 à 1. `None` = personne ne l'a mesurée.
        speaker_id: Le locuteur, si une séparation a eu lieu.
        transcript: Le texte, ou `None`. Jamais une approximation.
        transcript_source: `MEASURED` ou `ABSENT`.
        emotion: Ce qui a été observé de la prosodie.
    """

    segment_id: str
    start: float
    end: float
    original_audio_path: str
    language: Optional[str] = None
    language_confidence: Optional[float] = None
    speaker_id: Optional[str] = None
    transcript: Optional[str] = None
    transcript_source: str = "ABSENT"
    emotion: Optional[str] = None

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise VoiceSceneRefused(
                f"Segment « {self.segment_id} » : fin {self.end} avant début "
                f"{self.start}."
            )
        if not str(self.original_audio_path or "").strip():
            raise VoiceSceneRefused(
                f"Segment « {self.segment_id} » sans audio d'origine. La "
                "garantie de §22 — préserver la voix de la personne — tient à "
                "ce que ce fichier existe encore à la fin de la chaîne."
            )
        if self.language is not None and self.language not in LANGUES:
            raise VoiceSceneRefused(
                f"Langue « {self.language} » non déclarée. Déclarées : "
                f"{sorted(LANGUES)}. En deviner une afficherait de l'arabe à "
                "l'envers."
            )
        if self.language_confidence is not None \
                and not 0.0 <= self.language_confidence <= 1.0:
            raise VoiceSceneRefused(
                f"Confiance {self.language_confidence} hors de [0, 1]."
            )
        if self.transcript is not None and self.transcript_source != "MEASURED":
            raise VoiceSceneRefused(
                f"Segment « {self.segment_id} » porte un texte dont la source "
                "n'est pas mesurée. Une transcription approximative est mise "
                "dans la bouche de quelqu'un."
            )

    @property
    def duration(self) -> float:
        """La durée du segment."""
        return round(self.end - self.start, 4)

    @property
    def language_state(self) -> str:
        """
        L'état de l'identification de langue (§33).

        `UNKNOWN` quand rien n'a été identifié, `LOW_CONFIDENCE` sous le seuil
        déclaré, `KNOWN` au-dessus. Une langue identifiée à 0,3 et rapportée
        comme un fait ferait traduire depuis la mauvaise langue.
        """
        if self.language is None:
            return INCONNU
        if self.language_confidence is None:
            return CONFIANCE_FAIBLE
        return (CONNU if self.language_confidence >= SEUIL_DE_CONFIANCE
                else CONFIANCE_FAIBLE)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences comprises."""
        return {
            "segment_id": self.segment_id, "start": self.start,
            "end": self.end, "duration": self.duration,
            "original_audio_path": self.original_audio_path,
            "language": self.language,
            "language_confidence": self.language_confidence,
            "language_state": self.language_state,
            "speaker_id": self.speaker_id,
            "transcript": self.transcript,
            "transcript_source": self.transcript_source,
            "emotion": self.emotion,
        }


def language_capabilities(codes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """
    Ce que la plateforme sait faire de chaque langue, mesuré.

    Args:
        codes: Les langues à examiner. Toutes les langues déclarées par défaut.

    Returns:
        Par langue, si elle est comprise et si elle est parlée — séparément
        (§26). Aujourd'hui aucune n'est ni l'un ni l'autre : la transcription
        est indisponible et **aucune synthèse vocale n'existe dans ce dépôt**.
        Le dire par langue rend la lacune visible au lieu de la laisser
        combler par une mauvaise voix.
    """
    transcription = probe("transcription")
    capacites = []
    for code in sorted(codes or LANGUES):
        if code not in LANGUES:
            raise VoiceSceneRefused(
                f"Langue « {code} » non déclarée. Déclarées : {sorted(LANGUES)}."
            )
        capacites.append(LanguageCapability(
            code=code,
            understood=transcription["state"] == DISPONIBLE,
            speakable=False,
            understanding_reason=(
                "" if transcription["state"] == DISPONIBLE
                else f"Transcription {transcription['state']} : "
                     f"{transcription['reason']}"
            ),
            speaking_reason=(
                "Aucune synthèse vocale n'existe dans ce dépôt. Ce n'est pas "
                "une dépendance absente : c'est un module qui n'a pas été "
                "écrit, et §26 rappelle que pour les langues peu dotées la "
                "meilleure réponse reste l'enregistrement d'origine."
            ),
        ))

    return {
        "languages": [c.as_dict() for c in capacites],
        "understood": [c.code for c in capacites if c.understood],
        "speakable": [c.code for c in capacites if c.speakable],
        "note": (
            "Comprendre et parler sont **deux** capacités. Les confondre "
            "ferait remplacer la voix d'un locuteur wolof par une "
            "approximation synthétique d'une langue que le synthétiseur "
            "modélise mal."
        ),
    }


def pipeline_state() -> Dict[str, Any]:
    """
    L'état de chaque étape de la chaîne §21, mesuré par les sondes.

    Returns:
        Par étape : `READY` quand rien ne lui manque, `BLOCKED` avec la
        capacité absente sinon. L'ordre est celui de la directive, pour que le
        premier blocage se lise comme le point où la chaîne s'arrête.
    """
    etapes = []
    for nom, capacite in ETAPES:
        if not capacite:
            etapes.append({"stage": nom, "state": "READY", "missing": None,
                           "reason": "Réalisée par ce dépôt, sans dépendance."})
            continue
        if capacite in CAPACITES_EXTERNES:
            etapes.append({"stage": nom, "state": "BLOCKED",
                           "missing": capacite,
                           "reason": CAPACITES_EXTERNES[capacite]})
            continue
        resultat = probe(capacite)
        pret = resultat["state"] == DISPONIBLE
        etapes.append({
            "stage": nom, "state": "READY" if pret else "BLOCKED",
            "missing": None if pret else capacite,
            "reason": "" if pret else resultat["reason"],
        })

    bloquees = [e["stage"] for e in etapes if e["state"] == "BLOCKED"]
    return {
        "stages": etapes,
        "blocked": bloquees,
        "first_block": bloquees[0] if bloquees else None,
        "note": (
            "L'ordre est celui de §21 : le premier blocage est le point où la "
            "chaîne s'arrête réellement, et les étapes suivantes ne sont pas "
            "« prêtes » au sens utile du terme."
        ),
    }


def build_scene(
    segments: Sequence[AudioSegment], entities: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Construit une scène vocale à partir de segments **fournis**.

    Args:
        segments: Les segments, avec leurs temps mesurés et leur audio
            d'origine.
        entities: L'attribution locuteur → entité, quand quelqu'un l'a établie.

    Returns:
        La scène : segments, langues rencontrées, locuteurs, et ce qui reste
        inconnu. **Rien n'est transcrit ni identifié ici** — la transcription
        et la séparation de locuteurs sont indisponibles, et cette fonction
        assemble ce qu'on lui donne au lieu d'inventer ce qui manque.

    Raises:
        VoiceSceneRefused: Sans segment, ou si des segments se chevauchent —
            un chevauchement non résolu ferait attribuer une même parole à deux
            locuteurs.
    """
    if not segments:
        raise VoiceSceneRefused(
            "Aucun segment. Une scène construite sur rien décrirait une "
            "conversation qui n'a pas eu lieu."
        )

    ordonnes = sorted(segments, key=lambda s: s.start)
    for precedent, suivant in zip(ordonnes, ordonnes[1:]):
        if suivant.start < precedent.end:
            raise VoiceSceneRefused(
                f"Les segments « {precedent.segment_id} » et "
                f"« {suivant.segment_id} » se chevauchent "
                f"({precedent.end} > {suivant.start}). Non résolu, un "
                "chevauchement fait attribuer une même parole à deux locuteurs."
            )

    attribution = entities or {}
    langues = sorted({s.language for s in ordonnes if s.language})
    locuteurs = sorted({s.speaker_id for s in ordonnes if s.speaker_id})
    sans_langue = [s.segment_id for s in ordonnes if s.language is None]
    faible = [s.segment_id for s in ordonnes
              if s.language_state == CONFIANCE_FAIBLE]
    sans_texte = [s.segment_id for s in ordonnes if s.transcript is None]
    non_attribues = [s for s in locuteurs if s not in attribution]

    return {
        "segments": [s.as_dict() for s in ordonnes],
        "duration": round(ordonnes[-1].end - ordonnes[0].start, 4),
        "languages": langues,
        "code_switching": len(langues) > 1,
        "speakers": locuteurs,
        "entity_assignment": dict(attribution),
        "unassigned_speakers": non_attribues,
        "segments_without_language": sans_langue,
        "segments_low_confidence": faible,
        "segments_without_transcript": sans_texte,
        "original_audio_preserved": True,
        "note": (
            "Le minutage et l'audio d'origine sont conservés tels quels. Les "
            "segments sans langue ou sans texte sont **nommés** : les remplir "
            "au jugé mettrait des mots dans la bouche de quelqu'un, et §33 "
            "l'interdit."
        ),
    }


def voice_plan(scene: Dict[str, Any], synthesise: bool = False) -> Dict[str, Any]:
    """
    Décide ce que devient la voix — et par défaut, elle ne devient rien.

    Args:
        scene: La scène construite.
        synthesise: Demander explicitement une voix générée. Faux par défaut :
            remplacer une performance humaine est une décision de la personne,
            jamais un défaut de traitement.

    Returns:
        Le chemin retenu et sa raison. Une demande de synthèse est **refusée
        ici** parce qu'aucune synthèse n'existe dans ce dépôt : le dire vaut
        mieux que produire un silence ou une voix approximative.
    """
    if not synthesise:
        return {
            "path": "PRESERVE_ORIGINAL",
            "status": "OK",
            "reason": (
                "L'enregistrement d'origine est conservé : prononciation, "
                "accent, rythme, pauses, hésitations et intonation avec lui. "
                "C'est le chemin par défaut de §22, pas un repli."
            ),
            "original_audio": [s["original_audio_path"]
                               for s in scene["segments"]],
        }

    return {
        "path": "SYNTHESISE",
        "status": "NOT_AVAILABLE",
        "reason": (
            "Aucune synthèse vocale n'existe dans ce dépôt. Ce n'est pas une "
            "dépendance manquante : aucun module ne le fait, et aucune "
            "installation ne le fera apparaître. L'enregistrement d'origine "
            "reste disponible et reste le meilleur choix pour les langues peu "
            "dotées (§26)."
        ),
        "original_audio": [s["original_audio_path"] for s in scene["segments"]],
    }


def voice_scene_report() -> Dict[str, Any]:
    """
    Ce que la scène vocale garantit, et ce qu'elle refuse.

    Returns:
        Les états déclarés, l'état de la chaîne, et les règles tenues.
    """
    return {
        "linguistic_states": list(ETATS_LINGUISTIQUES),
        "confidence_threshold": SEUIL_DE_CONFIANCE,
        "stages": [nom for nom, _ in ETAPES],
        "pipeline": pipeline_state(),
        "capabilities": language_capabilities(),
        "rules": [
            "**L'enregistrement d'origine est le chemin par défaut** (§22), "
            "pas un repli. Le remplacer est une décision de la personne.",
            "La langue appartient au **segment**, jamais au fichier : une "
            "conversation à Dakar alterne wolof et français dans une phrase.",
            "**Comprendre et parler sont deux capacités** (§26), déclarées "
            "séparément par langue — sinon la lacune se comble par une "
            "mauvaise voix.",
            "Une identification sous le seuil est `LOW_CONFIDENCE`, pas un "
            "fait : traduire depuis une langue identifiée à 0,3 traduit depuis "
            "la mauvaise langue.",
            "Un segment sans transcription reste **sans transcription** et il "
            "est nommé : le remplir au jugé met des mots dans la bouche de "
            "quelqu'un (§33).",
            "Un chevauchement de segments est refusé : non résolu, il attribue "
            "une même parole à deux locuteurs.",
        ],
        "does_not": [
            "Transcrire, identifier une langue ou séparer des locuteurs — "
            "aucune de ces capacités n'est disponible ici.",
            "Inventer une traduction, un sens ou une prononciation.",
            "Remplacer une voix humaine par défaut.",
            "Perdre le fichier d'origine.",
        ],
    }


def original_audio_exists(scene: Dict[str, Any]) -> Dict[str, Any]:
    """
    Vérifie que les fichiers d'origine sont toujours là.

    Args:
        scene: La scène construite.

    Returns:
        Les fichiers présents et absents. C'est le contrôle qui rend §22
        vérifiable au lieu d'affirmée : une garantie de préservation qui ne
        regarde jamais le disque est une intention.
    """
    chemins = sorted({s["original_audio_path"] for s in scene["segments"]})
    presents = [c for c in chemins if os.path.isfile(c)]
    absents = [c for c in chemins if c not in presents]
    return {
        "checked": chemins,
        "present": presents,
        "missing": absents,
        "preserved": not absents,
        "note": (
            "Tous les enregistrements d'origine sont présents."
            if not absents else
            f"{len(absents)} fichier(s) d'origine introuvable(s) : la "
            "garantie de §22 ne tient plus, et le dire vaut mieux que la "
            "maintenir sur le papier."
        ),
    }
