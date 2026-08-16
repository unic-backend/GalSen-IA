"""
When each word was said — and the interpolation that must never happen.

Directive §5 forbids cutting in the middle of a spoken word. Obeying it needs
word boundaries, and word boundaries come from the transcriber or they do not
exist. This module holds that "or they do not exist" against the single most
tempting shortcut in the whole engine.

The shortcut: a transcriber returns segments — *"il faut comparer deux
fractions", 4.10 s → 6.30 s* — and the words inside are known but their
individual times are not. It is one line of arithmetic to spread 2.2 seconds
across five words and call the result word timings. Everyone does it. It even
looks right on a waveform.

It is wrong, and it is wrong in the exact place it matters. Real speech is not
uniform: a speaker pauses, stresses, hesitates. An interpolated boundary lands
inside a word about as often as between two, so a cut snapped to it removes half
a syllable. The listener hears it immediately, and the engineer who reads the
code sees timestamps that look measured.

So: `words_from_segments()` extracts word timings **only when the transcriber
supplied them**, and otherwise returns none with the reason. `interpolated=`
exists as an explicit, opt-in argument that marks its output `ESTIMATED`, never
`MEASURED`, so a caller who genuinely wants a rough preview can have one and
`safe_cut_points()` will still refuse to snap to it.

The transcriber itself is not reimplemented here. `src/multimodal/` (VOLET 32)
already owns provider selection and already returns `None` when nothing can
work — and its rule is the one this module inherits: an audio file that cannot
be transcribed is refused **out loud**, never treated as silence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

#: D'où vient un temps de mot. La distinction décide si une coupe peut s'y
#: appuyer : un temps estimé tombe dans un mot aussi souvent qu'entre deux.
MESURE = "MEASURED"
ESTIME = "ESTIMATED"

#: Écart minimal, en secondes, pour qu'un silence entre deux mots soit un point
#: de coupe utilisable. Déclaré, donc discutable : trop court, la coupe rogne
#: une consonne ; trop long, il ne reste aucun point où couper.
SILENCE_MINIMAL = 0.08


class WordTimingUnavailable(RuntimeError):
    """Des temps de mot demandés alors qu'aucun n'a été mesuré."""


@dataclass(frozen=True)
class WordTiming:
    """
    Un mot et l'instant où il a été prononcé.

    Attributes:
        word: Le mot, tel que le transcripteur l'a rendu.
        start: Son début, en secondes.
        end: Sa fin, en secondes.
        source: `MEASURED` ou `ESTIMATED`.
        confidence: La confiance du modèle, si elle est donnée.
    """

    word: str
    start: float
    end: float
    source: str = MESURE
    confidence: Optional[float] = None

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise WordTimingUnavailable(
                f"Mot « {self.word} » : fin {self.end} avant début {self.start}."
            )

    @property
    def is_measured(self) -> bool:
        """Vrai quand le temps vient du transcripteur, pas d'un calcul."""
        return self.source == MESURE

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "word": self.word, "start": self.start, "end": self.end,
            "source": self.source, "confidence": self.confidence,
        }


def words_from_segments(
    segments: Sequence[Dict[str, Any]], interpolate: bool = False,
) -> Dict[str, Any]:
    """
    Extrait les temps de mot des segments, sans jamais les inventer.

    Args:
        segments: Les segments rendus par un transcripteur.
        interpolate: Autorise explicitement une répartition uniforme quand les
            temps par mot manquent. Le résultat est marqué `ESTIMATED` et reste
            refusé par `safe_cut_points()`.

    Returns:
        Les mots avec leurs temps, leur origine, et la raison quand il n'y en a
        pas. Sans temps mesurés et sans demande explicite d'estimation, la liste
        est **vide** : répartir la durée d'un segment sur ses mots produit des
        frontières qui tombent dans un mot aussi souvent qu'entre deux, et la
        coupe qui s'y appuie enlève une demi-syllabe.
    """
    mots: List[WordTiming] = []
    segments_sans_mots = 0

    for segment in segments:
        entrees = segment.get("words") or []
        if entrees:
            for entree in entrees:
                debut, fin = entree.get("start"), entree.get("end")
                texte = str(entree.get("word", "")).strip()
                if texte and debut is not None and fin is not None:
                    mots.append(WordTiming(
                        word=texte, start=float(debut), end=float(fin),
                        source=MESURE, confidence=entree.get("probability"),
                    ))
            continue

        segments_sans_mots += 1
        if not interpolate:
            continue
        mots.extend(_repartir(segment))

    mesures = [mot for mot in mots if mot.is_measured]
    return {
        "words": mots,
        "measured_count": len(mesures),
        "estimated_count": len(mots) - len(mesures),
        "segments_without_word_times": segments_sans_mots,
        "all_measured": bool(mots) and len(mesures) == len(mots),
        "interpolated": interpolate and segments_sans_mots > 0,
        "reason": (
            "Temps par mot fournis par le transcripteur."
            if mots and not (interpolate and segments_sans_mots) else
            "Temps par mot **estimés** par répartition uniforme, à la demande "
            "explicite de l'appelant. Ils ne servent qu'à prévisualiser : une "
            "frontière estimée tombe dans un mot aussi souvent qu'entre deux."
            if interpolate and segments_sans_mots else
            f"{segments_sans_mots} segment(s) sans temps par mot, et aucune "
            "estimation demandée. Répartir la durée d'un segment sur ses mots "
            "produirait des frontières qui se lisent comme des mesures."
        ),
    }


