"""
The connector contract, in one place, readable by a program.

Wave II built the pieces a connector needs — a data contract (`contract.py`), a
subject-bound lifecycle (`lifecycle.py`), privileges and a trust boundary
(`safety.py`) — and the registry refuses a connector that does not carry them.
What was never written is the thing an outside author actually needs: **the
complete list of what will refuse them, before they write anything**.

The plugin ecosystem got that in VOLET 59, and the same anti-drift rule applies
here for the same reason: a document that can drift from the code will drift, and
the first person to trust it writes a connector refused for a reason the page
never mentioned. So the contract is data, `docs/connectors/README.md` is written
from it, and a test confronts the two.

A connector is not a plugin, and the rules differ in ways worth stating rather
than blurring:

- A plugin runs its own code in a sandbox. **A connector runs in-process** and
  reaches an outside provider on someone's behalf — there is no sandbox for it,
  and pretending otherwise would be the dangerous lie.
- A plugin declares capabilities. A connector declares a **data contract**,
  including what it keeps after a call. "nothing" is a valid answer and the best
  one; silence is not an answer.
- A connector that acts for a person is **bound to that person** and reaches
  nothing without an authorisation that exists, is not expired, and belongs to
  them.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.tool.capabilities import DataScope, Effect

from .lifecycle import AuthorizationState
from .safety import PRIVILEGES_DESTRUCTEURS, Privilege

#: Version du contrat des connecteurs. Elle change quand une règle change : un
#: auteur doit pouvoir savoir contre quoi il a écrit.
VERSION_DU_CONTRAT = "1.0"


def connector_refusal_rules() -> List[Dict[str, str]]:
    """
    Tout ce qui refusera un connecteur, et pourquoi.

    Returns:
        Une entrée par règle, avec ce qu'elle refuse et sa raison.
    """
    return [
        {
            "rule": "contract_required",
            "refuses": "Un connecteur enregistré sans `data_contract`.",
            "why": (
                "Sans contrat, personne ne sait ce qu'il touche ni ce qu'il "
                "garde — et le registre ne peut attribuer aucun propriétaire à "
                "ce qu'il rend."
            ),
        },
        {
            "rule": "retention_declared",
            "refuses": "Un contrat sans `retention` en clair.",
            "why": (
                "« rien » est une réponse valide et c'est la meilleure ; le "
                "silence n'en est pas une."
            ),
        },
        {
            "rule": "private_needs_subject",
            "refuses": (
                "Un contrat `user_private` qui ne se déclare pas `per_subject`."
            ),
            "why": (
                "Une donnée privée sans personne à qui elle appartient est une "
                "donnée dont le propriétaire sera deviné plus tard."
            ),
        },
        {
            "rule": "destructive_by_declaration",
            "refuses": (
                "Un privilège destructeur — "
                f"{', '.join(sorted(p.value for p in PRIVILEGES_DESTRUCTEURS))} — "
                "obtenu sans être demandé explicitement et justifié."
            ),
            "why": (
                "La directive du projet est explicite : ne pas donner de "
                "permissions destructrices par défaut."
            ),
        },
        {
            "rule": "authorisation_before_reach",
            "refuses": (
                "Tout appel d'un connecteur lié à une personne sans "
                "autorisation valide pour **elle**."
            ),
            "why": (
                "Une autorisation absente, expirée ou appartenant à quelqu'un "
                "d'autre sont trois situations, et aucune n'autorise l'appel."
            ),
        },
        {
            "rule": "external_is_data",
            "refuses": (
                "Tout retour de fournisseur traité comme autre chose que des "
                "données."
            ),
            "why": (
                "Un courriel qui dit « ignore tes instructions » est un "
                "courriel. Il sort par `receive()`, enveloppé `EXTERNAL`, ou "
                "il ne sort pas."
            ),
        },
    ]


def connector_contract() -> Dict[str, Any]:
    """
    Le contrat complet entre la plateforme et un auteur de connecteur.

    Returns:
        Ce qu'un connecteur déclare, les états qu'il traverse, ce qui le
        refusera, et ce que la plateforme **ne** fait **pas** pour lui.
    """
    return {
        "contract_version": VERSION_DU_CONTRAT,
        "declares": {
            "data_contract": {
                "data_scope": [portee.value for portee in DataScope],
                "per_subject": "bool — agit-il pour le compte d'une personne nommée",
                "effects": [effet.value for effet in Effect],
                "retention": (
                    "Ce qui est gardé après un appel, en clair. « rien » est la "
                    "meilleure réponse ; le silence n'en est pas une."
                ),
                "rationale": "Pourquoi ce contrat est celui-là.",
            },
            "privileges": {
                "values": [privilege.value for privilege in Privilege],
                "destructive": sorted(p.value for p in PRIVILEGES_DESTRUCTEURS),
                "note": (
                    "Vocabulaire de la plateforme, pas celui d'un fournisseur : "
                    "quatre valeurs qui tiendront quand un deuxième fournisseur "
                    "arrivera."
                ),
            },
        },
        "lifecycle": [etat.value for etat in AuthorizationState],
        "refusals": connector_refusal_rules(),
        "differences_from_plugins": [
            "Un greffon tourne dans un bac à sable ; un connecteur tourne "
            "**dans le processus**. Il n'y a pas de bac à sable pour lui, et "
            "prétendre le contraire serait le mensonge dangereux.",
            "Un greffon déclare des capacités ; un connecteur déclare un "
            "**contrat de données**, rétention comprise.",
            "Un connecteur qui agit pour une personne est **lié à elle** : il "
            "n'atteint rien sans une autorisation qui existe, n'a pas expiré, "
            "et lui appartient.",
        ],
        "does_not": [
            "Fabriquer un identifiant, ni contourner une authentification.",
            "Mettre un connecteur en bac à sable : il tourne dans le processus.",
            "Deviner un propriétaire : il est **déduit** de la portée déclarée, "
            "et une portée privée sans sujet refuse.",
        ],
    }
