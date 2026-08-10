"""
Gouvernance et qualité de la recherche (VOLET 14, chapitres 08 et 09).

Le chapitre 08 demande d'enregistrer les sources et de leur donner un
responsable ; le chapitre 09 demande de mesurer la qualité de la recherche.
Les deux répondent à la même question pratique — *sur quoi cherche-t-on, et
est-ce que ça marche* — et tiennent donc dans un seul rapport.

Comme pour la connaissance (VOLET 05 ch. 06), la propriété est déclarée dans
l'environnement : la plateforme ne tient pas d'annuaire et ne vérifie pas que le
responsable déclaré existe. Elle dit ce qui a été déclaré, et ce qui manque.
"""

import os
from typing import Any, Dict, Optional

from .types import SearchSource

# Format : "source:responsable,source:responsable". Exemple :
#   GALSEN_SEARCH_OWNERS="knowledge:aissatou,memory:moussa"
OWNERS_ENV = "GALSEN_SEARCH_OWNERS"

# Ce que la qualité de recherche ne sait pas mesurer ici, et pourquoi.
UNAVAILABLE_METRICS: Dict[str, str] = {
    "precision": (
        "exige un jeu de requêtes avec les résultats attendus, jugés par un humain : "
        "aucun n'existe dans le dépôt"
    ),
    "recall": (
        "même raison que la précision — sans jugement de référence, un taux de rappel "
        "serait un chiffre sans dénominateur"
    ),
    "user_satisfaction": "aucun retour utilisateur n'est collecté",
}


def configured_owners() -> Dict[SearchSource, str]:
    """
    Lit les responsables de sources déclarés dans l'environnement.

    Une entrée mal formée, une source inconnue ou un responsable vide est
    ignorée : la source apparaîtra sans responsable, ce qui est la vérité.
    """
    proprietaires: Dict[SearchSource, str] = {}
    for entree in os.environ.get(OWNERS_ENV, "").split(","):
        entree = entree.strip()
        if not entree or ":" not in entree:
            continue
        nom, _, responsable = entree.partition(":")
        responsable = responsable.strip()
        if not responsable:
            continue
        try:
            source = SearchSource(nom.strip().lower())
        except ValueError:
            continue
        proprietaires[source] = responsable
    return proprietaires


def governance_report(manager, indexer: Optional[Any] = None,
                      metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Dresse l'état des sources de recherche et de ce qui est mesurable.

    Args:
        manager: le gestionnaire de recherche interrogé
        indexer: l'indexeur à vérifier, s'il y en a un (chapitre 05)
        metrics: l'instantané des métriques, s'il est disponible (chapitre 06)

    Returns:
        Les sources déclarées et branchées, leur responsable, l'intégrité de
        l'index, les métriques de recherche observées, et la liste de ce qui
        n'est pas mesurable avec sa raison.
    """
    proprietaires = configured_owners()
    branchees = set(manager.registered_sources())

    sources: Dict[str, Dict[str, Any]] = {}
    for source in SearchSource:
        sources[source.value] = {
            "wired": source in branchees,
            "owner": proprietaires.get(source),
        }

    rapport: Dict[str, Any] = {
        "sources": sources,
        "wired_count": len(branchees),
        "declared_count": len(list(SearchSource)),
        # Une source branchée sans responsable est le manque que le chapitre 08
        # vise : réclamer un responsable pour une source inexistante serait du bruit.
        "unowned_wired_sources": sorted(
            s.value for s in branchees if s not in proprietaires
        ),
        "unavailable_metrics": dict(UNAVAILABLE_METRICS),
    }

    if indexer is not None:
        rapport["index"] = indexer.check_integrity()
    if metrics is not None:
        rapport["queries"] = metrics.get("search", {})

    return rapport
