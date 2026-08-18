"""
Which narrative shape — and the refusal to impose one that does not belong.

Directive §6 lists a structure — hook, introduction, context, argument,
evidence, demonstration, transition, conclusion, CTA — and then adds the
sentence that matters more than the list: *do not force this structure when
inappropriate.*

That sentence is the whole module, because the failure it prevents is the
default behaviour of every story engine ever written. The list above is a
**marketing** structure. Applied to a documentary it produces an advert with
archive footage; applied to a lesson it produces a sales pitch about
photosynthesis; applied to a news report it produces something a newsroom
cannot broadcast. The engine does not misbehave — it does exactly what it was
built to do, to material that never asked for it.

So structures are declared per domain and an undeclared domain gets **no
structure at all**. Falling back to the marketing shape would be the precise
error the directive names, arrived at by way of a sensible-looking default.

Two consequences follow.

**A call to action is a marketing device, not a narrative universal.** It is
allowed only in the domains that have one. A documentary that ends by asking
the viewer to subscribe has been turned into an advert, and the person who
notices is the client.

**A role is assigned to material that exists, never filled with invention.** The
story engine sorts what was actually said into narrative positions. A role with
nothing to put in it is reported empty, with its name — because "this
documentary has no evidence section" is a fact the director needs, and quietly
generating a plausible evidence section is how a machine ends up writing the
argument instead of arranging it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

#: Ce qu'une demande de structure peut donner.
STRUCTURE_TROUVEE = "STRUCTURE_FOUND"
STRUCTURE_INCONNUE = "STRUCTURE_UNKNOWN"

#: Les structures déclarées, par domaine. Chacune vient de la façon dont son
#: domaine raconte réellement, pas d'un gabarit unique décliné.
#:
#: Un domaine absent de cette table n'a **pas** de structure ici. C'est un
#: refus, pas un trou à combler : retomber sur la structure marketing est
#: exactement l'erreur que la directive §6 nomme.
STRUCTURES: Dict[str, Dict[str, Any]] = {
    "marketing": {
        "roles": ("hook", "context", "argument", "evidence", "cta"),
        "allows_cta": True,
        "note": "Convaincre. L'appel à l'action y est légitime et attendu.",
    },
    "social": {
        "roles": ("hook", "payoff", "cta"),
        "allows_cta": True,
        "note": "Retenir en quelques secondes. La promesse doit être tenue vite.",
    },
    "documentary": {
        "roles": ("hook", "context", "development", "evidence", "resolution"),
        "allows_cta": False,
        "note": (
            "Montrer et laisser conclure. Un appel à l'action en ferait une "
            "publicité, et c'est le client qui s'en aperçoit."
        ),
    },
    "education": {
        "roles": ("objective", "prior_knowledge", "explanation",
                  "demonstration", "practice", "summary"),
        "allows_cta": False,
        "note": (
            "Faire comprendre. L'objectif vient en premier parce qu'un élève "
            "doit savoir ce qu'il va apprendre avant d'apprendre."
        ),
    },
    "news": {
        "roles": ("lede", "context", "detail", "attribution"),
        "allows_cta": False,
        "note": (
            "Informer. L'attribution est un rôle à part entière : une "
            "information sans source n'est pas diffusable."
        ),
    },
    "interview": {
        "roles": ("question", "answer", "follow_up", "closing"),
        "allows_cta": False,
        "note": "Laisser parler. La structure suit l'échange, pas l'inverse.",
    },
    "sports_analysis": {
        "roles": ("situation", "action", "breakdown", "conclusion"),
        "allows_cta": False,
        "note": "Expliquer un geste. L'action précède toujours son analyse.",
    },
    "scientific": {
        "roles": ("question", "method", "result", "limitation"),
        "allows_cta": False,
        "note": (
            "La limite est un rôle **obligatoire** : un résultat présenté sans "
            "ses limites est une affirmation, pas une science."
        ),
    },
}


class StoryRefused(ValueError):
    """Une structure demandée qui ne peut pas être servie telle quelle."""


def structure_for(domain: str) -> Dict[str, Any]:
    """
    La structure narrative d'un domaine, ou un refus.

    Args:
        domain: Le domaine de la production.

    Returns:
        Ses rôles et ses règles, ou `STRUCTURE_UNKNOWN` avec les domaines
        déclarés. Aucun repli : appliquer la structure marketing à un
        documentaire produit une publicité avec des images d'archive, et le
        moteur n'aura pas mal fonctionné — il aura fait exactement ce pour quoi
        il a été écrit, sur une matière qui ne l'a pas demandé.
    """
    declare = STRUCTURES.get(str(domain or "").strip().lower())
    if declare is None:
        return {
            "status": STRUCTURE_INCONNUE,
            "domain": domain,
            "declared_domains": sorted(STRUCTURES),
            "reason": (
                f"Aucune structure déclarée pour « {domain} ». Retomber sur "
                "celle du marketing est exactement l'erreur que la directive "
                "§6 nomme : elle produirait un argumentaire là où personne n'en "
                "a demandé."
            ),
        }
    return {
        "status": STRUCTURE_TROUVEE,
        "domain": domain,
        "roles": list(declare["roles"]),
        "allows_cta": declare["allows_cta"],
        "note": declare["note"],
    }


def assign_roles(
    domain: str, material: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Range de la matière réelle dans les rôles narratifs du domaine.

    Args:
        domain: Le domaine de la production.
        material: Les éléments disponibles, chacun portant `role` et `quote`.
            Le rôle est proposé par un modèle ; la citation vient de la
            transcription.

    Returns:
        Les rôles remplis, ceux qui restent **vides et nommés**, et les rôles
        proposés qui n'existent pas dans ce domaine. Rien n'est inventé pour
        combler : « ce documentaire n'a pas de partie preuve » est un fait dont
        le réalisateur a besoin, et générer une section plausible est la façon
        dont une machine se met à écrire l'argument au lieu de l'agencer.

    Raises:
        StoryRefused: Pour un domaine sans structure déclarée.
    """
    structure = structure_for(domain)
    if structure["status"] != STRUCTURE_TROUVEE:
        raise StoryRefused(structure["reason"])

    roles = list(structure["roles"])
    remplis: Dict[str, List[Dict[str, Any]]] = {role: [] for role in roles}
    hors_structure: List[Dict[str, Any]] = []

    for element in material:
        role = str(element.get("role", "")).strip().lower()
        if role in remplis:
            remplis[role].append(dict(element))
        else:
            hors_structure.append({
                "role": role or "(sans rôle)",
                "quote": element.get("quote", ""),
                "reason": (
                    f"« {role} » n'est pas un rôle du domaine « {domain} ». Le "
                    "ranger ailleurs de force ferait raconter autre chose."
                ),
            })

    vides = [role for role in roles if not remplis[role]]
    return {
        "domain": domain,
        "roles": roles,
        "filled": {role: entrees for role, entrees in remplis.items() if entrees},
        "empty_roles": vides,
        "outside_structure": hors_structure,
        "complete": not vides,
        "allows_cta": structure["allows_cta"],
        "note": (
            "Les rôles vides sont **nommés**, jamais comblés. Générer une "
            "section plausible est la façon dont une machine se met à écrire "
            "l'argument au lieu de l'agencer."
        ),
    }


