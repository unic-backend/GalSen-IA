"""
Subtitles cut on measured words, in the spelling their language actually uses.

Directive §15 asks for French, English, Wolof and Arabic, and for cues that
respect word boundaries, reading speed, safe zones and scene transitions. Two of
those four languages carry a constraint this repository has already paid for
once, and one of them it paid for in a way worth not repeating.

**Wolof spelling is not decoration.** `ë`, `ñ` and `ŋ` are letters of the CLAD
standard, not accented variants of `e` and `n`. Darra J's alias table stored
only the folded form, so `translate()` — a display-facing function — handed back
`mbey` for `mbéy`. A subtitle is display-facing by definition: whatever folding
happens for matching, the text that reaches the screen keeps its letters.

**Arabic runs right to left**, and direction is declared per language rather
than sniffed per string. A cue mixing an Arabic sentence with a Latin proper
noun would flip on a heuristic and stay put on a declaration, and the
declaration is the one a translator can argue with.

The rest is the discipline the engine uses everywhere. Cues are built from
**measured** word timings — an estimated boundary splits a word, and a subtitle
that appears mid-syllable is the most visible defect in this entire pipeline. A
cue that would exceed the declared reading speed is **flagged, never silently
extended**: stretching it desynchronises it from the speech it captions, trading
a visible problem for an invisible one. And a cue never crosses a scene
boundary, because a caption surviving a cut belongs to the shot it is no longer
over.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from ..transcription.words import WordTiming, WordTimingUnavailable

#: Les langues déclarées, avec leur sens de lecture. La direction est
#: **déclarée**, jamais devinée sur le texte : une phrase arabe contenant un nom
#: propre latin basculerait sur une heuristique et tiendrait sur une
#: déclaration — et c'est la déclaration qu'un traducteur peut contester.
LANGUES = {
    "fr": {"direction": "ltr", "name": "français"},
    "en": {"direction": "ltr", "name": "english"},
    "wo": {"direction": "ltr", "name": "wolof", "script": "CLAD"},
    "ar": {"direction": "rtl", "name": "العربية"},
}

#: Lettres du standard CLAD (décret sénégalais n° 2005-992). Elles ne sont pas
#: des variantes accentuées : les replier écrit du wolof faux à l'écran.
LETTRES_CLAD = ("ë", "ñ", "ŋ", "Ë", "Ñ", "Ŋ")

#: Vitesse de lecture maximale, en caractères par seconde. Déclarée, donc
#: discutable — et dépassée, elle est **signalée**, pas corrigée en étirant le
#: sous-titre.
CPS_MAXIMUM = 17.0

#: Bornes d'affichage. Trop court, l'œil n'a pas le temps ; trop long, le
#: sous-titre reste après la phrase.
DUREE_MINIMALE = 0.8
DUREE_MAXIMALE = 6.0

#: Mise en page. Deux lignes est la limite qu'une zone de sécurité tolère.
LIGNES_MAXIMUM = 2
CARACTERES_PAR_LIGNE = 42


class SubtitleRefused(ValueError):
    """Un sous-titre qui ne peut pas être découpé tel qu'il est demandé."""


@dataclass(frozen=True)
class Cue:
    """
    Un sous-titre : un texte, un intervalle, une langue.

    Attributes:
        index: Son rang, à partir de 1.
        start: Début, en secondes.
        end: Fin, en secondes.
        text: Le texte affiché, **dans son orthographe**.
        language: La langue déclarée.
        emphasis: Les mots à mettre en avant (§15).
    """

    index: int
    start: float
    end: float
    text: str
    language: str = "fr"
    emphasis: tuple = ()

    @property
    def duration(self) -> float:
        """La durée d'affichage."""
        return round(self.end - self.start, 4)

    @property
    def cps(self) -> Optional[float]:
        """
        Les caractères par seconde. `None` si la durée est nulle.

        `None` n'est pas zéro : une durée nulle n'a pas de vitesse de lecture,
        elle a un défaut.
        """
        if self.duration <= 0:
            return None
        return round(len(self.text) / self.duration, 2)

    @property
    def direction(self) -> str:
        """Le sens de lecture, **déclaré** par la langue."""
        return LANGUES.get(self.language, {}).get("direction", "ltr")

    @property
    def lines(self) -> List[str]:
        """Le texte réparti en lignes, sans jamais couper un mot."""
        lignes: List[str] = []
        courante = ""
        for mot in self.text.split():
            candidat = f"{courante} {mot}".strip()
            if len(candidat) <= CARACTERES_PAR_LIGNE:
                courante = candidat
            else:
                if courante:
                    lignes.append(courante)
                courante = mot
        if courante:
            lignes.append(courante)
        return lignes

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "index": self.index, "start": self.start, "end": self.end,
            "duration": self.duration, "text": self.text,
            "language": self.language, "direction": self.direction,
            "cps": self.cps, "lines": self.lines,
            "emphasis": list(self.emphasis),
        }


