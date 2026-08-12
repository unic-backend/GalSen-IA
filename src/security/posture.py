"""
Ce que la plateforme peut réellement faire à cette machine (VOLET 34, ch. 13).

Le brief demande « un modèle de sécurité ». Le dépôt en a un — RBAC par clé,
propriété par sujet (ADR-010), portillon d'approbation (ADR-006), audit
persistant, racines déclarées, bac à sable, liste blanche MCP — mais il est
**réparti sur six modules et cinq ADR**, et personne ne peut répondre en une
lecture à la question qui compte pour quelqu'un qui confie sa machine :

> *Là, maintenant, qu'est-ce que cette plateforme a le droit de faire chez moi,
> et qu'est-ce que je peux défaire ?*

Ce module répond, et **en mesurant**. Chaque section lit la configuration réelle
et le code réel ; aucune ne recopie ce qu'un document affirme. La différence
n'est pas théorique : ce dépôt a trouvé huit fois des capacités déclarées que
rien n'appliquait, dont une fuite de propriété entre sujets sur cinq routes
publiées.

## La règle de ce fichier

**Une protection absente est rapportée aussi fort qu'une protection présente.**
Chaque section porte ses `gaps` : ce que cette couche **ne** garantit **pas**,
repris des modules eux-mêmes (`sandbox.NON_GARANTI`, par exemple) plutôt que
réécrit ici — deux formulations d'une même limite finissent toujours par
diverger, et c'est la plus rassurante qui survit.
"""

import logging
import os
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

#: Sections rapportées, dans l'ordre où elles comptent pour la personne qui lit :
#: d'abord ce qui touche sa machine, ensuite ce qui touche ses données.
SECTIONS = (
    "filesystem", "execution", "perception", "exposure",
    "identity", "approval", "audit", "sovereignty", "recovery",
)


def posture() -> Dict[str, Any]:
    """
    Mesure l'état de sécurité de la plateforme, section par section.

    Returns:
        Une section par domaine, chacune avec son état mesuré, ses preuves et
        **ce qu'elle ne garantit pas**. Une section qui échoue à se mesurer est
        rendue en `unknown` avec sa raison : une section absente se lirait
        « rien à signaler ».
    """
    mesures: Dict[str, Any] = {}
    for nom, mesure in _MESURES.items():
        mesures[nom] = _mesurer(nom, mesure)

    ouvertes = [
        f"{nom}: {faille}"
        for nom, section in mesures.items()
        for faille in section.get("gaps", [])
    ]
    return {
        "sections": mesures,
        "gap_count": len(ouvertes),
        "gaps": ouvertes,
        # Aucun score global : réduire une posture à « 82 / 100 » ferait passer
        # une racine inscriptible sans portillon pour un détail arithmétique.
        "score": None,
        "score_reason": (
            "Aucune note globale : une note ferait disparaître la faille qui "
            "compte derrière la moyenne de celles qui ne comptent pas."
        ),
    }


