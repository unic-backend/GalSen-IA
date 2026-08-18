"""
Mesurer avant d'entraîner (VOLET 33, ch. 02).

Sans jeu d'évaluation, un modèle affiné est **une impression**. C'est le mode
d'échec que `.claude/rules/verification.md` nomme : un résultat plausible là où
un statut était dû. Un entraînement dont personne ne peut dire s'il a aidé sera
gardé parce qu'il a coûté cher, pas parce qu'il vaut mieux.

Ce module fournit le **barème**, pas le contenu — et la distinction est la
raison d'être du fichier.

## Ce qui est mesuré ici, et pourquoi c'est ce qu'il fallait mesurer d'abord

Le **taux de récupération** : pour une question dont on connaît la source,
est-ce que la base rend bien ce passage ? Cette mesure a trois propriétés que
rien d'autre n'a à ce stade :

- elle **ne demande aucun jugement humain** — le passage attendu est là ou non ;
- elle **ne demande aucun modèle de génération**, donc elle tourne aujourd'hui,
  alors que le critère C1 est encore ouvert ;
- c'est exactement le score qui dira si le modèle d'embeddings affiné du
  VOLET 27 vaut mieux que sa base. C'est le premier entraînement prévu, et
  celui-ci est son juge.

## Ce qui n'est pas fait ici, et ne doit pas l'être

Aucune question agricole ou sanitaire sur le Sénégal n'est écrite dans ce dépôt
avec sa réponse. Fabriquer un jeu d'évaluation, c'est fabriquer la vérité contre
laquelle on se mesure : le modèle apprendrait à satisfaire une invention. Le jeu
sénégalais se construit **à partir de l'usage réel** — les questions posées, les
corrections reçues (ch. 01) — et se déclare dans un fichier JSONL versionné.
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

DEFAULT_SET = os.path.join("docs", "evaluation", "retrieval.jsonl")


@dataclass
class EvalCase:
    """Une question, et ce qu'on attend qu'elle retrouve."""

    question: str
    expected_source: str
    language: str = "fr"
    tags: List[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, donnees: Dict[str, Any]) -> "EvalCase":
        """Construit un cas depuis une ligne du fichier."""
        return cls(
            question=donnees["question"],
            expected_source=donnees["expected_source"],
            language=donnees.get("language", "fr"),
            tags=donnees.get("tags", []),
            notes=donnees.get("notes", ""),
        )


@dataclass
class EvalResult:
    """Ce qu'une évaluation a mesuré."""

    cases: int = 0
    hits: int = 0
    misses: List[Dict[str, Any]] = field(default_factory=list)
    by_language: Dict[str, Dict[str, int]] = field(default_factory=dict)
    method: str = ""
    ran_at: float = field(default_factory=time.time)

    @property
    def hit_rate(self) -> float:
        """Taux de récupération ; 0.0 sur un jeu vide, jamais 1.0."""
        return round(self.hits / self.cases, 4) if self.cases else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat, pour un manifeste d'entraînement."""
        return {
            "cases": self.cases,
            "hits": self.hits,
            "hit_rate": self.hit_rate,
            "method": self.method,
            # Les langues sont rendues **séparément** : une moyenne cacherait
            # qu'un modèle s'est amélioré en français en se dégradant en wolof.
            "by_language": {
                langue: {**compte, "hit_rate": round(compte["hits"] / compte["cases"], 4)}
                for langue, compte in self.by_language.items() if compte["cases"]
            },
            "misses": self.misses[:20],
            "ran_at": self.ran_at,
        }


def load_cases(chemin: Optional[str] = None) -> List[EvalCase]:
    """
    Charge le jeu d'évaluation depuis un fichier JSONL.

    Args:
        chemin: Fichier de cas ; `docs/evaluation/retrieval.jsonl` par défaut.

    Returns:
        Les cas déclarés. Un fichier absent rend une liste vide — et une liste
        vide fait rendre un taux de 0, jamais de 1 : un jeu vide n'est pas un
        sans-faute.
    """
    cible = chemin or os.path.join(_racine(), DEFAULT_SET)
    if not os.path.isfile(cible):
        return []

    cas = []
    with open(cible, "r", encoding="utf-8") as fichier:
        for ligne in fichier:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("//"):
                continue
            try:
                cas.append(EvalCase.from_dict(json.loads(ligne)))
            except (ValueError, KeyError):
                # Une ligne malformée est écartée, pas devinée : un cas
                # d'évaluation approximatif fausse la mesure qu'il sert.
                continue
    return cas


