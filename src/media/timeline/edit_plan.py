"""
The model says what stays. This module says where the cut lands.

Directive §5 states the split and directive §1 explains why: *never let the LLM
invent exact timestamps when deterministic analysis can calculate them.* Every
implementation agrees with that sentence and then breaks it in the same place —
by defining an interface where the model returns `{"start": 4.2, "end": 9.8}`.
Once that shape exists, the rule is a comment. The model will fill those fields,
fluently, and nobody downstream can tell an invented 4.2 from a measured one.

So the interface here has **no shape in which a timestamp can be returned.** A
`Selection` carries a quote and a reason. That is all it can carry. The model
says *keep "il faut comparer deux fractions", it is the thesis of the segment*;
it cannot say when that was said, because there is no field for it. This is the
same closure `pedagogy.explain()` uses in Darra J — a generator that returns only
text has no way to hand back a modified official field.

Locating the quote is then a deterministic problem, and it is solved exactly:

- The quote is matched against the **word sequence**, folded for case and
  punctuation only. No fuzzy matching, no closest span. A near-match would keep
  words the model did not choose while reporting success.
- A quote appearing twice is `AMBIGUOUS` and refused. Picking the first
  occurrence would silently keep a different take than the one that was
  reviewed — the "bad take selection" failure §5 asks to detect, created by the
  editor itself.
- A quote appearing nowhere is `NOT_FOUND`. The model hallucinated a sentence
  that was never said, and that is exactly the thing worth surfacing rather than
  approximating away.

Boundaries come from `words.py`: the cut sits in the silence before the first
word and after the last, never on the word itself.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from ..transcription.words import (
    SILENCE_MINIMAL,
    WordTiming,
    WordTimingUnavailable,
)

#: Ce qu'une sélection peut devenir.
LOCALISE = "LOCATED"
INTROUVABLE = "NOT_FOUND"
AMBIGU = "AMBIGUOUS"

#: Marge laissée autour d'un extrait quand le silence voisin est plus long que
#: nécessaire. Déclarée : sans marge la coupe colle à la parole et s'entend,
#: avec trop de marge elle ramasse le début du mot suivant.
MARGE_MAXIMALE = 0.25


class EditPlanRefused(ValueError):
    """Un montage qui ne peut pas être calculé sur ce qui a été fourni."""


def _replie(texte: str) -> str:
    """
    Ramène un mot à sa forme comparable : sans casse, sans accent, sans ponctuation.

    Le repliement s'arrête là. Il ne supprime pas de lettre, ne réduit pas de
    pluriel et ne rapproche pas deux mots voisins : rendre « fraction » et
    « fractions » identiques ferait garder un mot que personne n'a choisi.
    """
    decompose = unicodedata.normalize("NFKD", str(texte or ""))
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return "".join(
        c for c in sans_accent.casefold() if c.isalnum() or c.isspace()
    ).strip()


@dataclass(frozen=True)
class Selection:
    """
    Ce qu'un modèle demande de garder — et rien d'autre.

    Il n'y a **pas** de champ temporel, et c'est le mécanisme entier de ce
    module. Un modèle ne peut pas inventer un horodatage qu'aucune structure ne
    peut porter.

    Attributes:
        quote: Les mots à conserver, tels qu'ils ont été prononcés.
        reason: Pourquoi les garder. Utile à un relecteur, sans effet sur le
            calcul.
    """

    quote: str
    reason: str = ""

    def __post_init__(self) -> None:
        if not _replie(self.quote):
            raise EditPlanRefused(
                "Sélection vide. Un extrait sans mots ne désigne rien, et "
                "l'accepter produirait un segment de durée arbitraire."
            )


@dataclass(frozen=True)
class Segment:
    """
    Un extrait résolu, avec les temps **calculés** sur les mots.

    Attributes:
        start: Début, en secondes.
        end: Fin, en secondes.
        first_word: Index du premier mot conservé.
        last_word: Index du dernier mot conservé, inclus.
        words: Les mots conservés, dans l'ordre.
        quote: Ce que le modèle avait demandé.
        reason: Sa justification.
    """

    start: float
    end: float
    first_word: int
    last_word: int
    words: Tuple[str, ...]
    quote: str = ""
    reason: str = ""

    @property
    def duration(self) -> float:
        """La durée de l'extrait, en secondes."""
        return round(self.end - self.start, 4)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "start": self.start, "end": self.end, "duration": self.duration,
            "first_word": self.first_word, "last_word": self.last_word,
            "words": list(self.words), "quote": self.quote,
            "reason": self.reason,
        }


