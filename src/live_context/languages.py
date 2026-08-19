"""
Quelle langue est parlée, et ce qui arrive quand personne ne l'a mesurée
(L07.2, ADR-033, §10 et §11 de la directive Live Context).

## Ce qui existe déjà, et n'est pas réécrit ici

§10 demande de ne pas supposer qu'un enregistrement ne contient qu'une langue.
`creative/language/switching.py` répond déjà à cette demande — plages
homogènes, points de bascule, aveu explicite que l'alternance *à l'intérieur*
d'un segment n'a pas été regardée — et il le fait mieux que ne le ferait une
seconde implémentation, parce qu'il **ne détecte rien** : il structure ce que
quelqu'un d'autre a mesuré.

Ce module l'appelle. Il n'en refait pas la moitié, et il ne réécrit pas ses
sorties : le rapport d'alternance est rendu tel quel, sous sa propre clé.

## Ce qu'il ajoute : la distinction entre « pas de bascule » et « pas de mesure »

`switching_report` répond `switch_count: 0` sur des segments sans langue, ce qui
est exact de son point de vue — aucune bascule n'a été *constatée*. Dans un
contexte live, la même valeur se lit « la conversation est restée dans une seule
langue », ce qui est une affirmation sur la réunion.

Ici, sans aucune langue étiquetée, le compte vaut `None` : **non mesuré**.
C'est la même règle que les tours de parole de `speakers.py`.

## Une langue affirmée n'est pas une langue mesurée

Trois cas, trois statuts :

- pas de langue → `UNKNOWN`, en nommant qu'aucune identification de langue sur
  l'audio n'existe ici ;
- une langue sans confiance → `DECLARED` : quelqu'un l'affirme ;
- une langue avec sa confiance → `MEASURED`, la confiance portant sa base.

Une langue identifiée à 0,3 rapportée comme un fait ferait traduire depuis la
mauvaise langue, et `AudioSegment.language_state` le dit déjà.

## Aucune traduction n'est fabriquée

§10 l'interdit et il n'y a rien à contourner : **ce dépôt ne traduit pas des
énoncés.** `services/senegal/multilingual_aliases.py` traduit des *termes* à
partir d'une table certifiée, ce qui est autre chose. `translation_observation`
rend donc `ABSENT` avec ce constat, jamais une phrase.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Dict, List, Sequence

from src.creative.language.switching import switching_report
from src.creative.voice.scene import AudioSegment

from .state import DECLARE, MESURE, Observation, absent, unknown

#: Les modules qui porteraient une identification de langue **sur l'audio**.
#: `acquisition/language.py` identifie la langue d'un document, ce qui ne
#: s'applique pas à de la parole : le confondre ferait rapporter une mesure qui
#: n'a pas eu lieu.
MODULES_D_IDENTIFICATION_AUDIO = ("faster_whisper", "whisper", "speechbrain")

#: Ce qui existe pour traduire, et ce que cela couvre réellement.
TRADUCTION_DISPONIBLE = (
    "Aucune traduction d'énoncé n'existe dans ce dépôt. "
    "`services/senegal/multilingual_aliases.py` traduit des **termes** depuis "
    "une table certifiée, ce qui ne couvre pas une phrase parlée."
)

#: La base écrite dans l'observation quand une confiance de langue est portée.
BASE_DE_CONFIANCE = ("confiance d'identification de langue rapportée par le "
                     "segment (`AudioSegment.language_confidence`)")


def _module_present(nom: str) -> bool:
    """Dit si un module est importable, sans l'importer."""
    try:
        return importlib.util.find_spec(nom) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def audio_language_identification_state() -> Dict[str, Any]:
    """
    L'état de l'identification de langue **sur l'audio**, mesuré maintenant.

    Returns:
        Les modules cherchés, ceux trouvés, et l'état. La distinction avec
        l'identification de langue d'un *document* est écrite : elle existe
        (`acquisition/language.py`) et ne s'applique pas à de la parole.
    """
    trouves = [nom for nom in MODULES_D_IDENTIFICATION_AUDIO
               if _module_present(nom)]
    return {
        "modules_searched": list(MODULES_D_IDENTIFICATION_AUDIO),
        "modules_found": trouves,
        "state": "AVAILABLE" if trouves else "ABSENT",
        "reason": ("" if trouves else
                   f"aucun de {list(MODULES_D_IDENTIFICATION_AUDIO)} n'est "
                   "importable ici"),
        "document_identification": (
            "`acquisition/language.py` identifie la langue d'un document ; "
            "cela ne s'applique pas à de la parole."
        ),
    }