def _racine() -> str:
    """Retourne la racine du dépôt."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def evaluate_retrieval(
    rechercher: Callable[[str], Iterable[Any]],
    cases: Optional[List[EvalCase]] = None,
    method: str = "",
    top_k: int = 5,
    neutraliser_popularite: bool = True,
) -> EvalResult:
    """
    Mesure le taux de récupération sur le jeu d'évaluation.

    **Mesurer ne doit pas déplacer ce qu'on mesure.** Chercher incrémente le
    compteur de consultations, qui alimente le critère de popularité du
    classement : une même base, mesurée deux fois, ne rend pas le même score.
    Constaté sur le corpus du dépôt — 0,4 sur une base neuve, 0,5 après quelques
    passages, sans qu'une ligne de code ait changé. Un barème qui dérive à
    l'usage ne peut arbitrer aucun entraînement.

    `neutraliser_popularite` coupe donc le compteur le temps de la mesure.

    Args:
        rechercher: Fonction `(question) -> éléments`. C'est l'appelant qui
            décide comment chercher — lexical, sémantique, hybride — et le
            barème ne présume de rien.
        cases: Cas à évaluer ; le jeu par défaut sinon.
        method: Nom de la méthode évaluée, inscrit dans le résultat. Sans lui,
            deux mesures ne seraient pas comparables.
        top_k: Rang jusqu'auquel une réponse compte comme retrouvée.

    Returns:
        Le résultat, avec les échecs nommés — un taux sans ses échecs ne dit pas
        quoi corriger.
    """
    cas = cases if cases is not None else load_cases()
    resultat = EvalResult(method=method)

    from src.knowledge_engine.knowledge_manager import TRACK_ACCESS_VARIABLE

    ancien = os.environ.get(TRACK_ACCESS_VARIABLE)
    if neutraliser_popularite:
        os.environ[TRACK_ACCESS_VARIABLE] = "false"
    try:
        _mesurer(rechercher, cas, resultat, top_k)
    finally:
        if neutraliser_popularite:
            if ancien is None:
                os.environ.pop(TRACK_ACCESS_VARIABLE, None)
            else:
                os.environ[TRACK_ACCESS_VARIABLE] = ancien
    return resultat


def _mesurer(
    rechercher: Callable[[str], Iterable[Any]],
    cas: List[EvalCase],
    resultat: "EvalResult",
    top_k: int,
) -> None:
    """Exécute la mesure elle-même, sans se soucier de l'environnement."""
    for element in cas:
        resultat.cases += 1
        compte = resultat.by_language.setdefault(element.language, {"cases": 0, "hits": 0})
        compte["cases"] += 1

        try:
            trouves = list(rechercher(element.question))[:top_k]
        except Exception as erreur:
            resultat.misses.append({
                "question": element.question,
                "expected": element.expected_source,
                "error": str(erreur),
            })
            continue

        sources = [_source_de(trouve) for trouve in trouves]
        if any(element.expected_source in (source or "") for source in sources):
            resultat.hits += 1
            compte["hits"] += 1
        else:
            resultat.misses.append({
                "question": element.question,
                "expected": element.expected_source,
                "got": sources[:3],
            })


def _source_de(element: Any) -> Optional[str]:
    """Extrait l'identifiant de source d'un résultat de recherche."""
    source = getattr(element, "source", None)
    if source is not None:
        return getattr(source, "location", None) or getattr(source, "title", None)
    if isinstance(element, dict):
        return element.get("location") or element.get("source") or element.get("path")
    return str(element) if element is not None else None


def compare(avant: EvalResult, apres: EvalResult) -> Dict[str, Any]:
    """
    Compare deux mesures, et dit si le changement est une amélioration.

    C'est la fonction qui décide si un entraînement est **gardé**. Elle rend le
    détail par langue, parce qu'un gain global peut cacher une perte : un modèle
    qui progresse en français en régressant en wolof n'a pas progressé pour ce
    projet.

    Returns:
        L'écart global, l'écart par langue, et un verdict explicite.
    """
    ecarts = {}
    for langue in set(avant.by_language) | set(apres.by_language):
        avant_langue = avant.by_language.get(langue, {"cases": 0, "hits": 0})
        apres_langue = apres.by_language.get(langue, {"cases": 0, "hits": 0})
        taux_avant = avant_langue["hits"] / avant_langue["cases"] if avant_langue["cases"] else 0.0
        taux_apres = apres_langue["hits"] / apres_langue["cases"] if apres_langue["cases"] else 0.0
        ecarts[langue] = round(taux_apres - taux_avant, 4)

    regressions = [langue for langue, ecart in ecarts.items() if ecart < 0]
    delta = round(apres.hit_rate - avant.hit_rate, 4)

    if apres.cases == 0:
        verdict = "indécidable : le jeu d'évaluation est vide"
    elif regressions:
        verdict = f"gain global {delta:+} mais régression sur : {', '.join(sorted(regressions))}"
    elif delta > 0:
        verdict = f"amélioration : {delta:+}"
    elif delta == 0:
        verdict = "aucun changement mesurable"
    else:
        verdict = f"dégradation : {delta:+}"

    return {
        "before": avant.hit_rate,
        "after": apres.hit_rate,
        "delta": delta,
        "by_language": ecarts,
        "regressions": sorted(regressions),
        # Garder un modèle qui régresse quelque part demande une décision
        # explicite ; ce champ existe pour qu'elle ne se prenne pas par défaut.
        "keep": delta > 0 and not regressions,
        "verdict": verdict,
    }
