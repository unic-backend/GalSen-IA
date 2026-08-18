"""
Memory layers: how long a thing is kept, and who decided it would be.

The six memory types already existed (`MemoryType`), and each was used correctly
in isolation. What was never written down is the property that makes them a
*system*: **a layer is a lifetime**. Session memory dies with the session; user
memory outlives it; workspace memory belongs to a project; knowledge belongs to
nobody in particular.

Getting this wrong does not produce an error. It produces a platform that
remembers something it was never asked to keep — and the person who said it in
one conversation finds it quoted back months later, from a layer they never chose.

Three rules.

**Every layer declares its lifetime, and `None` means "does not expire" — which
is a decision, not a default.** A layer whose lifetime nobody wrote is a layer
that keeps everything forever by accident.

**Promotion between layers is explicit, and never a side effect.** A fact heard
in a session becoming a permanent user fact is a decision someone makes, with a
reason. Automatic promotion is how a base fills with things nobody meant to store,
each of them individually plausible.

**Demotion is free; promotion is not.** Moving something to a shorter-lived layer
asks nothing — it only ever removes. Moving it to a longer-lived one asks who and
why, exactly like enabling a plugin or a source.

Nothing here reads a memory's content. A layer is decided by its type and its
owner, never inferred from what it says — an inference would put a permanent
label on something a person mentioned once.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .types import MemoryType

#: Ce que chaque couche garde, et combien de temps. `lifetime_seconds: None`
#: signifie « ne périme pas » — écrit, donc décidé.
COUCHES: Dict[MemoryType, Dict[str, Any]] = {
    MemoryType.SESSION: {
        "lifetime_seconds": 60 * 60 * 12,
        "belongs_to": "session",
        "survives_session": False,
        "what": "Ce qui n'a de sens que dans la conversation en cours.",
    },
    MemoryType.SHORT_TERM: {
        "lifetime_seconds": 60 * 60 * 24 * 7,
        "belongs_to": "session",
        "survives_session": False,
        "what": "Le fil récent d'un échange, au-delà d'un seul tour.",
    },
    MemoryType.LONG_TERM: {
        "lifetime_seconds": None,
        "belongs_to": "user",
        "survives_session": True,
        "what": "Ce qu'une personne a voulu que la plateforme retienne d'elle.",
    },
    MemoryType.WORKSPACE: {
        "lifetime_seconds": None,
        "belongs_to": "workspace",
        "survives_session": True,
        "what": "Ce qui appartient à un projet, pas à la personne qui l'a écrit.",
    },
    MemoryType.AGENT_SHARED: {
        "lifetime_seconds": 60 * 60 * 24 * 30,
        "belongs_to": "platform",
        "survives_session": True,
        "what": "Ce que les agents se passent entre eux. Lu par d'autres que son auteur.",
    },
    MemoryType.KNOWLEDGE: {
        "lifetime_seconds": None,
        "belongs_to": "platform",
        "survives_session": True,
        "what": "La base commune. N'appartient à personne en particulier.",
    },
}

#: Ordre de durabilité, du plus éphémère au plus durable. Il sert à décider si
#: un déplacement est une promotion ou une rétrogradation — et les deux ne
#: coûtent pas le même prix.
DURABILITE: List[MemoryType] = [
    MemoryType.SESSION,
    MemoryType.SHORT_TERM,
    MemoryType.AGENT_SHARED,
    MemoryType.WORKSPACE,
    MemoryType.LONG_TERM,
    MemoryType.KNOWLEDGE,
]


class LayerRefused(ValueError):
    """Un déplacement de couche refusé, avec sa raison."""


def layer_of(memory_type: Any) -> Dict[str, Any]:
    """
    La couche d'un type de mémoire.

    Args:
        memory_type: Le type.

    Returns:
        Sa durée de vie, son propriétaire, et ce qu'elle garde.

    Raises:
        LayerRefused: Si le type n'est pas déclaré. Aucun défaut : un type sans
            couche garderait tout pour toujours par accident.
    """
    try:
        type_lu = memory_type if isinstance(memory_type, MemoryType) else MemoryType(
            str(memory_type).strip().lower()
        )
    except ValueError:
        connus = ", ".join(membre.value for membre in MemoryType)
        raise LayerRefused(
            f"Type de mémoire « {memory_type} » inconnu. Types déclarés : "
            f"{connus}."
        ) from None

    declaration = COUCHES.get(type_lu)
    if declaration is None:
        raise LayerRefused(
            f"Type « {type_lu.value} » sans couche déclarée : sa durée de vie "
            "n'est écrite nulle part, et il garderait tout pour toujours par "
            "accident."
        )
    return {"memory_type": type_lu.value, **declaration}


def expires_at(memory_type: Any, created_at: float) -> Optional[float]:
    """
    Quand une mémoire de ce type expire.

    Args:
        memory_type: Le type.
        created_at: L'instant de création.

    Returns:
        L'instant d'expiration, ou `None` si la couche ne périme pas — ce qui
        est une décision écrite, pas un oubli.
    """
    duree = layer_of(memory_type)["lifetime_seconds"]
    return None if duree is None else float(created_at) + float(duree)


def is_promotion(source: Any, cible: Any) -> bool:
    """
    Passer de `source` à `cible` rend-il la mémoire plus durable ?

    Args:
        source: La couche de départ.
        cible: La couche d'arrivée.

    Returns:
        Vrai si la cible survit plus longtemps que la source.
    """
    depart = MemoryType(layer_of(source)["memory_type"])
    arrivee = MemoryType(layer_of(cible)["memory_type"])
    return DURABILITE.index(arrivee) > DURABILITE.index(depart)


def move(
    source: Any, cible: Any, decided_by: str = "", reason: str = "",
) -> Dict[str, Any]:
    """
    Déplace une mémoire d'une couche à une autre, ou refuse.

    **Rétrograder est gratuit ; promouvoir ne l'est pas.** Raccourcir une durée
    de vie ne fait qu'enlever ; l'allonger fait garder quelque chose plus
    longtemps que ce que quelqu'un avait accepté, et cela se décide.

    Args:
        source: La couche de départ.
        cible: La couche d'arrivée.
        decided_by: Qui décide, obligatoire pour une promotion.
        reason: Pourquoi, obligatoire pour une promotion.

    Returns:
        Le déplacement, avec sa nature et sa trace.

    Raises:
        LayerRefused: Promotion anonyme ou sans motif, ou couche inconnue.
    """
    promotion = is_promotion(source, cible)
    depart = layer_of(source)
    arrivee = layer_of(cible)

    if promotion:
        if not (decided_by or "").strip():
            raise LayerRefused(
                f"Promotion de « {depart['memory_type']} » vers "
                f"« {arrivee['memory_type']} » sans auteur : garder quelque "
                "chose plus longtemps que prévu est une décision, et une "
                "décision a quelqu'un derrière."
            )
        if not (reason or "").strip():
            raise LayerRefused(
                "Une promotion dit pourquoi : sans raison, une base se remplit "
                "de choses que personne n'a voulu garder, chacune "
                "individuellement plausible."
            )

    return {
        "from": depart["memory_type"],
        "to": arrivee["memory_type"],
        "promotion": promotion,
        "decided_by": decided_by.strip() if promotion else None,
        "reason": reason.strip() if promotion else None,
        "note": (
            "Promotion : la mémoire survivra plus longtemps qu'à son entrée."
            if promotion else
            "Rétrogradation : elle survivra moins longtemps. Rien à justifier — "
            "raccourcir n'enlève jamais un droit à personne."
        ),
    }


def survives_session(memory_type: Any) -> bool:
    """
    Cette couche survit-elle à la fin d'une session ?

    Args:
        memory_type: Le type.

    Returns:
        Vrai si elle survit.
    """
    return bool(layer_of(memory_type)["survives_session"])


def layers_report() -> Dict[str, Any]:
    """
    Les couches, leurs durées de vie, et ce que ce module ne fait pas.

    Returns:
        Une entrée par couche et les règles tenues.
    """
    return {
        "layers": [layer_of(type_memoire) for type_memoire in DURABILITE],
        "durability_order": [type_memoire.value for type_memoire in DURABILITE],
        "rules": [
            "Une couche **est** une durée de vie. `null` veut dire « ne périme "
            "pas » — écrit, donc décidé, jamais oublié.",
            "Promouvoir est explicite : qui décide et pourquoi. Une promotion "
            "automatique est la façon dont une base se remplit de choses que "
            "personne n'a voulu garder.",
            "Rétrograder est gratuit : raccourcir une durée de vie n'enlève de "
            "droit à personne.",
            "Une couche se décide par le type et le propriétaire, **jamais** "
            "par le contenu : une inférence poserait une étiquette permanente "
            "sur ce qu'une personne a mentionné une fois.",
        ],
        "does_not": [
            "Lire le contenu d'une mémoire.",
            "Promouvoir quoi que ce soit tout seul.",
            "Supprimer : ce module décide des durées, il ne purge pas.",
        ],
    }


def effective_expiry(
    memory_type: Any, created_at: float, declared: Optional[float] = None,
) -> Dict[str, Any]:
    """
    L'expiration réellement appliquée à une mémoire, et pourquoi.

    Deux règles se rencontrent ici.

    **Une expiration explicite plus courte est respectée.** Raccourcir est
    gratuit : celui qui écrit sait parfois que sa note ne vaut qu'une heure.

    **Une expiration explicite plus longue est ramenée à la couche.** La
    rallonger ferait survivre la mémoire au-delà de ce que sa couche promet, ce
    qui est une promotion — et une promotion se décide par `move()`, avec un
    auteur et une raison, jamais en passant un nombre plus grand.

    Args:
        memory_type: Le type de la mémoire.
        created_at: Son instant de création.
        declared: L'expiration demandée, s'il y en a une.

    Returns:
        L'expiration retenue, et la raison si elle diffère de la demande.
    """
    plafond = expires_at(memory_type, created_at)

    if declared is None:
        return {
            "expires_at": plafond,
            "capped": False,
            "reason": (
                "Durée de vie de la couche."
                if plafond is not None else
                "Cette couche ne périme pas — décision écrite, pas un oubli."
            ),
        }

    demande = float(declared)
    if plafond is None or demande <= plafond:
        return {
            "expires_at": demande, "capped": False,
            "reason": "Expiration demandée, plus courte ou égale à la couche.",
        }

    return {
        "expires_at": plafond,
        "capped": True,
        "requested": demande,
        "reason": (
            "Expiration demandée plus longue que la couche : ramenée à la "
            "couche. La rallonger serait une promotion, et une promotion se "
            "décide avec un auteur et une raison — pas en passant un nombre "
            "plus grand."
        ),
    }