def _repartir(segment: Dict[str, Any]) -> List[WordTiming]:
    """
    Répartit uniformément la durée d'un segment sur ses mots.

    Explicitement demandé, explicitement marqué `ESTIMATED`. La parole réelle
    n'est pas uniforme — un locuteur marque, insiste, hésite — donc ce calcul
    est faux presque partout ; il n'est utile que pour montrer approximativement
    où se trouve une phrase.
    """
    texte = str(segment.get("text", "")).strip()
    debut, fin = segment.get("start"), segment.get("end")
    if not texte or debut is None or fin is None:
        return []

    decoupe = texte.split()
    if not decoupe:
        return []
    pas = (float(fin) - float(debut)) / len(decoupe)
    return [
        WordTiming(
            word=mot,
            start=round(float(debut) + rang * pas, 4),
            end=round(float(debut) + (rang + 1) * pas, 4),
            source=ESTIME,
        )
        for rang, mot in enumerate(decoupe)
    ]


def safe_cut_points(
    words: Sequence[WordTiming], min_silence: float = SILENCE_MINIMAL,
) -> Dict[str, Any]:
    """
    Les instants où une coupe ne traverse aucun mot.

    Args:
        words: Les mots avec leurs temps.
        min_silence: Silence minimal entre deux mots pour qu'une coupe y tienne.

    Returns:
        Les points de coupe sûrs, au milieu de chaque silence assez long, et le
        nombre d'intervalles trop courts. Les points sont rendus **triés**.

    Raises:
        WordTimingUnavailable: Si un seul mot porte un temps estimé. C'est le
            point où l'engrenage se referme : une coupe posée sur une frontière
            estimée enlève une demi-syllabe, et personne en aval ne peut plus
            distinguer ce temps d'un temps mesuré.
    """
    estimes = [mot for mot in words if not mot.is_measured]
    if estimes:
        raise WordTimingUnavailable(
            f"{len(estimes)} mot(s) portent un temps **estimé** "
            f"(« {estimes[0].word} »). Une coupe posée dessus enlève une "
            "demi-syllabe, et rien en aval ne distingue plus ce temps d'une "
            "mesure. Fournir des temps mesurés, ou ne pas couper ici."
        )
    if len(words) < 2:
        return {
            "cut_points": [], "gaps_too_short": 0,
            "reason": (
                f"{len(words)} mot(s) : il n'existe aucun intervalle entre "
                "deux mots où poser une coupe."
            ),
        }

    ordonnes = sorted(words, key=lambda mot: mot.start)
    points: List[float] = []
    trop_courts = 0
    for precedent, suivant in zip(ordonnes, ordonnes[1:]):
        silence = suivant.start - precedent.end
        if silence >= min_silence:
            points.append(round(precedent.end + silence / 2, 4))
        else:
            trop_courts += 1

    return {
        "cut_points": points,
        "gaps_too_short": trop_courts,
        "min_silence": min_silence,
        "reason": (
            f"{len(points)} point(s) de coupe au milieu d'un silence d'au moins "
            f"{min_silence} s ; {trop_courts} intervalle(s) trop court(s)."
        ),
    }


