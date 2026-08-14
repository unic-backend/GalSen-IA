"""
User data isolation: whose datum this is, and where it is allowed to go.

The connectors being built next read a person's mail, files and calendar. The
rule they must obey is short and absolute: **a user's private content never
enters a shared store.** Not the knowledge base, not the global corpus, not
training data. Once it is there, no later filter can take it back out.

The repository already had a `user_id` on memory items — but as an **optional
filter**. `search_memory(query)` with no `user_id` returns everyone's memories,
so the default was leakage and isolation was something a caller had to remember
to ask for. Every such design fails the same way: not through an attack, through
an omission.

This module removes the omission. Nothing here takes an optional owner:

- an **audience** is always stated, and `Audience.platform()` — nobody in
  particular — is an audience that **cannot read user-owned data at all**;
- a **destination** always states its visibility, and writing user-owned data
  to a shared one is refused, not warned about;
- ownership is **derived** from the declared scope of the tool or connector that
  produced the datum (`src/tool/capabilities.py`), never chosen by the caller.

That last point is what makes the boundary hold: a connector declared
`user_private` cannot hand back data labelled as public, whatever it believes
about it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from ..tool.capabilities import DataScope


class OwnerKind(str, Enum):
    """À qui appartient une donnée."""

    #: À la plateforme : donnée publique, acquise, ou produite par le système.
    #: Elle peut aller dans un magasin partagé.
    PLATFORM = "platform"

    #: À une personne. Elle ne peut aller que dans le magasin de cette personne.
    USER = "user"


class Visibility(str, Enum):
    """Ce qu'un magasin de destination laisse voir."""

    #: Base de connaissance, corpus, données d'entraînement, index public.
    #: Tout ce qui y entre est visible par quelqu'un d'autre que son auteur.
    SHARED = "shared"

    #: Magasin propre à une personne. Rien n'en sort vers un autre sujet.
    PRIVATE = "private"


class IsolationError(PermissionError):
    """Une écriture qui traverserait la frontière. Levée, jamais journalisée en silence."""