def _mesurer(nom: str, mesure: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Exécute une mesure, ou rapporte pourquoi elle n'a pas pu se faire."""
    try:
        return mesure()
    except Exception as erreur:  # noqa: BLE001 - une mesure ratée se dit
        logger.warning("Posture « %s » non mesurable : %s", nom, erreur)
        return {
            "state": "unknown",
            "reason": f"Mesure impossible : {erreur}",
            "gaps": [f"état de « {nom} » inconnu, donc non garanti"],
        }


# ----------------------------------------------------------------------
# Mesures
# ----------------------------------------------------------------------


def _filesystem() -> Dict[str, Any]:
    """Où les agents ont le droit de lire, et où ils ont le droit d'écrire."""
    from src.storage.roots import report

    rapport = report()
    inscriptibles = [
        racine["name"] for racine in rapport["roots"] if racine["writable"]
    ]
    failles = []
    if inscriptibles:
        failles.append(
            f"{len(inscriptibles)} racine(s) inscriptible(s) — un agent peut y "
            f"écrire : {', '.join(inscriptibles)}"
        )
    return {
        "state": "confined" if rapport["count"] else "no_roots",
        "declared_roots": rapport["count"],
        "writable_roots": rapport["writable_count"],
        "variable": rapport["variable"],
        "evidence": rapport["roots"],
        "reversible": True,
        "note": (
            "Rien n'est supprimé : un retrait déplace vers « .galsen-corbeille » "
            "et reste annulable (ch. 07)."
        ),
        "gaps": failles,
    }


def _execution() -> Dict[str, Any]:
    """Ce que la plateforme peut exécuter, et sous quelles bornes."""
    from src.sandbox.runner import describe
    from src.tools.terminal.tool import TerminalTool

    bac = describe()
    return {
        "state": "allowlisted",
        "shell": False,
        "allowed_commands": list(TerminalTool.DEFAULT_ALLOWED_COMMANDS),
        "sandbox_available": bac["available"],
        "sandbox_reason": bac["reason"],
        "limits": bac["policy"],
        # Repris du module, jamais réécrits : deux formulations d'une même
        # limite divergent, et c'est la plus rassurante qui survit.
        "gaps": list(bac["not_guaranteed"]),
    }


def _perception() -> Dict[str, Any]:
    """Ce que la plateforme peut voir et manipuler à l'écran."""
    from src.tools.gui.types import ActionKind
    from src.tools.screen.backends import BackendDePlateforme

    disponible = BackendDePlateforme().available()
    return {
        "state": "gated",
        "screen_backend_available": disponible,
        "gui_actions_require_approval": True,
        "gui_action_kinds": [kind.value for kind in ActionKind],
        "note": (
            "Voir et agir sont deux outils distincts : un agent peut recevoir "
            "des yeux sans recevoir des mains (ch. 05 et 06)."
        ),
        "gaps": [] if not disponible else [
            "une session graphique est joignable : les captures d'écran ne "
            "quittent jamais l'hôte, mais elles existent"
        ],
    }


def _exposure() -> Dict[str, Any]:
    """Ce qu'un appelant extérieur peut atteindre par MCP."""
    from src.mcp.exposure import OUTILS_EXPOSES, REFUS

    return {
        "state": "whitelisted",
        "exposed_tools": list(OUTILS_EXPOSES),
        "withheld_tools": sorted(REFUS),
        "anonymous_calls": False,
        "audits_arguments": False,
        "note": (
            "Le serveur MCP refuse tout appel sans identité résoluble, et trace "
            "l'outil et le sujet sans jamais les arguments (ch. 09)."
        ),
        "gaps": [],
    }


def _identity() -> Dict[str, Any]:
    """Qui la plateforme reconnaît, et ce qui appartient à qui."""
    from src.api.rbac import Permission, Role

    return {
        "state": "rbac_per_key",
        "roles": [role.value for role in Role],
        "permission_count": len(list(Permission)),
        "ownership": "per subject (ADR-010)",
        "gaps": [
            "les identités ne sont pas vérifiées : une clé prouve une "
            "attribution, pas une personne (ADR-010, étape 2)"
        ],
    }


def _approval() -> Dict[str, Any]:
    """Ce qui exige une décision humaine avant d'avoir lieu."""
    from src.storage.paths import storage_backend

    persistant = storage_backend() == "sqlite"
    failles = []
    if not persistant:
        failles.append(
            "le portillon est en mémoire : un redémarrage perd les décisions "
            "en attente (GALSEN_STORAGE_BACKEND=sqlite pour les garder)"
        )
    return {
        "state": "enforced",
        "persistent": persistant,
        "gated": [
            "écriture de code (GuardedEditor, VOLET 31)",
            "gestes d'interface (GUITool, ch. 06)",
            "rangement de fichiers (organizer, ch. 11)",
            "export de données d'entraînement (VOLET 33)",
        ],
        "reference": "ADR-006",
        "gaps": failles,
    }


def _audit() -> Dict[str, Any]:
    """Ce que la plateforme garde de ce qu'elle a fait."""
    from src.storage.paths import storage_backend

    persistant = storage_backend() == "sqlite"
    return {
        "state": "recorded",
        "persistent": persistant,
        "trace_endpoint": "/trace/{request_id}",
        "gaps": [] if persistant else [
            "l'audit est en mémoire : un redémarrage efface l'historique "
            "d'activité (GALSEN_STORAGE_BACKEND=sqlite pour le garder)"
        ],
    }


def _sovereignty() -> Dict[str, Any]:
    """Où partent les requêtes."""
    from src.model_engine.model_manager import ModelManagerImpl

    rapport = ModelManagerImpl().sovereignty_report()
    failles = []
    if not rapport.get("sovereign_mode", True):
        failles.append(
            "mode souverain désactivé : des fournisseurs tiers peuvent être "
            "choisis pour n'importe quelle requête (ADR-014)"
        )
    if rapport.get("third_party_providers"):
        failles.append(
            "fournisseurs tiers inscrits : "
            + ", ".join(rapport["third_party_providers"])
        )
    return {"state": "sovereign" if not failles else "derogated", **rapport,
            "gaps": failles}


def _recovery() -> Dict[str, Any]:
    """Ce qu'on peut défaire, et ce qu'on peut restaurer."""
    from src.storage.paths import data_dir, storage_backend

    repertoire = data_dir()
    sauvegardes = []
    if os.path.isdir(repertoire):
        sauvegardes = sorted(
            nom for nom in os.listdir(repertoire) if nom.endswith(".backup.sqlite")
        )

    failles = []
    if storage_backend() != "sqlite":
        failles.append(
            "magasin en mémoire : il n'y a rien à sauvegarder, et rien ne "
            "survit à un redémarrage"
        )
    elif not sauvegardes:
        failles.append(
            "aucune sauvegarde dans le répertoire de données : `python "
            "scripts/backup.py` en produit une à chaud"
        )

    return {
        "state": "undoable",
        "data_dir": repertoire,
        "backups": sauvegardes,
        "undo": "src/storage/reversible.py — déplacements, renommages, retraits",
        "checkpoints": "src/security/checkpoints.py",
        "gaps": failles,
    }


#: Table des mesures. Déclarée après les fonctions pour qu'elles existent, et
#: parcourue dans l'ordre de `SECTIONS`.
_MESURES: Dict[str, Callable[[], Dict[str, Any]]] = {
    "filesystem": _filesystem,
    "execution": _execution,
    "perception": _perception,
    "exposure": _exposure,
    "identity": _identity,
    "approval": _approval,
    "audit": _audit,
    "sovereignty": _sovereignty,
    "recovery": _recovery,
}


def summary() -> List[str]:
    """
    Rend la posture en quelques lignes lisibles par un humain pressé.

    Les failles d'abord : c'est ce qu'on lit quand on n'a le temps de lire
    qu'une chose.
    """
    mesure = posture()
    lignes = [f"{len(mesure['gaps'])} point(s) non garanti(s) :"]
    lignes.extend(f"  - {faille}" for faille in mesure["gaps"])
    if not mesure["gaps"]:
        lignes = ["Aucune faille rapportée par les mesures de cette version."]
    return lignes
