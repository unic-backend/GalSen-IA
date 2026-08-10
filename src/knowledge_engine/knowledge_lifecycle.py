"""
Cycle de vie d'une connaissance (VOLET 05, chapitre 03).

Le chapitre nomme huit étapes — création, revue, validation, approbation,
publication, maintenance, archivage, retrait — et exige que l'évolution soit
« contrôlée » et traçable. Ce module porte la partie contrôlée : quelles
transitions de statut sont permises, et lesquelles ne le sont pas.

Il ne décide pas *qui* a le droit de faire une transition : cela appartient à la
gouvernance (chapitre 06) et aux rôles de la plateforme.
"""

import datetime
import os
from typing import Dict, FrozenSet, Optional

from .types import KnowledgeItem, KnowledgeStatus

# Âge au-delà duquel une connaissance approuvée doit repasser en revue
# (chapitre 04, « periodic revalidation »). Configurable, jamais codé en dur.
DEFAULT_REVALIDATION_DAYS = 180
REVALIDATION_DAYS_ENV = "GALSEN_KNOWLEDGE_REVALIDATION_DAYS"


class InvalidStatusTransition(ValueError):
    """Transition de statut refusée par le cycle de vie du chapitre 03."""

    def __init__(self, current: KnowledgeStatus, target: KnowledgeStatus):
        self.current = current
        self.target = target
        permises = ", ".join(sorted(s.value for s in allowed_targets(current))) or "aucune"
        super().__init__(
            f"Transition refusée : {current.value} -> {target.value}. "
            f"Transitions permises depuis {current.value} : {permises}."
        )


# Transitions permises. Une progression peut reculer — une revue peut renvoyer un
# texte au brouillon, une revalidation périodique (chapitre 04) peut remettre en
# revue une connaissance approuvée — mais elle ne peut pas sauter la revue.
ALLOWED_TRANSITIONS: Dict[KnowledgeStatus, FrozenSet[KnowledgeStatus]] = {
    KnowledgeStatus.DRAFT: frozenset({
        KnowledgeStatus.UNDER_REVIEW,
        KnowledgeStatus.DEPRECATED,
    }),
    KnowledgeStatus.UNDER_REVIEW: frozenset({
        KnowledgeStatus.REVIEWED,
        KnowledgeStatus.DRAFT,
        KnowledgeStatus.DEPRECATED,
    }),
    KnowledgeStatus.REVIEWED: frozenset({
        KnowledgeStatus.APPROVED,
        KnowledgeStatus.UNDER_REVIEW,
        KnowledgeStatus.DEPRECATED,
    }),
    KnowledgeStatus.APPROVED: frozenset({
        KnowledgeStatus.UNDER_REVIEW,
        KnowledgeStatus.ARCHIVED,
        KnowledgeStatus.DEPRECATED,
    }),
    # Une connaissance archivée reste vraie : elle peut revenir en service, mais
    # seulement en repassant par une revue.
    KnowledgeStatus.ARCHIVED: frozenset({
        KnowledgeStatus.UNDER_REVIEW,
        KnowledgeStatus.DEPRECATED,
    }),
    # Le retrait est terminal : ce qui ne doit plus servir de référence ne
    # redevient pas une référence sans être réécrit, ce qui crée une révision.
    KnowledgeStatus.DEPRECATED: frozenset(),
}


def allowed_targets(current: KnowledgeStatus) -> FrozenSet[KnowledgeStatus]:
    """Retourne les statuts atteignables depuis le statut courant."""
    return ALLOWED_TRANSITIONS.get(current, frozenset())


def is_allowed(current: KnowledgeStatus, target: KnowledgeStatus) -> bool:
    """Indique si la transition demandée est permise."""
    return target in allowed_targets(current)


def check_transition(current: KnowledgeStatus, target: KnowledgeStatus) -> None:
    """Vérifie une transition et lève `InvalidStatusTransition` si elle est refusée."""
    if not is_allowed(current, target):
        raise InvalidStatusTransition(current, target)


def revalidation_days() -> int:
    """Âge maximal d'une approbation, en jours, avant revalidation.

    Lu dans l'environnement à chaque appel : un déploiement peut le changer sans
    redémarrer. Une valeur illisible ou nulle retombe sur le défaut plutôt que
    de désactiver silencieusement la revalidation.
    """
    brut = os.environ.get(REVALIDATION_DAYS_ENV)
    if not brut:
        return DEFAULT_REVALIDATION_DAYS
    try:
        jours = int(brut)
    except ValueError:
        return DEFAULT_REVALIDATION_DAYS
    return jours if jours > 0 else DEFAULT_REVALIDATION_DAYS


def approved_at(knowledge: KnowledgeItem) -> Optional[datetime.datetime]:
    """Date de la dernière approbation, lue dans l'historique des transitions.

    Retourne None si la connaissance n'a jamais été approuvée. Une connaissance
    approuvée sans historique — construite directement dans cet état — retombe
    sur `updated_at` : c'est la seule date réelle disponible, aucune n'est inventée.
    """
    if knowledge.status is not KnowledgeStatus.APPROVED:
        return None

    historique = knowledge.metadata.get("status_history") or []
    for entree in reversed(historique):
        if entree.get("to") == KnowledgeStatus.APPROVED.value and entree.get("at"):
            try:
                return datetime.datetime.fromisoformat(entree["at"])
            except (TypeError, ValueError):
                break
    return knowledge.updated_at


def is_due_for_revalidation(knowledge: KnowledgeItem, max_age_days: Optional[int] = None,
                            now: Optional[datetime.datetime] = None) -> bool:
    """Indique si une connaissance approuvée doit repasser en revue.

    Seules les connaissances approuvées sont concernées : un brouillon n'a pas
    d'approbation à périmer.
    """
    date = approved_at(knowledge)
    if date is None:
        return False

    reference = now or datetime.datetime.now(datetime.timezone.utc)
    # Une date sans fuseau vient d'un magasin ancien : on la lit en UTC.
    if date.tzinfo is None:
        date = date.replace(tzinfo=datetime.timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=datetime.timezone.utc)

    limite = max_age_days if max_age_days is not None else revalidation_days()
    return (reference - date) > datetime.timedelta(days=limite)
