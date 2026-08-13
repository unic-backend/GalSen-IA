"""
Collecter un document : sous portillon, et licite (VOLET 35, chapitre 08).

Télécharger, c'est agir sur le serveur de quelqu'un d'autre. Ce chapitre est le
seul du VOLET qui sorte de la machine, et il est donc celui où le refus doit
être le plus facile et l'accord le plus explicite.

## Quatre conditions, et aucune n'est facultative

1. **La source est inscrite au registre.** Pas de collecte hors registre : le
   chapitre 07 propose des candidats, une personne les inscrit, et seulement
   ensuite ils deviennent collectables. « Cherche sur internet » n'entre par
   aucune porte.
2. **`robots.txt` est respecté.** Il est lu et **appliqué**, pas consulté pour
   information. Un chemin interdit refuse la collecte.
3. **La licence est déclarée.** Une licence inconnue ne bloque pas — elle
   **dégrade** : le document devient `reference_only`, citable par son URL et
   non reproductible en entier. C'est la différence entre citer une source et la
   republier.
4. **L'accord humain est demandé** (ADR-006). Ce module ne télécharge rien : il
   prépare une demande. La collecte elle-même est faite par l'opérateur ou par
   un outil déjà approuvé.

## Ce que ce module ne fait pas, et pourquoi

**Il ne va pas sur le réseau.** Il ne récupère ni la page, ni `robots.txt` :
`robots.txt` lui est **donné**, et il l'applique. La raison est écrite au VOLET
36, ch. H : l'acquisition automatisée est différée tant qu'aucun corpus n'existe
— automatiser la collecte avant d'avoir une source collecterait du vide,
régulièrement. Ce qui est construit ici est la **décision**, qui manquait ; le
téléchargement, lui, n'a jamais manqué.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .source_registry import declared_source, denied_reason, load_registry

#: Licences qui autorisent la reproduction du contenu dans la base. Toute autre
#: valeur — et l'absence de valeur — donne `reference_only`.
LICENCES_REPRODUCTIBLES = frozenset({
    "cc0", "cc-by", "cc-by-sa", "cc-by-nd", "public-domain", "domaine public",
    "open-data", "etalab", "odbl",
})

#: Ce qu'un document non reproductible autorise quand même : le citer par son
#: URL. Une source qu'on ne peut pas republier reste une source qu'on peut
#: nommer, et l'oublier reviendrait à ignorer les meilleures.
REFERENCE_SEULE = "reference_only"
REPRODUCTIBLE = "reproducible"


class CollectionRefused(ValueError):
    """La collecte est refusée, et le message dit laquelle des conditions manque."""


def _chemin(url: str) -> str:
    """Retourne le chemin d'une URL, `/` par défaut."""
    return urlparse(str(url or "")).path or "/"


def robots_disallows(robots_txt: str, url: str, agent: str = "*") -> Optional[str]:
    """
    Applique un `robots.txt` à une URL.

    Args:
        robots_txt: Le contenu du fichier, **fourni** : ce module ne va pas le
            chercher.
        url: L'adresse visée.
        agent: L'agent déclaré. Les règles de `*` s'appliquent en plus des
            siennes ; les ignorer serait lire le fichier à moitié.

    Returns:
        Le chemin interdit qui s'applique, ou None si rien n'interdit.

    Un `robots.txt` vide ou absent n'interdit rien — c'est sa sémantique, et
    inventer une interdiction empêcherait de collecter une source parfaitement
    ouverte.
    """
    chemin = _chemin(url)
    agent_courant: Optional[str] = None
    interdits: List[str] = []

    for ligne in (robots_txt or "").splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if not ligne or ":" not in ligne:
            continue
        cle, valeur = (partie.strip() for partie in ligne.split(":", 1))
        cle = cle.lower()
        if cle == "user-agent":
            agent_courant = valeur.lower()
        elif cle == "disallow" and agent_courant in ("*", agent.lower()):
            if valeur:
                interdits.append(valeur)

    for interdit in interdits:
        if chemin.startswith(interdit):
            return interdit
    return None


