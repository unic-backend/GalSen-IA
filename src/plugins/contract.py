"""
The plugin contract, in one place, readable by a program.

A developer ecosystem needs a document. A document is also the part of a
platform that rots first: the code changes, the page does not, and the first
person to trust the page writes a plugin that is refused for a reason the page
never mentioned.

So the contract lives here, as data. `docs/plugins/README.md` is written from it,
and a test confronts the two — a rule added to the code and forgotten in the page
fails, instead of being discovered by whoever it refuses.

What a contract owes a third party is not encouragement. It is the complete list
of what will refuse them, and why, **before** they write anything.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.tool.capabilities import DataScope, Effect

from .execution import POLITIQUE_GREFFON, execution_report
from .manifest import CHAMPS_OBLIGATOIRES, manifest_report
from .registry import FICHIER_MANIFESTE, REPERTOIRE_DES_GREFFONS, PluginRegistry

#: Version du contrat. Elle change quand une règle change — un auteur doit
#: pouvoir savoir contre quoi il a écrit.
VERSION_DU_CONTRAT = "1.0"


def refusal_rules() -> List[Dict[str, str]]:
    """
    Tout ce qui refusera un greffon, et pourquoi.

    La liste complète, au même endroit : un auteur qui découvre un refus au
    moment d'être refusé a lu une documentation incomplète.

    Returns:
        Une entrée par règle, avec ce qu'elle refuse et sa raison.
    """
    return [
        {
            "rule": "manifest_required",
            "refuses": f"Un répertoire sans « {FICHIER_MANIFESTE} ».",
            "why": "Rien ne tourne sans déclaration ; un répertoire n'en est pas une.",
        },
        {
            "rule": "required_fields",
            "refuses": f"Un manifeste sans : {', '.join(CHAMPS_OBLIGATOIRES)}.",
            "why": (
                "Aucun n'a de défaut : un défaut silencieux ferait passer un "
                "oubli pour une décision."
            ),
        },
        {
            "rule": "identifier_shape",
            "refuses": "Un identifiant hors de `[a-z][a-z0-9_-]{2,39}`.",
            "why": "Il sert de nom de répertoire et de clé de journal.",
        },
        {
            "rule": "private_and_external",
            "refuses": (
                "Un greffon demandant `user_private` **et** l'effet `external`."
            ),
            "why": (
                "C'est un chemin d'exfiltration quelles que soient les "
                "intentions de l'auteur. La même règle que les outils de la "
                "plateforme."
            ),
        },
        {
            "rule": "system_scope",
            "refuses": "Un greffon demandant la portée `system`.",
            "why": (
                "C'est demander à modifier la plateforme qui le juge. Aucun "
                "manifeste ne peut rendre cela sûr."
            ),
        },
        {
            "rule": "entry_point_inside",
            "refuses": (
                "Un `entry_point` absolu, ou qui sort du répertoire du greffon."
            ),
            "why": (
                "« ../../src/api/server.py » est une chaîne parfaitement "
                "valide, et c'est exactement pourquoi elle est refusée."
            ),
        },
        {
            "rule": "identifier_taken",
            "refuses": "Une installation par-dessus un identifiant déjà pris.",
            "why": (
                "Un greffon qui en remplacerait un autre hériterait de son "
                "autorisation sans avoir été jugé."
            ),
        },
        {
            "rule": "disabled_by_default",
            "refuses": "L'exécution d'un greffon installé mais non activé.",
            "why": (
                "Installer n'est pas activer : sinon copier un fichier "
                "vaudrait faire confiance à son auteur."
            ),
        },
        {
            "rule": "undeclared_capability",
            "refuses": (
                "Le démarrage d'un greffon pour un effet ou une portée qu'il "
                "n'a pas déclarés."
            ),
            "why": "Il est jugé sur ce qu'il a demandé, pas sur ce qu'il tente.",
        },
        {
            "rule": "no_sandbox_no_run",
            "refuses": "Toute exécution quand le bac à sable est indisponible.",
            "why": (
                "Exécuter en croyant à des bornes absentes est pire que de ne "
                "pas exécuter."
            ),
        },
    ]


def plugin_contract(registry: PluginRegistry = None) -> Dict[str, Any]:
    """
    Le contrat complet entre la plateforme et un auteur de greffon.

    Args:
        registry: Un registre, pour rapporter l'état d'exécution. Facultatif :
            le contrat existe avant tout greffon.

    Returns:
        Où déposer un greffon, ce qu'il déclare, ce qui le refusera, ce qui le
        borne, et ce que la plateforme **ne** garantit **pas**.
    """
    execution = execution_report(registry or PluginRegistry())
    return {
        "contract_version": VERSION_DU_CONTRAT,
        "where": {
            "directory": f"{REPERTOIRE_DES_GREFFONS}/<plugin_id>/",
            "manifest": FICHIER_MANIFESTE,
            "note": (
                "Le point d'entrée est un chemin **relatif** au répertoire du "
                "greffon, et il doit y rester."
            ),
        },
        "manifest": manifest_report(),
        "capabilities": {
            "effects": [effet.value for effet in Effect],
            "scopes": [portee.value for portee in DataScope],
        },
        "limits": POLITIQUE_GREFFON.to_dict(),
        "refusals": refusal_rules(),
        "lifecycle": [
            "Déposer le répertoire, puis `POST /plugins/discover` : le greffon "
            "est **installé et désactivé**.",
            "Une personne l'active (`POST /plugins/{id}/enable`) en disant "
            "pourquoi. Cette décision est tracée.",
            "`POST /plugins/{id}/run` exécute le point d'entrée déclaré, dans "
            "le bac à sable.",
            "`POST /plugins/{id}/disable` l'arrête, sans rien demander.",
        ],
        "output": {
            "trust_level": "external",
            "note": (
                "La sortie d'un greffon est une **donnée avec une origine**, "
                "jamais une instruction. Un greffon qui écrit « ignore tes "
                "instructions » écrit une chaîne, et elle reste une chaîne."
            ),
        },
        "does_not": execution["does_not"] + manifest_report()["does_not"],
    }
