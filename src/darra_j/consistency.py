"""
Four people, four sentences, one official fact.

This is the institutional requirement of directive VI, and it is the one an
education system cannot negotiate. A student asking *"what am I supposed to
study this week?"*, a parent asking *"what is my child's programme?"*, a teacher
asking *"what is the official content?"* and an administrator asking with a form
are asking the same question. If the platform answers them differently, it has
not made a mistake in one answer — it has made the notion of an official
curriculum meaningless.

So consistency is not a hope about the retrieval; it is a **property that is
measured**, and this module measures it:

- It resolves a group of queries and compares the canonical identity of the
  answers, not their wording. The presentation is *supposed* to differ.
- It compares the content hash too. Two answers can share a `unit_id` and still
  differ if something rewrote the record between them, and that is precisely the
  failure worth catching.
- A group where one query lands on `UNKNOWN` and another on a record is
  **inconsistent**, not partially fine. Directive VI admits no such thing.

What it never does: make answers agree. If two resolutions disagree, this module
reports the disagreement. Reconciling them here would hide exactly what the
guarantee exists to expose.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .registry import TROUVE, CurriculumRegistry
from .resolution import CurriculumQuery, resolve

#: Ce qu'un groupe de questions peut donner.
COHERENT = "CONSISTENT"
INCOHERENT = "INCONSISTENT"
RIEN_A_COMPARER = "NOTHING_TO_COMPARE"


def canonical_identity(resolution: Dict[str, Any]) -> Optional[str]:
    """
    L'identité canonique d'une réponse : ce qui doit être partagé.

    Args:
        resolution: Le résultat d'une résolution.

    Returns:
        `unit_id:content_hash`, ou `None` si la question n'a pas abouti. Les
        deux, parce qu'un identifiant identique ne suffit pas : deux réponses
        peuvent désigner la même case et porter deux textes si quelque chose a
        réécrit l'enregistrement entre les deux.
    """
    if resolution.get("status") != TROUVE:
        return None
    return f"{resolution['unit_id']}:{resolution['unit']['content_hash']}"


def check_group(
    queries: List[CurriculumQuery], registry: CurriculumRegistry,
) -> Dict[str, Any]:
    """
    Vérifie qu'un groupe de questions désigne un seul fait officiel.

    Args:
        queries: Les questions — typiquement les mêmes coordonnées, formulées
            par des rôles différents.
        registry: Le registre.

    Returns:
        Le verdict, les identités obtenues, et **qui a divergé**. Un groupe où
        une question rend `UNKNOWN` et une autre un enregistrement est
        incohérent : la directive VI n'admet pas de demi-mesure.
    """
    if len(queries) < 2:
        return {
            "verdict": RIEN_A_COMPARER,
            "reason": "Il faut au moins deux questions pour comparer.",
            "resolutions": [],
        }

    resolutions = []
    for question in queries:
        resolution = resolve(question, registry)
        resolutions.append({
            "role": question.asked_by_role or "unspecified",
            "text": question.text,
            "status": resolution.get("status"),
            "identity": canonical_identity(resolution),
            "unit_id": resolution.get("unit_id"),
        })

    identites = {entree["identity"] for entree in resolutions}
    coherent = len(identites) == 1

    divergents: List[Dict[str, Any]] = []
    if not coherent:
        majoritaire = max(identites, key=lambda i: sum(
            1 for e in resolutions if e["identity"] == i
        ))
        divergents = [e for e in resolutions if e["identity"] != majoritaire]

    return {
        "verdict": COHERENT if coherent else INCOHERENT,
        "identities": sorted(i for i in identites if i is not None),
        "unresolved": [e["role"] for e in resolutions if e["identity"] is None],
        "diverging": divergents,
        "resolutions": resolutions,
        "reason": (
            "Toutes les questions désignent le même enregistrement officiel."
            if coherent else
            "Les questions ne désignent pas le même enregistrement. Ce n'est "
            "pas une erreur dans une réponse : c'est la notion de curriculum "
            "officiel qui cesse d'avoir un sens."
        ),
    }


def same_coordinates(
    academic_year: str,
    grade_id: str,
    subject: str,
    roles: Optional[List[str]] = None,
    **periode: Any,
) -> List[CurriculumQuery]:
    """
    Construit les mêmes coordonnées, posées par des rôles différents.

    C'est le cas de la directive VI, et le fabriquer ici évite que chaque test
    le réécrive — donc qu'il dérive.

    Args:
        academic_year: L'année scolaire.
        grade_id: Le niveau.
        subject: La matière.
        roles: Les rôles qui posent la question.
        **periode: `week`, `term`, `month` ou `sequence`.

    Returns:
        Une question par rôle, formulée différemment, coordonnées identiques.
    """
    formulations = {
        "student": "Qu'est-ce que je dois étudier ?",
        "parent": "Quel est le programme de mon enfant ?",
        "teacher": "Quel est le contenu officiel ?",
        "school_admin": "Contenu officiel du programme.",
        "education_authority": "Extrait du programme en vigueur.",
    }
    demandes = roles or ["student", "parent", "teacher", "school_admin"]
    return [
        CurriculumQuery(
            text=formulations.get(role, "Programme ?"),
            academic_year=academic_year, grade_id=grade_id, subject=subject,
            asked_by_role=role, **periode,
        )
        for role in demandes
    ]


def consistency_report() -> Dict[str, Any]:
    """
    Ce que la garantie de cohérence promet, et ce qu'elle refuse.

    Returns:
        Les verdicts, la règle, et ce que le module ne fait pas.
    """
    return {
        "verdicts": [COHERENT, INCOHERENT, RIEN_A_COMPARER],
        "compares": ["unit_id", "content_hash"],
        "rules": [
            "La présentation **doit** différer ; le fait sous-jacent ne le peut "
            "pas.",
            "L'identité comparée est `unit_id:content_hash` : un identifiant "
            "commun ne suffit pas, deux réponses peuvent désigner la même case "
            "et porter deux textes.",
            "Un groupe où une question rend `UNKNOWN` et une autre un "
            "enregistrement est **incohérent**, pas à moitié correct.",
            "Le rôle de celui qui demande n'entre jamais dans la résolution.",
        ],
        "does_not": [
            "Mettre les réponses d'accord : une divergence est rapportée, pas "
            "réconciliée. La réconcilier ici cacherait exactement ce que la "
            "garantie existe pour montrer.",
            "Comparer des formulations : deux phrases différentes sont "
            "attendues.",
        ],
    }
