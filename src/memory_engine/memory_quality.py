"""
Qualité et rétention de la mémoire (VOLET 07, chapitres 08 et 09).

Le chapitre 09 nomme six métriques et le chapitre 08 demande d'appliquer des
règles de rétention et de « revoir les mémoires inactives ». Les deux se
répondent : une mémoire qu'on n'a pas relue depuis longtemps est le premier
candidat à l'archivage.

Quatre métriques se calculent depuis le contenu réel. Deux ne se calculent pas
ici, et la sortie le dit plutôt que de produire un chiffre plausible :

- **la précision de récupération** demande de savoir ce qu'il aurait fallu
  retrouver ; aucun jeu de référence n'existe ;
- **la satisfaction utilisateur** demande un mécanisme de retour, absent.

La latence d'accès n'est pas mesurée ici non plus : elle appartient à `/metrics`
et aux cibles de `docs/standards/performance.md`, qui la mesurent déjà.
"""

import time
from typing import Any, Dict, List

from .types import MemoryItem, MemoryStatus

# Ce que ce module ne calcule pas, et pourquoi.
UNAVAILABLE_METRICS: Dict[str, str] = {
    "retrieval_accuracy": (
        "exige de connaître les mémoires qu'il aurait fallu retrouver : aucun jeu "
        "de requêtes jugées n'existe dans le dépôt"
    ),
    "user_satisfaction": "aucun mécanisme de retour utilisateur n'est collecté",
}

# Au-delà de ce silence, une mémoire est dite inactive (chapitre 08).
DEFAULT_INACTIVITY_DAYS = 90


def _ratio(numerateur: int, total: int) -> float:
    """Proportion arrondie, 0.0 si la base est vide."""
    return round(numerateur / total, 4) if total > 0 else 0.0


def _age_jours(horodatage: float, maintenant: float) -> float:
    """Âge en jours d'un horodatage epoch."""
    return (maintenant - horodatage) / 86400


def inactive_memories(items: List[MemoryItem], max_age_days: int = DEFAULT_INACTIVITY_DAYS,
                      now: float = None) -> List[MemoryItem]:
    """
    Retourne les mémoires actives que personne n'a modifiées depuis longtemps.

    Le chapitre 08 demande de « revoir les mémoires inactives ». Ce module les
    désigne ; il n'archive rien de lui-même — l'archivage retire une mémoire de
    l'usage, et cette décision revient à un appelant, pas à un rapport.
    """
    reference = now if now is not None else time.time()
    return [
        item for item in items
        if item.status is MemoryStatus.ACTIVE
        and _age_jours(item.updated_at, reference) > max_age_days
    ]


def quality_report(store, max_age_days: int = DEFAULT_INACTIVITY_DAYS) -> Dict[str, Any]:
    """
    Calcule les métriques de qualité mesurables sur le contenu réel du magasin.

    Args:
        store: un magasin de mémoire
        max_age_days: seuil d'inactivité, en jours

    Returns:
        Fraîcheur, taux de doublons, complétude des métadonnées, répartition par
        statut et par type, mémoires inactives, et la liste de ce qui n'est pas
        mesurable avec sa raison.
    """
    items: List[MemoryItem] = store.list_items(limit=100000)
    total = len(items)
    maintenant = time.time()

    ages = [_age_jours(i.updated_at, maintenant) for i in items]
    ages.sort()

    # Doublons : contenus textuels rigoureusement identiques pour un même sujet.
    empreintes: Dict[Any, int] = {}
    for item in items:
        if isinstance(item.content, str):
            cle = (item.user_id, item.content.strip())
            empreintes[cle] = empreintes.get(cle, 0) + 1
    redondants = sum(compte - 1 for compte in empreintes.values() if compte > 1)

    # Complétude des métadonnées : ce qu'une mémoire doit porter pour être gouvernée.
    avec_proprietaire = sum(1 for i in items if i.user_id)
    avec_tags = sum(1 for i in items if i.tags)
    avec_expiration = sum(1 for i in items if i.expires_at is not None)

    par_statut: Dict[str, int] = {}
    par_type: Dict[str, int] = {}
    for item in items:
        statut = item.status.value if hasattr(item.status, "value") else str(item.status)
        type_ = item.memory_type.value if hasattr(item.memory_type, "value") else str(item.memory_type)
        par_statut[statut] = par_statut.get(statut, 0) + 1
        par_type[type_] = par_type.get(type_, 0) + 1

    inactives = inactive_memories(items, max_age_days, maintenant)

    return {
        "items": total,
        "freshness": {
            "median_age_days": round(ages[len(ages) // 2], 2) if ages else 0.0,
            "oldest_age_days": round(ages[-1], 2) if ages else 0.0,
            "inactive_over_threshold": len(inactives),
            "threshold_days": max_age_days,
        },
        "duplicates": {
            "rate": _ratio(redondants, total),
            "redundant_items": redondants,
        },
        "metadata_completeness": {
            "with_owner": _ratio(avec_proprietaire, total),
            "with_tags": _ratio(avec_tags, total),
            "with_expiry": _ratio(avec_expiration, total),
        },
        "by_status": par_statut,
        "by_type": par_type,
        "unavailable": dict(UNAVAILABLE_METRICS),
    }