def plan_collection(
    url: str,
    licence: str = "",
    robots_txt: str = "",
    agent: str = "*",
    registre: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Décide si un document peut être collecté, et sous quelle forme.

    Args:
        url: Adresse du document visé.
        licence: Licence déclarée par l'opérateur. Vide = inconnue.
        robots_txt: Contenu de `robots.txt` du domaine, fourni par l'appelant.
        agent: Agent déclaré pour la lecture de `robots.txt`.
        registre: Registre déjà chargé.

    Returns:
        Le verdict, l'usage autorisé (`reproducible` ou `reference_only`), et la
        demande d'approbation à soumettre. **Rien n'est téléchargé.**
    """
    registre = registre or load_registry()

    raison_de_refus = denied_reason(url, registre)
    if raison_de_refus:
        return _refus(url, f"Source refusée par le registre : {raison_de_refus}")

    inscrite = declared_source(url, registre)
    if inscrite is None:
        return _refus(
            url,
            "Domaine non inscrit au registre. Le chapitre 07 propose des candidats ; "
            "les inscrire est une décision humaine, et c'est elle qui autorise la "
            "collecte. Aucune recherche libre sur le web n'est faite.",
        )

    interdit = robots_disallows(robots_txt, url, agent)
    if interdit:
        return _refus(
            url,
            f"`robots.txt` interdit « {interdit} » pour cet agent. Le fichier est "
            "appliqué, pas consulté pour information.",
        )

    normalisee = licence.strip().lower()
    reproductible = normalisee in LICENCES_REPRODUCTIBLES
    usage = REPRODUCTIBLE if reproductible else REFERENCE_SEULE

    return {
        "allowed": True,
        "url": url,
        "source": inscrite["name"],
        "scope": inscrite["scope"],
        "category": inscrite["category"].value,
        "licence": licence.strip() or "inconnue",
        "usage": usage,
        "usage_reason": (
            "Licence reproductible déclarée : le contenu peut être stocké en entier."
            if reproductible else
            "Licence inconnue ou non reproductible : le document est citable par son "
            "URL, pas reproductible en entier. Une licence absente ne bloque pas, elle "
            "dégrade — sinon les meilleures sources seraient les premières écartées."
        ),
        # Le portillon (ADR-006) est la quatrième condition, et la seule qu'un
        # module ne peut pas satisfaire seul.
        "requires_approval": True,
        "approval_request": {
            "action": "collect_document",
            "description": (
                f"Collecter « {url} » depuis {inscrite['name']} "
                f"(licence : {licence.strip() or 'inconnue'}, usage : {usage})."
            ),
            "metadata": {
                "url": url,
                "source": inscrite["name"],
                "licence": licence.strip() or "inconnue",
                "usage": usage,
                "scope": inscrite["scope"],
            },
        },
        "downloaded": False,
        "note": (
            "Rien n'a été téléchargé. Ce module décide ; la collecte est faite "
            "ensuite, une fois la demande approuvée."
        ),
    }


def _refus(url: str, raison: str) -> Dict[str, Any]:
    """Assemble un refus de collecte."""
    return {
        "allowed": False,
        "url": url,
        "reason": raison,
        "requires_approval": False,
        "downloaded": False,
        "usage": None,
    }


def submit_collection(context: Any, plan: Dict[str, Any]) -> Optional[str]:
    """
    Soumet un plan de collecte au portillon humain.

    Args:
        context: `AgentContext` portant le portillon.
        plan: Le plan rendu par `plan_collection`.

    Returns:
        L'identifiant de la demande, ou None si le portillon est indisponible.

    Raises:
        CollectionRefused: Si le plan n'est pas autorisé. Soumettre un plan
            refusé demanderait à un humain de valider ce que la règle a déjà
            écarté — et rendrait le refus négociable.
    """
    if not plan.get("allowed"):
        raise CollectionRefused(plan.get("reason", "Collecte refusée."))

    demande = plan["approval_request"]
    return context.submit_approval(
        action=demande["action"],
        description=demande["description"],
        metadata=demande["metadata"],
    )
