"""
Mesurer une réponse contre ses passages, sans modèle (VOLET 36, chapitre C).

Deux mesures existaient déjà et aucune ne dit si une **réponse** est vraie :
`citations.py` compte les éléments qui portent une source, et
`src/training/evaluation.py` mesure le taux de rappel de la recherche. Une
réponse pouvait donc afficher une couverture de citations de 100 % en affirmant
des choses qu'aucun passage cité ne dit.

## Ce que ce module mesure, et ce qu'il ne mesure pas

Il mesure ce qui est **mécanique** — donc disponible aujourd'hui, C1 encore
fermé, et surtout **indépendant du modèle qui a répondu**. Un évaluateur qui
demanderait au modèle s'il a eu raison ne mesurerait que sa confiance en
lui-même.

| Mesure | Ici |
|---|---|
| Affirmations non étayées | **comptées**, une par une |
| Justesse des citations | vérifiée : le passage cité porte-t-il l'affirmation |
| Justesse factuelle | **non** — demande un jeu de référence et un modèle |
| Contradiction entre sources | **non** — voir `MESURES_INDISPONIBLES` |
| Calibration de l'incertitude | partiellement : répondre sans aucun passage est mesurable |

## Le soutien est lexical, et le mot compte

« Étayée » veut dire ici : **les termes de l'affirmation se retrouvent dans le
passage**. Ce n'est pas de l'inférence. Une affirmation vraie écrite avec
d'autres mots que sa source sera comptée non étayée, et c'est le sens voulu —
une réponse qui reformule au point que sa source ne se reconnaît plus n'est pas
vérifiable par un lecteur non plus.

L'inverse est le vrai danger : une affirmation **contredisant** son passage
partage presque tous ses mots avec lui. Un score de recouvrement seul la
déclarerait étayée. La polarité est donc comparée séparément, et un désaccord de
polarité rend `DISPUTED` — jamais `SUPPORTED`. C'est une heuristique étroite qui
attrape la négation, pas un moteur d'implication : elle est là pour que le
module ne puisse pas *affirmer* qu'une contradiction est étayée.
"""

import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional

from src.text_normalization import normalize_token, tokenize

from .knowledge_indexer import InMemoryKnowledgeIndexer

#: Part des termes d'une affirmation qui doivent se retrouver dans un passage
#: pour la dire étayée. Assez haut pour qu'une phrase qui partage deux mots
#: banals avec un passage ne passe pas ; assez bas pour tolérer une
#: reformulation partielle.
SEUIL_DE_SOUTIEN = 0.6

#: En dessous de ce nombre de termes utiles, une affirmation n'est pas évaluable :
#: « C'est exact. » n'a rien à comparer, et lui donner un verdict ferait un
#: chiffre là où il n'y a pas de mesure.
TERMES_MINIMUM = 3

#: Marques de négation en français. Retirées des mots vides pour cette mesure :
#: la liste de l'indexeur écarte « pas », ce qui est juste pour une recherche et
#: faux ici — c'est précisément le mot qui distingue une affirmation de son
#: contraire.
MARQUEURS_DE_NEGATION = frozenset({
    "ne", "n", "pas", "plus", "jamais", "aucun", "aucune", "ni", "non", "rien",
})

#: Mots vides de la mesure de soutien : ceux de l'indexeur, moins les négations.
#: Réutiliser la liste existante évite deux listes qui divergeraient ; la
#: soustraction porte sa raison ci-dessus.
MOTS_VIDES = frozenset(InMemoryKnowledgeIndexer.STOP_WORDS) - MARQUEURS_DE_NEGATION

#: Ce que ce module **ne sait pas** mesurer, avec la raison. Un rapport qui ne
#: montrerait que les mesures disponibles laisserait croire qu'une réponse
#: étayée est une réponse vraie.
MESURES_INDISPONIBLES = {
    "factual_correctness": (
        "Demande un jeu de référence d'affirmations attendues. Le jeu sénégalais "
        "existe mais ne porte aucune entrée vérifiée — voir `senegal-facts.jsonl`."
    ),
    "contradiction_handling": (
        "Demande de comparer deux passages entre eux, pas une affirmation à un "
        "passage. Mesurable mécaniquement seulement pour la négation."
    ),
    "source_relevance": (
        "« Le passage parle-t-il de la question » demande une mesure sémantique ; "
        "le recouvrement lexical répond à une autre question."
    ),
}

#: Fin de phrase. Découpage volontairement simple : le module compte des
#: affirmations approximatives et le dit, plutôt que d'embarquer un analyseur.
_FIN_DE_PHRASE = re.compile(r"(?<=[.!?])\s+")


