"""
Reviewing third-party code: what the declaration says, what the code shows.

The platform can already read a repository and edit it under approval
(`src/agent/guarded_editor.py`). Pointing that loop at a plugin raises a question
the loop never had to answer, because until now every file it touched had been
written here.

**Editing a plugin disables it.** The authorisation was granted for what its
author wrote. Once someone else has edited it, the thing running is no longer the
thing that was approved — and leaving it enabled would silently transfer that
approval to code the author never saw. Re-enabling is a fresh decision, named and
justified like the first one.

**A static check finds contradictions, never intentions.** This module reads a
plugin's source as a syntax tree and compares what it *imports* with what its
manifest *declares*. A manifest saying "no network" next to a file importing
`urllib` is a discrepancy — a fact about two documents, not a judgement about
their author. It might be an oversight, a leftover, or something worse; this
module does not know which and does not pretend to.

**And it is not a safety proof.** A plugin can reach the network through an
import this module does not know, through a name built at runtime, through a
dependency. Reporting "no discrepancy" as "safe" would be the most damaging thing
this file could do, so it says so in its own report.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional

from src.tool.capabilities import DataScope, Effect

from .manifest import PluginManifest
from .registry import PluginRegistry

#: Modules dont l'import indique une sortie de la machine. Liste **connue et
#: incomplète** : c'est une piste, pas une preuve, et le rapport le répète.
MODULES_RESEAU = frozenset({
    "socket", "http", "urllib", "urllib3", "requests", "httpx", "ftplib",
    "smtplib", "telnetlib", "asyncio", "aiohttp", "websockets", "xmlrpc",
})

#: Modules qui touchent le système de fichiers ou le système lui-même.
MODULES_SYSTEME = frozenset({
    "subprocess", "shutil", "ctypes", "multiprocessing", "importlib", "pty",
})


class ReviewRefused(ValueError):
    """Une relecture impossible, avec sa raison."""


def _imports(source: str) -> List[str]:
    """
    Les modules importés par un fichier, par lecture de son arbre syntaxique.

    Args:
        source: Le code source.

    Returns:
        Les noms de modules de premier niveau, sans doublon, triés.

    Raises:
        ReviewRefused: Si le fichier n'est pas du Python lisible. Un fichier
            illisible n'est pas un fichier sans import.
    """
    try:
        arbre = ast.parse(source)
    except SyntaxError as erreur:
        raise ReviewRefused(
            f"Source illisible ({erreur.msg}, ligne {erreur.lineno}). Un "
            "fichier qu'on ne peut pas analyser n'est pas un fichier sans "
            "import."
        ) from None

    trouves = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            trouves.update(alias.name.split(".")[0] for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            trouves.add(noeud.module.split(".")[0])
    return sorted(trouves)


def discrepancies(manifeste: PluginManifest, source: str) -> List[Dict[str, str]]:
    """
    Les écarts entre ce qu'un greffon déclare et ce que son code montre.

    Args:
        manifeste: Le manifeste déclaré.
        source: Le code du point d'entrée.

    Returns:
        Un écart par contradiction, avec le fait qui l'atteste.
    """
    importes = set(_imports(source))
    ecarts: List[Dict[str, str]] = []

    reseau = sorted(importes & MODULES_RESEAU)
    if reseau and Effect.EXTERNAL not in manifeste.effects:
        ecarts.append({
            "kind": "network_without_external",
            "evidence": f"Importe {', '.join(reseau)}.",
            "declared": "Aucun effet `external` déclaré.",
            "note": (
                "Deux documents se contredisent. Cela peut être un oubli, un "
                "reste de code ou autre chose : ce module ne sait pas lequel "
                "et ne le prétend pas."
            ),
        })

    systeme = sorted(importes & MODULES_SYSTEME)
    if systeme and DataScope.SYSTEM not in manifeste.scopes:
        ecarts.append({
            "kind": "system_reach_without_scope",
            "evidence": f"Importe {', '.join(systeme)}.",
            "declared": "Aucune portée `system` déclarée.",
            "note": (
                "La portée `system` est de toute façon refusée à la "
                "déclaration : un greffon qui l'atteint par le code atteint "
                "ce qu'aucun manifeste ne peut lui accorder."
            ),
        })

    return ecarts


def review_plugin(
    plugin_id: str, registry: PluginRegistry, source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Relit un greffon installé et rapporte les écarts.

    Args:
        plugin_id: Le greffon.
        registry: Le registre.
        source: Le code, si l'appelant l'a déjà. Lu depuis le point d'entrée
            sinon.

    Returns:
        Les écarts, la méthode employée, et ce que la relecture ne prouve pas.

    Raises:
        ReviewRefused: Greffon inconnu, ou sans code sur le disque.
    """
    manifeste = registry.get(plugin_id)
    if manifeste is None:
        raise ReviewRefused(f"Greffon « {plugin_id} » inconnu.")

    if source is None:
        emplacement = registry.location_of(plugin_id)
        if emplacement is None:
            raise ReviewRefused(
                f"Greffon « {plugin_id} » sans code sur le disque : il n'y a "
                "rien à relire."
            )
        with open(emplacement["entry_file"], "r", encoding="utf-8") as flux:
            source = flux.read()

    ecarts = discrepancies(manifeste, source)
    return {
        "plugin_id": plugin_id,
        "discrepancies": ecarts,
        "imports": _imports(source),
        # La méthode voyage avec le résultat : `ast` lit des noms, elle ne
        # comprend rien.
        "method": "ast",
        "proves_nothing": (
            "Aucun écart trouvé ne veut pas dire « sûr ». Un greffon peut "
            "atteindre le réseau par un import que ce module ne connaît pas, "
            "par un nom construit à l'exécution, ou par une dépendance. Lire "
            "« aucun écart » comme « sans danger » serait la chose la plus "
            "nuisible que ce fichier puisse provoquer."
        ),
    }


