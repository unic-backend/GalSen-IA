"""
A spoken request turned into a production plan — without filling in what was
never said.

Directive §25 gives four sentences a user might say and asks that GalSen AI
turn them into a structured production plan. The failure mode is not parsing;
it is **completion**. A request that says nothing about duration gets 60
seconds, one that says nothing about the domain gets "marketing" because that is
the first structure in the table, and the plan that comes back describes a video
nobody asked for — convincingly, with a duration and a structure, so nobody
questions it until the delivery.

So an unstated field is `UNSPECIFIED` and produces a **question**, never a
default. This is the shape Darra J already reached: incomplete coordinates
answer `CLARIFICATION_REQUIRED` rather than resolving to the nearest record.

Two domains in one sentence — "turn this **interview** into a
**documentary**" — are not an error and not a coin toss. The target is read
from a **declared** marker (`into`, `en`, `vers`…), the other domain is kept as
the source material, and when no marker settles it the request is reported
ambiguous with both candidates. A declared rule can be argued with; a heuristic
that silently picks the first match cannot.

And the request is text (§30). The *intent* of a user's own sentence is
trusted — that is what `TrustLevel.USER` means. Anything it quotes from the
media it describes is not: a filename, a subtitle line or a metadata field
saying "ignore the previous instructions" is a caption, and it is inspected and
reported rather than obeyed or quietly stripped. Stripping it would destroy the
evidence that someone tried.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ...security.trust import inspect as inspect_trust
from ..story.structures import STRUCTURES
from .catalog import plan_chain

#: Ce qu'une demande n'a pas dit. Ce n'est pas une valeur par défaut en
#: attente : c'est une question à poser.
NON_PRECISE = "UNSPECIFIED"

#: Plusieurs lectures possibles, aucune retenue.
AMBIGU = "AMBIGUOUS"

#: Les états d'une demande analysée.
PLAN_PRET = "PLAN_READY"
CLARIFICATION_REQUISE = "CLARIFICATION_REQUIRED"

#: Les termes qui désignent un domaine narratif, par domaine déclaré dans
#: `src/media/story/structures.py`. Ils sont comparés **par mots entiers** :
#: chercher une sous-chaîne ferait reconnaître « pub » dans « publication ».
TERMES_DE_DOMAINE: Dict[str, Tuple[str, ...]] = {
    "marketing": ("publicité", "pub", "promo", "marketing", "commercial",
                  "advert", "advertisement", "spot"),
    "social": ("réseaux sociaux", "tiktok", "instagram", "reel", "reels",
               "short", "shorts", "social"),
    "documentary": ("documentaire", "documentary", "reportage"),
    "education": ("cours", "leçon", "lesson", "pédagogique", "éducatif",
                  "educational", "tutoriel", "tutorial"),
    "news": ("journal", "actualité", "actualités", "news", "bulletin"),
    "interview": ("interview", "entretien"),
    "sports_analysis": ("football", "match", "sport", "sports",
                        "analyse sportive", "sports analysis"),
    "scientific": ("scientifique", "scientific", "étude", "recherche",
                   "research"),
}

#: Les marqueurs qui désignent la **cible** d'une transformation. Déclarés,
#: donc discutables — c'est ce qui les sépare d'une heuristique.
MARQUEURS_DE_CIBLE = ("into", "en un", "en une", "en ", "vers", "transformer en",
                      "make it a", "turn it into", "convert to")

#: Fenêtre, en caractères, dans laquelle un marqueur désigne le domaine qui le
#: suit. Au-delà, « into » et le domaine appartiennent à deux propositions
#: différentes et le lien serait imaginaire.
FENETRE_DE_CIBLE = 40

#: Les formats de diffusion nommables dans une demande.
TERMES_DE_FORMAT = {
    "9:16": ("vertical", "verticale", "9:16", "tiktok", "reel", "reels",
             "short", "shorts", "story", "stories"),
    "16:9": ("horizontal", "horizontale", "16:9", "paysage", "landscape",
             "youtube"),
    "1:1": ("carré", "carrée", "1:1", "square"),
}

#: Les langues qu'une demande peut nommer, alignées sur le moteur de
#: sous-titres — nommer une langue qu'il ne connaît pas produirait un plan
#: irréalisable.
TERMES_DE_LANGUE = {
    "fr": ("français", "french", "en français"),
    "en": ("anglais", "english", "in english"),
    "wo": ("wolof",),
    "ar": ("arabe", "arabic", "العربية"),
}


class IntentRefused(ValueError):
    """Une demande qui ne peut pas être analysée telle qu'elle est écrite."""


