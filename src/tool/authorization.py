"""
Tool authorization: crossing who is asking with what the tool touches.

Before this module, `TOOL_EXECUTE` was a single global right. Whoever held it
could run `metrics` — read-only, public — and `terminal` — arbitrary commands on
the machine — through the same door. That is not least privilege; it is one
privilege wearing four role names.

The fix is not a new permission per tool: twenty-two tools would become
twenty-two permissions, and the twenty-third would be forgotten. A **role
ceiling** is declared instead — the widest data scope and the strongest effect a
role may ever reach — and every tool is measured against it using the capability
it already declares (`capabilities.py`).

Three things this module refuses to do:

- **Let an administrator skip an approval.** Approval is a property of the act,
  not of the actor: `terminal` and `gui` stay gated for everyone.
- **Answer with a boolean.** « Allowed », « needs a human » and « never » are
  three different answers, and collapsing the middle one into either of the
  others is how a gate gets bypassed.
- **Authorize an undeclared tool.** A tool nobody described cannot be shown to
  be within any ceiling.

This module does not import the API layer: an actor is described by three plain
fields, so the policy stays testable without FastAPI and the layering holds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional

from .capabilities import (
    CapabilityRegistry,
    DataScope,
    Effect,
    ToolCapability,
    load_capabilities,
)

# La permission qui ouvre la porte. Elle reste nécessaire — ce module la
# complète, il ne la remplace pas.
PERMISSION_EXECUTION = "tool:execute"


class Decision(str, Enum):
    """Le verdict d'une demande d'exécution."""

    #: L'acteur peut exécuter l'outil maintenant.
    ALLOWED = "allowed"

    #: L'acteur est dans son plafond, mais l'acte demande un humain.
    #: Ce n'est ni un oui ni un non : c'est un renvoi vers le portillon.
    REQUIRES_APPROVAL = "requires_approval"

    #: L'acteur ne peut pas exécuter cet outil, quelle que soit l'approbation.
    REFUSED = "refused"


@dataclass(frozen=True)
class Actor:
    """
    Qui demande l'exécution.

    Trois champs plats, volontairement : le module de politique ne doit pas
    dépendre de la couche API pour être lisible ni testable.

    Attributes:
        subject: L'identifiant stable du porteur (ADR-010), jamais un secret.
        role: Le nom du rôle, tel que `Role.value` le donne.
        permissions: Les permissions détenues, sous leur forme textuelle.
    """

    subject: str
    role: str
    permissions: FrozenSet[str] = frozenset()

    @classmethod
    def from_rbac(cls, context: Any) -> "Actor":
        """
        Construit un acteur depuis un contexte RBAC de la couche API.

        Lu par attributs plutôt qu'importé : c'est ce qui garde `src/tool`
        indépendant de `src/api`.

        Args:
            context: Un `RBACContext`, ou tout objet portant `subject`, `role`
                et `permissions`.

        Returns:
            L'acteur correspondant.
        """
        return cls(
            subject=getattr(context, "subject", "anonymous"),
            role=getattr(getattr(context, "role", None), "value", str(getattr(context, "role", ""))),
            permissions=frozenset(
                getattr(permission, "value", str(permission))
                for permission in getattr(context, "permissions", ())
            ),
        )


@dataclass(frozen=True)
class RoleCeiling:
    """
    Ce qu'un rôle peut atteindre au maximum.

    Le plafond est une borne, pas une liste d'outils : un outil ajouté demain
    est couvert le jour où il déclare sa capacité, sans qu'on ait à penser à
    lui. C'est l'inverse d'une liste blanche, qui oublie toujours le vingt-
    troisième outil.

    Attributes:
        scopes: Les classes de données que le rôle peut atteindre.
        effects: Les effets que le rôle peut produire.
        rationale: Pourquoi ce plafond est celui-là.
    """

    scopes: FrozenSet[DataScope]
    effects: FrozenSet[Effect]
    rationale: str = ""


#: Le plafond le plus étroit. Il sert de défaut à tout rôle inconnu : un rôle
#: mal orthographié dans la configuration ne doit pas ouvrir plus de portes que
#: le rôle le plus faible.
PLAFOND_MINIMAL = RoleCeiling(
    scopes=frozenset({DataScope.PUBLIC}),
    effects=frozenset({Effect.READ}),
    rationale="Rôle inconnu : lecture de données publiques uniquement.",
)


#: Les plafonds par rôle. Les noms sont ceux de `src.api.rbac.Role`, sous forme
#: textuelle pour ne pas importer la couche API. Un test garde la couverture :
#: un rôle ajouté là-bas sans plafond ici serait détecté.
PLAFONDS: Dict[str, RoleCeiling] = {
    "admin": RoleCeiling(
        scopes=frozenset(DataScope),
        effects=frozenset(Effect),
        rationale=(
            "L'administration atteint tout — mais reste soumise aux "
            "approbations, qui portent sur l'acte et non sur l'acteur."
        ),
    ),
    "operator": RoleCeiling(
        scopes=frozenset({DataScope.PUBLIC, DataScope.SYSTEM}),
        effects=frozenset(Effect),
        rationale=(
            "Exploiter la plateforme demande d'atteindre son état ; cela ne "
            "demande jamais d'atteindre les données privées d'une personne."
        ),
    ),
    "user": RoleCeiling(
        scopes=frozenset({DataScope.PUBLIC, DataScope.USER_PRIVATE}),
        effects=frozenset(Effect),
        rationale=(
            "Un utilisateur atteint ses propres données, jamais l'état de la "
            "plateforme. À qui appartiennent ces données est la question du "
            "VOLET 40 ; ce plafond dit seulement de quelle classe elles sont."
        ),
    ),
    "readonly": RoleCeiling(
        scopes=frozenset({DataScope.PUBLIC}),
        effects=frozenset({Effect.READ}),
        rationale="Consultation de données publiques, sans effet sur le monde.",
    ),

    # --- Rôles éducatifs (Darra J, VOLET 13) ---------------------------------
    # Aucun d'eux n'atteint `SYSTEM` : une position dans une école ne donne
    # aucune raison d'atteindre l'état de la plateforme.
    "student": RoleCeiling(
        scopes=frozenset({DataScope.PUBLIC, DataScope.USER_PRIVATE}),
        effects=frozenset({Effect.READ, Effect.WRITE}),
        rationale=(
            "Un élève atteint le curriculum public et ses propres données. "
            "`USER_PRIVATE` dit la classe de la donnée ; à qui elle appartient "
            "reste vérifié par `src/darra_j/access.py`."
        ),
    ),
    "parent": RoleCeiling(
        scopes=frozenset({DataScope.PUBLIC, DataScope.USER_PRIVATE}),
        effects=frozenset({Effect.READ}),
        rationale=(
            "Un responsable **lit** : il consulte le programme et les mesures "
            "de l'enfant qui lui est déclaré, et ne produit rien."
        ),
    ),
    "teacher": RoleCeiling(
        scopes=frozenset({DataScope.PUBLIC, DataScope.USER_PRIVATE}),
        effects=frozenset({Effect.READ, Effect.WRITE}),
        rationale=(
            "Un enseignant prépare, corrige et enregistre ses décisions. Il "
            "n'atteint pas l'état de la plateforme."
        ),
    ),
    "school_admin": RoleCeiling(
        scopes=frozenset({DataScope.PUBLIC, DataScope.USER_PRIVATE}),
        effects=frozenset({Effect.READ, Effect.WRITE}),
        rationale=(
            "Une direction d'établissement enregistre des décisions scolaires ; "
            "administrer une école n'est pas administrer la plateforme."
        ),
    ),
    "education_authority": RoleCeiling(
        scopes=frozenset({DataScope.PUBLIC}),
        effects=frozenset({Effect.READ, Effect.WRITE}),
        rationale=(
            "Une autorité éducative définit un programme **public** et "
            "n'atteint aucune donnée privée : publier un curriculum national "
            "n'a jamais demandé de lire ce qu'un enfant a répondu."
        ),
    ),
    "researcher": RoleCeiling(
        scopes=frozenset({DataScope.PUBLIC}),
        effects=frozenset({Effect.READ}),
        rationale=(
            "La recherche porte sur des agrégats publiés. Aucun rattachement "
            "ne peut lui ouvrir un enfant : le plafond l'en empêche avant même "
            "la permission."
        ),
    ),
}


def ceiling_for(role: str) -> RoleCeiling:
    """
    Retourne le plafond d'un rôle.

    Args:
        role: Le nom du rôle.

    Returns:
        Son plafond, ou `PLAFOND_MINIMAL` si le rôle est inconnu.
    """
    return PLAFONDS.get((role or "").lower(), PLAFOND_MINIMAL)


@dataclass(frozen=True)
class ToolDecision:
    """
    Le verdict rendu pour un acteur et un outil, avec sa raison.

    Attributes:
        tool_id: L'outil demandé.
        subject: Qui demandait.
        role: Sous quel rôle.
        decision: Le verdict.
        reason: Pourquoi. Un refus sans motif est indébogable.
        capability: La capacité qui a servi à décider.
    """

    tool_id: str
    subject: str
    role: str
    decision: Decision
    reason: str
    capability: Optional[ToolCapability] = None

    @property
    def allowed(self) -> bool:
        """Vrai seulement si l'exécution peut avoir lieu **sans** autre étape."""
        return self.decision is Decision.ALLOWED

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, pour l'API et l'audit."""
        return {
            "tool_id": self.tool_id,
            "subject": self.subject,
            "role": self.role,
            "decision": self.decision.value,
            "reason": self.reason,
            "capability": self.capability.as_dict() if self.capability else None,
        }


def _refus(tool_id: str, actor: Actor, raison: str,
           capacite: Optional[ToolCapability] = None) -> ToolDecision:
    """Construit un refus motivé."""
    return ToolDecision(
        tool_id=tool_id,
        subject=actor.subject,
        role=actor.role,
        decision=Decision.REFUSED,
        reason=raison,
        capability=capacite,
    )


def authorize(
    tool_id: str,
    actor: Actor,
    registry: Optional[CapabilityRegistry] = None,
) -> ToolDecision:
    """
    Décide si un acteur peut exécuter un outil.

    L'ordre des contrôles est délibéré : la permission d'abord — elle ne dépend
    d'aucune donnée d'outil —, puis la déclaration, puis le plafond, puis
    l'approbation en dernier. Un acteur hors plafond reçoit un refus, pas une
    invitation à demander l'approbation d'un acte qu'il ne pourrait pas faire.

    Args:
        tool_id: L'outil demandé.
        actor: Qui demande.
        registry: Le registre des capacités, déjà chargé si possible.

    Returns:
        Le verdict et sa raison.
    """
    registre = registry or load_capabilities()
    capacite = registre.get(tool_id)

    if PERMISSION_EXECUTION not in actor.permissions:
        return _refus(
            tool_id, actor,
            f"Le rôle '{actor.role}' ne détient pas la permission "
            f"'{PERMISSION_EXECUTION}'.",
            capacite,
        )

    if not capacite.declared:
        return _refus(tool_id, actor, capacite.reason, capacite)

    plafond = ceiling_for(actor.role)

    if capacite.data_scope not in plafond.scopes:
        return _refus(
            tool_id, actor,
            f"L'outil atteint la classe de données "
            f"'{capacite.data_scope.value}', hors du plafond du rôle "
            f"'{actor.role}'. {plafond.rationale}",
            capacite,
        )

    hors_plafond = sorted(
        effet.value for effet in capacite.effects if effet not in plafond.effects
    )
    if hors_plafond:
        return _refus(
            tool_id, actor,
            f"L'outil produit l'effet {', '.join(hors_plafond)}, hors du "
            f"plafond du rôle '{actor.role}'. {plafond.rationale}",
            capacite,
        )

    if capacite.requires_approval:
        # Ni oui ni non. Répondre « autorisé » ici laisserait un appelant
        # sauter le portillon ; répondre « refusé » dirait « jamais », ce qui
        # est faux. L'appelant doit ouvrir une demande d'approbation.
        return ToolDecision(
            tool_id=tool_id,
            subject=actor.subject,
            role=actor.role,
            decision=Decision.REQUIRES_APPROVAL,
            reason=(
                capacite.reason
                or "L'outil exige une approbation humaine à chaque exécution."
            ),
            capability=capacite,
        )

    return ToolDecision(
        tool_id=tool_id,
        subject=actor.subject,
        role=actor.role,
        decision=Decision.ALLOWED,
        reason=f"Dans le plafond du rôle '{actor.role}', sans approbation requise.",
        capability=capacite,
    )


def authorized_tools(
    actor: Actor, registry: Optional[CapabilityRegistry] = None
) -> Dict[str, List[str]]:
    """
    Ce qu'un acteur peut faire, en une réponse.

    Les trois verdicts sont rendus séparément : une interface qui n'afficherait
    que `allowed` cacherait à l'utilisateur les outils qu'il peut demander.

    Args:
        actor: Qui demande.
        registry: Le registre des capacités, déjà chargé si possible.

    Returns:
        Les identifiants d'outils triés, rangés par verdict.
    """
    registre = registry or load_capabilities()
    rangement: Dict[str, List[str]] = {verdict.value: [] for verdict in Decision}

    for tool_id in sorted(registre.capabilities):
        verdict = authorize(tool_id, actor, registre)
        rangement[verdict.decision.value].append(tool_id)

    return rangement


def authorization_report(
    registry: Optional[CapabilityRegistry] = None,
) -> Dict[str, Any]:
    """
    La matrice rôle × verdict, telle qu'elle est réellement appliquée.

    Elle est calculée, jamais recopiée : une politique décrite dans un document
    et une politique appliquée par le code divergent au premier changement.

    Args:
        registry: Le registre des capacités, déjà chargé si possible.

    Returns:
        Pour chaque rôle, son plafond et le rangement des outils par verdict.
    """
    registre = registry or load_capabilities()
    matrice: Dict[str, Any] = {}

    for role, plafond in PLAFONDS.items():
        # Le rapport décrit le plafond, donc il suppose la permission détenue.
        # Un rôle qui ne l'a pas est signalé séparément plutôt que de faire
        # apparaître un plafond que rien n'atteint.
        acteur = Actor(
            subject="—", role=role, permissions=frozenset({PERMISSION_EXECUTION})
        )
        matrice[role] = {
            "scopes": sorted(portee.value for portee in plafond.scopes),
            "effects": sorted(effet.value for effet in plafond.effects),
            "rationale": plafond.rationale,
            "tools": authorized_tools(acteur, registre),
        }

    return {
        "roles": matrice,
        "tools": len(registre.capabilities),
        "note": (
            "Le rapport suppose la permission 'tool:execute' détenue : il "
            "décrit le plafond du rôle, pas l'accès d'une clé donnée."
        ),
    }
