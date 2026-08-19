"""
Qui parle — et pourquoi, ici, la réponse est presque toujours « on ne sait pas »
(L07.1, ADR-033, §9 de la directive Live Context).

## Ce que §9 demande, et ce que cette machine peut en tenir

§9 demande la séparation des locuteurs, leur identification et le suivi des
tours de parole. **Aucune séparation de locuteurs n'existe dans ce dépôt**, et
`creative/voice/scene.py` le déclare déjà avec sa raison : `pyannote` exige
`torch` et une acceptation de conditions sur Hugging Face, que cet
environnement refuse (`403` mesuré). Ce module **reprend cette déclaration** au
lieu d'en écrire une seconde.

Il ne reste donc pas grand-chose à calculer, et c'est précisément le sujet : ce
qui reste à faire correctement, c'est **dire qui parle quand personne ne le
sait**, sans que la sortie ressemble à une réponse.

## Numéroter des locuteurs serait la fabrication la plus facile du dépôt

Découper un enregistrement et étiqueter les morceaux `SPEAKER_1`, `SPEAKER_2`,
`SPEAKER_3` produit une sortie qui a exactement la forme d'une diarisation.
Elle en a la forme et pas le contenu : rien ne garantit que `SPEAKER_1` au
début et `SPEAKER_1` à la fin soient la même personne.

**Ce module n'expose aucune fonction qui numérote un locuteur.** Un segment
sans `speaker_id` produit une observation `UNKNOWN` qui nomme ce qui manque.

## Un canal n'est pas un locuteur

Call.md sépare deux canaux — le microphone local et le flux distant — et c'est
une bonne idée qui est reprise. Mais un canal dit **d'où vient le son**, pas
**qui parle** : trois personnes autour d'un microphone partagent un canal, et
une réunion transférée en change. Une identité déduite d'un canal est donc
`DECLARED`, jamais `MEASURED`, et le sujet de l'observation le dit.

## Zéro tour de parole n'existe pas

Sans locuteurs connus, le nombre de tours est `None` — **non mesuré** — et
jamais `0`. Zéro voudrait dire « personne n'a pris la parole », ce qui est une
affirmation sur la réunion ; `None` dit « personne n'a compté », ce qui est une
affirmation sur nous.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Dict, List, Sequence

from src.creative.voice.scene import CAPACITES_EXTERNES, AudioSegment

from .state import DECLARE, MESURE, Observation, absent, unknown

#: D'où une identité de locuteur peut venir, et ce que cela vaut comme statut.
#: `CHANNEL` et `DECLARED_BY_USER` sont des affirmations : la première déduit
#: une personne d'une provenance de son, la seconde rapporte ce que quelqu'un a
#: dit. Aucune des deux n'est une mesure.
SOURCES_D_IDENTITE: Dict[str, str] = {
    "DIARIZATION": MESURE,
    "CHANNEL": DECLARE,
    "DECLARED_BY_USER": DECLARE,
}

#: Le sujet d'observation selon la source. Un canal a le sien pour qu'une
#: lecture rapide ne prenne pas une provenance de son pour une identité.
_SUJET: Dict[str, str] = {
    "DIARIZATION": "speaker",
    "CHANNEL": "speaker_channel",
    "DECLARED_BY_USER": "speaker_declared",
}

#: Les modules qui porteraient une diarisation. Sondés, jamais supposés.
MODULES_DE_DIARISATION = ("pyannote.audio", "speechbrain")


class SpeakerRefused(ValueError):
    """Une observation de locuteur impossible telle quelle."""


def _module_present(nom: str) -> bool:
    """Dit si un module est importable, sans l'importer."""
    try:
        return importlib.util.find_spec(nom) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def diarization_state() -> Dict[str, Any]:
    """
    L'état de la séparation de locuteurs, mesuré maintenant.

    Returns:
        Les modules cherchés, ceux trouvés, et la raison déclarée quand rien
        n'est trouvé. La raison vient de `creative/voice/scene.py`, qui la
        portait déjà : deux formulations du même blocage finiraient par diverger.
    """
    trouves = [nom for nom in MODULES_DE_DIARISATION if _module_present(nom)]
    return {
        "modules_searched": list(MODULES_DE_DIARISATION),
        "modules_found": trouves,
        "state": "AVAILABLE" if trouves else "ABSENT",
        "declared_reason": CAPACITES_EXTERNES["speaker_diarization"],
        "measured_reason": (
            "" if trouves else
            f"aucun de {list(MODULES_DE_DIARISATION)} n'est importable ici"
        ),
    }