@dataclass(frozen=True)
class ProductionRequest:
    """
    Une demande analysée : ce qui a été dit, et ce qui ne l'a pas été.

    Attributes:
        text: La demande, **conservée telle quelle**.
        domain: Le domaine narratif visé, `UNSPECIFIED` ou `AMBIGUOUS`.
        source_domains: Les domaines qui décrivent la matière d'origine.
        duration_seconds: La durée demandée, `None` si elle n'a pas été dite.
        aspect: Le format de diffusion, `UNSPECIFIED` s'il n'a pas été dit.
        language: La langue demandée, `UNSPECIFIED` si elle n'a pas été dite.
        candidates: Les domaines en concurrence, quand rien ne les départage.
        suspicions: Les motifs relevés dans la demande (§30).
    """

    text: str
    domain: str = NON_PRECISE
    source_domains: Tuple[str, ...] = ()
    duration_seconds: Optional[float] = None
    aspect: str = NON_PRECISE
    language: str = NON_PRECISE
    candidates: Tuple[str, ...] = ()
    suspicions: Tuple[str, ...] = field(default=())

    @property
    def is_resolved(self) -> bool:
        """Vrai quand un domaine narratif a été établi, pas deviné."""
        return self.domain in STRUCTURES

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences comprises."""
        return {
            "text": self.text, "domain": self.domain,
            "source_domains": list(self.source_domains),
            "duration_seconds": self.duration_seconds,
            "aspect": self.aspect, "language": self.language,
            "candidates": list(self.candidates),
            "suspicions": list(self.suspicions),
            "resolved": self.is_resolved,
        }


def _mots(texte: str) -> List[str]:
    """Les mots d'un texte, repliés pour la comparaison."""
    return re.findall(r"[\wàâäçéèêëîïôöùûüÿñæœ']+", (texte or "").lower())


def _contient(texte_replie: str, mots: Sequence[str], terme: str) -> bool:
    """
    Indique si un terme apparaît, **par mots entiers**.

    Un terme composé est cherché dans le texte replié ; un terme simple est
    cherché dans la liste des mots. Chercher une sous-chaîne ferait reconnaître
    « pub » dans « publication » et « sport » dans « transport » — l'erreur de
    rapprochement approximatif que ce dépôt a déjà payée.
    """
    if " " in terme:
        return terme in texte_replie
    return terme in mots


def _domaines_cites(texte: str) -> Dict[str, int]:
    """Les domaines nommés dans la demande, avec la position de leur terme."""
    replie = " ".join(_mots(texte))
    mots = _mots(texte)
    trouves: Dict[str, int] = {}
    for domaine, termes in TERMES_DE_DOMAINE.items():
        for terme in termes:
            if _contient(replie, mots, terme):
                position = replie.find(terme)
                if domaine not in trouves or position < trouves[domaine]:
                    trouves[domaine] = position
    return trouves


def _cible(texte: str, domaines: Dict[str, int]) -> Tuple[str, Tuple[str, ...]]:
    """
    Départage un domaine cible d'un domaine source.

    Returns:
        Le domaine visé et ceux qui décrivent la matière. Quand aucun marqueur
        déclaré ne tranche, la cible reste `AMBIGUOUS` : choisir le premier
        terme rencontré donnerait un documentaire à qui demandait une interview.
    """
    if not domaines:
        return NON_PRECISE, ()
    if len(domaines) == 1:
        return next(iter(domaines)), ()

    replie = " ".join(_mots(texte))
    apres_marqueur = [
        domaine for domaine, position in domaines.items()
        if any(marqueur in replie[max(0, position - FENETRE_DE_CIBLE):position]
               for marqueur in MARQUEURS_DE_CIBLE)
    ]
    if len(apres_marqueur) == 1:
        cible = apres_marqueur[0]
        return cible, tuple(sorted(d for d in domaines if d != cible))

    return AMBIGU, ()


