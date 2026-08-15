"""
Preparing a teacher's material without ever becoming the teacher.

The directive's prohibition list opens with *impersonate a teacher* and
*impersonate a ministry*, and the reason is not politeness. In a school, the
authority behind a sentence is what makes it actionable: the same words about a
student mean one thing from a teacher and nothing at all from a machine. A
platform that lets its output be signed by a human it invented has manufactured
authority, which is worse than manufacturing content.

Two mechanisms hold that line, and neither of them is a warning label.

**Nothing produced here has an author.** `prepared_by` is always the platform,
`authored_by` is always `None`, and `attribute_to()` refuses any human or
institutional identity. There is no argument that turns a prepared lesson into a
teacher's lesson.

**A decision needs a named decider.** `record_decision()` refuses without one —
the same rule `registry.publish(decided_by=...)` already applies to publishing a
curriculum, applied to the other end of the system. And the platform's own
outputs are observations: `Observation` has a `fact` and where it was measured,
and **no verdict field at all**. There is no shape in which it could carry
"this student is truant" — the directive's example — because a conclusion about
a student is a decision, and decisions have deciders.

What a teacher gets is therefore: the official record verbatim, whatever
explanation was generated beside it clearly typed, and measurements. What they
do with it is theirs.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from .firewall import CANONIQUE, answer
from .pedagogy import explain
from .registry import CurriculumRegistry
from .resolution import CurriculumQuery

#: Ce que la plateforme est dans tout ce qu'elle prépare. Jamais un enseignant,
#: jamais un ministère.
#:
#: C'est un libellé lisible, pas un identifiant technique : écrit en capitales
#: avec des tirets bas, il avait la forme exacte d'une variable d'environnement
#: `GALSEN_*` et le contrôle de configuration l'a pris pour telle.
PREPARE_PAR = "GalSen IA — Darra J"

#: Les identités qu'aucune sortie ne peut porter. Se les attribuer fabriquerait
#: de l'autorité, ce qui est pire que fabriquer du contenu.
IDENTITES_REFUSEES = (
    "teacher", "enseignant", "ministry", "ministere", "ministère",
    "education_authority", "school_admin", "inspecteur", "inspector",
)

#: Les noms sous lesquels la plateforme se désignerait elle-même. Les accepter
#: comme décideur laisserait blanchir une décision de la plateforme en décision
#: « enregistrée » : le trou est petit et il annule toute la règle.
#:
#: La comparaison se fait **mot par mot**, jamais par sous-chaîne : « ia » est
#: contenu dans « Mariama », et refuser une décision parce que la personne
#: s'appelle Mariama serait un défaut bien pire que celui qu'on ferme.
IDENTITES_PLATEFORME = frozenset({
    "galsen", "darra", "claude", "ia", "ai", "assistant", "systeme", "system",
    "plateforme", "platform", "modele", "model", "bot", "agent", "llm", "gpt",
})

#: Les décisions que la plateforme ne prend pas. Elles ne lui sont pas
#: seulement interdites : aucune fonction ici n'en produit.
DECISIONS_RESERVEES = (
    "grading", "promotion", "retention", "discipline", "absence_verdict",
    "orientation", "exclusion",
)


class TeacherRefused(ValueError):
    """Une demande qui ferait parler la plateforme à la place de quelqu'un."""


@dataclass(frozen=True)
class Observation:
    """
    Un fait mesuré, sans conclusion.

    Il n'y a **pas** de champ verdict, et c'est le mécanisme : il n'existe
    aucune forme dans laquelle cet objet pourrait porter « cet élève est
    absentéiste ». Une conclusion sur un élève est une décision, et une décision
    a un décideur — voir `record_decision`.

    Attributes:
        fact: Ce qui a été mesuré, en clair.
        measured_from: D'où vient la mesure.
        subject_ref: La référence opaque de l'élève, si la mesure en concerne un.
    """

    fact: str
    measured_from: str
    subject_ref: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "fact": self.fact, "measured_from": self.measured_from,
            "subject_ref": self.subject_ref,
            "is_decision": False,
            "note": "Observation mesurée. Aucune conclusion n'y est attachée.",
        }


def _mots(valeur: str) -> List[str]:
    """Découpe un nom en mots comparables : sans accent, sans casse."""
    decompose = unicodedata.normalize("NFKD", str(valeur or ""))
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return [mot for mot in re.split(r"[^0-9a-z]+", sans_accent.casefold()) if mot]