def snap_to_word_boundary(
    time: float, words: Sequence[WordTiming], min_silence: float = SILENCE_MINIMAL,
) -> Dict[str, Any]:
    """
    Ramène un instant voulu au point de coupe sûr le plus proche.

    Args:
        time: L'instant demandé — typiquement décidé par un modèle, qui a le
            droit de dire *où à peu près*, jamais *où exactement*.
        words: Les mots avec leurs temps mesurés.
        min_silence: Silence minimal exigé.

    Returns:
        L'instant retenu, l'écart avec la demande, et si un mot était traversé.
        C'est le partage de la directive §1 rendu exécutable : le modèle décide
        **ce qui reste**, ce module décide **où la coupe peut tomber**.

    Raises:
        WordTimingUnavailable: Sans temps mesurés, ou sans aucun point sûr — un
            repli sur l'instant demandé ferait exactement la coupe que cette
            fonction existe pour empêcher.
    """
    sûrs = safe_cut_points(words, min_silence=min_silence)
    points = sûrs["cut_points"]
    if not points:
        raise WordTimingUnavailable(
            f"Aucun point de coupe sûr : {sûrs['reason']} Se replier sur "
            "l'instant demandé ferait exactement la coupe que cette fonction "
            "existe pour empêcher."
        )

    retenu = min(points, key=lambda point: abs(point - time))
    traverse = next(
        (mot.word for mot in words if mot.start < time < mot.end), None,
    )
    return {
        "requested": time,
        "cut_at": retenu,
        "shift": round(retenu - time, 4),
        "crossed_word": traverse,
        "reason": (
            f"L'instant demandé tombait dans « {traverse} » ; la coupe est "
            f"déplacée de {round(retenu - time, 4)} s vers le silence le plus "
            "proche."
            if traverse else
            "L'instant demandé ne traversait aucun mot ; il est aligné sur le "
            "silence le plus proche."
        ),
    }


def transcribe_media(path: str, language: Optional[str] = None) -> Dict[str, Any]:
    """
    Transcrit un média en réutilisant le registre du VOLET 32.

    Args:
        path: Le fichier, **déjà résolu** par `src/storage/roots.py`.
        language: La langue attendue, si elle est connue.

    Returns:
        Le texte, les segments, les temps de mot mesurés, et le modèle employé.

    Raises:
        WordTimingUnavailable: Quand aucun transcripteur ne peut travailler.
            C'est la règle du VOLET 32, héritée telle quelle : un fichier audio
            qu'on ne peut pas transcrire est refusé **à voix haute**, jamais
            traité comme un silence.
    """
    from ...multimodal.registry import active_transcriber

    fournisseur = active_transcriber()
    if fournisseur is None:
        raise WordTimingUnavailable(
            "Aucun transcripteur actif (VOLET 32). Un fichier audio qu'on ne "
            "peut pas transcrire est refusé à voix haute, jamais traité comme "
            "un silence — une transcription vide se confondrait avec « la "
            "personne n'a rien dit »."
        )

    resultat = fournisseur.transcribe(path, language=language)
    mots = words_from_segments(resultat.segments)
    return {
        "text": resultat.text,
        "language": resultat.language,
        "model": resultat.model_name,
        "segments": list(resultat.segments),
        "words": [mot.as_dict() for mot in mots["words"]],
        "word_timings_measured": mots["all_measured"],
        "word_timing_reason": mots["reason"],
    }


def word_timing_report() -> Dict[str, Any]:
    """
    Ce que les temps de mot garantissent, et ce qu'ils refusent.

    Returns:
        Les origines, le silence minimal, et les règles tenues.
    """
    return {
        "sources": [MESURE, ESTIME],
        "min_silence": SILENCE_MINIMAL,
        "rules": [
            "Un temps de mot vient du transcripteur ou n'existe pas. Répartir "
            "la durée d'un segment sur ses mots produit des frontières qui se "
            "lisent comme des mesures.",
            "La parole n'est pas uniforme : un locuteur marque, insiste, "
            "hésite. Une frontière estimée tombe dans un mot aussi souvent "
            "qu'entre deux.",
            "Une estimation reste possible **sur demande explicite**, marquée "
            "`ESTIMATED`, et `safe_cut_points()` la refuse quand même.",
            "Le modèle décide *ce qui reste* ; ce module décide *où la coupe "
            "peut tomber*. C'est le partage de la directive §1, exécutable.",
            "Sans transcripteur, le fichier est refusé à voix haute : une "
            "transcription vide se confondrait avec « la personne n'a rien "
            "dit ».",
        ],
        "does_not": [
            "Interpoler des temps de mot en silence.",
            "Couper sur une frontière estimée.",
            "Se replier sur l'instant demandé quand aucun point n'est sûr.",
            "Traiter un audio non transcriptible comme un silence.",
        ],
    }


__all__ = [
    "ESTIME",
    "MESURE",
    "SILENCE_MINIMAL",
    "WordTiming",
    "WordTimingUnavailable",
    "safe_cut_points",
    "snap_to_word_boundary",
    "transcribe_media",
    "word_timing_report",
    "words_from_segments",
]
