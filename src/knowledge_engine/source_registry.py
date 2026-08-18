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
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .scope import KnowledgeScope
from .types import SourceCategory

#: Registre par défaut, relatif à la racine du dépôt. Conservé : il reste le
#: registre sénégalais, qui n'est plus le seul mais n'a rien perdu.
REGISTRE_PAR_DEFAUT = os.path.join("corpus", "sources", "senegal.yaml")

#: Répertoire des registres. **Tous** les fichiers `.yaml` qu'il contient sont
#: chargés et fusionnés (phase 51.1) : le Sénégal devient un registre parmi
#: d'autres au lieu d'être le registre. Un registre mondial dans un seul fichier
#: rendrait toute relecture d'un domaine national un diff de mille lignes.
REPERTOIRE_DES_REGISTRES = os.path.join("corpus", "sources")

#: Valeur d'un champ que personne n'a encore établi. `unknown` n'est pas `no` :
#: une politique d'accès inconnue n'est pas une politique permissive.
INCONNU = "unknown"

#: Catégories qui affirment une autorité. Elles exigent un domaine inscrit :
#: c'est exactement la déclaration qu'un blog pouvait s'attribuer.
CATEGORIES_D_AUTORITE = frozenset({
    SourceCategory.OFFICIAL,
    SourceCategory.GOVERNMENT,
    SourceCategory.PEER_REVIEWED,
    SourceCategory.OFFICIAL_DOCUMENTATION,
    SourceCategory.STANDARD,
})


class SourceTier(Enum):
    """
    Ce que la plateforme a le droit de **faire** d'une source (ADR-021).

    `category` dit quel genre d'éditeur c'est ; le rang dit ce qu'on peut en
    faire. Les confondre reviendrait à laisser un média établi soutenir une
    affirmation parce qu'il est établi.
    """

    A_PRIMARY_OFFICIAL = "TIER_A_PRIMARY_OFFICIAL"
    A_ACADEMIC = "TIER_A_ACADEMIC"
    B_INTERNATIONAL = "TIER_B_INTERNATIONAL"
    C_SECONDARY = "TIER_C_SECONDARY"
    D_DISCOVERY_ONLY = "TIER_D_DISCOVERY_ONLY"


#: Rangs qui peuvent être acquis. `TIER_D` est une **piste**, jamais une preuve :
#: un fil de forum peut faire chercher un décret, il n'entre pas lui-même.
RANGS_ACQUERABLES = frozenset({
    SourceTier.A_PRIMARY_OFFICIAL,
    SourceTier.A_ACADEMIC,
    SourceTier.B_INTERNATIONAL,
    SourceTier.C_SECONDARY,
})

#: Repli d'un rang absent, depuis la catégorie déjà déclarée. Il existe pour que
#: le registre reste lisible pendant la transition — **pas** pour dispenser de la
#: relecture : un rang replié est un rang que personne n'a revu, et le rapport le
#: dit (`tiers_defaulted`).
RANG_PAR_DEFAUT = {
    SourceCategory.OFFICIAL: SourceTier.A_PRIMARY_OFFICIAL,
    SourceCategory.GOVERNMENT: SourceTier.A_PRIMARY_OFFICIAL,
    SourceCategory.OFFICIAL_DOCUMENTATION: SourceTier.A_PRIMARY_OFFICIAL,
    SourceCategory.PEER_REVIEWED: SourceTier.A_ACADEMIC,
    SourceCategory.INSTITUTIONAL: SourceTier.B_INTERNATIONAL,
    SourceCategory.STANDARD: SourceTier.B_INTERNATIONAL,
    SourceCategory.TRUSTED_DOCUMENTATION: SourceTier.C_SECONDARY,
    SourceCategory.INDUSTRY: SourceTier.C_SECONDARY,
    SourceCategory.EXPERT_CONSENSUS: SourceTier.C_SECONDARY,
    # Ce qui ne peut soutenir aucune affirmation retombe sur le rang qui ne le
    # permet pas. Une estimation ou une opinion peut faire **chercher** ; elle
    # n'entre pas.
    SourceCategory.ESTIMATE: SourceTier.D_DISCOVERY_ONLY,
    SourceCategory.OPINION: SourceTier.D_DISCOVERY_ONLY,
    SourceCategory.UNKNOWN: SourceTier.D_DISCOVERY_ONLY,
}

