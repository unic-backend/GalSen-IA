"""
Sécurité de lecture des connaissances (VOLET 05, chapitre 07).

Le chapitre demande « restrict sensitive knowledge » et « least privilege
access ». La sensibilité (chapitre 02) dit ce qui doit être protégé ; les rôles
de la plateforme disent qui lit. Ce module fait la correspondance, et rien d'autre.

Les rôles sont désignés par leur valeur textuelle (« admin », « operator », …)
plutôt que par l'énumération `src.api.rbac.Role` : le moteur de connaissances ne
doit pas dépendre de la couche API. Les deux listes doivent rester alignées, et
`tests/test_knowledge_security.py` échoue si un rôle apparaît d'un côté seulement.
"""

from typing import Dict, FrozenSet, Iterable, List, Optional

from .types import KnowledgeItem, KnowledgeSensitivity

# Sensibilités lisibles par rôle, du moins privilégié au plus privilégié.
# Un rôle absent de cette table — ou inconnu — ne lit que le public : le défaut
# d'un contrôle d'accès doit être le refus, jamais l'ouverture.
READABLE_BY_ROLE: Dict[str, FrozenSet[KnowledgeSensitivity]] = {
    "readonly": frozenset({KnowledgeSensitivity.PUBLIC}),
    "user": frozenset({KnowledgeSensitivity.PUBLIC, KnowledgeSensitivity.INTERNAL}),
    "operator": frozenset({
        KnowledgeSensitivity.PUBLIC,
        KnowledgeSensitivity.INTERNAL,
        KnowledgeSensitivity.CONFIDENTIAL,
    }),
    "admin": frozenset(KnowledgeSensitivity),

    # Rôles éducatifs (Darra J, VOLET 13). Ils lisent le **public** et rien
    # d'autre : le curriculum officiel et les connaissances qui l'accompagnent
    # sont publics par nature, et une position dans une école n'a jamais donné
    # de raison de lire l'interne d'une plateforme.
    #
    # Une autorité éducative n'est pas une exception : elle définit un programme
    # national, ce qui ne demande rien de confidentiel **ici**. Lui accorder
    # `INTERNAL` par respect institutionnel serait accorder un privilège pour un
    # motif qui n'est pas un besoin.
    "student": frozenset({KnowledgeSensitivity.PUBLIC}),
    "parent": frozenset({KnowledgeSensitivity.PUBLIC}),
    "teacher": frozenset({KnowledgeSensitivity.PUBLIC}),
    "school_admin": frozenset({KnowledgeSensitivity.PUBLIC}),
    "education_authority": frozenset({KnowledgeSensitivity.PUBLIC}),
    "researcher": frozenset({KnowledgeSensitivity.PUBLIC}),
}

# Ce que lit un appelant dont le rôle n'est pas connu.
PUBLIC_ONLY: FrozenSet[KnowledgeSensitivity] = frozenset({KnowledgeSensitivity.PUBLIC})


def readable_sensitivities(role: Optional[str]) -> FrozenSet[KnowledgeSensitivity]:
    """
    Retourne les sensibilités qu'un rôle peut lire.

    Un rôle absent, vide ou inconnu ne lit que le public.
    """
    if not role:
        return PUBLIC_ONLY
    return READABLE_BY_ROLE.get(str(role).strip().lower(), PUBLIC_ONLY)


def can_read(role: Optional[str], knowledge: KnowledgeItem) -> bool:
    """Indique si un rôle peut lire une connaissance donnée."""
    return knowledge.sensitivity in readable_sensitivities(role)


def filter_readable(role: Optional[str], items: Iterable[KnowledgeItem]) -> List[KnowledgeItem]:
    """
    Retire les connaissances qu'un rôle n'a pas le droit de lire.

    Le filtrage est silencieux par conception : dire « 3 résultats vous sont
    cachés » révèle déjà l'existence de ce qui est protégé.
    """
    return [item for item in items if can_read(role, item)]