class ClaimVerdict(Enum):
    """
    Ce qu'on peut dire d'une affirmation face aux passages retenus.

    `DISPUTED` n'est pas `UNSUPPORTED` : la première dit « un passage parle de
    cela et dit le contraire », la seconde « aucun passage n'en parle ». Les
    confondre ferait disparaître le cas le plus grave dans le plus banal.
    """

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    DISPUTED = "disputed"
    NOT_ASSESSABLE = "not_assessable"


@dataclass(frozen=True)
class ClaimAssessment:
    """
    Le verdict porté sur une affirmation, et sur quoi il repose.

    Attributes:
        claim: L'affirmation, telle qu'écrite dans la réponse.
        verdict: Le verdict.
        score: Part des termes de l'affirmation retrouvés dans le meilleur passage.
        passage: Référence du passage le mieux placé, s'il y en a un.
    """

    claim: str
    verdict: ClaimVerdict
    score: float = 0.0
    passage: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le verdict."""
        return {
            "claim": self.claim,
            "verdict": self.verdict.value,
            "score": self.score,
            "passage": self.passage,
        }


def _texte_de(passage: Any) -> str:
    """Retourne le texte d'un passage, qu'il soit une chaîne ou une connaissance."""
    if isinstance(passage, str):
        return passage
    for champ in ("content", "text", "prompt_text"):
        valeur = getattr(passage, champ, None)
        if valeur:
            return str(valeur)
    if isinstance(passage, Mapping):
        for champ in ("content", "text", "prompt_text"):
            if passage.get(champ):
                return str(passage[champ])
    return ""


def _reference_de(passage: Any, rang: int) -> str:
    """
    Nomme un passage pour qu'un verdict puisse être remonté à sa source.

    Un verdict qui ne dit pas sur quel passage il porte oblige à relire toute la
    réponse pour le vérifier.
    """
    if isinstance(passage, Mapping):
        for champ in ("id", "title", "source"):
            if passage.get(champ):
                return str(passage[champ])
    if isinstance(passage, str):
        # Une chaîne n'a pas de provenance — et `str.title` est une méthode :
        # la lire comme un champ rendrait une référence absurde au lieu du rang.
        return f"passage #{rang}"
    for champ in ("id", "title"):
        valeur = getattr(passage, champ, None)
        if valeur:
            return str(valeur)
    source = getattr(passage, "source", None)
    for champ in ("title", "url", "location"):
        valeur = getattr(source, champ, None)
        if valeur:
            return str(valeur)
    return f"passage #{rang}"


def lexical_terms(texte: str) -> List[str]:
    """
    Découpe un texte en termes comparables, négations conservées.

    Publique parce que la détection de contradictions (VOLET 35, ch. 09) compare
    les mêmes termes que la mesure de soutien : deux découpages différents
    diraient « étayé » ici et « contradictoire » là pour le même couple.
    """
    return tokenize(texte, MOTS_VIDES)


def carries_negation(termes: Iterable[str]) -> bool:
    """Indique si un texte porte une négation."""
    normalises = {normalize_token(terme) for terme in MARQUEURS_DE_NEGATION}
    return any(terme in normalises for terme in termes)


def split_claims(answer: str) -> List[str]:
    """
    Découpe une réponse en affirmations.

    **Une phrase n'est pas une affirmation** : une phrase peut en porter deux, et
    deux phrases peuvent n'en porter qu'une. Le découpage est une approximation
    assumée — le rapport donne le nombre d'affirmations trouvées pour qu'un
    lecteur voie ce qui a été compté.
    """
    if not answer or not answer.strip():
        return []
    phrases = (phrase.strip() for phrase in _FIN_DE_PHRASE.split(answer.strip()))
    return [phrase for phrase in phrases if phrase]


def assess_claim(claim: str, passages: Iterable[Any]) -> ClaimAssessment:
    """
    Confronte une affirmation aux passages retenus.

    Args:
        claim: L'affirmation à évaluer.
        passages: Les passages retenus — connaissances, dictionnaires ou chaînes.

    Returns:
        Le verdict, le score de recouvrement et le passage le mieux placé.
        Une affirmation trop courte pour être comparée rend `NOT_ASSESSABLE`
        plutôt qu'un verdict inventé.
    """
    termes_affirmation = lexical_terms(claim)
    utiles = [terme for terme in termes_affirmation if terme not in MARQUEURS_DE_NEGATION]
    if len(utiles) < TERMES_MINIMUM:
        return ClaimAssessment(claim=claim, verdict=ClaimVerdict.NOT_ASSESSABLE)

    negation_affirmation = carries_negation(termes_affirmation)
    meilleur_score = 0.0
    meilleure_reference: Optional[str] = None
    conteste = False

    for rang, passage in enumerate(passages, start=1):
        termes_passage = set(lexical_terms(_texte_de(passage)))
        if not termes_passage:
            continue
        recouvrement = sum(1 for terme in utiles if terme in termes_passage) / len(utiles)
        if recouvrement <= meilleur_score:
            continue
        meilleur_score = recouvrement
        meilleure_reference = _reference_de(passage, rang)
        # La polarité se compare sur le passage retenu, pas sur l'ensemble :
        # c'est celui-là qu'on dirait « portant » l'affirmation.
        conteste = carries_negation(termes_passage) != negation_affirmation

    score = round(meilleur_score, 4)
    if meilleur_score < SEUIL_DE_SOUTIEN:
        return ClaimAssessment(claim, ClaimVerdict.UNSUPPORTED, score, meilleure_reference)
    if conteste:
        return ClaimAssessment(claim, ClaimVerdict.DISPUTED, score, meilleure_reference)
    return ClaimAssessment(claim, ClaimVerdict.SUPPORTED, score, meilleure_reference)


def evaluate_answer(answer: str, passages: Iterable[Any]) -> Dict[str, Any]:
    """
    Mesure une réponse entière contre les passages qui devaient la porter.

    Returns:
        Le compte d'affirmations, celles qui sont étayées, la liste **complète**
        de celles qui ne le sont pas, et `unavailable` — ce que cette mesure ne
        sait pas faire. Répondre alors qu'aucun passage n'a été retenu est
        signalé à part : c'est le cas où une réponse fluide est le plus
        trompeuse.
    """
    retenus = list(passages)
    affirmations = split_claims(answer)
    verdicts = [assess_claim(affirmation, retenus) for affirmation in affirmations]

    evaluables = [v for v in verdicts if v.verdict is not ClaimVerdict.NOT_ASSESSABLE]
    etayees = [v for v in evaluables if v.verdict is ClaimVerdict.SUPPORTED]

    return {
        "claims": len(affirmations),
        "assessable": len(evaluables),
        "supported": len(etayees),
        # Une base vide ne rend pas 100 % : sans affirmation évaluable, il n'y a
        # pas de taux, et un 1.0 par défaut ferait passer le vide pour un
        # sans-faute.
        "support_rate": round(len(etayees) / len(evaluables), 4) if evaluables else 0.0,
        "unsupported": [v.to_dict() for v in evaluables if v.verdict is ClaimVerdict.UNSUPPORTED],
        "disputed": [v.to_dict() for v in evaluables if v.verdict is ClaimVerdict.DISPUTED],
        "passages": len(retenus),
        "answered_without_sources": bool(affirmations) and not retenus,
        "support_threshold": SEUIL_DE_SOUTIEN,
        "unavailable": dict(MESURES_INDISPONIBLES),
    }


def citation_correctness(cited: Mapping[str, Iterable[Any]]) -> Dict[str, Any]:
    """
    Vérifie que chaque source citée porte réellement ce qu'on lui fait dire.

    Args:
        cited: Une affirmation, et les passages cités **pour elle**.

    Returns:
        Le compte de citations justes, et la liste des fautives avec leur
        verdict. Une citation qui contredit l'affirmation apparaît comme
        `disputed`, pas comme absente : ce n'est pas la même faute.
    """
    erreurs: List[Dict[str, Any]] = []
    total = 0
    justes = 0

    for affirmation, passages in cited.items():
        for rang, passage in enumerate(list(passages), start=1):
            total += 1
            verdict = assess_claim(affirmation, [passage])
            if verdict.verdict is ClaimVerdict.SUPPORTED:
                justes += 1
                continue
            entree = verdict.to_dict()
            entree["passage"] = verdict.passage or _reference_de(passage, rang)
            erreurs.append(entree)

    return {
        "citations": total,
        "correct": justes,
        "rate": round(justes / total, 4) if total else 0.0,
        "errors": erreurs,
    }


# ----------------------------------------------------------------------
# Le jeu de référence sénégalais
# ----------------------------------------------------------------------

#: Jeu de référence, relatif à la racine du dépôt.
BENCHMARK_SET = os.path.join("docs", "evaluation", "senegal-facts.jsonl")

#: Une entrée est notable, ou elle attend sa source. Rien d'autre.
VERIFIED = "verified"
TO_SOURCE = "to_source"


class BenchmarkRefused(ValueError):
    """On a demandé de noter une entrée qui n'est pas notable."""