def is_platform_identity(name: str) -> bool:
    """
    Dit si un nom désigne la plateforme elle-même.

    Args:
        name: Le nom examiné.

    Returns:
        Vrai si l'un de ses **mots** est un nom de la plateforme. La comparaison
        est faite mot par mot : « ia » est contenu dans « Mariama », et refuser
        une décision parce que la personne s'appelle Mariama serait un défaut
        bien pire que celui qu'on ferme.
    """
    return any(mot in IDENTITES_PLATEFORME for mot in _mots(name))


def attribute_to(identity: str) -> None:
    """
    Refuse d'attribuer une sortie à un enseignant ou à une institution.

    Args:
        identity: L'identité demandée.

    Raises:
        TeacherRefused: Toujours, pour les identités réservées. La fonction
            existe pour que la règle soit **appelable et testable**, pas
            seulement écrite dans un rapport.
    """
    replie = " ".join(str(identity or "").casefold().split())
    if any(refusee in replie for refusee in IDENTITES_REFUSEES):
        raise TeacherRefused(
            f"« {identity} » ne peut pas signer une sortie de la plateforme. "
            "S'attribuer l'autorité d'un enseignant ou d'un ministère "
            "fabriquerait de l'autorité, ce qui est pire que fabriquer du "
            "contenu."
        )


def prepare_lesson(
    query: CurriculumQuery,
    registry: CurriculumRegistry,
    generator: Optional[Callable[[Dict[str, Any]], str]] = None,
    level: int = 2,
) -> Dict[str, Any]:
    """
    Prépare de quoi faire un cours, sans faire le cours.

    Args:
        query: La question de curriculum.
        registry: Le registre des versions officielles.
        generator: L'explication pédagogique, injectée.
        level: Le niveau d'explication (1 à 5).

    Returns:
        Le fait officiel **tel quel**, l'explication typée à côté, les exigences
        d'évaluation officielles, et l'attribution — toujours la plateforme,
        jamais un enseignant. Une question sans enregistrement officiel rend le
        refus du pare-feu, sans substitut.
    """
    reponse = answer(query, registry, explain=None, level=level)
    if reponse.get("answer_type") != CANONIQUE:
        return {
            "prepared_by": PREPARE_PAR,
            "authored_by": None,
            "canonical": None,
            "answer_type": reponse.get("answer_type"),
            "reason": reponse.get("reason"),
            "checks": reponse.get("checks", []),
            "note": (
                "Rien n'est préparé : sans enregistrement officiel, un support "
                "de cours serait un programme inventé."
            ),
        }

    pedagogie = explain(reponse["canonical"], level=level, generator=generator)
    canonique = reponse["canonical"]

    return {
        "prepared_by": PREPARE_PAR,
        "authored_by": None,
        "answer_type": CANONIQUE,
        "canonical": canonique,
        "explanation": pedagogie["explanation"],
        "explanation_type": pedagogie.get("level_name"),
        "explanation_available": pedagogie["explanation_available"],
        "official_evaluation_requirements": list(
            canonique.get("evaluation_requirements") or []
        ),
        "unit_id": reponse["unit_id"],
        "version_id": reponse["version_id"],
        "provenance": reponse["provenance"],
        "reserved_decisions": list(DECISIONS_RESERVEES),
        "note": (
            "Support **préparé**, non signé. Le fait officiel est repris tel "
            "quel ; l'explication est produite à côté et typée. L'enseignant "
            "reste l'auteur de tout ce qui sera dit en classe."
        ),
    }


