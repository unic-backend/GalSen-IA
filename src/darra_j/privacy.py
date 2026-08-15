"""
Two locks on a child's data, and neither one opens without the other.

VOLET 13's question is not "who is allowed?" — `src/api/rbac.py` answers that.
It is the narrower one an education system gets wrong: *a role that is allowed
to read learners is not allowed to read **this** learner.* A teacher permission
says the holder may read pupils' work. It says nothing about whose.

So authorisation here is a conjunction, and both halves are required:

1. **The permission** — `LEARNER_DATA_READ_LINKED`, held by students, parents,
   teachers and school administrations, and by no platform role at all. Its name
   carries its limit: there is no permission for reading an *unlinked* learner,
   because none was created.
2. **The link** — `access.require_own` for a student's own data,
   `access.require_declared_link` for a guardian's, both from a declared
   enrolment source and never inferred.

Holding one without the other opens nothing, and the two failures are reported
differently: "you may not read learner data at all" and "you may, but not this
child" are different facts, and collapsing them into one message makes the
second one impossible to diagnose.

The last piece is what gets written down. A learner reference is not a secret,
but it is personal, and a trail that names children is a trail nobody can
publish. `redact_learner()` keeps a short, stable digest — enough to follow one
learner through an audit, not enough to name them — reusing the rule
`src/security/redaction.py` already applies to secrets.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, Optional

from ..api.rbac import EDUCATION_ROLES, Permission, Role, get_permissions_for_role
from .access import AccessRefused, require_declared_link, require_own

#: La permission qui ouvre les données d'apprenant — **rattachées**. Le nom
#: porte la limite : il n'existe aucune permission pour un apprenant non
#: rattaché, donc aucun rôle n'en reçoit une.
PERMISSION_APPRENANT = Permission.LEARNER_DATA_READ_LINKED

#: Longueur de l'empreinte gardée dans les traces. Douze caractères suffisent à
#: suivre un apprenant dans un audit sans permettre de le nommer — la même règle
#: que `key_fingerprint` applique aux clés API.
LONGUEUR_EMPREINTE = 12


class PrivacyRefused(PermissionError):
    """Une lecture refusée par la permission, avant même la question du lien."""


def may_read_learners(role: Role) -> bool:
    """
    Dit si un rôle peut lire des données d'apprenant **rattachées**.

    Args:
        role: Le rôle du demandeur.

    Returns:
        Vrai pour les rôles éducatifs qui portent la permission. Faux pour tout
        rôle de plateforme, autorité éducative et chercheur compris : définir un
        programme national ou étudier des agrégats n'a jamais demandé de savoir
        ce qu'un enfant a répondu.
    """
    return PERMISSION_APPRENANT in get_permissions_for_role(role)


def authorize_learner_read(
    role: Role,
    viewer_ref: str,
    subject_ref: str,
    authorized_subjects: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """
    Vérifie **les deux** verrous : la permission, puis le rattachement.

    Args:
        role: Le rôle du demandeur.
        viewer_ref: Sa référence.
        subject_ref: L'apprenant visé.
        authorized_subjects: Les apprenants déclarés du demandeur, pour un
            responsable ou un enseignant. Inutile pour un élève sur lui-même.

    Returns:
        Ce qui a été vérifié, et par quelle voie le lien a été établi.

    Raises:
        PrivacyRefused: Le rôle ne lit aucune donnée d'apprenant. C'est un fait
            différent de « pas cet enfant-là », et les confondre rendrait le
            second impossible à diagnostiquer.
        AccessRefused: Le rôle lit des apprenants, mais pas celui-ci.
    """
    if not may_read_learners(role):
        raise PrivacyRefused(
            f"Le rôle « {role.value} » ne lit aucune donnée d'apprenant. "
            "Ce n'est pas la même chose que « pas cet enfant-là » : les "
            "confondre rendrait le second refus impossible à diagnostiquer."
        )

    if role is Role.STUDENT:
        # Un élève n'a pas de liste : il est sa propre autorisation, et
        # seulement lui-même.
        require_own(viewer_ref, subject_ref)
        voie = "own"
    else:
        require_declared_link(viewer_ref, subject_ref, authorized_subjects)
        voie = "declared_link"

    return {
        "authorized": True,
        "role": role.value,
        "permission": PERMISSION_APPRENANT.value,
        "link": voie,
        "viewer": redact_learner(viewer_ref),
        "subject": redact_learner(subject_ref),
        "note": (
            "Les deux verrous ont été franchis : la permission dit qu'on peut "
            "lire des apprenants, le rattachement dit lequel."
        ),
    }


def redact_learner(reference: str) -> str:
    """
    Réduit une référence d'apprenant à une empreinte utilisable en journal.

    Args:
        reference: La référence de l'apprenant.

    Returns:
        `learner:<12 hexadécimaux>`, stable pour une même référence. Une
        référence d'élève n'est pas un secret, mais elle est personnelle : une
        piste d'audit qui nomme des enfants est une piste que personne ne peut
        publier. L'empreinte suffit à suivre un apprenant d'un bout à l'autre
        d'un incident sans le nommer.
    """
    texte = str(reference or "").strip()
    if not texte:
        return "learner:—"
    condense = hashlib.sha256(texte.encode("utf-8")).hexdigest()
    return f"learner:{condense[:LONGUEUR_EMPREINTE]}"


def safe_trail_entry(
    action: str, viewer_ref: str, subject_ref: str, **extra: Any,
) -> Dict[str, Any]:
    """
    Construit une entrée de piste qui ne nomme aucun enfant.

    Args:
        action: Ce qui a été fait.
        viewer_ref: Qui l'a fait.
        subject_ref: Sur quel apprenant.
        **extra: Le reste de l'entrée, tel quel.

    Returns:
        L'entrée, avec les références **remplacées** par leurs empreintes. Elle
        est construite champ par champ : les références en clair n'y entrent
        pas, plutôt que d'y entrer puis d'en être retirées.
    """
    return {
        "action": action,
        "viewer": redact_learner(viewer_ref),
        "subject": redact_learner(subject_ref),
        **extra,
    }


def privacy_report() -> Dict[str, Any]:
    """
    Ce que la confidentialité garantit, et par quels mécanismes.

    Returns:
        Les rôles qui lisent des apprenants, ceux qui n'en lisent pas, et les
        règles tenues.
    """
    lecteurs = sorted(
        role.value for role in EDUCATION_ROLES if may_read_learners(role)
    )
    return {
        "learner_permission": PERMISSION_APPRENANT.value,
        "roles_reading_learners": lecteurs,
        "roles_never_reading_learners": sorted(
            role.value for role in Role if not may_read_learners(role)
        ),
        "rules": [
            "L'autorisation est une **conjonction** : la permission dit qu'on "
            "peut lire des apprenants, le rattachement dit lequel. L'une sans "
            "l'autre n'ouvre rien.",
            "Il n'existe aucune permission pour un apprenant **non rattaché** — "
            "elle n'a pas été créée, donc aucun rôle ne peut la recevoir.",
            "Un refus de permission et un refus de rattachement sont deux faits "
            "distincts : les confondre rendrait le second indiagnosticable.",
            "Une autorité éducative et un chercheur ne lisent aucun apprenant : "
            "définir un programme ou étudier des agrégats ne l'a jamais "
            "demandé.",
            "Aucun rôle de plateforme, administrateur compris, ne lit un "
            "apprenant.",
            "Une piste d'audit porte une **empreinte** d'apprenant, jamais sa "
            "référence : une piste qui nomme des enfants est une piste que "
            "personne ne peut publier.",
        ],
        "does_not": [
            "Déduire un rattachement d'un nom, d'un foyer ou d'une "
            "conversation.",
            "Accorder par le rôle ce que seul le rattachement peut accorder.",
            "Écrire une référence d'apprenant en clair dans une trace.",
        ],
    }


__all__ = [
    "AccessRefused",
    "LONGUEUR_EMPREINTE",
    "PERMISSION_APPRENANT",
    "PrivacyRefused",
    "authorize_learner_read",
    "may_read_learners",
    "privacy_report",
    "redact_learner",
    "safe_trail_entry",
]