def language_observation(segment: AudioSegment) -> Observation:
    """
    Ce qu'on sait de la langue d'un segment — y compris rien.

    Args:
        segment: Le segment concerné. Son `original_audio_path` voyage dans le
            détail (§11).

    Returns:
        `UNKNOWN` sans langue, `DECLARED` avec une langue sans confiance,
        `MEASURED` avec une langue et sa confiance — la confiance portant sa
        base, sans quoi `state.py` la refuse.
    """
    contexte = (f"segment « {segment.segment_id} », audio d'origine : "
                f"{segment.original_audio_path}")
    if segment.language is None:
        etat = audio_language_identification_state()
        manque = etat["reason"] or "aucune identification fournie"
        return unknown(subject="language", modality="audio",
                       detail=f"{contexte} — sans langue : {manque}.")
    if segment.language_confidence is None:
        return Observation(
            subject="language", status=DECLARE, modality="audio",
            value=segment.language,
            detail=(f"{contexte} — langue affirmée sans confiance mesurée "
                    f"(`language_state` : {segment.language_state})."),
        )
    return Observation(
        subject="language", status=MESURE, modality="audio",
        value=segment.language, confidence=segment.language_confidence,
        confidence_basis=BASE_DE_CONFIANCE,
        detail=f"{contexte} — `language_state` : {segment.language_state}.",
    )


def transcript_observation(segment: AudioSegment) -> Observation:
    """
    Ce qui a été transcrit d'un segment — ou rien, dit comme tel.

    Args:
        segment: Le segment concerné.

    Returns:
        `MEASURED` quand le segment porte un texte, `UNKNOWN` sinon.

    Note:
        Il n'y a aucun cas intermédiaire, parce qu'`AudioSegment` refuse déjà à
        la construction un texte dont la source n'est pas mesurée : « une
        transcription approximative est mise dans la bouche de quelqu'un ».
        L'invariant est hérité, pas revérifié.
    """
    contexte = (f"segment « {segment.segment_id} », audio d'origine : "
                f"{segment.original_audio_path}")
    if segment.transcript is None:
        return unknown(subject="transcript", modality="audio",
                       detail=f"{contexte} — aucune transcription "
                              f"(`transcript_source` : {segment.transcript_source}).")
    return Observation(subject="transcript", status=MESURE, modality="audio",
                       value=segment.transcript, detail=contexte)


def translation_observation(segment: AudioSegment,
                            target_language: str) -> Observation:
    """
    Ce qui serait la traduction d'un segment — et pourquoi il n'y en a pas.

    Args:
        segment: Le segment concerné.
        target_language: La langue demandée.

    Returns:
        Une observation `ABSENT` portant le constat. **Jamais une phrase** :
        §10 interdit de fabriquer une traduction, et il n'y a rien à
        contourner puisque ce dépôt ne traduit pas d'énoncé.
    """
    return absent(
        subject="translation", modality="audio",
        detail=(f"traduction vers « {target_language} » demandée pour le "
                f"segment « {segment.segment_id} » : {TRADUCTION_DISPONIBLE} "
                f"Audio d'origine : {segment.original_audio_path}."),
    )


def language_observations(segments: Sequence[AudioSegment]) -> List[Observation]:
    """
    Les observations de langue d'une suite de segments.

    Args:
        segments: Les segments examinés.

    Returns:
        Une observation par segment, dans l'ordre reçu.
    """
    return [language_observation(segment) for segment in segments]