@dataclass(frozen=True)
class Owner:
    """
    Le propriétaire d'une donnée.

    Attributes:
        kind: Plateforme ou personne.
        subject: L'identifiant stable de la personne (ADR-010), `None` pour la
            plateforme. Ce n'est jamais un secret : il apparaît dans l'audit.
    """

    kind: OwnerKind
    subject: Optional[str] = None

    @classmethod
    def platform(cls) -> "Owner":
        """La plateforme : donnée publique ou acquise, partageable."""
        return cls(kind=OwnerKind.PLATFORM)

    @classmethod
    def user(cls, subject: str) -> "Owner":
        """
        Une personne nommée.

        Args:
            subject: L'identifiant stable du porteur.

        Returns:
            Le propriétaire correspondant.

        Raises:
            IsolationError: Si le sujet est vide. Une donnée privée sans
                propriétaire nommé n'est protégeable par personne — la refuser
                vaut mieux que de l'attribuer à « quelqu'un ».
        """
        if not (subject or "").strip():
            raise IsolationError(
                "Une donnée privée sans sujet nommé n'est protégeable par "
                "personne. Le propriétaire est obligatoire."
            )
        return cls(kind=OwnerKind.USER, subject=subject.strip())

    @property
    def is_private(self) -> bool:
        """Vrai si la donnée appartient à une personne."""
        return self.kind is OwnerKind.USER

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, pour l'API et l'audit."""
        return {"kind": self.kind.value, "subject": self.subject}


@dataclass(frozen=True)
class Audience:
    """
    Pour qui une lecture est faite.

    Il n'y a **pas** de valeur « non précisée ». Une lecture faite pour personne
    en particulier est `Audience.platform()`, et c'est une audience réelle avec
    des droits réels : elle ne voit aucune donnée de personne. C'est ce qui
    remplace l'ancien `user_id=None`, qui voulait dire « tout le monde ».
    """

    owner: Owner

    @classmethod
    def platform(cls) -> "Audience":
        """La plateforme elle-même : tâche de fond, routine, maintenance."""
        return cls(owner=Owner.platform())

    @classmethod
    def user(cls, subject: str) -> "Audience":
        """
        Une personne nommée.

        Args:
            subject: L'identifiant stable du porteur.

        Returns:
            L'audience correspondante.
        """
        return cls(owner=Owner.user(subject))

    @classmethod
    def from_actor(cls, actor: Any) -> "Audience":
        """
        Construit une audience depuis un acteur de la couche d'autorisation.

        Lu par attribut, pour ne pas coupler la sécurité à la couche outil.

        Args:
            actor: Un `Actor`, ou tout objet portant un `subject`.

        Returns:
            L'audience de cet acteur, ou celle de la plateforme si le sujet est
            anonyme — un sujet anonyme ne désigne personne, donc il ne peut
            posséder aucune donnée.
        """
        sujet = (getattr(actor, "subject", "") or "").strip()
        if not sujet or sujet == "anonymous":
            return cls.platform()
        return cls.user(sujet)


def owner_for(scope: Optional[DataScope], subject: Optional[str] = None) -> Owner:
    """
    Déduit le propriétaire d'une donnée de la portée déclarée de sa source.

    C'est le pont avec `src/tool/capabilities.py`, et le point qui tient toute
    la frontière : **l'appelant ne choisit pas**. Un connecteur déclaré
    `user_private` produit de la donnée privée, quoi qu'il en pense.

    Args:
        scope: La portée déclarée de l'outil ou du connecteur.
        subject: Le sujet pour le compte de qui la source a été appelée.

    Returns:
        Le propriétaire de la donnée produite.

    Raises:
        IsolationError: Si la portée est `user_private` sans sujet nommé, ou si
            la portée est inconnue. Une portée non déclarée ne peut pas être
            supposée publique : ce serait le sens le plus dangereux des deux.
    """
    if scope is None:
        raise IsolationError(
            "Portée non déclarée : la donnée ne peut pas être supposée "
            "publique. Déclarez la capacité de la source."
        )
    if scope is DataScope.USER_PRIVATE:
        return Owner.user(subject or "")
    return Owner.platform()


# ----------------------------------------------------------------------
# Écriture
# ----------------------------------------------------------------------

def may_store(owner: Owner, destination: Visibility) -> Tuple[bool, str]:
    """
    Cette donnée peut-elle entrer dans ce magasin ?

    Args:
        owner: Le propriétaire de la donnée.
        destination: La visibilité du magasin visé.

    Returns:
        Le verdict et sa raison.
    """
    if owner.is_private and destination is Visibility.SHARED:
        return False, (
            f"Donnée appartenant à '{owner.subject}' vers un magasin partagé. "
            "Une fois entrée, aucun filtre postérieur ne l'en retire."
        )
    return True, f"Donnée '{owner.kind.value}' vers un magasin '{destination.value}'."


def check_store(owner: Owner, destination: Visibility) -> None:
    """
    Vérifie l'écriture et lève si elle traverse la frontière.

    La forme qui lève existe parce qu'un appelant peut ignorer un booléen sans
    le vouloir ; il ne peut pas ignorer une exception.

    Args:
        owner: Le propriétaire de la donnée.
        destination: La visibilité du magasin visé.

    Raises:
        IsolationError: Si l'écriture est refusée.
    """
    autorise, raison = may_store(owner, destination)
    if not autorise:
        raise IsolationError(raison)


# ----------------------------------------------------------------------
# Lecture
# ----------------------------------------------------------------------

def may_read(audience: Audience, owner: Owner) -> Tuple[bool, str]:
    """
    Cette audience peut-elle voir cette donnée ?

    Trois cas, et le deuxième est celui que l'ancien `user_id=None` ratait :

    1. Donnée de la plateforme → visible par tous.
    2. Donnée d'une personne, lecture faite pour **personne en particulier** →
       refusée. Une tâche de fond ne lit le courrier de personne.
    3. Donnée d'une personne, lecture faite pour une **autre** personne →
       refusée.

    Args:
        audience: Pour qui la lecture est faite.
        owner: Le propriétaire de la donnée.

    Returns:
        Le verdict et sa raison.
    """
    if not owner.is_private:
        return True, "Donnée de la plateforme."

    if not audience.owner.is_private:
        return False, (
            "Lecture faite pour la plateforme, sans sujet : elle ne peut "
            "atteindre la donnée de personne."
        )

    if audience.owner.subject != owner.subject:
        return False, (
            f"Donnée de '{owner.subject}', lecture faite pour "
            f"'{audience.owner.subject}'."
        )

    return True, f"Donnée de '{owner.subject}', lue pour son propriétaire."


def visible_to(
    audience: Audience,
    items: Iterable[Any],
    owner_of: Callable[[Any], Owner],
) -> List[Any]:
    """
    Filtre une suite d'éléments pour cette audience.

    Le filtre est appliqué **après** la recherche, jamais à sa place : une
    recherche qui classerait sur des éléments interdits laisserait fuir leur
    existence par le classement, même sans les rendre.

    Args:
        audience: Pour qui la lecture est faite.
        items: Les éléments candidats.
        owner_of: Comment lire le propriétaire d'un élément.

    Returns:
        Les éléments visibles, dans l'ordre reçu.
    """
    return [element for element in items if may_read(audience, owner_of(element))[0]]


def isolation_report(
    audience: Audience,
    items: Iterable[Any],
    owner_of: Callable[[Any], Owner],
) -> Dict[str, Any]:
    """
    Ce qui a été rendu, ce qui a été retiré, et pour qui.

    Le rapport dit **combien** d'éléments ont été retirés, jamais lesquels :
    nommer ce qui est caché serait le divulguer à moitié.

    Args:
        audience: Pour qui la lecture est faite.
        items: Les éléments candidats.
        owner_of: Comment lire le propriétaire d'un élément.

    Returns:
        Le décompte et l'audience.
    """
    candidats = list(items)
    visibles = visible_to(audience, candidats, owner_of)
    return {
        "audience": audience.owner.as_dict(),
        "candidates": len(candidats),
        "visible": len(visibles),
        "withheld": len(candidats) - len(visibles),
    }
