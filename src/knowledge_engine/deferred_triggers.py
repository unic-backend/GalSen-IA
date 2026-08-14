"""
Les capacités différées, et la mesure qui les rouvrira (VOLET 36, chapitre H).

Le chapitre H du plan est le seul à ne rien construire, et c'est sa conclusion
qui est le travail : base vectorielle, base graphe, stockage objet, flux
d'événements, acquisition automatisée. Chacune est **différée avec son
déclencheur écrit** — pas refusée.

## Pourquoi un module plutôt qu'un paragraphe

Un déclencheur écrit dans un document est un déclencheur que personne ne relit.
« Adopter une base graphe au-delà de 100 000 entités » est vrai le jour où on
l'écrit et oublié six mois plus tard, quand il y en a 400 000 et que quelqu'un
choisit une infrastructure au jugé — ou continue sans, faute d'avoir regardé.

Ce module **mesure** l'état réel du dépôt contre chaque seuil, et le détecteur
`deferred_capabilities` (`src/proactive/`) ne parle **que** si un seuil est
franchi. Tant que rien n'est atteint, il se tait : c'est la différence entre
une décision différée et une décision oubliée.

## Un déclencheur peut être faux, et celui-ci l'était

`automated_acquisition` était différée sur « un corpus sénégalais existant qu'il
faut tenir à jour ». Ce déclencheur mesurait le **résultat** de la capacité
manquante : aucun chemin du dépôt ne pouvait produire ce corpus tant que
l'acquisition n'existait pas, et `met` ne pouvait donc jamais devenir vrai.

Corrigé le 2026-08-14 par l'ADR-021. La question à poser à tout déclencheur est
écrite ici pour la prochaine fois : **ce que je mesure peut-il bouger sans que
la capacité existe ?** Si non, ce n'est pas un report — c'est un refus déguisé
en mesure.

## Ce que ce module ne fait pas

Il ne construit aucune de ces capacités, et il n'en recommande aucune tant que
sa mesure ne le justifie pas. Un seuil non atteint et un seuil non mesurable
sont **deux réponses distinctes** : `met: false` dit « mesuré, en dessous »,
`measurable: false` dit « ce fait ne se lit pas depuis le dépôt » — un
déploiement supplémentaire est une réalité d'exploitation, pas une ligne de code.
"""

import os
from typing import Any, Dict, List, Optional

#: Seuils, tels qu'ils ont été écrits quand la décision a été prise. Les changer
#: est une décision en soi : ils existent pour qu'une infrastructure soit
#: adoptée sur une mesure, jamais sur une impression.
SEUIL_VECTEURS = 100_000
SEUIL_ENTITES = 100_000
SEUIL_PROFONDEUR = 3
SEUIL_MILLISECONDES = 200


def _compter_connaissances() -> Optional[int]:
    """Retourne le nombre d'éléments de connaissance, ou None si illisible."""
    try:
        from src.integration.engine_registry import get_shared_registry

        moteur = get_shared_registry().try_get("knowledge")
        if moteur is None:
            return None
        return int(moteur.quality_report().get("items", 0))
    except Exception:
        # Une mesure impossible se dit `None` et devient `measurable: false` :
        # rendre 0 ferait passer une panne de lecture pour une base vide.
        return None


def _compter_entites() -> Dict[str, Any]:
    """Retourne le nombre d'entités et le magasin qui l'a rendu."""
    try:
        from src.knowledge_engine.entities import entity_store

        rapport = entity_store().report()
        return {"count": rapport["entities"], "backend": rapport["backend"]}
    except Exception:
        return {"count": None, "backend": "unknown"}


def _compter_sources_activees() -> int:
    """
    Retourne le nombre de sources **activées et acquérables** au registre.

    C'est la mesure qui remplace celle du corpus : elle porte sur ce qu'une
    personne a décidé, pas sur le résultat de la capacité différée.
    """
    try:
        from src.knowledge_engine.source_registry import acquirable_sources

        return len(acquirable_sources())
    except Exception:
        return 0


def _compter_documents_senegalais() -> Optional[int]:
    """Retourne le nombre d'éléments de portée `country:sn`, ou None."""
    try:
        from src.integration.engine_registry import get_shared_registry

        moteur = get_shared_registry().try_get("knowledge")
        if moteur is None:
            return None
        elements = moteur.get_store().list_items(limit=10000)
        return sum(1 for element in elements if str(getattr(element, "scope", "")) == "country:sn")
    except Exception:
        return None