def live_switching(segments: Sequence[AudioSegment]) -> Dict[str, Any]:
    """
    L'alternance de langues, avec la distinction que le contexte live impose.

    Args:
        segments: Les segments examinés.

    Returns:
        Deux clés. `switching` est le rapport de
        `creative/language/switching.py`, **rendu tel quel** : le réécrire
        ferait diverger deux vérités. `live` porte l'état de la mesure —
        `switch_count` vaut `None` quand aucun segment ne porte de langue.

    Note:
        `switch_count: 0` sur des segments sans langue est exact du point de vue
        du module d'alternance : aucune bascule n'a été constatée. Lu en live,
        il dit « la conversation est restée dans une seule langue », ce qui est
        une affirmation sur la réunion. `None` dit que personne n'a mesuré.
    """
    rapport = switching_report(segments)
    etiquetes = [s for s in segments if s.language is not None]
    if not etiquetes:
        etat = audio_language_identification_state()
        live = {
            "state": "NOT_MEASURED",
            "switch_count": None,
            "languages": [],
            "reason": ("aucun segment ne porte de langue : "
                       + (etat["reason"] or "aucune identification fournie")),
        }
    else:
        complet = len(etiquetes) == len(segments)
        live = {
            "state": "MEASURED" if complet else "PARTIAL",
            "switch_count": rapport["switch_count"],
            "languages": rapport["languages"],
            "reason": "" if complet else (
                f"{len(segments) - len(etiquetes)} segment(s) sans langue : "
                "les bascules ne couvrent pas tout l'enregistrement"
            ),
        }
    live["coverage"] = f"{len(etiquetes)}/{len(segments)} segment(s) étiqueté(s)"
    return {"switching": rapport, "live": live}


def languages_view(segments: Sequence[AudioSegment]) -> Dict[str, Any]:
    """
    Ce qu'on sait des langues d'un enregistrement, et ce qu'on n'en sait pas.

    Args:
        segments: Les segments examinés.

    Returns:
        Les observations, l'alternance, l'état mesuré de l'identification, et
        le nombre de segments sans langue. **Aucune langue dominante** et
        aucune langue de fichier : `switching.py` explique pourquoi, et une
        couche live n'a aucune raison de revenir dessus.
    """
    observations = language_observations(segments)
    return {
        "observations": [o.as_dict() for o in observations],
        "switching": live_switching(segments),
        "identification": audio_language_identification_state(),
        "segments_without_language": sum(1 for s in segments
                                         if s.language is None),
        "dominant_language": None,
        "dominant_language_reason": (
            "Aucune langue dominante n'est calculée : la langue appartient au "
            "segment, et un champ au niveau du fichier est faux pour la moitié "
            "d'une conversation dakaroise."
        ),
    }


def languages_report() -> Dict[str, Any]:
    """
    Ce que la couche langues garantit, et ce qu'elle refuse de faire.

    Returns:
        L'état mesuré, ce qui est réutilisé, et les règles tenues.
    """
    return {
        "identification": audio_language_identification_state(),
        "translation_available": False,
        "translation_reason": TRADUCTION_DISPONIBLE,
        "reused": [
            "creative/language/switching.py — plages, bascules, alternance",
            "creative/voice/scene.py — AudioSegment et `language_state`",
        ],
        "rules": [
            "Aucune traduction n'est fabriquée : ce dépôt ne traduit pas "
            "d'énoncé, et l'observation le dit au lieu de rendre une phrase.",
            "Aucune transcription n'est approximée : un texte sans source "
            "mesurée est refusé par AudioSegment.",
            "Une langue sans confiance est DECLARED, jamais MEASURED.",
            "Sans langue étiquetée, `switch_count` vaut None : zéro bascule "
            "affirmerait que la conversation est restée dans une seule langue.",
            "Aucune langue dominante et aucune langue de fichier.",
            "Le rapport d'alternance réutilisé est rendu tel quel.",
        ],
    }