def class_observations(
    scorings: Sequence[Dict[str, Any]], source: str = "quiz",
) -> Dict[str, Any]:
    """
    Agrège des corrections en observations, sans conclure sur personne.

    Args:
        scorings: Les résultats de `assessment.score_attempt`.
        source: D'où viennent les mesures.

    Returns:
        Les observations mesurées et ce qui n'a pas pu l'être. Aucun élève n'est
        qualifié : la sortie ne contient ni classement, ni appréciation, ni
        verdict — `Observation` n'a pas de champ pour en porter un.
    """
    corriges = sum(entree.get("scored_count", 0) for entree in scorings)
    justes = sum(entree.get("correct_count", 0) for entree in scorings)
    sans_reponse = sum(entree.get("unanswered_count", 0) for entree in scorings)
    non_corriges = sum(len(entree.get("not_scored", [])) for entree in scorings)

    observations: List[Observation] = [
        Observation(
            fact=f"{justes} réponses justes sur {corriges} items corrigés.",
            measured_from=source,
        ),
        Observation(
            fact=f"{sans_reponse} items laissés sans réponse.",
            measured_from=source,
        ),
    ]
    if non_corriges:
        observations.append(Observation(
            fact=f"{non_corriges} items sans clé de correction, non comptés.",
            measured_from=source,
        ))

    return {
        "prepared_by": PREPARE_PAR,
        "authored_by": None,
        "attempts": len(scorings),
        "observations": [observation.as_dict() for observation in observations],
        "grade": None,
        "ranking": None,
        "note": (
            "Des observations, pas un jugement. Ni note, ni classement, ni "
            "appréciation : ce sont des décisions, et une décision a un "
            "décideur nommé."
        ),
    }


def record_decision(
    decision: str, decided_by: str, about: str = "", rationale: str = "",
) -> Dict[str, Any]:
    """
    Enregistre une décision **prise par quelqu'un**, sans jamais la prendre.

    C'est la règle que `registry.publish(decided_by=...)` applique déjà à la
    publication d'un curriculum, appliquée à l'autre bout du système : une
    décision scolaire sans décideur nommé est une décision que la plateforme
    aurait prise.

    Args:
        decision: Ce qui est décidé.
        decided_by: Qui décide. Obligatoire.
        about: Sur qui ou quoi, par référence opaque.
        rationale: Le motif, s'il est donné.

    Returns:
        La décision, attribuée à son décideur.

    Raises:
        TeacherRefused: Sans décideur nommé, sans intitulé de décision, ou
            lorsque le décideur désigné est la plateforme elle-même.
    """
    if not str(decided_by or "").strip():
        raise TeacherRefused(
            "Aucun décideur nommé. Une décision scolaire sans décideur est une "
            "décision que la plateforme aurait prise à la place d'un "
            "enseignant."
        )
    if is_platform_identity(decided_by):
        raise TeacherRefused(
            f"« {decided_by} » désigne la plateforme. Enregistrer sa propre "
            "décision sous ce nom la blanchirait en décision « enregistrée » : "
            "le trou est petit et il annule toute la règle."
        )
    if not str(decision or "").strip():
        raise TeacherRefused("Une décision doit dire ce qui est décidé.")

    return {
        "decision": decision,
        "decided_by": decided_by,
        "about": about,
        "rationale": rationale,
        "recorded_by": PREPARE_PAR,
        "is_platform_decision": False,
        "note": (
            "Décision **enregistrée**, pas prise. La plateforme en conserve la "
            "trace et son auteur."
        ),
    }


def teacher_report() -> Dict[str, Any]:
    """
    Ce que le mode enseignant prépare, et ce qu'il ne signe jamais.

    Returns:
        L'attribution, les décisions réservées, et les règles tenues.
    """
    return {
        "prepared_by": PREPARE_PAR,
        "authored_by": None,
        "refused_identities": list(IDENTITES_REFUSEES),
        "platform_identities": sorted(IDENTITES_PLATEFORME),
        "reserved_decisions": list(DECISIONS_RESERVEES),
        "rules": [
            "Rien de ce qui est préparé n'a d'auteur : `authored_by` vaut "
            "toujours `None` et aucun argument ne le change.",
            "S'attribuer l'identité d'un enseignant ou d'un ministère est "
            "refusé — fabriquer de l'autorité est pire que fabriquer du "
            "contenu.",
            "Une observation n'a **pas** de champ verdict : il n'existe aucune "
            "forme dans laquelle elle pourrait dire « cet élève est "
            "absentéiste ».",
            "Une décision exige un décideur nommé, comme la publication d'une "
            "version de curriculum — et ce décideur ne peut pas être la "
            "plateforme sous un autre nom.",
            "Sans enregistrement officiel, rien n'est préparé : un support de "
            "cours serait un programme inventé.",
        ],
        "does_not": [
            "Noter, classer ou apprécier un élève.",
            "Conclure à un absentéisme, à un retard ou à une difficulté.",
            "Signer un document au nom d'un enseignant ou d'une institution.",
            "Préparer un cours sur un programme que personne n'a publié.",
        ],
    }