def diarization_observation() -> Observation:
    """
    L'absence — ou la présence — de diarisation, sous forme d'observation.

    Returns:
        Une observation `ABSENT` portant le constat mesuré, ou `MEASURED`
        nommant les modules trouvés. Elle entre dans un `LiveContextState`
        comme n'importe quelle autre : l'état doit porter ce qui lui manque.
    """
    etat = diarization_state()
    if etat["state"] == "ABSENT":
        return absent(subject="diarization", modality="audio",
                      detail=f"{etat['measured_reason']} — "
                             f"{etat['declared_reason']}")
    return Observation(subject="diarization", status=MESURE, modality="audio",
                       value=", ".join(etat["modules_found"]),
                       detail="module de diarisation importable")


def speaker_observation(segment: AudioSegment,
                        source: str = "DIARIZATION") -> Observation:
    """
    Ce qu'on sait du locuteur d'un segment — y compris rien.

    Args:
        segment: Le segment concerné. Son `original_audio_path` voyage dans le
            détail : §11 veut que l'enregistrement reste l'artefact source, et
            une observation qui perd le chemin le rend introuvable.
        source: Une clé de `SOURCES_D_IDENTITE`.

    Returns:
        Une observation `MEASURED` ou `DECLARED` selon la source quand le
        segment porte un locuteur, `UNKNOWN` sinon — et l'inconnue **nomme ce
        qui manque** plutôt que de laisser croire à un silence.

    Raises:
        SpeakerRefused: Si la source n'est pas déclarée.
    """
    if source not in SOURCES_D_IDENTITE:
        raise SpeakerRefused(
            f"Source d'identité « {source} » non déclarée. Déclarées : "
            f"{list(SOURCES_D_IDENTITE)}."
        )
    sujet = _SUJET[source]
    if segment.speaker_id is None:
        etat = diarization_state()
        manque = (etat["measured_reason"] or "aucune identification fournie")
        return unknown(
            subject=sujet, modality="audio",
            detail=(f"segment « {segment.segment_id} » sans locuteur : {manque}. "
                    f"Audio d'origine : {segment.original_audio_path}."),
        )
    detail = f"segment « {segment.segment_id} », audio d'origine : " \
             f"{segment.original_audio_path}"
    if source == "CHANNEL":
        detail += (". Un canal dit d'où vient le son, pas qui parle : trois "
                   "personnes partagent un microphone.")
    return Observation(subject=sujet, status=SOURCES_D_IDENTITE[source],
                       modality="audio", value=segment.speaker_id,
                       detail=detail)


def speaker_observations(segments: Sequence[AudioSegment],
                         source: str = "DIARIZATION") -> List[Observation]:
    """
    Les observations de locuteur d'une suite de segments.

    Args:
        segments: Les segments, dans l'ordre voulu.
        source: La source d'identité commune à ces segments.

    Returns:
        Une observation par segment. Aucune n'est fusionnée avec une autre :
        deux segments portant le même identifiant restent deux observations, et
        `fusion.corroboration()` dira qu'elles concordent sans les réduire.
    """
    return [speaker_observation(segment, source) for segment in segments]


def known_speakers(segments: Sequence[AudioSegment]) -> List[str]:
    """
    Les locuteurs réellement portés par les segments, triés.

    Args:
        segments: Les segments examinés.

    Returns:
        Les identifiants distincts. **Aucun n'est inventé** : un segment sans
        locuteur n'en ajoute pas.
    """
    return sorted({s.speaker_id for s in segments if s.speaker_id is not None})