def check_cta(domain: str, has_cta: bool) -> Dict[str, Any]:
    """
    Dit si un appel à l'action a sa place dans ce domaine.

    Args:
        domain: Le domaine.
        has_cta: Si la production en contient un.

    Returns:
        Le verdict et sa raison. Un appel à l'action est un procédé **marketing**,
        pas un universel narratif : un documentaire qui finit en demandant de
        s'abonner a été transformé en publicité.
    """
    structure = structure_for(domain)
    if structure["status"] != STRUCTURE_TROUVEE:
        return {"allowed": False, "reason": structure["reason"]}

    if not has_cta:
        return {"allowed": True, "present": False,
                "reason": "Aucun appel à l'action."}
    if structure["allows_cta"]:
        return {"allowed": True, "present": True,
                "reason": f"L'appel à l'action est attendu en « {domain} »."}
    return {
        "allowed": False, "present": True,
        "reason": (
            f"Un appel à l'action n'a pas sa place en « {domain} ». Il "
            "transforme la production en publicité, et c'est le client qui s'en "
            "aperçoit."
        ),
    }


def story_report() -> Dict[str, Any]:
    """
    Ce que l'intelligence narrative garantit, et ce qu'elle refuse.

    Returns:
        Les domaines déclarés, leurs rôles, et les règles tenues.
    """
    return {
        "domains": {
            nom: {"roles": list(details["roles"]),
                  "allows_cta": details["allows_cta"]}
            for nom, details in sorted(STRUCTURES.items())
        },
        "states": [STRUCTURE_TROUVEE, STRUCTURE_INCONNUE],
        "rules": [
            "La structure de la directive §6 est une structure **marketing**. "
            "L'appliquer à un documentaire produit une publicité avec des "
            "images d'archive.",
            "Un domaine non déclaré n'a **aucune** structure ici : retomber "
            "sur celle du marketing serait l'erreur nommée par la directive, "
            "atteinte par un défaut d'apparence raisonnable.",
            "L'appel à l'action est un procédé marketing, pas un universel : il "
            "n'est permis que là où le domaine en a un.",
            "Un rôle est rempli avec de la matière **existante**. Un rôle vide "
            "est nommé, jamais comblé.",
            "Un rôle proposé qui n'existe pas dans le domaine est rapporté : le "
            "ranger de force ferait raconter autre chose.",
        ],
        "does_not": [
            "Imposer une structure à un domaine qui n'en déclare pas.",
            "Ajouter un appel à l'action à un documentaire, une leçon ou une "
            "information.",
            "Générer le contenu d'un rôle vide.",
            "Déplacer un élément vers un rôle voisin pour compléter la forme.",
        ],
    }
