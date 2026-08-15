"""
Running a plugin: inside the sandbox this repository already has.

The audit listed "plugin system" as absent, and that was true. What was **not**
absent is the sandbox: `src/sandbox/` was written in VOLET 34 with kernel limits,
an explicit list of what it does not guarantee (`NON_GARANTI`), and escape tests
that try to get out. Writing a second one here would produce something nobody has
ever tried to escape from, which is worse than the first one in every way that
matters.

So this module runs plugins **through it**, and adds only what is specific to
third-party code.

**A disabled plugin does not run.** Not "runs and is ignored" — does not run. The
registry's enable/disable is the switch, and this is the only place that reads it.

**A plugin never runs beyond what it declared.** It asked for `read` and
`public`; a plugin that then reaches private data is not caught by this module,
and pretending otherwise would be the dangerous lie. What this module does is
narrower and true: it refuses to *start* a plugin whose declaration does not
cover what it is being asked to do.

**A plugin's output is data with an origin, never an instruction.** It comes back
wrapped by `src/security/trust.py` at `EXTERNAL` — the same boundary as a fetched
web page. A plugin that returns "ignore your previous instructions" is returning a
string, and it stays a string.

**What the sandbox does not guarantee travels with every result.** Not in the
documentation — in the returned object. Someone reading a plugin's output should
not have to go looking for the limits of the thing that produced it.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.sandbox import SandboxPolicy, describe, run_python, unavailable_reason
from src.security.trust import TrustLevel, wrap
from src.tool.capabilities import DataScope, Effect

from .manifest import PluginManifest
from .registry import PluginRegistry

#: Bornes appliquées à un greffon, plus serrées que le défaut du bac à sable :
#: du code écrit ailleurs n'a pas à disposer d'autant qu'un agent de la maison.
POLITIQUE_GREFFON = SandboxPolicy(
    cpu_seconds=5,
    wall_seconds=10,
    memory_bytes=256 * 1024 * 1024,
    output_bytes=64 * 1024,
)


class PluginExecutionRefused(RuntimeError):
    """Une exécution refusée, avec sa raison."""


def may_run(
    manifeste: PluginManifest,
    effect: Optional[Effect] = None,
    scope: Optional[DataScope] = None,
) -> tuple:
    """
    Ce greffon peut-il faire cela, d'après ce qu'il a déclaré ?

    Args:
        manifeste: Le manifeste du greffon.
        effect: L'effet demandé.
        scope: La classe de données demandée.

    Returns:
        Le verdict et sa raison.
    """
    if not manifeste.enabled:
        return False, (
            f"Greffon « {manifeste.plugin_id} » désactivé : il ne tourne pas. "
            "« Désactivé » ne veut pas dire « tourne et on ignore le "
            "résultat »."
        )
    if effect is not None and effect not in manifeste.effects:
        declares = ", ".join(e.value for e in manifeste.effects) or "aucun"
        return False, (
            f"Greffon « {manifeste.plugin_id} » : effet « {effect.value} » "
            f"non déclaré (déclarés : {declares}). Il est jugé sur ce qu'il a "
            "demandé, pas sur ce qu'il tente."
        )
    if scope is not None and scope not in manifeste.scopes:
        declarees = ", ".join(s.value for s in manifeste.scopes) or "aucune"
        return False, (
            f"Greffon « {manifeste.plugin_id} » : portée « {scope.value} » "
            f"non déclarée (déclarées : {declarees})."
        )
    return True, f"Greffon « {manifeste.plugin_id} » dans ce qu'il a déclaré."


def run_plugin(
    plugin_id: str,
    code: str,
    registry: PluginRegistry,
    effect: Optional[Effect] = None,
    scope: Optional[DataScope] = None,
    policy: Optional[SandboxPolicy] = None,
) -> Dict[str, Any]:
    """
    Exécute un greffon dans le bac à sable, et rend sa sortie **comme donnée**.

    Args:
        plugin_id: Le greffon.
        code: Le code à exécuter.
        registry: Le registre qui dit s'il est activé.
        effect: L'effet demandé, confronté à la déclaration.
        scope: La classe de données demandée.
        policy: Bornes appliquées. Celles des greffons par défaut.

    Returns:
        Le résultat, la sortie enveloppée en `EXTERNAL`, et ce que le bac à
        sable ne garantit pas.

    Raises:
        PluginExecutionRefused: Greffon inconnu, désactivé, hors de sa
            déclaration, ou bac à sable indisponible.
    """
    manifeste = registry.get(plugin_id)
    if manifeste is None:
        raise PluginExecutionRefused(f"Greffon « {plugin_id} » inconnu.")

    permis, motif = may_run(manifeste, effect, scope)
    if not permis:
        raise PluginExecutionRefused(motif)

    indisponible = unavailable_reason()
    if indisponible:
        # Exécuter sans bornes en croyant en avoir est le seul comportement
        # que ce dépôt refuse plus fermement que de ne pas exécuter du tout.
        raise PluginExecutionRefused(
            f"Bac à sable indisponible : {indisponible} Un greffon ne tourne "
            "pas hors de ses bornes."
        )

    resultat = run_python(code, policy=policy or POLITIQUE_GREFFON)

    return {
        "plugin_id": plugin_id,
        "exit_code": resultat.exit_code,
        "timed_out": resultat.timed_out,
        "killed_by": resultat.killed_by,
        "truncated": resultat.truncated,
        "duration_seconds": round(resultat.duration_seconds, 3),
        # La sortie d'un greffon est une donnée avec une origine, jamais une
        # instruction : même frontière qu'une page web récupérée.
        "output": wrap(
            resultat.stdout, TrustLevel.EXTERNAL, origin=f"plugin:{plugin_id}",
        ),
        "stderr": resultat.stderr,
        # Les limites voyagent avec le résultat : personne ne devrait avoir à
        # les chercher ailleurs après avoir lu une sortie.
        "sandbox": describe(policy or POLITIQUE_GREFFON),
    }


def execution_report(registry: PluginRegistry) -> Dict[str, Any]:
    """
    Ce que l'exécution des greffons garantit, et ce qu'elle ne garantit pas.

    Args:
        registry: Le registre interrogé.

    Returns:
        L'état du bac à sable, les greffons activés, et les règles tenues.
    """
    return {
        "sandbox": describe(POLITIQUE_GREFFON),
        "enabled_plugins": [m.plugin_id for m in registry.enabled()],
        "rules": [
            "Un greffon désactivé **ne tourne pas** — ce n'est pas « tourne et "
            "on ignore le résultat ».",
            "Un greffon est jugé sur ce qu'il a déclaré : un effet ou une "
            "portée non déclarés refusent le **démarrage**.",
            "Sa sortie est une donnée avec une origine, jamais une "
            "instruction : elle revient enveloppée en `EXTERNAL`.",
            "Le bac à sable n'est pas réécrit ici : celui du VOLET 34 a des "
            "tests d'évasion, un second n'en aurait aucun.",
            "Sans bac à sable disponible, rien ne tourne : exécuter en croyant "
            "à des bornes absentes est pire que de ne pas exécuter.",
        ],
        "does_not": [
            "Empêcher un greffon activé de faire, dans son code, autre chose "
            "que ce qu'il a déclaré : ce module refuse le démarrage, il "
            "n'inspecte pas l'exécution. Prétendre l'inverse serait le "
            "mensonge dangereux.",
            "Vérifier l'identité de l'auteur d'un greffon.",
            "Garantir ce que `src/sandbox/policy.py` déclare explicitement ne "
            "pas garantir.",
        ],
    }
