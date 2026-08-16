"""
Reusable production rules — and the promotion that never happens by itself.

Directive §17 describes skills, then constrains them with the sentence that
shapes this module: *corrections from previous productions may become candidate
skills, but MUST NOT automatically become permanent truth without validation.*
§19 says the same thing from the other side: the system may learn from
corrections *at the project/skill level without silently rewriting global
behaviour*.

Both are guarding against one failure, and it is a quiet one. A client asks for
larger captions on Tuesday. The system, being helpful, records that preference.
Three months later a different client on a different continent gets larger
captions, and nobody can say why — the rule has no author, no date, and no
reason attached, so nobody can argue with it either.

So promotion is an act with a name on it. `promote()` requires a validator, and
refuses the platform's own identity: a rule the platform validated for itself is
a rule nobody chose. Until then a correction sits in `candidates` — visible,
countable, and doing nothing.

**Scope is the second guard.** A rule promoted inside a project stays inside
that project. Reaching the global scope needs its own explicit promotion, with
its own validator, because "this worked for one client" and "this is how we work"
are different claims and only one of them is supported by a single Tuesday.

Skills also declare `forbidden` patterns, which matter more than the positive
rules. A house style saying *never full-screen text over a face* stops a
mistake; the same style saying *use blue* only expresses a taste.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Les portées d'une règle. Une règle de projet et une règle maison ne sont pas
#: la même affirmation : « cela a marché pour un client » et « c'est ainsi
#: qu'on travaille » ne s'appuient pas sur les mêmes preuves.
PORTEE_PROJET = "PROJECT"
PORTEE_GLOBALE = "GLOBAL"
PORTEES = (PORTEE_PROJET, PORTEE_GLOBALE)

#: Les domaines qu'une règle peut toucher (§17).
DOMAINES = (
    "typography", "colors", "spacing", "animation", "subtitles", "audio",
    "transitions", "models", "editing", "forbidden",
)

#: Les identités qui ne peuvent valider aucune règle : la plateforme
#: elle-même. Une règle qu'elle a validée pour elle-même est une règle que
#: personne n'a choisie. Même mécanisme que `teacher.is_platform_identity`
#: dans Darra J, et pour la même raison.
IDENTITES_PLATEFORME = frozenset({
    "galsen", "darra", "claude", "ia", "ai", "assistant", "systeme", "system",
    "plateforme", "platform", "modele", "model", "bot", "agent", "llm", "gpt",
})


class SkillRefused(ValueError):
    """Une règle qui ne peut pas être promue ou employée telle quelle."""


def _mots(valeur: str) -> List[str]:
    """Découpe un nom en mots comparables, sans accent ni casse."""
    import re
    import unicodedata

    decompose = unicodedata.normalize("NFKD", str(valeur or ""))
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return [m for m in re.split(r"[^0-9a-z]+", sans_accent.casefold()) if m]


def is_platform_identity(name: str) -> bool:
    """
    Dit si un nom désigne la plateforme.

    La comparaison est faite **mot par mot**, jamais par sous-chaîne : « ia »
    est contenu dans « Mariama », et refuser une validation parce que la
    personne s'appelle Mariama serait un défaut bien pire que celui qu'on ferme.
    """
    return any(mot in IDENTITES_PLATEFORME for mot in _mots(name))


@dataclass(frozen=True)
class Rule:
    """
    Une règle de production, avec ce qui permet de la contester.

    Attributes:
        domain: Le domaine touché, parmi `DOMAINES`.
        statement: Ce que la règle dit.
        scope: `PROJECT` ou `GLOBAL`.
        validated_by: Qui l'a promue. Vide pour une candidate.
        validated_at: Quand.
        evidence: Les corrections qui l'ont suggérée.
        project_id: Le projet, pour une règle de portée projet.
    """

    domain: str
    statement: str
    scope: str = PORTEE_PROJET
    validated_by: str = ""
    validated_at: float = 0.0
    evidence: Tuple[str, ...] = ()
    project_id: str = ""

    def __post_init__(self) -> None:
        if self.domain not in DOMAINES:
            raise SkillRefused(
                f"Domaine « {self.domain} » non déclaré. Déclarés : "
                f"{list(DOMAINES)}."
            )
        if self.scope not in PORTEES:
            raise SkillRefused(f"Portée « {self.scope} » inconnue.")
        if not str(self.statement or "").strip():
            raise SkillRefused(
                "Une règle sans énoncé ne peut être ni appliquée ni contestée."
            )

    @property
    def is_validated(self) -> bool:
        """Vrai seulement pour une règle qu'une personne nommée a promue."""
        return bool(str(self.validated_by or "").strip())

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "domain": self.domain, "statement": self.statement,
            "scope": self.scope, "validated_by": self.validated_by,
            "validated_at": self.validated_at,
            "evidence": list(self.evidence), "project_id": self.project_id,
            "validated": self.is_validated,
        }


