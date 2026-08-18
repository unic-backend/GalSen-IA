"""
Une conversation qui change de langue en cours de phrase (C13, §25).

## Ce que §25 demande, et pourquoi c'est structurel

« Ne pas supposer qu'un enregistrement ne contient qu'une seule langue. » À
Dakar, une phrase commence en wolof, prend un mot français, revient au wolof. Un
champ `langue` au niveau du fichier force un choix qui est faux pour la moitié
de l'enregistrement, et **tout ce qui est en aval hérite de l'erreur** : le
sous-titre, la recherche, la voix, l'analyse.

Ce module ne détecte rien. Il **structure** ce que quelqu'un d'autre a mesuré :
les segments arrivent déjà étiquetés, et il en tire les points de bascule, les
plages homogènes et les langues en présence.

## La ligne à ne pas franchir

L'alternance **à l'intérieur** d'un segment n'est pas observable ici. La
détecter demanderait un alignement mot à mot, donc une transcription — et la
transcription est indisponible sur cette machine (sonde `transcription`
mesurée). Un module qui la rapporterait quand même produirait des points de
bascule inventés, à des instants inventés.

Elle est donc rapportée `UNKNOWN`, avec ce qui la débloquerait. §33 en fait la
réponse correcte, pas une réponse dégradée : les segments viennent d'une
segmentation dont personne n'a garanti qu'elle coupe aux frontières de langue.

## Une bascule n'est pas un défaut

Rien ici ne « corrige » une alternance, ne choisit une langue dominante, ni ne
signale un enregistrement mixte comme un problème à résoudre. L'alternance
codique est une façon de parler, pas une erreur de saisie.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from ..voice.scene import (
    CONFIANCE_FAIBLE,
    INCONNU,
    AudioSegment,
    VoiceSceneRefused,
)

#: L'alternance intra-segment : jamais observée ici, et nommée pour que son
#: absence ne se lise pas comme une absence d'alternance.
INTRA_SEGMENT_INCONNU = "UNKNOWN"


@dataclass(frozen=True)
class LanguageSpan:
    """
    Une suite de segments consécutifs dans la même langue.

    Attributes:
        language: La langue de la plage, ou `None` si elle est inconnue — une
            suite de segments non identifiés est une plage, elle aussi.
        start: Début de la plage, en secondes.
        end: Fin de la plage.
        segment_ids: Les segments qu'elle couvre, dans l'ordre.
        speakers: Les locuteurs qui y parlent, quand ils sont connus.
        lowest_confidence: La plus faible confiance rencontrée. C'est elle qui
            qualifie la plage : une plage n'est pas plus sûre que son maillon
            le moins sûr.
    """

    language: Optional[str]
    start: float
    end: float
    segment_ids: List[str]
    speakers: List[str]
    lowest_confidence: Optional[float] = None

    @property
    def duration(self) -> float:
        """La durée de la plage."""
        return round(self.end - self.start, 4)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "language": self.language, "start": self.start, "end": self.end,
            "duration": self.duration, "segment_ids": list(self.segment_ids),
            "speakers": list(self.speakers),
            "lowest_confidence": self.lowest_confidence,
        }


@dataclass(frozen=True)
class LanguageSwitch:
    """
    Le passage d'une langue à une autre, entre deux segments.

    Attributes:
        at: L'instant de la bascule — la fin du segment précédent, mesurée.
        from_language: La langue quittée, ou `None`.
        to_language: La langue prise, ou `None`.
        from_segment: Le segment quitté.
        to_segment: Le segment pris.
        same_speaker: Vrai si la même personne bascule. C'est la distinction
            utile : une bascule chez un même locuteur est de l'alternance
            codique, deux locuteurs de langues différentes n'en sont pas.
        confident: Faux dès qu'une des deux identifications est faible ou
            absente. Une bascule fondée sur une langue identifiée à 0,3 est une
            bascule supposée.
    """

    at: float
    from_language: Optional[str]
    to_language: Optional[str]
    from_segment: str
    to_segment: str
    same_speaker: bool
    confident: bool

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "at": self.at, "from_language": self.from_language,
            "to_language": self.to_language, "from_segment": self.from_segment,
            "to_segment": self.to_segment, "same_speaker": self.same_speaker,
            "confident": self.confident,
        }


def _ordonner(segments: Sequence[AudioSegment]) -> List[AudioSegment]:
    """Trie les segments et refuse une entrée vide."""
    if not segments:
        raise VoiceSceneRefused(
            "Aucun segment : il n'y a pas d'alternance dans le silence."
        )
    return sorted(segments, key=lambda segment: segment.start)


def language_spans(segments: Sequence[AudioSegment]) -> List[LanguageSpan]:
    """
    Regroupe les segments consécutifs partageant une langue.

    Args:
        segments: Les segments, étiquetés par qui les a mesurés.

    Returns:
        Les plages homogènes, dans l'ordre du temps. Les segments sans langue
        forment leurs propres plages : les fondre dans la plage voisine
        étendrait une langue à de la parole que personne n'a identifiée.
    """
    plages: List[LanguageSpan] = []
    courant: List[AudioSegment] = []

    def fermer() -> None:
        """Referme la plage en cours, si elle existe."""
        if not courant:
            return
        confiances = [s.language_confidence for s in courant
                      if s.language_confidence is not None]
        plages.append(LanguageSpan(
            language=courant[0].language,
            start=courant[0].start,
            end=courant[-1].end,
            segment_ids=[s.segment_id for s in courant],
            speakers=sorted({s.speaker_id for s in courant if s.speaker_id}),
            lowest_confidence=min(confiances) if confiances else None,
        ))

    for segment in _ordonner(segments):
        if courant and segment.language == courant[0].language:
            courant.append(segment)
            continue
        fermer()
        courant = [segment]
    fermer()
    return plages


def detect_switches(segments: Sequence[AudioSegment]) -> List[LanguageSwitch]:
    """
    Les points où la langue change, entre segments.

    Args:
        segments: Les segments étiquetés.

    Returns:
        Une entrée par bascule. Un passage vers ou depuis une langue inconnue
        **est** une bascule : l'ignorer ferait croire à une continuité de langue
        à travers de la parole que personne n'a identifiée.
    """
    ordonnes = _ordonner(segments)
    bascules = []
    for precedent, suivant in zip(ordonnes, ordonnes[1:]):
        if precedent.language == suivant.language:
            continue
        incertains = (CONFIANCE_FAIBLE, INCONNU)
        sur = (precedent.language_state not in incertains
               and suivant.language_state not in incertains)
        bascules.append(LanguageSwitch(
            at=precedent.end,
            from_language=precedent.language,
            to_language=suivant.language,
            from_segment=precedent.segment_id,
            to_segment=suivant.segment_id,
            same_speaker=(
                precedent.speaker_id is not None
                and precedent.speaker_id == suivant.speaker_id
            ),
            confident=sur,
        ))
    return bascules


def switching_report(segments: Sequence[AudioSegment]) -> Dict[str, Any]:
    """
    Ce que l'enregistrement fait de ses langues.

    Args:
        segments: Les segments étiquetés.

    Returns:
        Les plages, les bascules, les langues rencontrées — et l'aveu explicite
        que l'alternance **à l'intérieur** d'un segment n'a pas été regardée.

        Il n'y a délibérément **pas** de « langue dominante » ni de « langue du
        fichier ». Les calculer inviterait à s'en servir, et §25 refuse
        exactement cette réduction : la langue appartient au segment.
    """
    ordonnes = _ordonner(segments)
    plages = language_spans(ordonnes)
    bascules = detect_switches(ordonnes)
    langues = sorted({s.language for s in ordonnes if s.language})
    supposees = [b for b in bascules if not b.confident]
    intra_locuteur = [b for b in bascules if b.same_speaker]

    return {
        "spans": [p.as_dict() for p in plages],
        "switches": [b.as_dict() for b in bascules],
        "languages": langues,
        "code_switching": len(langues) > 1,
        "switch_count": len(bascules),
        "assumed_switches": [b.as_dict() for b in supposees],
        "same_speaker_switches": [b.as_dict() for b in intra_locuteur],
        "segments_without_language": [
            s.segment_id for s in ordonnes if s.language is None
        ],
        "intra_segment_switching": INTRA_SEGMENT_INCONNU,
        "intra_segment_reason": (
            "Une bascule à l'intérieur d'un segment demanderait un alignement "
            "mot à mot, donc une transcription — indisponible ici (sonde "
            "`transcription`). La rapporter quand même produirait des instants "
            "de bascule inventés."
        ),
        "note": (
            "Aucune « langue dominante » n'est calculée, et l'enregistrement "
            "n'a pas de langue à lui : §25 fait de la langue une propriété du "
            "segment, et un champ au niveau du fichier est faux pour la moitié "
            "d'une conversation dakaroise. Une alternance n'est pas un défaut "
            "à corriger — c'est une façon de parler."
        ),
    }
