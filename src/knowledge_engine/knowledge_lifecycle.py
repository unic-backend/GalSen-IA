"""
Cycle de vie d'une connaissance (VOLET 05, chapitre 03).

Le chapitre nomme huit étapes — création, revue, validation, approbation,
publication, maintenance, archivage, retrait — et exige que l'évolution soit
« contrôlée » et traçable. Ce module porte la partie contrôlée : quelles
transitions de statut sont permises, et lesquelles ne le sont pas.

Il ne décide pas *qui* a le droit de faire une transition : cela appartient à la
gouvernance (chapitre 06) et aux rôles de la plateforme.
"""

from typing import Dict, FrozenSet

from .types import KnowledgeStatus


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