@dataclass
class Skill:
    """
    Un ensemble de règles réutilisables, nommé.

    Attributes:
        skill_id: Son identité.
        title: Son nom lisible.
        rules: Les règles validées.
        candidates: Les règles suggérées, **sans effet**.
    """

    skill_id: str
    title: str = ""
    rules: List[Rule] = field(default_factory=list)
    candidates: List[Rule] = field(default_factory=list)

    def rules_for(
        self, domain: str, scope: Optional[str] = None,
        project_id: str = "",
    ) -> List[Rule]:
        """
        Les règles validées applicables à un domaine.

        Une règle de portée projet ne sort **jamais** de son projet : c'est le
        second garde-fou du volet.
        """
        retenues = []
        for regle in self.rules:
            if regle.domain != domain or not regle.is_validated:
                continue
            if scope and regle.scope != scope:
                continue
            if regle.scope == PORTEE_PROJET and regle.project_id != project_id:
                continue
            retenues.append(regle)
        return retenues

    @property
    def forbidden(self) -> List[str]:
        """
        Ce que ce style interdit.

        Rendu à part parce qu'il compte davantage : « jamais de texte plein
        écran sur un visage » évite une faute, tandis que « utiliser du bleu »
        n'exprime qu'un goût.
        """
        return [
            regle.statement for regle in self.rules
            if regle.domain == "forbidden" and regle.is_validated
        ]

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, candidates comprises."""
        return {
            "skill_id": self.skill_id, "title": self.title,
            "rules": [regle.as_dict() for regle in self.rules],
            "candidates": [regle.as_dict() for regle in self.candidates],
            "forbidden": self.forbidden,
            "rule_count": len(self.rules),
            "candidate_count": len(self.candidates),
        }


class SkillRegistry:
    """
    Les styles connus. Aucune promotion n'y arrive toute seule.
    """

    def __init__(self) -> None:
        self._verrou = threading.RLock()
        self._skills: Dict[str, Skill] = {}
        self._journal: List[Dict[str, Any]] = []

    def create(self, skill_id: str, title: str = "") -> Skill:
        """Crée un style, ou rend celui qui existe déjà."""
        with self._verrou:
            if skill_id not in self._skills:
                self._skills[skill_id] = Skill(skill_id=skill_id, title=title)
            return self._skills[skill_id]

    def get(self, skill_id: str) -> Optional[Skill]:
        """Un style par son identité."""
        with self._verrou:
            return self._skills.get(skill_id)

    def suggest(
        self, skill_id: str, domain: str, statement: str,
        evidence: Sequence[str] = (), project_id: str = "",
    ) -> Rule:
        """
        Enregistre une règle **candidate**, qui ne fait rien.

        Args:
            skill_id: Le style visé.
            domain: Le domaine touché.
            statement: Ce que la règle dirait.
            evidence: Les corrections qui la suggèrent.
            project_id: Le projet d'où elle vient.

        Returns:
            La candidate. Elle est visible et dénombrable, et **sans effet** :
            un client qui demande des sous-titres plus grands un mardi ne doit
            pas produire, trois mois plus tard, des sous-titres plus grands chez
            un autre client sur un autre continent — sans auteur, sans date et
            sans raison, une telle règle ne peut pas non plus être contestée.
        """
        candidate = Rule(
            domain=domain, statement=statement, scope=PORTEE_PROJET,
            evidence=tuple(evidence), project_id=project_id,
        )
        with self._verrou:
            style = self.create(skill_id)
            style.candidates.append(candidate)
            self._journal.append({
                "at": time.time(), "action": "suggested",
                "skill_id": skill_id, "domain": domain,
            })
        return candidate

    def promote(
        self, skill_id: str, candidate: Rule, validated_by: str,
        scope: str = PORTEE_PROJET, project_id: str = "",
    ) -> Rule:
        """
        Promeut une candidate en règle — par un acte signé.

        Args:
            skill_id: Le style visé.
            candidate: La règle candidate.
            validated_by: Qui valide. Obligatoire, et ne peut pas être la
                plateforme.
            scope: `PROJECT` ou `GLOBAL`. Atteindre le global demande **cette**
                promotion-ci, pas la précédente.
            project_id: Le projet, pour une portée projet.

        Returns:
            La règle validée.

        Raises:
            SkillRefused: Sans validateur, avec une identité de plateforme, ou
                pour une portée projet sans projet. Une règle que la plateforme
                a validée pour elle-même est une règle que personne n'a choisie.
        """
        if not str(validated_by or "").strip():
            raise SkillRefused(
                "Aucun validateur. Une règle sans auteur ne peut être ni datée "
                "ni contestée, et elle s'appliquera à des clients qui ne l'ont "
                "jamais demandée."
            )
        if is_platform_identity(validated_by):
            raise SkillRefused(
                f"« {validated_by} » désigne la plateforme. Une règle qu'elle "
                "valide pour elle-même est une règle que personne n'a choisie."
            )
        if scope not in PORTEES:
            raise SkillRefused(f"Portée « {scope} » inconnue.")
        if scope == PORTEE_PROJET and not str(project_id or candidate.project_id):
            raise SkillRefused(
                "Une règle de portée projet doit nommer son projet, sinon elle "
                "s'appliquerait partout en prétendant le contraire."
            )

        validee = Rule(
            domain=candidate.domain, statement=candidate.statement,
            scope=scope, validated_by=validated_by, validated_at=time.time(),
            evidence=candidate.evidence,
            project_id="" if scope == PORTEE_GLOBALE
            else (project_id or candidate.project_id),
        )
        with self._verrou:
            style = self.create(skill_id)
            style.rules.append(validee)
            if candidate in style.candidates:
                style.candidates.remove(candidate)
            self._journal.append({
                "at": validee.validated_at, "action": "promoted",
                "skill_id": skill_id, "domain": candidate.domain,
                "scope": scope, "validated_by": validated_by,
            })
        return validee

    def history(self) -> List[Dict[str, Any]]:
        """Les suggestions et promotions, dans l'ordre."""
        with self._verrou:
            return list(self._journal)

    def report(self) -> Dict[str, Any]:
        """L'état du registre, sans rien arrondir."""
        with self._verrou:
            styles = list(self._skills.values())
        return {
            "skills": [style.as_dict() for style in styles],
            "total_rules": sum(len(s.rules) for s in styles),
            "total_candidates": sum(len(s.candidates) for s in styles),
            "global_rules": [
                regle.as_dict() for style in styles for regle in style.rules
                if regle.scope == PORTEE_GLOBALE
            ],
            "note": (
                "Une candidate est visible, dénombrable et **sans effet**. "
                "Atteindre la portée globale demande sa propre promotion, avec "
                "son propre validateur."
            ),
        }