#: Débit par défaut, volontairement bas. Un défaut de politesse se corrige en
#: relisant les conditions du site ; un site surchargé, non.
DEBIT_PAR_DEFAUT = 0.2


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
        # `//ansd.sn/x` est une URL relative au protocole : sans ce traitement,
        # `urlparse` n'y voit qu'un chemin et le registre rendait « aucune URL »
        # pour une adresse parfaitement lisible. Le reste — `rapport.pdf`,
        # `/data/x.pdf` — n'est pas une URL et ne doit pas en devenir une :
        # inventer un domaine à partir d'un nom de fichier ferait refuser
        # l'ingestion d'un document local que le projet détient déjà.
        if not texte.startswith("//"):
            return ""
    hote = (urlparse(texte).hostname or "").lower()
    return hote[4:] if hote.startswith("www.") else hote


def _domaine_declare(valeur: str) -> str:
    """
    Normalise un domaine **inscrit au registre**.

    Le registre écrit `tiktok.com`, sans protocole : c'est une déclaration
    relue, pas une adresse rencontrée dans un document. La tolérance s'arrête
    là — ce qui vient d'un document passe par `_domaine()`, qui n'invente aucun
    domaine à partir d'un nom de fichier.
    """
    texte = str(valeur or "").strip()
    if not texte:
        return ""
    if "://" not in texte and not texte.startswith("//"):
        texte = "//" + texte
    return _domaine(texte)


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


def _rang(declare: Any, categorie: SourceCategory, nom: str) -> tuple:
    """
    Retourne le rang d'une source, et s'il a été replié depuis la catégorie.

    Un rang inconnu **refuse le chargement de l'entrée** au lieu de retomber en
    silence : une faute de frappe dans `tier` donnerait sinon une source dont
    personne ne connaît le régime, et c'est exactement le genre d'entrée qui
    finit par être crue.

    Raises:
        SourceRefused: Si `tier` est déclaré mais n'existe pas.
    """
    if declare in (None, ""):
        return RANG_PAR_DEFAUT.get(categorie, SourceTier.D_DISCOVERY_ONLY), True
    try:
        return SourceTier(str(declare).strip().upper()), False
    except ValueError:
        raise SourceRefused(
            f"« {nom} » déclare le rang « {declare} », qui n'existe pas. "
            f"Rangs valides : {', '.join(rang.value for rang in SourceTier)}."
        ) from None


def _pays(declare: Any, portee: str) -> str:
    """
    Retourne le pays d'une source.

    Déduire `SN` de la portée `country:sn` n'est pas une supposition : c'est le
    même fait, déjà déclaré par une personne, écrit dans l'autre sens.
    """
    if declare:
        return str(declare).strip().upper()
    if portee.startswith("country:"):
        return portee.split(":", 1)[1].upper()
    return INCONNU


def _politique_d_acces(declaree: Any) -> Dict[str, Any]:
    """
    Retourne la politique d'accès déclarée, complétée par des inconnues.

    Rien n'est supposé présent : un `robots.txt` non mesuré vaut `unknown`, pas
    « absent ». Seul le débit reçoit un défaut, et il est volontairement bas —
    se tromper vers la lenteur est réparable, se tromper vers la charge ne l'est
    pas.
    """
    declaree = declaree if isinstance(declaree, dict) else {}
    return {
        "robots_txt": str(declaree.get("robots_txt") or INCONNU),
        "sitemap": str(declaree.get("sitemap") or INCONNU),
        "terms_reviewed": str(declaree.get("terms_reviewed") or INCONNU),
        "rate_limit_rps": float(declaree.get("rate_limit_rps") or DEBIT_PAR_DEFAUT),
    }


def _fichiers_a_charger(chemin: Optional[str]) -> List[str]:
    """
    Résout ce qu'il faut charger.

    Trois cas, et le troisième est celui de la phase 51.1 : sans argument, ce
    sont **tous** les registres du répertoire, dans l'ordre alphabétique — un
    ordre stable, pour qu'un doublon soit toujours signalé de la même façon.

    Args:
        chemin: Un fichier, un répertoire, ou `None`.

    Returns:
        Les chemins à charger.
    """
    if chemin and os.path.isfile(chemin):
        return [chemin]

    repertoire = chemin or os.path.join(_racine(), REPERTOIRE_DES_REGISTRES)
    if not os.path.isdir(repertoire):
        return [chemin] if chemin else []
    return sorted(
        os.path.join(repertoire, nom)
        for nom in os.listdir(repertoire)
        if nom.endswith((".yaml", ".yml"))
    )