def turn_taking(segments: Sequence[AudioSegment]) -> Dict[str, Any]:
    """
    Les tours de parole, quand ils sont mesurables.

    Args:
        segments: Les segments, ordonnés par le temps de leur `start`.

    Returns:
        Le nombre de tours et leurs bornes, ou `turns: None` avec
        `state: NOT_MEASURED` quand aucun locuteur n'est connu.

    Note:
        **`None`, jamais `0`.** Zéro tour affirmerait que personne n'a pris la
        parole ; `None` dit que personne n'a compté. La première est une
        affirmation sur la réunion, la seconde sur nous.
    """
    ordonnes = sorted(segments, key=lambda s: s.start)
    etiquetes = [s for s in ordonnes if s.speaker_id is not None]
    if not etiquetes:
        return {
            "turns": None,
            "state": "NOT_MEASURED",
            "speakers": [],
            "reason": ("aucun segment ne porte de locuteur : "
                       + (diarization_state()["measured_reason"]
                          or "aucune identification fournie")),
            "coverage": f"0/{len(ordonnes)} segment(s) étiqueté(s)",
        }

    tours: List[Dict[str, Any]] = []
    for segment in etiquetes:
        if tours and tours[-1]["speaker"] == segment.speaker_id:
            tours[-1]["end"] = segment.end
            tours[-1]["segments"] += 1
            continue
        tours.append({"speaker": segment.speaker_id, "start": segment.start,
                      "end": segment.end, "segments": 1})
    return {
        "turns": len(tours),
        "state": "MEASURED" if len(etiquetes) == len(ordonnes) else "PARTIAL",
        "speakers": known_speakers(etiquetes),
        "reason": "" if len(etiquetes) == len(ordonnes) else (
            f"{len(ordonnes) - len(etiquetes)} segment(s) sans locuteur : les "
            "tours ne couvrent pas tout l'enregistrement"
        ),
        "coverage": f"{len(etiquetes)}/{len(ordonnes)} segment(s) étiqueté(s)",
        "boundaries": tours,
    }


def speakers_view(segments: Sequence[AudioSegment],
                  source: str = "DIARIZATION") -> Dict[str, Any]:
    """
    Ce qu'on sait des locuteurs d'un enregistrement, et ce qu'on n'en sait pas.

    Args:
        segments: Les segments examinés.
        source: La source d'identité.

    Returns:
        Les observations, les locuteurs connus, les tours, et l'état mesuré de
        la diarisation. `speaker_count` vaut `None` quand rien n'est étiqueté —
        pour la même raison que `turns`.
    """
    if source not in SOURCES_D_IDENTITE:
        raise SpeakerRefused(
            f"Source d'identité « {source} » non déclarée. Déclarées : "
            f"{list(SOURCES_D_IDENTITE)}."
        )
    observations = speaker_observations(segments, source)
    connus = known_speakers(segments)
    return {
        "observations": [o.as_dict() for o in observations],
        "known_speakers": connus,
        "speaker_count": len(connus) if connus else None,
        "unlabelled_segments": sum(1 for s in segments if s.speaker_id is None),
        "turn_taking": turn_taking(segments),
        "diarization": diarization_state(),
        "identity_source": source,
        "identity_is_measured": SOURCES_D_IDENTITE[source] == MESURE,
    }


def speakers_report() -> Dict[str, Any]:
    """
    Ce que la couche locuteurs garantit, et ce qu'elle refuse de faire.

    Returns:
        Le vocabulaire, l'état mesuré de la diarisation, et les règles tenues.
    """
    return {
        "identity_sources": {k: v for k, v in SOURCES_D_IDENTITE.items()},
        "diarization": diarization_state(),
        "numbers_speakers": False,
        "rules": [
            "Aucune fonction ne numérote un locuteur : SPEAKER_1 découpé au "
            "hasard a la forme d'une diarisation sans en avoir le contenu.",
            "Un canal n'est pas un locuteur : une identité déduite d'un canal "
            "est DECLARED, jamais MEASURED.",
            "Un segment sans locuteur produit UNKNOWN qui nomme ce qui manque.",
            "Zéro tour de parole n'existe pas : sans locuteur connu, `turns` "
            "vaut None.",
            "Le chemin de l'audio d'origine voyage avec l'observation (§11).",
            "La raison du blocage vient de `creative/voice/scene.py` : deux "
            "formulations du même blocage finiraient par diverger.",
        ],
    }
