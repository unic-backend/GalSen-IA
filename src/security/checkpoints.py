"""
Ce qu'on peut encore défaire (VOLET 34, ch. 13, phase 2).

Le brief demande des « points de reprise ». Ils existent déjà, mais chacun dans
son coin : le journal des opérations de fichiers (ch. 07), les décisions du
portillon (ADR-006), les sauvegardes de base (`scripts/backup.py`). Quelqu'un
qui découvre au réveil qu'un agent a rangé son disque ne va pas ouvrir trois
modules pour savoir ce qui est réversible.

Ce module rassemble, **sans rien réimplémenter** : chaque point de reprise dit
d'où il vient et comment on le défait. La vue est en lecture seule ; annuler
reste l'affaire du sous-système concerné, qui sait ce qu'il fait.

## Ce qu'il ne prétend pas être

**Il n'y a pas de « tout annuler ».** Un bouton unique laisserait croire que
l'état de la machine se rembobine, alors que seules certaines opérations sont
réversibles :

| Origine | Réversible ? |
|---|---|
| Opérations de fichiers | **oui**, une par une, tant que la destination n'a pas bougé |
| Écritures de code | **oui** via le retour arrière de la boucle (VOLET 31) |
| Décisions d'approbation | **non** — une décision prise est un fait, pas un état |
| Commandes exécutées | **non** — rien ne sait défaire un effet de bord |
| Sauvegardes de base | **restauration**, pas annulation : elle ramène *tout* |

Rendre ces lignes ensemble, avec leur colonne « réversible », est plus utile
qu'un bouton qui mentirait sur la moitié d'entre elles.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Types de points de reprise rassemblés ici.
ORIGINES = ("file_operation", "approval", "backup")


def list_checkpoints(limit: int = 100) -> Dict[str, Any]:
    """
    Rassemble les points de reprise disponibles, du plus récent au plus ancien.

    Args:
        limit: Nombre maximal d'entrées par origine.

    Returns:
        Les entrées, le nombre de celles qui sont réellement annulables, et les
        origines qui n'ont pas pu être lues — une origine muette se lirait
        « rien à défaire », ce qui est le contraire de ce qu'elle veut dire.
    """
    entrees: List[Dict[str, Any]] = []
    indisponibles: List[Dict[str, str]] = []

    for origine, collecte in (
        ("file_operation", _operations_de_fichiers),
        ("approval", _decisions),
        ("backup", _sauvegardes),
    ):
        try:
            entrees.extend(collecte(limit))
        except Exception as erreur:  # noqa: BLE001 - une origine muette se dit
            logger.warning("Points de reprise « %s » illisibles : %s", origine, erreur)
            indisponibles.append({"origin": origine, "reason": str(erreur)})

    entrees.sort(key=lambda entree: entree.get("at") or 0, reverse=True)
    annulables = [entree for entree in entrees if entree["reversible"]]

    return {
        "checkpoints": entrees,
        "count": len(entrees),
        "reversible_count": len(annulables),
        "unavailable": indisponibles,
        # Dit une fois, ici, pour que personne n'attende un bouton qui n'existe
        # pas : rembobiner une machine n'est pas une opération.
        "global_undo": False,
        "note": (
            "Il n'y a pas d'annulation globale : seules les opérations marquées "
            "« reversible » se défont, une par une."
        ),
    }


def undo(checkpoint_id: str) -> Dict[str, Any]:
    """
    Défait un point de reprise, quand son origine sait le faire.

    Args:
        checkpoint_id: Identifiant rendu par `list_checkpoints()`.

    Returns:
        Le résultat de l'annulation, ou le refus **avec sa raison**. Un
        identifiant inconnu et une opération non réversible sont deux réponses
        distinctes : les confondre enverrait chercher au mauvais endroit.
    """
    if not checkpoint_id.startswith("op_"):
        return {
            "status": "refused",
            "reason": (
                "Seules les opérations de fichiers se défont. Une décision "
                "d'approbation est un fait, et une sauvegarde se restaure — "
                "elle ramène tout, ce qui n'est pas la même chose."
            ),
        }

    from src.storage.reversible import ReversibleFiles
    from src.storage.roots import declared_roots

    try:
        operation = ReversibleFiles(declared_roots()).undo(checkpoint_id)
    except Exception as erreur:  # noqa: BLE001 - un refus d'annulation est une donnée
        return {"status": "refused", "reason": str(erreur)}
    return {"status": "undone", "operation": operation.to_dict()}


# ----------------------------------------------------------------------
# Origines
# ----------------------------------------------------------------------


def _operations_de_fichiers(limit: int) -> List[Dict[str, Any]]:
    """Lit le journal des opérations de fichiers (ch. 07)."""
    from src.storage.reversible import ReversibleFiles
    from src.storage.roots import declared_roots

    journal = ReversibleFiles(declared_roots())
    entrees = []
    for operation in journal.history(limit=limit):
        entrees.append({
            "id": operation.id,
            "origin": "file_operation",
            "at": operation.at,
            "description": operation.describe(),
            "reason": operation.reason,
            # Une opération déjà annulée n'est plus un point de reprise : la
            # rejouer écraserait ce qui est revenu à sa place.
            "reversible": not operation.undone,
            "undone": operation.undone,
            "how": "src.security.checkpoints.undo(id)",
        })
    return entrees


def _decisions(limit: int) -> List[Dict[str, Any]]:
    """Lit les décisions du portillon d'approbation (ADR-006)."""
    from src.integration.engine_registry import get_shared_registry

    portillon = get_shared_registry().try_get("approval")
    if portillon is None:
        return []

    entrees = []
    for demande in portillon.list_requests(limit=limit):
        statut = getattr(demande, "status", None)
        statut = getattr(statut, "value", statut)
        entrees.append({
            "id": demande.id,
            "origin": "approval",
            "at": getattr(demande, "decided_at", None) or getattr(demande, "created_at", None),
            "description": f"{demande.action} — {statut}",
            "reason": getattr(demande, "reason", "") or "",
            # Une décision humaine ne se défait pas : elle a eu lieu. Ce qu'elle
            # a autorisé se défait peut-être, et cela apparaît ailleurs.
            "reversible": False,
            "status": statut,
            "how": "une décision prise est un fait ; c'est son effet qui se défait",
        })
    return entrees


def _sauvegardes(limit: int) -> List[Dict[str, Any]]:
    """Liste les sauvegardes de base présentes sur le disque."""
    from src.storage.paths import data_dir

    repertoire = data_dir()
    if not os.path.isdir(repertoire):
        return []

    entrees = []
    for nom in sorted(os.listdir(repertoire)):
        if not nom.endswith(".backup.sqlite"):
            continue
        chemin = os.path.join(repertoire, nom)
        entrees.append({
            "id": nom,
            "origin": "backup",
            "at": os.path.getmtime(chemin),
            "description": f"sauvegarde {nom}",
            "reason": "",
            # Restaurer n'est pas annuler : cela ramène **tout** l'état de la
            # base, y compris ce que personne ne voulait perdre depuis.
            "reversible": False,
            "path": chemin,
            "size_bytes": os.path.getsize(chemin),
            "how": "restauration manuelle, instance arrêtée (docs/deployment/rollback.md)",
        })
    return entrees[:limit]


def describe(checkpoint_id: str, limit: int = 500) -> Optional[Dict[str, Any]]:
    """Retourne un point de reprise par identifiant, ou None."""
    for entree in list_checkpoints(limit=limit)["checkpoints"]:
        if entree["id"] == checkpoint_id:
            return entree
    return None
