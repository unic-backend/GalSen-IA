"""
Le registre des sources : qui fait autorité, et sur quoi (VOLET 35, chapitre 03).

`SourceCategory` existe depuis longtemps et `retrieve_reliable()` s'en sert pour
pondérer une réponse. Mais **la catégorie était déclarée par celui qui ingérait**
— un blog rangé en `government` pesait autant que le Journal officiel, et rien
dans le dépôt ne pouvait le contredire.

Ce module est ce qui manquait : la correspondance entre un domaine internet et
une catégorie, **déclarée, versionnée, relue**. La fiabilité vient du registre,
pas du document qui la revendique.

## Les deux refus

1. **La liste de refus est explicite et motivée.** Réseaux sociaux, plateformes
   vidéo, messageries, contenu anonyme : une ingestion dont l'URL correspond est
   refusée **avec sa raison**, jamais rétrogradée en silence. Rétrograder
   laisserait la source entrer et peser un peu, ce qui est pire.

2. **Une catégorie d'autorité ne se déclare pas soi-même.** `official`,
   `government` et `peer_reviewed` ne sont acceptées que pour un domaine inscrit
   au registre. C'est ce qui rend l'affirmation « ceci est officiel »
   vérifiable au lieu de crédible.

## Ce que le registre ne fait pas

Il ne visite aucune URL et ne collecte rien : aucune acquisition automatique
n'existe (VOLET 36, ch. H). Il ne juge pas non plus la qualité d'un contenu —
une vidéo peut être excellente. Il constate qu'on ne peut ni savoir **qui**
affirme, ni retrouver l'affirmation si elle change.

Un document **sans URL** ne reçoit aucun verdict : sa provenance est le
manifeste qui le déclare, et refuser tout fichier local reviendrait à interdire
l'ingestion de ce que le projet détient déjà.
"""

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .scope import KnowledgeScope
from .types import SourceCategory

#: Registre par défaut, relatif à la racine du dépôt.
REGISTRE_PAR_DEFAUT = os.path.join("corpus", "sources", "senegal.yaml")

#: Catégories qui affirment une autorité. Elles exigent un domaine inscrit :
#: c'est exactement la déclaration qu'un blog pouvait s'attribuer.
CATEGORIES_D_AUTORITE = frozenset({
    SourceCategory.OFFICIAL,
    SourceCategory.GOVERNMENT,
    SourceCategory.PEER_REVIEWED,
    SourceCategory.OFFICIAL_DOCUMENTATION,
    SourceCategory.STANDARD,
})


class SourceRefused(ValueError):
    """Une source est refusée, et le message dit pourquoi."""


def _racine() -> str:
    """Retourne la racine du dépôt."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _domaine(url: str) -> str:
    """
    Extrait le domaine d'une URL, sans `www.`.

    Une chaîne qui n'est pas une URL rend une chaîne vide : le registre ne
    devine pas un domaine à partir d'un chemin de fichier.
    """
    texte = str(url or "").strip()
    if not texte:
        return ""
    if "://" not in texte:
        texte = "//" + texte
    hote = (urlparse(texte).hostname or "").lower()
    return hote[4:] if hote.startswith("www.") else hote


def _correspond(domaine: str, declare: str) -> bool:
    """
    Indique si un domaine relève d'un domaine déclaré.

    Les sous-domaines comptent (`ifan.ucad.sn` relève de `ucad.sn`), mais
    `notucad.sn` ne relève pas de `ucad.sn` : la comparaison est faite sur les
    étiquettes, pas sur la fin de la chaîne — sinon `faux-ansd.sn` passerait
    pour l'ANSD.
    """
    if not domaine or not declare:
        return False
    return domaine == declare or domaine.endswith("." + declare)


def load_registry(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge le registre déclaré.

    Un fichier absent rend un registre vide — et un registre vide **refuse les
    catégories d'autorité** au lieu de les accepter toutes : perdre le fichier
    ne doit pas ouvrir la porte.
    """
    import yaml

    cible = chemin or os.path.join(_racine(), REGISTRE_PAR_DEFAUT)
    if not os.path.isfile(cible):
        return {"sources": [], "deny": [], "path": cible, "loaded": False}

    with open(cible, "r", encoding="utf-8") as fichier:
        donnees = yaml.safe_load(fichier) or {}

    sources = []
    for entree in donnees.get("sources", []) or []:
        domaine = _domaine(entree.get("base_url", ""))
        if not domaine or not entree.get("name"):
            continue
        sources.append({
            "name": entree["name"],
            "domain": domaine,
            "scope": str(KnowledgeScope.parse(entree.get("scope", "global"))),
            "subjects": list(entree.get("subjects", []) or []),
            "category": SourceCategory(entree.get("category", "unknown")),
            "base_url": entree.get("base_url", ""),
        })

    refus = [
        {"domain": _domaine(entree.get("domain", "")), "reason": entree.get("reason", "")}
        for entree in (donnees.get("deny", []) or [])
        if entree.get("domain")
    ]
    return {"sources": sources, "deny": refus, "path": cible, "loaded": True}


