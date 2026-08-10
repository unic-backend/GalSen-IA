"""
Qualité des connaissances (VOLET 05, chapitre 09).

Le chapitre nomme six métriques : exactitude, complétude, fraîcheur, taux de
doublons, couverture de validation et retour utilisateur. Quatre se calculent
depuis le contenu réel de la base. Deux ne se calculent pas ici, et ce module le
dit dans sa sortie plutôt que de produire un chiffre plausible :

- **l'exactitude** demande une vérité de référence que la plateforme n'a pas ;
  ce qu'elle sait, c'est la fiabilité déclarée de la source (P1–P4) ;
- **le retour utilisateur** demande un mécanisme de retour, qui n'existe pas.

Un taux calculé sur une base vide vaut 0.0 et non 1.0 : « rien à reprocher »
n'est pas « tout est bon ».
"""

import datetime
import statistics
from typing import Any, Dict, List

from .knowledge_lifecycle import is_due_for_revalidation
from .types import KnowledgeDomain, KnowledgeItem, KnowledgeStatus

# Statuts qui témoignent d'un passage par la revue (chapitre 04).
VALIDATED_STATUSES = frozenset({
    KnowledgeStatus.REVIEWED,
    KnowledgeStatus.APPROVED,
})

# Ce que ce module ne calcule pas, et pourquoi.
UNAVAILABLE_METRICS: Dict[str, str] = {
    "accuracy_rate": (
        "aucune vérité de référence : la plateforme connaît la fiabilité déclarée "
        "de la source (P1-P4), pas l'exactitude du contenu"
    ),
    "user_feedback": "aucun mécanisme de retour utilisateur n'existe",
}


def _ratio(numerateur: int, total: int) -> float:
    """Proportion arrondie, 0.0 si la base est vide."""
    if total <= 0:
        return 0.0
    return round(numerateur / total, 4)


def _age_en_jours(item: KnowledgeItem, maintenant: datetime.datetime) -> float:
    """Âge de la dernière mise à jour, en jours."""
    date = item.updated_at
    if date.tzinfo is None:
        date = date.replace(tzinfo=datetime.timezone.utc)
    return (maintenant - date).total_seconds() / 86400


def quality_report(store) -> Dict[str, Any]:
    """
    Calcule les métriques de qualité mesurables sur le contenu réel du magasin.

    Args:
        store: un `KnowledgeStore`

    Returns:
        Un dictionnaire portant les quatre métriques calculables, la liste des
        métriques indisponibles avec leur raison, et le nombre d'éléments sur
        lequel le calcul porte.
    """
    items: List[KnowledgeItem] = store.list_items(limit=10000)
    total = len(items)
    maintenant = datetime.datetime.now(datetime.timezone.utc)

    # Complétude : ce que le chapitre 02 exige de renseigner sur chaque élément.
    classes = sum(1 for k in items if k.domain is not KnowledgeDomain.UNSPECIFIED)
    sources_tracables = sum(
        1 for k in items
        if k.source and k.source.id not in (None, "", "unknown")
        and k.source.location not in (None, "", "unknown")
    )
    avec_resume = sum(1 for k in items if k.summary and k.summary.strip())

    # Fraîcheur : âge des contenus, et approbations périmées (chapitre 04).
    ages = [_age_en_jours(k, maintenant) for k in items]
    approbations_perimees = sum(1 for k in items if is_due_for_revalidation(k, now=maintenant))

    # Doublons : contenus rigoureusement identiques, comparés par empreinte.
    empreintes: Dict[str, int] = {}
    for k in items:
        empreinte = k.compute_content_hash()
        empreintes[empreinte] = empreintes.get(empreinte, 0) + 1
    groupes_doublons = sum(1 for compte in empreintes.values() if compte > 1)
    elements_en_double = sum(compte - 1 for compte in empreintes.values() if compte > 1)

    # Couverture de validation : ce qui est passé par la revue.
    par_statut: Dict[str, int] = {}
    for k in items:
        par_statut[k.status.value] = par_statut.get(k.status.value, 0) + 1
    valides = sum(1 for k in items if k.status in VALIDATED_STATUSES)

    return {
        "items": total,
        "completeness": {
            "classified_domain": _ratio(classes, total),
            "traceable_source": _ratio(sources_tracables, total),
            "with_summary": _ratio(avec_resume, total),
        },
        "freshness": {
            "median_age_days": round(statistics.median(ages), 2) if ages else 0.0,
            "oldest_age_days": round(max(ages), 2) if ages else 0.0,
            "stale_approvals": approbations_perimees,
        },
        "duplicates": {
            "rate": _ratio(elements_en_double, total),
            "groups": groupes_doublons,
            "redundant_items": elements_en_double,
        },
        "validation_coverage": {
            "reviewed_or_approved": _ratio(valides, total),
            "by_status": par_statut,
        },
        "unavailable": dict(UNAVAILABLE_METRICS),
    }