def edited_plugin_must_be_reenabled(
    plugin_id: str, registry: PluginRegistry, edited_by: str,
) -> Dict[str, Any]:
    """
    Désactive un greffon dont le code vient d'être modifié.

    **La règle du VOLET.** L'autorisation portait sur ce que son auteur avait
    écrit. Une fois que quelqu'un d'autre l'a modifié, ce qui tourne n'est plus
    ce qui a été approuvé — et le laisser activé transférerait cette approbation
    à du code que l'auteur n'a jamais vu.

    Args:
        plugin_id: Le greffon modifié.
        registry: Le registre.
        edited_by: Qui a modifié.

    Returns:
        L'état du greffon après désactivation, et pourquoi.

    Raises:
        ReviewRefused: Si le greffon est inconnu.
    """
    manifeste = registry.get(plugin_id)
    if manifeste is None:
        raise ReviewRefused(f"Greffon « {plugin_id} » inconnu.")

    etait_actif = manifeste.enabled
    if etait_actif:
        registry.disable(plugin_id)

    return {
        "plugin_id": plugin_id,
        "was_enabled": etait_actif,
        "enabled": False,
        "edited_by": str(edited_by or "").strip() or "UNKNOWN",
        "reason": (
            "Code modifié après approbation : ce qui tournerait n'est plus ce "
            "qui a été approuvé. Réactiver est une décision neuve, nommée et "
            "justifiée comme la première."
        ),
    }


def review_report() -> Dict[str, Any]:
    """
    Ce que la relecture de greffons fait, et surtout ce qu'elle ne fait pas.

    Returns:
        Les règles tenues et les limites assumées.
    """
    return {
        "method": "ast",
        "known_network_modules": sorted(MODULES_RESEAU),
        "known_system_modules": sorted(MODULES_SYSTEME),
        "rules": [
            "Modifier un greffon le **désactive** : l'autorisation portait sur "
            "ce que son auteur avait écrit.",
            "Un écart est un fait sur **deux documents** — le manifeste et le "
            "code — jamais un jugement sur l'auteur.",
            "Un fichier illisible n'est pas un fichier sans import : la "
            "relecture refuse plutôt que de rendre une liste vide.",
        ],
        "does_not": [
            "Prouver qu'un greffon est sûr : « aucun écart » ne veut pas dire "
            "« sans danger », et le lire ainsi serait la chose la plus nuisible "
            "que ce module puisse provoquer.",
            "Comprendre le code : `ast` lit des noms.",
            "Connaître tous les modules réseau : la liste est explicitement "
            "incomplète.",
            "Modifier quoi que ce soit : l'écriture reste au `GuardedEditor`, "
            "sous approbation.",
        ],
    }