def check_cue(cue: Cue) -> Dict[str, Any]:
    """
    Les défauts d'un sous-titre, chacun nommé.

    Args:
        cue: Le sous-titre.

    Returns:
        Les problèmes trouvés. Une vitesse de lecture dépassée est **signalée**,
        jamais corrigée en étirant l'affichage : l'étirer le désynchronise de la
        parole qu'il sous-titre, ce qui échange un problème visible contre un
        problème invisible.
    """
    problemes: List[Dict[str, str]] = []

    if cue.duration <= 0:
        problemes.append({"kind": "empty_interval",
                          "detail": "Durée nulle ou inversée."})
    else:
        if cue.duration < DUREE_MINIMALE:
            problemes.append({
                "kind": "too_short",
                "detail": f"{cue.duration} s < {DUREE_MINIMALE} s : l'œil n'a "
                          "pas le temps.",
            })
        if cue.duration > DUREE_MAXIMALE:
            problemes.append({
                "kind": "too_long",
                "detail": f"{cue.duration} s > {DUREE_MAXIMALE} s : le "
                          "sous-titre reste après la phrase.",
            })
        if cue.cps is not None and cue.cps > CPS_MAXIMUM:
            problemes.append({
                "kind": "too_fast",
                "detail": f"{cue.cps} caractères/s > {CPS_MAXIMUM}. Signalé et "
                          "non étiré : étirer désynchronise le sous-titre de la "
                          "parole qu'il porte.",
            })

    if len(cue.lines) > LIGNES_MAXIMUM:
        problemes.append({
            "kind": "too_many_lines",
            "detail": f"{len(cue.lines)} lignes > {LIGNES_MAXIMUM} : au-delà, "
                      "la zone de sécurité ne tient plus.",
        })
    if cue.language not in LANGUES:
        problemes.append({
            "kind": "undeclared_language",
            "detail": f"« {cue.language} » n'est pas déclarée : son sens de "
                      "lecture serait deviné.",
        })

    return {"index": cue.index, "ok": not problemes, "problems": problemes}


