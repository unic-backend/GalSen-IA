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
            "trigger": "un corpus sénégalais existant qu'il faut tenir à jour",
            "measured": senegalais,
            "threshold": 1,
            "measurable": senegalais is not None,
            "met": bool(senegalais),
            "note": (
                "Le goulot n'est pas l'ingestion — elle fonctionne, manifeste "
                "compris. Il est qu'aucun document sénégalais n'est encore "
                "déclaré. Automatiser la collecte avant d'avoir une source "
                "collecterait du vide, régulièrement."
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