def denied_reason(url: str, registre: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Retourne la raison du refus d'une URL, ou None si elle n'est pas refusée."""
    domaine = _domaine(url)
    if not domaine:
        return None
    for entree in (registre or load_registry())["deny"]:
        if _correspond(domaine, entree["domain"]):
            return entree["reason"] or "Source refusée par le registre."
    return None


def declared_source(url: str, registre: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Retourne l'entrée du registre correspondant à cette URL, ou None."""
    domaine = _domaine(url)
    if not domaine:
        return None
    for entree in (registre or load_registry())["sources"]:
        if _correspond(domaine, entree["domain"]):
            return entree
    return None


def check_source(
    url: str,
    category: Any = SourceCategory.UNKNOWN,
    registre: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Vérifie qu'une source peut entrer, et avec quelle autorité.

    Args:
        url: Adresse du document. Vide pour un fichier local.
        category: Catégorie **déclarée** par celui qui ingère.
        registre: Registre déjà chargé, pour éviter de relire le fichier.

    Returns:
        `{"allowed": bool, "reason": str, "declared_by_registry": …}`.

    Raises:
        SourceRefused: Jamais levée ici — ce module rapporte. C'est l'ingestion
            qui refuse (`src/knowledge_engine/ingestion.py`), pour que la
            vérification puisse aussi servir à expliquer sans bloquer.
    """
    registre = registre or load_registry()
    declaree = category if isinstance(category, SourceCategory) else SourceCategory(str(category))

    raison_de_refus = denied_reason(url, registre)
    if raison_de_refus:
        return {
            "allowed": False,
            "reason": f"Source refusée : {raison_de_refus}",
            "url": url,
            "declared_category": declaree.value,
            "registry_category": None,
        }

    inscrite = declared_source(url, registre)

    # Un document sans URL n'a pas de domaine à vérifier : sa provenance est le
    # manifeste. Le registre n'a rien à en dire, et prétendre le contraire
    # bloquerait l'ingestion de ce que le projet détient déjà.
    if not _domaine(url):
        return {
            "allowed": True,
            "reason": "Aucune URL : la provenance est celle du manifeste.",
            "url": url,
            "declared_category": declaree.value,
            "registry_category": None,
        }

    if declaree in CATEGORIES_D_AUTORITE and inscrite is None:
        return {
            "allowed": False,
            "reason": (
                f"« {declaree.value} » affirme une autorité : elle n'est acceptée que "
                f"pour un domaine inscrit au registre, et « {_domaine(url)} » ne l'est "
                "pas. Inscrire la source dans `corpus/sources/senegal.yaml`, ou "
                "déclarer une catégorie qui n'affirme pas d'autorité."
            ),
            "url": url,
            "declared_category": declaree.value,
            "registry_category": None,
        }

    if inscrite is not None:
        return {
            "allowed": True,
            "reason": f"Source inscrite : {inscrite['name']}.",
            "url": url,
            "declared_category": declaree.value,
            "registry_category": inscrite["category"].value,
            "registry_scope": inscrite["scope"],
            "registry_subjects": inscrite["subjects"],
        }

    return {
        "allowed": True,
        "reason": "Domaine non inscrit : la catégorie déclarée n'affirme aucune autorité.",
        "url": url,
        "declared_category": declaree.value,
        "registry_category": None,
    }


def registry_report(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Décrit le registre tel qu'il est réellement.

    `loaded: false` **n'est pas** un registre vide : c'est un fichier absent, et
    la distinction compte — un registre absent refuse toute catégorie
    d'autorité, ce qui se voit ici plutôt qu'à la première ingestion.
    """
    registre = load_registry(chemin)
    par_portee: Dict[str, int] = {}
    par_categorie: Dict[str, int] = {}
    for entree in registre["sources"]:
        par_portee[entree["scope"]] = par_portee.get(entree["scope"], 0) + 1
        nom = entree["category"].value
        par_categorie[nom] = par_categorie.get(nom, 0) + 1

    return {
        "file": REGISTRE_PAR_DEFAUT,
        "loaded": registre["loaded"],
        "sources": len(registre["sources"]),
        "denied_domains": len(registre["deny"]),
        "by_scope": dict(sorted(par_portee.items())),
        "by_category": dict(sorted(par_categorie.items())),
        "authority_categories": sorted(c.value for c in CATEGORIES_D_AUTORITE),
        "note": (
            "La fiabilité vient du registre, pas du document qui la revendique. "
            "Une URL refusée l'est **avec sa raison** — jamais rétrogradée en silence."
        ),
    }


def known_sources(chemin: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retourne les sources déclarées, sous une forme sérialisable."""
    return [
        {
            "name": entree["name"],
            "domain": entree["domain"],
            "scope": entree["scope"],
            "subjects": entree["subjects"],
            "category": entree["category"].value,
        }
        for entree in load_registry(chemin)["sources"]
    ]