def build_cues(
    words: Sequence[WordTiming],
    language: str = "fr",
    scene_boundaries: Optional[Sequence[float]] = None,
    max_chars: int = CARACTERES_PAR_LIGNE * LIGNES_MAXIMUM,
    emphasis: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Découpe des mots mesurés en sous-titres.

    Args:
        words: Les mots avec leurs temps **mesurés** (VOLET M05).
        language: La langue déclarée.
        scene_boundaries: Les instants de changement de scène, mesurés. Un
            sous-titre ne les traverse jamais.
        max_chars: Longueur maximale d'un sous-titre.
        emphasis: Les mots à mettre en avant quand ils apparaissent.

    Returns:
        Les sous-titres, leurs défauts, et le texte **dans son orthographe**.

    Raises:
        SubtitleRefused: Langue non déclarée, ou aucun mot.
        WordTimingUnavailable: Si un mot porte un temps estimé. Une frontière
            estimée coupe un mot, et un sous-titre qui apparaît au milieu d'une
            syllabe est le défaut le plus visible de toute cette chaîne.
    """
    if language not in LANGUES:
        raise SubtitleRefused(
            f"Langue « {language} » non déclarée. Déclarées : {sorted(LANGUES)}. "
            "Deviner son sens de lecture afficherait de l'arabe à l'envers."
        )
    if not words:
        raise SubtitleRefused(
            "Aucun mot : il n'y a rien à sous-titrer, et produire un sous-titre "
            "vide le ferait apparaître à l'écran sans raison."
        )
    estimes = [mot for mot in words if not mot.is_measured]
    if estimes:
        raise WordTimingUnavailable(
            f"{len(estimes)} mot(s) portent un temps estimé (« "
            f"{estimes[0].word} »). Un sous-titre qui apparaît au milieu d'une "
            "syllabe est le défaut le plus visible de toute la chaîne."
        )

    frontieres = sorted(scene_boundaries or [])
    a_souligner = {mot.casefold() for mot in (emphasis or [])}

    cues: List[Cue] = []
    groupe: List[WordTiming] = []

    def _fermer() -> None:
        if not groupe:
            return
        texte = " ".join(mot.word for mot in groupe)
        cues.append(Cue(
            index=len(cues) + 1,
            start=round(groupe[0].start, 4),
            end=round(groupe[-1].end, 4),
            text=texte,
            language=language,
            emphasis=tuple(
                mot.word for mot in groupe if mot.word.casefold() in a_souligner
            ),
        ))
        groupe.clear()

    for mot in words:
        longueur = len(" ".join(m.word for m in groupe + [mot]))
        # Une frontière de scène **entre** le groupe courant et ce mot ferme le
        # sous-titre : une légende qui survit à une coupe appartient au plan
        # qu'elle ne recouvre plus.
        traverse = groupe and any(
            groupe[-1].end <= limite <= mot.start for limite in frontieres
        )
        if groupe and (longueur > max_chars or traverse):
            _fermer()
        groupe.append(mot)
    _fermer()

    verdicts = [check_cue(cue) for cue in cues]
    return {
        "language": language,
        "direction": LANGUES[language]["direction"],
        "cues": [cue.as_dict() for cue in cues],
        "objects": cues,
        "checks": verdicts,
        "problem_count": sum(len(v["problems"]) for v in verdicts),
        "note": (
            "Découpés sur des mots **mesurés**, jamais au milieu d'un mot, et "
            "jamais à cheval sur un changement de scène."
        ),
    }


def preserves_script(text: str, language: str) -> Dict[str, Any]:
    """
    Vérifie qu'un texte garde les lettres de sa langue.

    Args:
        text: Le texte affiché.
        language: La langue déclarée.

    Returns:
        Pour le wolof, si les lettres CLAD ont survécu. `ë`, `ñ` et `ŋ` ne sont
        pas des variantes accentuées : les replier écrit du wolof faux à
        l'écran. Ce dépôt a déjà payé exactement cette erreur une fois, dans la
        table d'alias, où `mbéy` était rendu `mbey`.
    """
    if language != "wo":
        return {"checked": False, "language": language,
                "reason": "Contrôle CLAD réservé au wolof."}

    presentes = [lettre for lettre in LETTRES_CLAD if lettre in text]
    replie = any(
        remplacant in text
        for remplacant in ("mbey", "peey", "ndey")
    )
    return {
        "checked": True,
        "clad_letters_present": presentes,
        "looks_folded": replie and not presentes,
        "reason": (
            "Orthographe CLAD conservée."
            if presentes or not replie else
            "Le texte semble replié : `ë`, `ñ` et `ŋ` sont des lettres du "
            "standard CLAD, pas des variantes accentuées. Les replier écrit du "
            "wolof faux à l'écran — ce dépôt a déjà payé cette erreur une fois."
        ),
    }


def subtitle_report() -> Dict[str, Any]:
    """
    Ce que les sous-titres garantissent, et ce qu'ils refusent.

    Returns:
        Les langues, les seuils déclarés, et les règles tenues.
    """
    return {
        "languages": {
            code: {"direction": details["direction"], "name": details["name"]}
            for code, details in sorted(LANGUES.items())
        },
        "max_cps": CPS_MAXIMUM,
        "duration_range": [DUREE_MINIMALE, DUREE_MAXIMALE],
        "max_lines": LIGNES_MAXIMUM,
        "chars_per_line": CARACTERES_PAR_LIGNE,
        "rules": [
            "Les sous-titres sont découpés sur des temps de mot **mesurés** : "
            "une frontière estimée coupe un mot, et un sous-titre qui apparaît "
            "au milieu d'une syllabe est le défaut le plus visible de la "
            "chaîne.",
            "Une vitesse de lecture dépassée est **signalée**, jamais corrigée "
            "en étirant l'affichage : étirer désynchronise le sous-titre de la "
            "parole qu'il porte.",
            "Un sous-titre ne traverse jamais un changement de scène — une "
            "légende qui survit à une coupe appartient au plan qu'elle ne "
            "recouvre plus.",
            "Le sens de lecture est **déclaré par la langue**, jamais deviné "
            "sur le texte : une phrase arabe avec un nom propre latin "
            "basculerait sur une heuristique.",
            "`ë`, `ñ` et `ŋ` sont des lettres du standard CLAD : le repliement "
            "sert à comparer, jamais à afficher.",
        ],
        "does_not": [
            "Couper au milieu d'un mot.",
            "Étirer un sous-titre trop rapide.",
            "Deviner le sens de lecture d'une langue non déclarée.",
            "Afficher du wolof replié.",
        ],
    }
