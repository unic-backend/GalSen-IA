"""
What actually reaches the agents — measured, not assumed.

Five waves of work added tools, knowledge, plugins, routines, layers. Each was
tested where it was written. None of that answers the question this wave exists
for: **can an agent use it?**

The failure mode is specific and quiet. A capability lands in `src/`, gets a
route, gets tests, and never appears in `AgentContext` — so it works for
everyone except the agents the platform is made of. Nobody notices, because
nothing fails: the agents simply keep doing what they did before.

So this module confronts two lists it does not own: what the platform declares
it can do, and what an agent can actually call. The gap between them is the
finding, and it is reported whether it is empty or not — a coverage report that
only speaks when something is missing teaches nobody that it was checked.

**It measures by name, and says so.** It looks for a method on `AgentContext`;
it does not verify that the method works, which the capability's own tests do.
Reading "reaches: true" as "works" would be the wrong lesson.
"""

from __future__ import annotations

from typing import Any, Dict, List

#: Ce que la plateforme sait faire, et par quelle méthode un agent l'atteint.
#: Écrit à la main **exprès** : une liste dérivée automatiquement du code
#: dirait seulement que le code est cohérent avec lui-même. Celle-ci dit ce
#: qu'on **voulait** qui arrive aux agents.
CAPACITES: Dict[str, Dict[str, str]] = {
    "tools": {
        "method": "use_tool",
        "what": "Appeler un outil du registre, sous plafond de rôle (VOLET 39).",
    },
    "memory_write": {
        "method": "remember",
        "what": "Écrire un souvenir, dans une couche qui a une durée de vie (VOLET 60).",
    },
    "memory_read": {
        "method": "recall",
        "what": "Relire ses souvenirs.",
    },
    "knowledge_search": {
        "method": "search_knowledge",
        "what": "Chercher dans la base de connaissance.",
    },
    "knowledge_write": {
        "method": "add_knowledge",
        "what": "Ajouter une connaissance, sous la frontière d'isolation (VOLET 40).",
    },
    "world_knowledge": {
        "method": "ask_knowledge",
        "what": (
            "Interroger les couches mondiale et sénégalaise, en sachant "
            "laquelle répond (VOLETs 52 et 57)."
        ),
    },
    "documents": {
        "method": "analyze_document",
        "what": "Lire et analyser un document.",
    },
    "vision": {
        "method": "analyze_image",
        "what": "Analyser une image.",
    },
    "web": {
        "method": "search_web",
        "what": "Chercher sur le web.",
    },
    "generation": {
        "method": "generate",
        "what": "Demander une génération à un modèle.",
    },
    "delegation": {
        "method": "delegate",
        "what": "Confier une tâche à un autre agent.",
    },
    "audit": {
        "method": "record_audit",
        "what": "Écrire au journal d'audit.",
    },
    "approval": {
        "method": "submit_approval",
        "what": "Demander une décision humaine (ADR-006).",
    },
}

#: Capacités que les agents **n'ont pas**, avec la raison. Nommées plutôt
#: qu'absentes : une capacité manquante et une capacité volontairement hors de
#: portée se ressemblent, et seule la seconde est une décision.
HORS_DE_PORTEE: Dict[str, str] = {
    "plugins": (
        "Un agent n'installe ni n'active un greffon : accorder sa confiance à "
        "du code écrit ailleurs est une décision humaine (VOLET 58)."
    ),
    "routines": (
        "Un agent ne déclare pas de routine : ce qui tourne sans témoin se "
        "décide en dehors d'un tour d'agent (VOLET 47)."
    ),
    "notifications": (
        "Un agent ne notifie pas directement : les événements qui méritent une "
        "notification sont émis par les moteurs qui les constatent (VOLET 50)."
    ),
    "connectors": (
        "Un agent n'appelle pas un connecteur : il passe par un outil, qui "
        "porte un plafond et une capacité déclarée."
    ),
}


def agent_reach(context_class: Any = None) -> Dict[str, Any]:
    """
    Ce qu'un agent peut réellement appeler, et ce qui lui manque.

    Args:
        context_class: La classe de contexte examinée. `AgentContext` par
            défaut.

    Returns:
        Une entrée par capacité, la liste de ce qui n'arrive pas, et ce que
        cette mesure ne prouve pas.
    """
    if context_class is None:
        from .context import AgentContext

        context_class = AgentContext

    atteintes: List[Dict[str, Any]] = []
    manquantes: List[Dict[str, Any]] = []

    for nom, declaration in sorted(CAPACITES.items()):
        present = callable(getattr(context_class, declaration["method"], None))
        entree = {
            "capability": nom,
            "method": declaration["method"],
            "what": declaration["what"],
            "reaches_agents": present,
        }
        (atteintes if present else manquantes).append(entree)

    return {
        "capabilities": atteintes + manquantes,
        "reached": len(atteintes),
        "missing": [entree["capability"] for entree in manquantes],
        "out_of_reach_by_design": dict(sorted(HORS_DE_PORTEE.items())),
        "method": "attribute_lookup",
        "rules": [
            "La liste des capacités est écrite à la main : dérivée du code, "
            "elle dirait seulement que le code est cohérent avec lui-même.",
            "Ce qui est **volontairement** hors de portée est nommé : une "
            "capacité manquante et une capacité écartée se ressemblent, et "
            "seule la seconde est une décision.",
            "Le rapport parle même quand rien ne manque : un contrôle qui ne "
            "s'exprime qu'en cas d'échec n'apprend à personne qu'il a eu lieu.",
        ],
        "does_not": [
            "Vérifier qu'une méthode **fonctionne** : elle est cherchée par son "
            "nom. Lire « atteint » comme « marche » serait la mauvaise leçon — "
            "ce sont les tests de chaque capacité qui l'établissent.",
            "Découvrir une capacité que personne n'a déclarée ici.",
        ],
    }
