"""
Gouvernance des connaissances (VOLET 05, chapitre 06).

Le chapitre commence par « assign an owner to every knowledge domain ». Ce module
porte cette attribution et la rend vérifiable : qui possède quel domaine, et
quels domaines réellement utilisés n'ont personne.

La propriété est déclarée dans l'environnement, comme les clés d'API (ADR-010) :
la plateforme ne tient pas d'annuaire et ne prétend pas vérifier que le sujet
déclaré existe. Elle dit seulement ce qui a été déclaré, et ce qui manque.
"""

import os
from typing import Any, Dict, List, Optional

from .types import KnowledgeDomain, KnowledgeStatus

# Format : "domain:subject,domain:subject". Exemple :
#   GALSEN_KNOWLEDGE_OWNERS="legal:aissatou,technical:moussa"
OWNERS_ENV = "GALSEN_KNOWLEDGE_OWNERS"


def configured_owners() -> Dict[KnowledgeDomain, str]:
    """
    Lit les propriétaires déclarés dans l'environnement.

    Une entrée mal formée, un domaine inconnu ou un sujet vide sont ignorés :
    une déclaration illisible ne doit pas empêcher les autres d'être lues, et
    surtout ne doit pas produire un propriétaire inventé. Le domaine concerné
    apparaîtra alors comme non attribué, ce qui est la vérité.
    """
    brut = os.environ.get(OWNERS_ENV, "")
    proprietaires: Dict[KnowledgeDomain, str] = {}
    for entree in brut.split(","):
        entree = entree.strip()
        if not entree or ":" not in entree:
            continue
        nom_domaine, _, sujet = entree.partition(":")
        sujet = sujet.strip()
        if not sujet:
            continue
        try:
            domaine = KnowledgeDomain(nom_domaine.strip().lower())
        except ValueError:
            continue
        proprietaires[domaine] = sujet
    return proprietaires


def owner_of(domain: KnowledgeDomain) -> Optional[str]:
    """Retourne le propriétaire déclaré d'un domaine, ou None s'il n'y en a pas."""
    return configured_owners().get(domain)


def unowned_domains(domains_in_use: List[KnowledgeDomain]) -> List[KnowledgeDomain]:
    """
    Retourne les domaines utilisés qui n'ont pas de propriétaire.

    Seuls les domaines réellement portés par des connaissances sont retournés :
    réclamer un propriétaire pour un domaine vide produirait une liste de
    reproches sans objet.
    """
    proprietaires = configured_owners()
    return [d for d in domains_in_use if d not in proprietaires]


def governance_report(store) -> Dict[str, Any]:
    """
    Dresse l'état de la gouvernance à partir du contenu réel du magasin.

    Args:
        store: un `KnowledgeStore`

    Returns:
        Un dictionnaire portant, par domaine utilisé : le nombre de connaissances,
        leur répartition par statut et le propriétaire déclaré (None s'il n'y en a
        pas), plus la liste des domaines utilisés sans propriétaire et le nombre de
        connaissances non classées.
    """
    proprietaires = configured_owners()
    par_domaine: Dict[str, Dict[str, Any]] = {}
    non_classees = 0

    for item in store.list_items(limit=10000):
        if item.domain is KnowledgeDomain.UNSPECIFIED:
            non_classees += 1
        entree = par_domaine.setdefault(item.domain.value, {
            "items": 0,
            "owner": proprietaires.get(item.domain),
            "by_status": {},
        })
        entree["items"] += 1
        statut = item.status.value if isinstance(item.status, KnowledgeStatus) else str(item.status)
        entree["by_status"][statut] = entree["by_status"].get(statut, 0) + 1

    domaines_utilises = [KnowledgeDomain(nom) for nom in par_domaine]
    return {
        "domains": par_domaine,
        "unowned_domains": [d.value for d in unowned_domains(domaines_utilises)],
        "unclassified_items": non_classees,
        "declared_owners": {d.value: s for d, s in proprietaires.items()},
    }
