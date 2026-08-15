"""
Resolving *which* curriculum record is being asked about, before looking at any.

A curriculum question must never be answered by similarity. "Week 10" is not a
search term — it is one coordinate of a record that also needs a school year, a
grade, a subject and a version before it means anything. The same week number
carries different content in 2026 and in 2027, and a retrieval that ranked
passages by resemblance would happily return last year's programme with total
confidence.

So resolution happens in a fixed order, and each step can refuse:

1. **Read the declared dimensions.** What the caller stated, unchanged.
2. **Read the markers**, and only for dimensions a number can carry — a week, a
   term, a month. Never a year, never a grade, never a subject: those cannot be
   guessed from prose without inventing, and inventing here is the failure this
   module exists to prevent.
3. **Refuse if the coordinates are incomplete** — `CLARIFICATION_REQUIRED`, with
   the missing dimensions named. Asking one question is better than answering the
   wrong one.
4. **Resolve the version** through the register, which already answers `UNKNOWN`
   and `AMBIGUOUS` rather than picking.
5. **Retrieve by identity**, not by ranking. The unit identifier is derived from
   the coordinates, so retrieval is a lookup.

A declared dimension always wins over a spotted one: the markers recognise
digits, they understand nothing, and saying so is half their usefulness — the
same rule `knowledge_engine/routing.py` already applies to subjects.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .canonical import CurriculumUnit
from .registry import AMBIGU, INCONNU, TROUVE, CurriculumRegistry

#: Une quatrième issue, à côté de `FOUND`, `UNKNOWN` et `AMBIGUOUS` : les
#: coordonnées ne suffisent pas. Elle n'est pas un échec — c'est la seule
#: réponse honnête à « qu'est-ce qu'on étudie en semaine 10 ? » posée sans année
#: ni niveau.
CLARIFICATION = "CLARIFICATION_REQUIRED"

#: Les dimensions sans lesquelles aucune unité ne peut être désignée.
DIMENSIONS_REQUISES = ("academic_year", "grade_id", "subject")

#: Ce qu'un marqueur numérique peut renseigner. Volontairement court : une année
#: scolaire, un niveau ou une matière tirés d'une phrase seraient devinés, et
#: deviner est exactement ce que ce module refuse.
MARQUEURS = {
    "week": r"\bsemaines?\s*(?:n[°o]\s*)?(\d{1,2})\b",
    "term": r"\b(?:trimestre|semestre)\s*(\d)\b",
    "month": r"\bmois\s*(?:n[°o]\s*)?(\d{1,2})\b",
    "sequence": r"\bs[ée]quence\s*(?:n[°o]\s*)?(\d{1,2})\b",
}


def _replie(texte: str) -> str:
    """Ramène un libellé à sa forme comparable : sans accent, sans casse."""
    decompose = unicodedata.normalize("NFKD", str(texte or ""))
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(sans_accent.casefold().split())


@dataclass
class CurriculumQuery:
    """
    Une question de curriculum, ramenée à ses coordonnées.

    Attributes:
        text: La question telle qu'elle a été posée. Conservée pour l'audit et
            pour les marqueurs — jamais pour classer des passages.
        academic_year: L'année scolaire déclarée.
        grade_id: Le niveau déclaré.
        subject: La matière déclarée — identifiant, nom officiel ou alias.
        week, term, month, sequence: La période déclarée.
        version_id: Une version explicitement demandée (question historique).
        asked_by_role: Le rôle qui pose la question. Ne change **rien** à la
            résolution ; il n'existe que pour la présentation en aval, et
            l'écrire ici est ce qui rend la garantie de cohérence entre usagers
            (directive VI) vérifiable.
    """

    text: str = ""
    academic_year: Optional[str] = None
    grade_id: Optional[str] = None
    subject: Optional[str] = None
    week: Optional[int] = None
    term: Optional[int] = None
    month: Optional[int] = None
    sequence: Optional[int] = None
    version_id: Optional[str] = None
    asked_by_role: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "text": self.text, "academic_year": self.academic_year,
            "grade_id": self.grade_id, "subject": self.subject,
            "week": self.week, "term": self.term, "month": self.month,
            "sequence": self.sequence, "version_id": self.version_id,
            "asked_by_role": self.asked_by_role,
        }


@dataclass
class Dimensions:
    """
    Les coordonnées d'une unité, et **comment** chacune a été obtenue.

    Attributes:
        values: Les dimensions résolues.
        methods: Pour chacune, `declared` ou `keywords`. Une dimension dont on
            ne sait pas d'où elle vient est une dimension qu'on ne peut pas
            contester.
        missing: Les dimensions requises qui manquent.
    """

    values: Dict[str, Any] = field(default_factory=dict)
    methods: Dict[str, str] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """Vrai quand aucune dimension requise ne manque."""
        return not self.missing

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "values": dict(self.values), "methods": dict(self.methods),
            "missing": list(self.missing), "complete": self.complete,
        }


def extract_dimensions(query: CurriculumQuery) -> Dimensions:
    """
    Lit les coordonnées d'une question, sans jamais en inventer.

    Args:
        query: La question.

    Returns:
        Les dimensions trouvées, la méthode de chacune, et celles qui manquent.

    Note:
        Une dimension **déclarée** l'emporte toujours sur une dimension repérée :
        les marqueurs reconnaissent des chiffres, ils ne comprennent rien.
        L'année scolaire, le niveau et la matière ne sont **jamais** tirés d'une
        phrase — les deviner produirait une réponse plausible et fausse, ce qui
        est le pire des résultats possibles pour un fait institutionnel.
    """
    dimensions = Dimensions()

    for nom in ("academic_year", "grade_id", "subject", "version_id"):
        valeur = getattr(query, nom)
        if valeur:
            dimensions.values[nom] = valeur
            dimensions.methods[nom] = "declared"

    replie = _replie(query.text)
    for nom, motif in MARQUEURS.items():
        declaree = getattr(query, nom)
        if declaree is not None:
            dimensions.values[nom] = int(declaree)
            dimensions.methods[nom] = "declared"
            continue
        trouve = re.search(motif, replie)
        if trouve:
            dimensions.values[nom] = int(trouve.group(1))
            dimensions.methods[nom] = "keywords"

    dimensions.missing = [
        nom for nom in DIMENSIONS_REQUISES if not dimensions.values.get(nom)
    ]
    # Une période est nécessaire aussi : sans elle, la question porte sur toute
    # l'année, ce qui est une autre question — légitime, mais pas celle-ci.
    if not any(
        dimensions.values.get(nom) for nom in ("week", "term", "month", "sequence")
    ):
        dimensions.missing.append("period")

    return dimensions


def _correspond(unite: CurriculumUnit, dimensions: Dict[str, Any]) -> bool:
    """
    Dit si une unité porte exactement ces coordonnées.

    La matière est comparée à son identifiant, à son nom officiel **et** à ses
    alias, en forme repliée — mais toujours à l'identique. Aucun rapprochement
    approché : deux matières voisines par le nom sont deux matières, et la leçon
    a déjà été payée une fois (`find_country`, VOLET 69).
    """
    demandee = _replie(str(dimensions.get("subject", "")))
    noms = {_replie(unite.subject.subject_id), _replie(unite.subject.official_name)}
    noms.update(_replie(alias) for alias in unite.subject.aliases)
    if demandee not in noms:
        return False

    if _replie(unite.grade.grade_id) != _replie(str(dimensions.get("grade_id", ""))):
        return False
    if unite.period.academic_year != dimensions.get("academic_year"):
        return False

    for nom in ("week", "term", "month", "sequence"):
        attendu = dimensions.get(nom)
        if attendu is not None and getattr(unite.period, nom) != attendu:
            return False
    return True


def resolve(
    query: CurriculumQuery, registry: CurriculumRegistry,
) -> Dict[str, Any]:
    """
    Résout une question de curriculum, ou dit précisément ce qui manque.

    Args:
        query: La question.
        registry: Le registre des versions officielles.

    Returns:
        Un des quatre états :

        - `CLARIFICATION_REQUIRED` — les coordonnées ne suffisent pas, et les
          dimensions manquantes sont nommées.
        - `UNKNOWN` — aucune version officielle, ou aucune unité à ces
          coordonnées. C'est l'état attendu tant qu'aucune autorité n'a fourni
          de données, et il ne se déguise pas en réponse.
        - `AMBIGUOUS` — plusieurs enregistrements correspondent. Aucun n'est
          choisi.
        - `FOUND` — un seul, avec sa provenance.
    """
    dimensions = extract_dimensions(query)
    if not dimensions.complete:
        return {
            "status": CLARIFICATION,
            "dimensions": dimensions.as_dict(),
            "missing": dimensions.missing,
            "reason": (
                "Coordonnées insuffisantes : "
                + ", ".join(dimensions.missing)
                + ". La semaine 10 de deux années scolaires ne porte pas le "
                "même contenu ; répondre sans ces dimensions reviendrait à "
                "choisir laquelle, en silence."
            ),
        }

    version = registry.resolve_version(
        dimensions.values["academic_year"],
        version_id=dimensions.values.get("version_id"),
    )
    if version["status"] != TROUVE:
        return {
            "status": AMBIGU if version["status"] == AMBIGU else INCONNU,
            "dimensions": dimensions.as_dict(),
            "reason": version["reason"],
            "candidates": version.get("candidates", []),
        }

    trouvee = version["version"]
    candidates = [
        unite for unite in registry.units_of(
            trouvee.version_id, dimensions.values["grade_id"],
            _identifiant_de_matiere(registry, trouvee.version_id,
                                    dimensions.values["grade_id"],
                                    dimensions.values["subject"]),
        )
        if _correspond(unite, dimensions.values)
    ]

    if not candidates:
        return {
            "status": INCONNU,
            "dimensions": dimensions.as_dict(),
            "version_id": trouvee.version_id,
            "reason": (
                "Aucune unité officielle à ces coordonnées dans la version "
                f"« {trouvee.version_id} ». `UNKNOWN` est la réponse : combler "
                "avec ce qu'un modèle croit savoir remplacerait un fait "
                "institutionnel par une vraisemblance."
            ),
        }
    if len(candidates) > 1:
        return {
            "status": AMBIGU,
            "dimensions": dimensions.as_dict(),
            "version_id": trouvee.version_id,
            "candidates": sorted(unite.unit_id for unite in candidates),
            "reason": (
                f"{len(candidates)} unités officielles à ces coordonnées. "
                "Aucune n'est choisie : deux enregistrements officiels pour la "
                "même case sont un conflit, pas une préférence."
            ),
        }

    unite = candidates[0]
    return {
        "status": TROUVE,
        "dimensions": dimensions.as_dict(),
        "version_id": trouvee.version_id,
        "unit_id": unite.unit_id,
        "unit": unite.as_dict(),
        "provenance": registry.provenance_of(unite.unit_id),
        "reason": "Résolu par coordonnées, sans classement ni similarité.",
    }


def _identifiant_de_matiere(
    registry: CurriculumRegistry, version_id: str, grade_id: str, demandee: str,
) -> str:
    """
    Retrouve l'identifiant d'une matière à partir d'un nom ou d'un alias.

    L'index du registre est tenu par identifiant ; une question peut arriver
    avec « Mathématiques », « maths » ou « matematik ». La correspondance reste
    **exacte** sur la forme repliée : aucun rapprochement approché.
    """
    replie = _replie(demandee)
    for cle, identifiants in registry._par_dimensions.items():  # noqa: SLF001
        if cle[0] != version_id or _replie(cle[1]) != _replie(grade_id):
            continue
        for unit_id in identifiants:
            unite = registry.get_unit(unit_id)
            if unite is None:
                continue
            noms = {_replie(unite.subject.subject_id),
                    _replie(unite.subject.official_name)}
            noms.update(_replie(alias) for alias in unite.subject.aliases)
            if replie in noms:
                return unite.subject.subject_id
    return demandee


def resolution_report() -> Dict[str, Any]:
    """
    Ce que la résolution garantit, et ce qu'elle refuse de faire.

    Returns:
        Les quatre issues, les dimensions requises, et les règles tenues.
    """
    return {
        "outcomes": [TROUVE, INCONNU, AMBIGU, CLARIFICATION],
        "required_dimensions": list(DIMENSIONS_REQUISES) + ["period"],
        "marker_dimensions": sorted(MARQUEURS),
        "rules": [
            "Aucune similarité : une unité est retrouvée par ses coordonnées, "
            "pas par ressemblance. Un classement rendrait le programme de "
            "l'an dernier avec assurance.",
            "L'année scolaire, le niveau et la matière ne sont **jamais** tirés "
            "d'une phrase : les deviner produirait une réponse plausible et "
            "fausse.",
            "Une dimension déclarée l'emporte sur une dimension repérée — les "
            "marqueurs reconnaissent des chiffres et ne comprennent rien.",
            "Des coordonnées incomplètes rendent `CLARIFICATION_REQUIRED` en "
            "nommant ce qui manque : poser une question vaut mieux que "
            "répondre à côté.",
            "Le rôle de celui qui demande n'entre pas dans la résolution : "
            "c'est ce qui rendra la cohérence entre usagers vérifiable.",
        ],
        "does_not": [
            "Choisir entre plusieurs enregistrements officiels.",
            "Compléter une coordonnée absente par une valeur par défaut.",
            "Répondre depuis la mémoire d'un modèle quand le registre est vide.",
        ],
    }
