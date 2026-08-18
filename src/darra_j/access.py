"""
Who may see a student's data — decided by a declaration, never by inference.

Darra J's prohibition list ends on *expose private student information*, and the
way that happens in practice is never an attack. It is an omission: a function
that takes an optional viewer, defaults to showing everything, and works
perfectly in every test written by someone who already knew which student they
meant. `src/security/isolation.py` was written after exactly that discovery —
`search_memory(query)` with no `user_id` returned everyone's memories, so the
default was leakage.

This module applies the same conclusion to school data, in one sentence: **the
viewer and the subject are both required, and access comes from a declared
list.**

- Nothing here takes an optional viewer. Omitting one is an error, not "show
  everything".
- A guardian's link to a child is **declared by the caller** — from an
  enrolment record — and never inferred from a name, a household, or a
  conversation. A platform that guesses who a parent is will eventually guess
  wrong, and the wrong guess hands one family another family's child.
- An empty declared list grants nothing. It is the honest state before an
  enrolment source exists, and it behaves like every other empty thing here:
  it refuses rather than defaults.

The education roles themselves (`student`, `parent`, `teacher`, `school_admin`,
`education_authority`, `researcher`) join `src/api/rbac.py` in VOLET 13. This
module is the guard those roles will call, not a second permission system.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


class AccessRefused(PermissionError):
    """Une lecture qui traverserait la frontière entre deux élèves."""


def require_own(viewer_ref: str, subject_ref: str) -> None:
    """
    Exige que le lecteur soit l'élève concerné.

    Args:
        viewer_ref: La référence du lecteur.
        subject_ref: La référence de l'élève concerné.

    Raises:
        AccessRefused: Si l'une manque, ou si elles diffèrent. Une référence
            absente n'ouvre rien : c'est par l'omission que ces frontières
            tombent, pas par l'attaque.
    """
    if not str(viewer_ref or "").strip() or not str(subject_ref or "").strip():
        raise AccessRefused(
            "Lecteur ou élève non identifié. Une référence absente ne donne pas "
            "accès à tout : c'est par l'omission que ces frontières tombent."
        )
    if viewer_ref != subject_ref:
        raise AccessRefused(
            "Ces données concernent un autre élève. La plateforme ne montre "
            "jamais le travail d'un élève à un autre."
        )


def require_declared_link(
    viewer_ref: str, subject_ref: str, authorized_subjects: Optional[Iterable[str]],
) -> None:
    """
    Exige un lien **déclaré** entre un responsable et un élève.

    Args:
        viewer_ref: La référence du responsable.
        subject_ref: La référence de l'élève.
        authorized_subjects: Les élèves que ce responsable est déclaré suivre,
            tels qu'une source d'inscription les donne. `None` ou vide
            n'accorde rien.

    Raises:
        AccessRefused: Sans déclaration, ou pour un élève hors de la
            déclaration. Le lien n'est **jamais** déduit d'un nom, d'un foyer ou
            d'une conversation : une plateforme qui devine qui est le parent
            finira par se tromper, et une erreur remet un enfant à la mauvaise
            famille.
    """
    if not str(viewer_ref or "").strip() or not str(subject_ref or "").strip():
        raise AccessRefused("Responsable ou élève non identifié.")

    declares = list(authorized_subjects or [])
    if not declares:
        raise AccessRefused(
            "Aucun lien déclaré. C'est l'état attendu tant qu'aucune source "
            "d'inscription n'existe, et il refuse au lieu de laisser passer."
        )
    if subject_ref not in declares:
        raise AccessRefused(
            "Cet élève n'est pas rattaché à ce responsable. Le lien est "
            "déclaré par une source d'inscription, jamais déduit."
        )


def access_report() -> Dict[str, Any]:
    """
    Ce que la frontière garantit, et ce qu'elle refuse de deviner.

    Returns:
        Les règles tenues et ce que le module ne fait pas.
    """
    return {
        "rules": [
            "Le lecteur et l'élève sont **tous deux** requis : omettre l'un est "
            "une erreur, pas une autorisation.",
            "Le lien d'un responsable à un élève est **déclaré** par une source "
            "d'inscription.",
            "Une déclaration vide n'accorde rien — c'est l'état honnête avant "
            "qu'une source d'inscription existe.",
            "Un élève ne voit jamais le travail d'un autre élève.",
        ],
        "does_not": [
            "Déduire un lien de parenté d'un nom, d'un foyer ou d'une "
            "conversation.",
            "Traiter une référence absente comme « tout montrer ».",
            "Remplacer `src/api/rbac.py` : les rôles éducatifs le rejoignent au "
            "VOLET 13 et appellent cette garde.",
        ],
    }