@dataclass(frozen=True)
class BenchmarkEntry:
    """
    Une entrée du jeu de référence.

    Attributes:
        question: La question posée.
        status: `verified` — adossée à un document que le projet détient — ou
            `to_source`, qui décrit la **forme** de la réponse attendue et le
            **type** de source qui la trancherait, sans jamais l'écrire.
        expected_shape: Ce à quoi ressemblerait une réponse juste.
        source_type: L'institution qui ferait autorité (ANSD, ISRA, ministère…).
        expected_claims: Les affirmations attendues — seulement pour `verified`.
        source: Le document qui l'établit — seulement pour `verified`.
    """

    question: str
    status: str = TO_SOURCE
    expected_shape: str = ""
    source_type: str = ""
    expected_claims: tuple = ()
    source: str = ""

    @property
    def scorable(self) -> bool:
        """Indique si cette entrée peut servir à noter une réponse."""
        return self.status == VERIFIED and bool(self.expected_claims) and bool(self.source)

    @classmethod
    def from_dict(cls, donnees: Mapping[str, Any]) -> "BenchmarkEntry":
        """Lit une entrée depuis sa forme JSON."""
        return cls(
            question=str(donnees.get("question", "")).strip(),
            status=str(donnees.get("status", TO_SOURCE)).strip().lower(),
            expected_shape=str(donnees.get("expected_shape", "")).strip(),
            source_type=str(donnees.get("source_type", "")).strip(),
            expected_claims=tuple(donnees.get("expected_claims", ()) or ()),
            source=str(donnees.get("source", "")).strip(),
        )