def locate_quote(
    quote: str, words: Sequence[WordTiming],
) -> Dict[str, Any]:
    """
    Trouve la suite de mots correspondant **exactement** à une citation.

    Args:
        quote: Les mots demandés.
        words: Les mots transcrits, avec leurs temps mesurés.

    Returns:
        `LOCATED` avec les index, `NOT_FOUND`, ou `AMBIGUOUS` avec toutes les
        occurrences. Aucun rapprochement approché : une correspondance voisine
        garderait des mots que le modèle n'a pas choisis tout en rapportant un
        succès.
    """
    cible = _replie(quote).split()
    if not cible:
        return {"status": INTROUVABLE, "reason": "Citation vide."}

    suite = [_replie(mot.word) for mot in words]
    occurrences = [
        depart for depart in range(len(suite) - len(cible) + 1)
        if suite[depart:depart + len(cible)] == cible
    ]

    if not occurrences:
        return {
            "status": INTROUVABLE, "quote": quote, "occurrences": [],
            "reason": (
                "Cette suite de mots n'apparaît pas dans la transcription. Le "
                "modèle a cité une phrase qui n'a jamais été dite — c'est "
                "précisément ce qu'il faut faire remonter, pas approximer."
            ),
        }
    if len(occurrences) > 1:
        return {
            "status": AMBIGU, "quote": quote, "occurrences": occurrences,
            "reason": (
                f"Cette suite apparaît {len(occurrences)} fois. Prendre la "
                "première garderait en silence une autre prise que celle qui a "
                "été relue — c'est le défaut de « mauvaise prise » que la "
                "directive §5 demande de détecter, fabriqué par le monteur "
                "lui-même."
            ),
        }

    depart = occurrences[0]
    return {
        "status": LOCALISE, "quote": quote,
        "first_word": depart, "last_word": depart + len(cible) - 1,
        "occurrences": occurrences,
    }


def _bornes(
    words: Sequence[WordTiming], premier: int, dernier: int,
    min_silence: float, marge: float,
) -> Tuple[float, float, List[str]]:
    """
    Les temps de coupe autour d'un extrait, posés dans les silences voisins.

    La coupe ne tombe jamais sur un mot : elle se place dans le silence qui
    précède le premier mot et dans celui qui suit le dernier, à une marge bornée
    pour ne pas ramasser le mot d'à côté.

    Returns:
        Le début, la fin, et les bords dont le silence voisin est **plus court
        que `min_silence`**. Ces bords-là sont ceux qui rognent une consonne :
        la coupe reste techniquement entre deux mots, mais si près de la parole
        qu'elle s'entend. Les signaler avant le rendu vaut mieux que de les
        retrouver après, dans la transcription du fichier fini.
    """
    debut_mot = words[premier].start
    fin_mot = words[dernier].end
    serres: List[str] = []

    if premier == 0:
        debut = debut_mot
    else:
        silence = max(debut_mot - words[premier - 1].end, 0.0)
        debut = debut_mot - min(silence / 2, marge)
        if silence < min_silence:
            serres.append("start")

    if dernier == len(words) - 1:
        fin = fin_mot
    else:
        silence = max(words[dernier + 1].start - fin_mot, 0.0)
        fin = fin_mot + min(silence / 2, marge)
        if silence < min_silence:
            serres.append("end")

    return round(max(debut, 0.0), 4), round(fin, 4), serres


