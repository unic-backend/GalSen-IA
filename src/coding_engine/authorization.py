"""
Qui peut confier une tâche à un moteur de codage (ADR-028).

## Le trou que ce module bouche

`POST /coding/task` exigeait `tool:execute`, et rien d'autre. Or `Role.USER`
détient `tool:execute` — c'est la permission qui ouvre la météo, la recherche et
la calculatrice. Un utilisateur ordinaire pouvait donc désigner **n'importe quel
dossier de l'hôte** et y faire écrire un moteur qui lance des commandes.

La permission n'était pas le bon instrument : elle dit qu'on a le droit
d'exécuter *un* outil, jamais lequel. C'est exactement le problème que
`src/tool/authorization.py` a déjà résolu pour les outils, avec un **plafond de
rôle** — la classe de données la plus large et l'effet le plus fort qu'un rôle
peut atteindre. `terminal` y est refusé à `Role.USER` parce qu'il atteint
`system` ; un moteur de codage atteint exactement la même chose.

## Pourquoi réutiliser plutôt que déclarer une permission de plus

Une `Permission.CODING_EXECUTE` aurait marché, et aurait été le deuxième modèle
d'autorisation du dépôt pour la même question. Les plafonds existent, ils
couvrent déjà `system`, et un rôle ajouté demain y sera confronté sans que
personne ait à penser au moteur de codage. Une permission de plus, elle, se
serait oubliée au prochain rôle.

Ce qui n'est **pas** décidé ici : l'approbation. Elle porte sur l'acte —
`inspect_instruction()` la déclenche sur une publication distante ou une
suppression récursive — jamais sur l'acteur. Un administrateur passe le plafond
et reste soumis au portillon.
"""

from __future__ import annotations

from typing import Any

from src.tool.authorization import Actor, Decision, ToolDecision, authorize
from src.tool.capabilities import (
    CapabilityRegistry,
    DataScope,
    Effect,
    ToolCapability,
)

#: L'identifiant sous lequel le moteur de codage est autorisé. Ce n'est pas une
#: entrée de `tools/tools.yaml` : le moteur n'est pas un outil chargeable, il a
#: ses propres routes. L'identifiant sert au verdict et à l'audit.
CODING_ENGINE_ID = "coding_engine"

#: Ce qu'un moteur de codage fait au monde, déclaré comme n'importe quelle autre
#: capacité. `system` parce qu'il écrit des fichiers et lance des commandes avec
#: les droits de l'utilisateur qui fait tourner GalSen IA — `workspace.py` le
#: dit dans son propre en-tête : ce module confine les chemins, il n'isole pas
#: le processus.
#:
#: `requires_approval` est **faux ici**, et ce n'est pas un adoucissement : le
#: portillon existe, il est per-tâche (`inspect_instruction`), et le déclencher
#: aussi au niveau du plafond exigerait une approbation pour lire un fichier.
#: Le plafond décide de l'acteur ; l'inspection décide de l'acte.
CAPACITE = ToolCapability(
    tool_id=CODING_ENGINE_ID,
    declared=True,
    effects=frozenset({Effect.READ, Effect.WRITE}),
    data_scope=DataScope.SYSTEM,
    requires_approval=False,
    unattended=False,
    reason=(
        "Un moteur de codage écrit des fichiers et lance des commandes avec "
        "les droits du processus. Personne ne relit ce qu'il a fait s'il "
        "tourne sans témoin."
    ),
)

#: Un registre d'une seule entrée, pour passer par `authorize()` sans toucher au
#: registre des outils. Construit une fois : la capacité est constante.
_REGISTRE = CapabilityRegistry(
    capabilities={CODING_ENGINE_ID: CAPACITE},
    registry_path="src/coding_engine/authorization.py",
)


def authorize_coding(actor: Actor) -> ToolDecision:
    """
    Décide si un acteur peut confier une tâche à un moteur de codage.

    Args:
        actor: Qui demande, avec son rôle et ses permissions.

    Returns:
        Le verdict et sa raison, dans le vocabulaire des outils — `ALLOWED`,
        `REQUIRES_APPROVAL`, `REFUSED`. Un rôle dont le plafond n'atteint pas
        `system` est refusé, quelle que soit l'approbation qu'il pourrait
        obtenir : on ne demande pas la permission de faire ce qu'on ne pourrait
        pas faire.
    """
    return authorize(CODING_ENGINE_ID, actor, registry=_REGISTRE)


def refused_reason(context: Any) -> str:
    """
    La raison du refus pour un contexte RBAC, ou une chaîne vide s'il passe.

    Args:
        context: Un `RBACContext`, ou tout objet portant `subject`, `role` et
            `permissions`.

    Returns:
        Le motif du refus, en clair, ou `""` quand l'acteur est dans son
        plafond. La chaîne vide vaut « autorisé » ; elle ne vaut jamais
        « on n'a pas regardé », parce que la fonction regarde toujours.
    """
    verdict = authorize_coding(Actor.from_rbac(context))
    return "" if verdict.decision is not Decision.REFUSED else verdict.reason