def deferred_report() -> Dict[str, Any]:
    """
    Mesure chaque capacité différée contre son déclencheur.

    Returns:
        Une entrée par capacité : le déclencheur écrit, la mesure du jour, et
        `met` — vrai seulement quand le seuil est franchi. Les capacités dont
        le déclencheur ne se lit pas depuis le dépôt portent
        `measurable: false` avec la raison, jamais un `false` qui ferait croire
        à une mesure.
    """
    connaissances = _compter_connaissances()
    entites = _compter_entites()
    senegalais = _compter_documents_senegalais()
    sources_activees = _compter_sources_activees()

    capacites: List[Dict[str, Any]] = [
        {
            "capability": "vector_database",
            "trigger": f"plus de {SEUIL_VECTEURS:,} vecteurs à indexer".replace(",", " "),
            "measured": connaissances,
            "threshold": SEUIL_VECTEURS,
            "measurable": connaissances is not None,
            "met": bool(connaissances is not None and connaissances >= SEUIL_VECTEURS),
            "note": (
                "`src/embeddings/` porte déjà un index sémantique en mémoire. Une "
                "base vectorielle dédiée est un service à exploiter : elle se "
                "justifie par un volume, pas par une envie."
            ),
        },
        {
            "capability": "graph_database",
            "trigger": (
                f"plus de {SEUIL_ENTITES:,} entités, un parcours au-delà de la "
                f"profondeur {SEUIL_PROFONDEUR}, ou une requête au-delà de "
                f"{SEUIL_MILLISECONDES} ms en SQLite"
            ).replace(",", " "),
            "measured": entites["count"],
            "threshold": SEUIL_ENTITES,
            "measurable": entites["count"] is not None,
            "met": bool(entites["count"] is not None and entites["count"] >= SEUIL_ENTITES),
            "note": (
                f"Magasin lu : « {entites['backend']} ». En `in-memory`, le compte "
                "vaut 0 par construction — rien ne persiste d'une exécution à "
                "l'autre, et ce n'est pas une mesure du corpus."
            ),
        },
        {
            "capability": "object_storage_for_knowledge",
            "trigger": "une seconde instance ou un second déploiement (ADR-009 en autorise une)",
            "measured": None,
            "threshold": None,
            # Un second déploiement est une réalité d'exploitation : il ne se lit
            # pas dans le dépôt. `GALSEN_ALLOW_MULTI_INSTANCE` dit seulement ce
            # que l'opérateur a déclaré, ce qui est une intention, pas un fait.
            "measurable": False,
            "met": False,
            "declared_multi_instance": os.getenv("GALSEN_ALLOW_MULTI_INSTANCE", "").strip().lower()
            in ("1", "true", "yes", "oui"),
            "note": (
                "Le stockage objet **existe déjà** pour le service de fichiers "
                "(`src/services/file/store_s3.py`, ADR-016) : ce qui est différé, "
                "c'est d'y déplacer la connaissance et ses index. Le fait "
                "déclencheur ne se lit pas depuis le dépôt — le verrou d'instance "
                "(`src/api/instance_lock.py`) refuse une seconde instance tant "
                "qu'elle n'est pas déclarée, et c'est là que la question se posera."
            ),
        },
        {
            "capability": "event_streams",
            "trigger": "un consommateur asynchrone qu'un appel direct ne sert pas",
            "measured": None,
            "threshold": None,
            "measurable": False,
            "met": False,
            "note": (
                "Aucun consommateur asynchrone n'existe. Une file d'attente sans "
                "consommateur ajoute une panne possible et aucune capacité."
            ),
        },
        {
            "capability": "automated_acquisition",
            # **Déclencheur corrigé le 2026-08-14 (ADR-021).** Il disait « un
            # corpus sénégalais existant qu'il faut tenir à jour » et mesurait
            # donc le **résultat** de la capacité manquante : rien ne pouvait
            # produire ce corpus tant que l'acquisition n'existait pas, et `met`
            # ne pouvait devenir vrai par aucun chemin du dépôt.
            "trigger": (
                "une source déclarée **et activée** au registre, dont les "
                "conditions d'accès ont été établies (ADR-021)"
            ),
            "measured": sources_activees,
            "threshold": 1,
            "measurable": True,
            "met": bool(sources_activees),
            # La capacité n'est plus différée : elle est construite (étapes 1 à
            # 10 de `docs/architecture/senegal-knowledge-acquisition.md`). Ce qui
            # reste ouvert est l'activation d'une source — une décision humaine,
            # pas une ligne de code manquante.
            "status": "built_and_gated",
            "note": (
                "Le chemin existe : registre, découverte, décision, approbation "
                "par lot, récupération polie, barrière de confiance, dix "
                "contrôles, proposition de manifeste. Il n'atteint aucune source "
                "tant qu'aucune n'est activée, et l'activer demande d'avoir lu "
                "des conditions d'utilisation — ce qu'aucun programme ne fait "
                "honnêtement. Documents sénégalais en base : "
                f"{senegalais if senegalais is not None else 'non mesurable'}."
            ),
        },
    ]

    return {
        "capabilities": capacites,
        "met": [entree["capability"] for entree in capacites if entree["met"]],
        "unmeasurable": [
            entree["capability"] for entree in capacites if not entree["measurable"]
        ],
        "note": (
            "Différé n'est pas refusé. Chaque capacité porte le déclencheur qui "
            "rouvrira la décision, et il est mesuré à chaque scan proactif au "
            "lieu de dormir dans un document."
        ),
    }