def build_plan(
    selections: Sequence[Selection],
    words: Sequence[WordTiming],
    min_silence: float = SILENCE_MINIMAL,
    margin: float = MARGE_MAXIMALE,
) -> Dict[str, Any]:
    """
    Résout des sélections en segments, avec des temps calculés sur les mots.

    Args:
        selections: Ce que le modèle demande de garder.
        words: Les mots transcrits avec leurs temps **mesurés**.
        min_silence: Silence minimal considéré comme utilisable.
        margin: Marge maximale prise dans un silence voisin.

    Returns:
        Les segments retenus dans l'ordre de la source, ceux qui n'ont pas pu
        l'être **avec leur raison**, et la durée totale.

    Raises:
        EditPlanRefused: Sans mot, ou si un mot porte un temps estimé. Monter
            sur des temps estimés produit des coupes au milieu des mots, et rien
            en aval ne les distingue de coupes mesurées.
    """
    if not words:
        raise EditPlanRefused(
            "Aucun mot transcrit : il n'existe aucune frontière sur laquelle "
            "poser une coupe. Un montage calculé ici le serait sur du vide."
        )
    estimes = [mot for mot in words if not mot.is_measured]
    if estimes:
        raise WordTimingUnavailable(
            f"{len(estimes)} mot(s) portent un temps estimé (« "
            f"{estimes[0].word} »). Monter dessus produit des coupes au milieu "
            "des mots, indistinguables de coupes mesurées."
        )

    segments: List[Segment] = []
    refusees: List[Dict[str, Any]] = []
    bords_serres: List[Dict[str, Any]] = []

    for selection in selections:
        localisation = locate_quote(selection.quote, words)
        if localisation["status"] != LOCALISE:
            refusees.append({
                "quote": selection.quote,
                "status": localisation["status"],
                "reason": localisation["reason"],
                "occurrences": localisation.get("occurrences", []),
            })
            continue

        premier, dernier = localisation["first_word"], localisation["last_word"]
        debut, fin, serres = _bornes(words, premier, dernier, min_silence, margin)
        segments.append(Segment(
            start=debut, end=fin, first_word=premier, last_word=dernier,
            words=tuple(mot.word for mot in words[premier:dernier + 1]),
            quote=selection.quote, reason=selection.reason,
        ))
        if serres:
            bords_serres.append({
                "quote": selection.quote, "edges": serres,
                "reason": (
                    f"Silence voisin plus court que {min_silence} s. La coupe "
                    "reste entre deux mots, mais si près de la parole qu'elle "
                    "s'entend — c'est ce bord-là qui rogne une consonne."
                ),
            })

    # Remis dans l'ordre de la source : un modèle peut citer dans le désordre,
    # et monter dans cet ordre-là produirait un discours réarrangé que personne
    # n'a demandé.
    segments.sort(key=lambda segment: segment.first_word)

    return {
        "segments": [segment.as_dict() for segment in segments],
        "objects": segments,
        "refused": refusees,
        "kept_words": sum(len(segment.words) for segment in segments),
        "source_words": len(words),
        "total_duration": round(sum(s.duration for s in segments), 4),
        "overlaps": _chevauchements(segments),
        "tight_boundaries": bords_serres,
        "note": (
            "Les temps sont **calculés** sur les mots transcrits. Aucune "
            "sélection ne porte d'horodatage : la structure n'en a pas de "
            "champ, donc un modèle ne peut pas en inventer un."
        ),
    }


def _chevauchements(segments: Sequence[Segment]) -> List[Dict[str, Any]]:
    """
    Les segments qui se recouvrent.

    Rapportés, jamais fusionnés : deux extraits qui se chevauchent veulent
    généralement dire que le modèle a cité deux fois la même chose, et les
    fondre effacerait la question au lieu de la poser.
    """
    trouves: List[Dict[str, Any]] = []
    for precedent, suivant in zip(segments, segments[1:]):
        if suivant.first_word <= precedent.last_word:
            trouves.append({
                "first": precedent.quote, "second": suivant.quote,
                "reason": (
                    "Ces extraits se recouvrent. Ils sont rapportés et non "
                    "fusionnés : les fondre effacerait la question au lieu de "
                    "la poser."
                ),
            })
    return trouves


def intended_transcript(plan: Dict[str, Any]) -> str:
    """
    Le texte que le montage **devrait** produire.

    Args:
        plan: Le plan rendu par `build_plan`.

    Returns:
        Les mots conservés, dans l'ordre de la source. C'est la référence contre
        laquelle le rendu final sera comparé (§5) : sans elle, « vérifier le
        montage » n'a pas d'objet de comparaison.
    """
    return " ".join(
        mot for segment in plan["objects"] for mot in segment.words
    )


def edit_plan_report() -> Dict[str, Any]:
    """
    Ce que le plan de montage garantit, et ce qu'il refuse.

    Returns:
        Les états de localisation et les règles tenues.
    """
    return {
        "location_states": [LOCALISE, INTROUVABLE, AMBIGU],
        "max_margin": MARGE_MAXIMALE,
        "rules": [
            "Une sélection porte une **citation**, jamais un temps : la "
            "structure n'a pas de champ temporel, donc un modèle ne peut pas "
            "en inventer un.",
            "La citation est retrouvée par correspondance **exacte** de la "
            "suite de mots. Un rapprochement approché garderait des mots que "
            "le modèle n'a pas choisis en rapportant un succès.",
            "Une citation qui apparaît deux fois est `AMBIGUOUS` : prendre la "
            "première garderait une autre prise que celle qui a été relue.",
            "Une citation introuvable est rapportée telle quelle — le modèle a "
            "cité une phrase jamais dite, et c'est ce qu'il faut faire "
            "remonter.",
            "Les coupes tombent dans les silences voisins, jamais sur un mot.",
            "Les segments sont remis dans l'ordre de la source : monter dans "
            "l'ordre des citations produirait un discours réarrangé.",
            "Un bord dont le silence voisin est trop court est **signalé avant "
            "le rendu** : la coupe reste entre deux mots mais s'entend, et le "
            "retrouver après coup dans la transcription du fichier fini coûte "
            "un rendu entier.",
        ],
        "does_not": [
            "Accepter un horodatage venant d'un modèle.",
            "Rapprocher une citation d'une suite de mots voisine.",
            "Choisir entre deux occurrences identiques.",
            "Fusionner deux extraits qui se recouvrent.",
            "Monter sur des temps de mot estimés.",
        ],
    }