def skill_report() -> Dict[str, Any]:
    """
    Ce que les skills garantissent, et ce qu'ils refusent.

    Returns:
        Les portées, les domaines, et les règles tenues.
    """
    return {
        "scopes": list(PORTEES),
        "domains": list(DOMAINES),
        "rules": [
            "Une correction devient **candidate**, jamais règle. Une candidate "
            "est visible, dénombrable et sans effet.",
            "La promotion exige un **validateur nommé** qui n'est pas la "
            "plateforme : une règle qu'elle valide pour elle-même est une règle "
            "que personne n'a choisie.",
            "Une règle de projet reste dans son projet. Atteindre le global "
            "demande sa propre promotion — « cela a marché pour un client » et "
            "« c'est ainsi qu'on travaille » ne s'appuient pas sur les mêmes "
            "preuves.",
            "Les interdits comptent davantage que les préférences : « jamais de "
            "texte plein écran sur un visage » évite une faute, « utiliser du "
            "bleu » exprime un goût.",
            "La comparaison d'identité se fait mot par mot : « ia » est contenu "
            "dans « Mariama ».",
        ],
        "does_not": [
            "Promouvoir une correction toute seule.",
            "Accepter la plateforme comme validateur.",
            "Étendre une règle de projet au global sans acte explicite.",
            "Appliquer une règle candidate.",
        ],
    }