def _racine() -> str:
    """Retourne la racine du dépôt."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_benchmark(chemin: Optional[str] = None) -> List[BenchmarkEntry]:
    """
    Charge le jeu de référence sénégalais.

    Un fichier absent rend une liste vide. Une ligne illisible est écartée, pas
    devinée : une entrée de référence approximative fausse toutes les mesures
    qu'elle sert.
    """
    cible = chemin or os.path.join(_racine(), BENCHMARK_SET)
    entrees: List[BenchmarkEntry] = []
    if not os.path.isfile(cible):
        return entrees
    with open(cible, "r", encoding="utf-8") as fichier:
        for ligne in fichier:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("//"):
                continue
            try:
                donnees = json.loads(ligne)
            except ValueError:
                continue
            entree = BenchmarkEntry.from_dict(donnees)
            if entree.question:
                entrees.append(entree)
    return entrees


def score_entry(entry: BenchmarkEntry, answer: str, passages: Iterable[Any]) -> Dict[str, Any]:
    """
    Note une réponse contre une entrée du jeu de référence.

    Raises:
        BenchmarkRefused: Si l'entrée n'est pas vérifiée. **C'est le cœur du
            chapitre** : une entrée écrite de mémoire, sans document derrière,
            transformerait chaque mesure future en mesure de cette mémoire. Une
            entrée `to_source` décrit ce qu'il faudrait aller chercher ; elle ne
            note rien.
    """
    if not entry.scorable:
        raise BenchmarkRefused(
            f"L'entrée « {entry.question} » n'est pas notable (statut « {entry.status} ») : "
            "elle attend un document qui l'établisse. Une entrée sans source ne "
            "mesure que ce que quelqu'un a cru se rappeler."
        )

    rapport = evaluate_answer(answer, passages)
    attendues = [
        assess_claim(attendue, [answer]).verdict is ClaimVerdict.SUPPORTED
        for attendue in entry.expected_claims
    ]
    rapport["expected_claims"] = len(attendues)
    rapport["expected_claims_found"] = sum(attendues)
    rapport["source"] = entry.source
    return rapport


def benchmark_report(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Décrit le jeu de référence tel qu'il est réellement.

    Le nombre d'entrées vérifiées est publié **même quand il vaut 0** — et il
    vaut 0 tant que le dépôt ne détient aucun document sénégalais. L'état vide
    est l'état honnête ; le cacher ferait croire qu'une mesure existe.
    """
    entrees = load_benchmark(chemin)
    notables = [entree for entree in entrees if entree.scorable]
    a_sourcer = [entree for entree in entrees if not entree.scorable]
    return {
        "file": BENCHMARK_SET,
        "entries": len(entrees),
        "verified": len(notables),
        "to_source": len(a_sourcer),
        "scorable": len(notables),
        "source_types": sorted({entree.source_type for entree in a_sourcer if entree.source_type}),
        "note": (
            "Les entrées « to_source » ne notent rien : elles nomment la question et "
            "le type de source qui la trancherait. Une entrée écrite de mémoire "
            "mesurerait cette mémoire, pas la plateforme."
        ),
    }