def load_registry(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge les registres déclarés.

    Sans argument, **tous** les fichiers de `corpus/sources/` sont chargés et
    fusionnés ; un chemin de fichier n'en charge qu'un.

    Un fichier absent rend un registre vide — et un registre vide **refuse les
    catégories d'autorité** au lieu de les accepter toutes : perdre le fichier
    ne doit pas ouvrir la porte.

    Args:
        chemin: Un fichier, un répertoire, ou `None` pour tous les registres.

    Returns:
        Les sources fusionnées, les refus fusionnés, et les fichiers lus.

    Raises:
        SourceRefused: Si deux registres déclarent le même domaine. La
            plateforme répondrait alors selon l'ordre de chargement, ce qui est
            la pire sorte de désaccord — celle que personne ne voit.
    """
    fichiers = _fichiers_a_charger(chemin)
    sources: List[Dict[str, Any]] = []
    refus: List[Dict[str, Any]] = []
    lus: List[str] = []
    declare_par: Dict[str, str] = {}

    for fichier in fichiers:
        partiel = _charger_fichier(fichier)
        if not partiel["loaded"]:
            continue
        lus.append(fichier)
        for entree in partiel["sources"]:
            precedent = declare_par.get(entree["domain"])
            if precedent is not None:
                raise SourceRefused(
                    f"Le domaine « {entree['domain'] } » est déclaré deux fois : "
                    f"dans {os.path.basename(precedent)} et dans "
                    f"{os.path.basename(fichier)}. La plateforme répondrait selon "
                    "l'ordre de chargement — un désaccord que personne ne voit. "
                    "Un domaine appartient à un seul registre."
                )
            declare_par[entree["domain"]] = fichier
            sources.append(entree)
        refus.extend(partiel["deny"])

    return {
        "sources": sources,
        # Un refus déclaré dans un registre vaut pour tous : c'est le sens sûr
        # de la fusion.
        "deny": refus,
        "path": lus[0] if len(lus) == 1 else os.path.join(
            _racine(), REPERTOIRE_DES_REGISTRES
        ),
        "files": lus,
        "loaded": bool(lus),
    }


def _charger_fichier(cible: str) -> Dict[str, Any]:
    """
    Charge un seul fichier de registre.

    Args:
        cible: Le chemin du fichier.

    Returns:
        Ses sources et ses refus, chacun sachant d'où il vient.
    """
    import yaml

    if not os.path.isfile(cible):
        return {"sources": [], "deny": [], "path": cible, "loaded": False}

    with open(cible, "r", encoding="utf-8") as fichier:
        donnees = yaml.safe_load(fichier) or {}

    sources = []
    for entree in donnees.get("sources", []) or []:
        domaine = _domaine_declare(entree.get("base_url", "")) or _domaine_declare(
            entree.get("domain", "")
        )
        if not domaine or not entree.get("name"):
            continue
        categorie = SourceCategory(entree.get("category", "unknown"))
        rang, replie = _rang(entree.get("tier"), categorie, entree["name"])
        portee = str(KnowledgeScope.parse(entree.get("scope", "global")))
        sources.append({
            "name": entree["name"],
            "domain": domaine,
            "scope": portee,
            "subjects": list(entree.get("subjects", []) or []),
            "category": categorie,
            "base_url": entree.get("base_url", ""),
            # Ajouts de l'ADR-021. Aucun n'est deviné : ce qui n'est pas déclaré
            # vaut `unknown`, et `enabled` vaut faux.
            "tier": rang,
            "tier_defaulted": replie,
            "country": _pays(entree.get("country"), portee),
            "institution_type": str(entree.get("institution_type") or INCONNU),
            "languages": list(entree.get("languages", []) or []),
            "allowed_content_types": list(entree.get("allowed_content_types", []) or []),
            "access_policy": _politique_d_acces(entree.get("access_policy")),
            "authority_scope": str(entree.get("authority_scope") or INCONNU),
            "reliability_notes": str(entree.get("reliability_notes") or ""),
            "last_verified": str(entree.get("last_verified") or INCONNU),
            "enabled": bool(entree.get("enabled", False)),
            # D'où vient cette déclaration. Un rapport qui ne le dit pas oblige
            # à chercher dans quel fichier relire une source.
            "registry_file": os.path.basename(cible),
        })

    refus = [
        {
            "domain": _domaine_declare(entree.get("domain", "")),
            "reason": entree.get("reason", ""),
            "registry_file": os.path.basename(cible),
        }
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
                f"pas. Inscrire la source dans `{REPERTOIRE_DES_REGISTRES}/` — le "
                "registre du pays concerné, ou le registre mondial —, ou déclarer "
                "une catégorie qui n'affirme pas d'autorité."
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


def acquirable_sources(
    chemin: Optional[str] = None, registre: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Retourne les sources qu'une acquisition a le droit d'atteindre (ADR-021).

    Deux conditions, et elles sont cumulatives :

    1. **`enabled: true`.** Inscrire une source ne la rend pas collectable ;
       l'activer est une modification relue, séparée. Le défaut est faux, donc
       une source ajoutée aujourd'hui n'est atteignable par aucun chemin.
    2. **Un rang acquérable.** `TIER_D` reste une piste : il peut faire chercher
       un document ailleurs, il n'est jamais collecté lui-même.

    Une liste vide est le résultat normal tant que personne n'a activé de
    source, et c'est ce qui rend la règle 1 réelle plutôt que commentée.
    """
    registre = registre or load_registry(chemin)
    return [
        entree for entree in registre["sources"]
        if entree["enabled"] and entree["tier"] in RANGS_ACQUERABLES
    ]


def registry_report(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Décrit le registre tel qu'il est réellement.

    `loaded: false` **n'est pas** un registre vide : c'est un fichier absent, et
    la distinction compte — un registre absent refuse toute catégorie
    d'autorité, ce qui se voit ici plutôt qu'à la première ingestion.

    Le rapport nomme aussi ce que personne n'a relu : les rangs repliés depuis la
    catégorie et les sources jamais vérifiées. Un repli silencieux donnerait à
    une source un régime que personne n'a choisi.
    """
    registre = load_registry(chemin)
    par_portee: Dict[str, int] = {}
    par_categorie: Dict[str, int] = {}
    par_rang: Dict[str, int] = {}
    for entree in registre["sources"]:
        par_portee[entree["scope"]] = par_portee.get(entree["scope"], 0) + 1
        nom = entree["category"].value
        par_categorie[nom] = par_categorie.get(nom, 0) + 1
        rang = entree["tier"].value
        par_rang[rang] = par_rang.get(rang, 0) + 1

    replies = [e["name"] for e in registre["sources"] if e["tier_defaulted"]]
    jamais_verifiees = [
        e["name"] for e in registre["sources"] if e["last_verified"] == INCONNU
    ]
    par_registre: Dict[str, int] = {}
    for entree in registre["sources"]:
        fichier = entree.get("registry_file", "?")
        par_registre[fichier] = par_registre.get(fichier, 0) + 1

    return {
        "file": REGISTRE_PAR_DEFAUT,
        # Les registres réellement lus. `file` reste le registre sénégalais, qui
        # n'est plus le seul : le lecteur doit voir la différence.
        "files": [os.path.basename(f) for f in registre.get("files", [])],
        "by_registry": dict(sorted(par_registre.items())),
        "loaded": registre["loaded"],
        "sources": len(registre["sources"]),
        "denied_domains": len(registre["deny"]),
        "by_scope": dict(sorted(par_portee.items())),
        "by_category": dict(sorted(par_categorie.items())),
        "by_tier": dict(sorted(par_rang.items())),
        "authority_categories": sorted(c.value for c in CATEGORIES_D_AUTORITE),
        "enabled": sum(1 for e in registre["sources"] if e["enabled"]),
        "acquirable": len(acquirable_sources(registre=registre)),
        "tiers_defaulted": replies,
        "never_verified": jamais_verifiees,
        "note": (
            "La fiabilité vient du registre, pas du document qui la revendique. "
            "Une URL refusée l'est **avec sa raison** — jamais rétrogradée en silence."
        ),
        "acquisition_note": (
            "Une source inscrite n'est pas collectable : il faut `enabled: true` "
            "et un rang acquérable. Un rang replié depuis la catégorie est un rang "
            "que personne n'a relu — il est nommé ici, pas supposé validé."
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
            "tier": entree["tier"].value,
            "tier_defaulted": entree["tier_defaulted"],
            "country": entree["country"],
            "enabled": entree["enabled"],
            "last_verified": entree["last_verified"],
        }
        for entree in load_registry(chemin)["sources"]
    ]