def _duree(texte: str) -> Optional[float]:
    """
    La durée demandée, en secondes, ou `None`.

    `None` n'est pas « une minute ». Une durée inventée ici décide du montage
    entier, et personne en aval ne saura qu'elle a été inventée.
    """
    replie = " ".join(_mots(texte))
    secondes = re.search(
        r"\b(\d+(?:[.,]\d+)?)\s*(?:secondes?|seconds?|sec|s)\b", replie)
    if secondes:
        return float(secondes.group(1).replace(",", "."))
    minutes = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:minutes?|min|mn)\b", replie)
    if minutes:
        return float(minutes.group(1).replace(",", ".")) * 60
    return None


def _terme_declare(texte: str, table: Dict[str, Tuple[str, ...]]) -> str:
    """La seule valeur nommée par la demande, ou `UNSPECIFIED` / `AMBIGUOUS`."""
    replie = " ".join(_mots(texte))
    mots = _mots(texte)
    trouves = [
        cle for cle, termes in table.items()
        if any(_contient(replie, mots, terme) for terme in termes)
    ]
    if len(trouves) == 1:
        return trouves[0]
    return AMBIGU if trouves else NON_PRECISE


def parse_request(text: str) -> ProductionRequest:
    """
    Analyse une demande en langage naturel (§25).

    Args:
        text: La phrase de l'utilisateur.

    Returns:
        Ce que la demande a **dit**, et rien d'autre. Chaque champ non dit vaut
        `UNSPECIFIED` et deviendra une question : une durée par défaut décide du
        montage entier, et personne en aval ne saura qu'elle a été inventée.

    Raises:
        IntentRefused: Sur une demande vide. Analyser le vide produirait un plan
            complet appuyé sur rien.
    """
    if not str(text or "").strip():
        raise IntentRefused(
            "Demande vide : il n'y a rien à analyser. Un plan construit ici "
            "serait complet et n'appuierait sur rien."
        )

    domaines = _domaines_cites(text)
    domaine, sources = _cible(text, domaines)

    return ProductionRequest(
        text=text.strip(),
        domain=domaine,
        source_domains=sources,
        duration_seconds=_duree(text),
        aspect=_terme_declare(text, TERMES_DE_FORMAT),
        language=_terme_declare(text, TERMES_DE_LANGUE),
        candidates=tuple(sorted(domaines)) if domaine == AMBIGU else (),
        # La demande est inspectée, jamais nettoyée : effacer le passage
        # suspect ferait disparaître la preuve de la tentative.
        suspicions=tuple(inspect_trust(text)),
    )


#: Les questions posées pour chaque champ resté sans réponse. Écrites une fois,
#: pour qu'elles soient les mêmes quel que soit l'appelant.
QUESTIONS = {
    "domain": (
        "Quel type de production ? Les structures déclarées sont "
        f"{sorted(STRUCTURES)}. Aucune n'est appliquée par défaut : forcer une "
        "structure sur une demande qui n'en nomme aucune produit une vidéo qui "
        "suit un plan que personne n'a choisi (§6)."
    ),
    "duration_seconds": (
        "Quelle durée ? Elle décide du montage entier ; une durée choisie ici "
        "ne se distinguerait plus d'une durée demandée."
    ),
    "aspect": (
        "Quel format de diffusion ? Il décide du cadrage de chaque incrustation "
        "(§22)."
    ),
}


def clarifications(request: ProductionRequest) -> List[Dict[str, str]]:
    """
    Les questions à poser avant de produire quoi que ce soit.

    Args:
        request: La demande analysée.

    Returns:
        Une question par champ non résolu, avec la raison pour laquelle il ne
        peut pas être choisi à la place de l'utilisateur.
    """
    questions: List[Dict[str, str]] = []

    if request.domain == AMBIGU:
        questions.append({
            "field": "domain", "state": AMBIGU,
            "candidates": ", ".join(request.candidates),
            "question": (
                f"La demande nomme plusieurs domaines ({', '.join(request.candidates)}) "
                "et aucun marqueur ne dit lequel est visé. Lequel est la cible ?"
            ),
        })
    elif not request.is_resolved:
        questions.append({"field": "domain", "state": NON_PRECISE,
                          "question": QUESTIONS["domain"]})

    if request.duration_seconds is None:
        questions.append({"field": "duration_seconds", "state": NON_PRECISE,
                          "question": QUESTIONS["duration_seconds"]})

    if request.aspect in (NON_PRECISE, AMBIGU):
        questions.append({"field": "aspect", "state": request.aspect,
                          "question": QUESTIONS["aspect"]})

    return questions


#: L'enchaînement d'outils proposé selon ce que la production demande. Il est
#: **vérifié** par le catalogue avant d'être rendu : proposer un ordre
#: impossible ferait échouer la chaîne trois étapes plus loin.
CHAINE_PAR_DEFAUT = (
    "analyze_media", "transcribe_media", "detect_scenes", "create_storyboard",
    "create_edit_plan", "generate_subtitles", "select_music", "render_video",
    "inspect_video", "export_video",
)


def production_plan(
    text: str, available: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Transforme une demande en plan de production structuré (§25).

    Args:
        text: La demande en langage naturel.
        available: Ce qui existe déjà, typiquement `("media",)`.

    Returns:
        Le plan, ou `CLARIFICATION_REQUIRED` avec les questions à poser.

        **Aucune chaîne d'outils n'est proposée tant qu'une question reste
        ouverte.** Un plan complet appuyé sur des champs devinés est plus
        dangereux qu'une question : il se lit comme une décision prise.
    """
    demande = parse_request(text)
    questions = clarifications(demande)
    disponibles = list(available or ["media", "project"])

    resultat: Dict[str, Any] = {
        "request": demande.as_dict(),
        "status": CLARIFICATION_REQUISE if questions else PLAN_PRET,
        "clarifications": questions,
        "trust": {
            "level": "user",
            "suspicions": list(demande.suspicions),
            "note": (
                "L'intention d'une demande utilisateur est de confiance ; ce "
                "qu'elle **cite** du média ne l'est pas. Les motifs relevés "
                "sont rapportés et le texte est conservé tel quel : l'effacer "
                "ferait disparaître la preuve de la tentative (§30)."
            ),
        },
    }

    if questions:
        resultat["chain"] = None
        resultat["note"] = (
            f"{len(questions)} question(s) ouverte(s). Aucune chaîne n'est "
            "proposée : un plan complet appuyé sur des champs devinés se lit "
            "comme une décision prise."
        )
        return resultat

    chaine = plan_chain(CHAINE_PAR_DEFAUT, disponibles)
    resultat["chain"] = chaine
    resultat["structure"] = STRUCTURES[demande.domain]["roles"]
    resultat["note"] = (
        "Plan structuré à partir de ce que la demande a dit. L'ordre des outils "
        "est **vérifié** par le catalogue, et les outils listés dans `blocked` "
        "attendent une capacité, pas une décision."
    )
    return resultat


def intent_report() -> Dict[str, Any]:
    """
    Ce que l'analyse de demande garantit, et ce qu'elle refuse.

    Returns:
        Les domaines reconnus, les marqueurs déclarés, et les règles tenues.
    """
    return {
        "domains": sorted(TERMES_DE_DOMAINE),
        "target_markers": list(MARQUEURS_DE_CIBLE),
        "states": [PLAN_PRET, CLARIFICATION_REQUISE],
        "rules": [
            "Un champ non dit vaut `UNSPECIFIED` et devient une **question** : "
            "une durée par défaut décide du montage entier, et personne en aval "
            "ne saura qu'elle a été inventée.",
            "Deux domaines dans une phrase sont départagés par un marqueur "
            "**déclaré**, ou rapportés ambigus. Un marqueur déclaré se "
            "conteste ; une heuristique silencieuse, non.",
            "Les termes sont comparés **par mots entiers** : « pub » n'est pas "
            "dans « publication », « sport » n'est pas dans « transport ».",
            "Aucune chaîne d'outils n'est proposée tant qu'une question reste "
            "ouverte.",
            "La demande est **inspectée** (§30) et conservée telle quelle : "
            "effacer un passage suspect ferait disparaître la preuve.",
        ],
        "does_not": [
            "Choisir une structure narrative quand la demande n'en nomme aucune.",
            "Choisir une durée quand la demande n'en donne pas.",
            "Trancher entre deux domaines sans marqueur.",
            "Nettoyer une demande suspecte.",
        ],
    }
