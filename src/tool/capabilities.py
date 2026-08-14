"""
Tool capabilities: what a tool touches, what it changes, and who may run it.

The tool registry (`tools/tools.yaml`) already says *how* to load a tool —
module, class, configuration. It says nothing about what running that tool
actually costs: whether it reads or writes, whether it leaves the machine, and
whether a human must be present.

Three things being built on top of this registry need exactly that answer:

- the permission model, to decide who may run a tool;
- the connectors, so private user data cannot leak into a public store;
- the routine engine, which runs tools **with nobody watching**.

This module is the vocabulary and the guard. It declares nothing by itself: a
tool whose capability is missing from the registry is reported as **undeclared**
and treated as the most restrictive case. `undeclared` is not `harmless`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

import yaml

# Chemin par défaut du registre, aligné sur `ToolLoader`.
REGISTRE_PAR_DEFAUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "tools",
    "tools.yaml",
)


class Effect(str, Enum):
    """Ce qu'un outil fait au monde quand il s'exécute."""

    #: Observe sans rien modifier. Une lecture reste une lecture même si elle
    #: consomme du temps ou de la mémoire.
    READ = "read"

    #: Modifie un état local : fichier, base, dépôt, conteneur.
    WRITE = "write"

    #: Quitte la machine. C'est le seul effet qui rend une donnée irrécupérable
    #: une fois partie — d'où son traitement séparé.
    EXTERNAL = "external"


class DataScope(str, Enum):
    """La classe de données qu'un outil peut atteindre."""

    #: Donnée publique ou déjà publiée. Sa fuite ne révèle rien.
    PUBLIC = "public"

    #: Donnée appartenant à une personne : courriels, fichiers privés, agenda.
    #: Elle ne doit jamais entrer dans un magasin partagé.
    USER_PRIVATE = "user_private"

    #: État de la plateforme elle-même : configuration, écran, processus,
    #: identifiants. Sa fuite compromet tout le reste.
    SYSTEM = "system"


class CapabilityError(ValueError):
    """Une déclaration de capacité incohérente. Levée au chargement, pas plus tard."""


@dataclass(frozen=True)
class PreApproval:
    """
    Une **partie** d'un outil, approuvée une fois, en configuration.

    Le besoin est réel et étroit : l'agent testeur exécute `python -m pytest`
    sans personne devant — c'est sa raison d'être — alors que `terminal` est
    déclaré `requires_approval` parce qu'une commande peut tout faire. Les deux
    affirmations sont vraies ; ce qui manquait, c'est de pouvoir approuver la
    **borne** plutôt que l'outil entier.

    Une pré-approbation porte toujours un nom, une date et un motif. Sans eux,
    elle est anonyme : personne ne peut la révoquer ni dire pourquoi elle
    existe, et une approbation que nul n'assume n'est pas une approbation.

    Attributes:
        operation: Le préfixe d'appel approuvé, par exemple `"read"` ou
            `"python -m pytest"`. La comparaison se fait sur des mots entiers.
        approved_by: Qui l'a accordée.
        approved_on: Quand, en `AAAA-MM-JJ`.
        rationale: Pourquoi cette borne est sûre alors que l'outil ne l'est pas.
    """

    operation: str
    approved_by: str
    approved_on: str
    rationale: str

    def matches(self, arguments: Any) -> bool:
        """
        Indique si un appel tombe dans cette borne.

        La comparaison porte sur des **mots entiers** : `"read"` ne couvre pas
        `"read_and_write"`, et `"python -m pytest"` ne couvre pas
        `"python -m pytester"`. Un préfixe de caractères aurait ouvert
        exactement ce que la borne prétend fermer.

        Args:
            arguments: Le premier argument de l'appel, chaîne ou liste.

        Returns:
            True si l'appel commence par l'opération approuvée.
        """
        appel = normalize_call(arguments).split()
        borne = self.operation.split()
        return bool(borne) and appel[: len(borne)] == borne

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, pour l'API et l'audit."""
        return {
            "operation": self.operation,
            "approved_by": self.approved_by,
            "approved_on": self.approved_on,
            "rationale": self.rationale,
        }


def normalize_call(arguments: Any) -> str:
    """
    Réduit le premier argument d'un appel d'outil à une chaîne comparable.

    Les outils ne s'appellent pas tous pareil : `use_tool("filesystem", "read",
    chemin)` passe une opération nommée, `use_tool("terminal", ["python", "-m",
    "pytest"])` passe une commande découpée. Les deux se ramènent à des mots.

    Args:
        arguments: Le premier argument positionnel de l'appel.

    Returns:
        Les mots de l'appel, séparés par une espace. Chaîne vide si l'appel
        n'est pas comparable — auquel cas aucune borne ne peut le couvrir.
    """
    if isinstance(arguments, str):
        return " ".join(arguments.split())
    if isinstance(arguments, (list, tuple)):
        return " ".join(
            str(element) for element in arguments if isinstance(element, (str, int, float))
        )
    return ""


@dataclass(frozen=True)
class ToolCapability:
    """
    Ce qu'un outil est autorisé à faire, tel que le registre le déclare.

    Attributes:
        tool_id: L'identifiant de l'outil au registre.
        declared: `False` quand le registre ne porte aucune déclaration. Tous
            les autres champs valent alors leur valeur la plus restrictive.
        effects: Les effets de l'outil. Vide uniquement si non déclaré.
        data_scope: La classe de données atteinte. `None` si non déclaré.
        requires_approval: Un humain doit approuver chaque exécution.
        unattended: L'outil peut tourner sans personne devant, dans une routine.
        reason: Pourquoi `unattended` est refusé, quand il l'est.
    """

    tool_id: str
    declared: bool
    effects: FrozenSet[Effect] = frozenset()
    data_scope: Optional[DataScope] = None
    requires_approval: bool = True
    unattended: bool = False
    reason: str = ""
    #: Les bornes de l'outil approuvées une fois, en configuration.
    pre_approved: Tuple[PreApproval, ...] = ()

    def pre_approval_for(self, arguments: Any) -> Optional[PreApproval]:
        """
        Retourne la pré-approbation couvrant cet appel, s'il en existe une.

        Args:
            arguments: Le premier argument de l'appel.

        Returns:
            La borne qui couvre l'appel, ou `None`.
        """
        for borne in self.pre_approved:
            if borne.matches(arguments):
                return borne
        return None

    def touches(self, scope: DataScope) -> bool:
        """Indique si l'outil atteint cette classe de données."""
        return self.data_scope == scope

    def has(self, effect: Effect) -> bool:
        """Indique si l'outil produit cet effet."""
        return effect in self.effects

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, pour l'API et les rapports."""
        return {
            "tool_id": self.tool_id,
            "declared": self.declared,
            "effects": sorted(effet.value for effet in self.effects),
            "data_scope": self.data_scope.value if self.data_scope else None,
            "requires_approval": self.requires_approval,
            "unattended": self.unattended,
            "reason": self.reason,
            "pre_approved": [borne.as_dict() for borne in self.pre_approved],
        }


def undeclared(tool_id: str) -> ToolCapability:
    """
    La capacité d'un outil qui n'en déclare aucune.

    Le défaut est le refus : pas d'exécution sans humain, approbation exigée.
    Un outil inconnu qui tournerait librement dans une routine est exactement
    le défaut que ce module existe pour empêcher.

    Args:
        tool_id: L'identifiant de l'outil.

    Returns:
        Une capacité non déclarée, restrictive, portant sa raison.
    """
    return ToolCapability(
        tool_id=tool_id,
        declared=False,
        requires_approval=True,
        unattended=False,
        reason=(
            "Capacité non déclarée au registre. Le défaut est le refus : "
            "« non déclaré » n'est pas « inoffensif »."
        ),
    )


# ----------------------------------------------------------------------
# Les règles que le registre ne peut pas violer
# ----------------------------------------------------------------------

def _verifier_coherence(capacite: ToolCapability) -> None:
    """
    Refuse une déclaration qui se contredit.

    Deux règles seulement, toutes deux sur `unattended`, parce que c'est le seul
    champ qui retire un humain de la boucle :

    1. **Approbation et absence d'humain s'excluent.** Déclarer les deux
       laisserait une routine s'auto-approuver.
    2. **Donnée privée plus sortie de la machine ne tourne jamais seul.**
       C'est la définition d'un chemin d'exfiltration ; il lui faut un humain.

    Args:
        capacite: La capacité lue au registre.

    Raises:
        CapabilityError: Si la déclaration est incohérente.
    """
    if capacite.requires_approval and capacite.unattended:
        raise CapabilityError(
            f"Outil '{capacite.tool_id}' : `requires_approval` et `unattended` "
            "sont incompatibles — l'un exige un humain, l'autre affirme qu'il "
            "n'y en a pas."
        )

    if (
        capacite.unattended
        and capacite.data_scope == DataScope.USER_PRIVATE
        and Effect.EXTERNAL in capacite.effects
    ):
        raise CapabilityError(
            f"Outil '{capacite.tool_id}' : donnée privée et sortie de la machine "
            "forment un chemin d'exfiltration. Il ne peut pas tourner sans humain."
        )


#: Les champs qu'une pré-approbation doit porter. Sans eux elle est anonyme,
#: donc ni révocable ni auditable — et une approbation que nul n'assume n'est
#: pas une approbation.
CHAMPS_DE_PRE_APPROBATION = ("operation", "approved_by", "approved_on", "rationale")


def _lire_pre_approbations(
    tool_id: str, brut: Any, capacite_partielle: Dict[str, Any]
) -> Tuple[PreApproval, ...]:
    """
    Lit et valide les bornes pré-approuvées d'un outil.

    Quatre règles, toutes refusées au chargement :

    1. **Une borne n'a de sens que sur un outil qui en a besoin.** Sur un outil
       déjà exécutable seul et sans approbation, elle n'a rien à lever et
       laisserait croire à une restriction qui n'existe pas.
    2. **Une borne vide approuverait tout.** C'est l'inverse de son objet.
    3. **Chaque champ est obligatoire.** Une approbation anonyme n'en est pas une.
    4. **Aucune borne n'ouvre l'exfiltration.** Donnée privée plus sortie de la
       machine reste interdite, quelle que soit l'étroitesse revendiquée.

    Args:
        tool_id: L'identifiant de l'outil.
        brut: La valeur lue au registre.
        capacite_partielle: Les champs déjà lus, pour vérifier la cohérence.

    Returns:
        Les bornes, dans l'ordre du registre.

    Raises:
        CapabilityError: Si une borne est mal formée ou incohérente.
    """
    if brut is None:
        return ()
    if not isinstance(brut, list):
        raise CapabilityError(
            f"Outil '{tool_id}' : `pre_approved` doit être une liste."
        )

    if capacite_partielle.get("unattended") and not capacite_partielle.get(
        "requires_approval"
    ):
        raise CapabilityError(
            f"Outil '{tool_id}' : une pré-approbation n'a rien à lever sur un "
            "outil déjà exécutable seul et sans approbation. Elle laisserait "
            "croire à une restriction qui n'existe pas."
        )

    if (
        capacite_partielle.get("data_scope") == DataScope.USER_PRIVATE
        and Effect.EXTERNAL in capacite_partielle.get("effects", frozenset())
    ):
        raise CapabilityError(
            f"Outil '{tool_id}' : aucune borne ne pré-approuve un chemin "
            "d'exfiltration — donnée privée et sortie de la machine."
        )

    bornes = []
    for entree in brut:
        if not isinstance(entree, dict):
            raise CapabilityError(
                f"Outil '{tool_id}' : chaque pré-approbation doit être un bloc."
            )
        manquants = [
            champ for champ in CHAMPS_DE_PRE_APPROBATION
            if not str(entree.get(champ, "")).strip()
        ]
        if manquants:
            raise CapabilityError(
                f"Outil '{tool_id}' : pré-approbation incomplète, champs "
                f"manquants : {', '.join(manquants)}. Une approbation que nul "
                "n'assume n'est pas une approbation."
            )
        bornes.append(PreApproval(
            operation=" ".join(str(entree["operation"]).split()),
            approved_by=str(entree["approved_by"]).strip(),
            approved_on=str(entree["approved_on"]).strip(),
            rationale=str(entree["rationale"]).strip(),
        ))
    return tuple(bornes)


def _lire_effets(tool_id: str, brut: Any) -> FrozenSet[Effect]:
    """Convertit la liste d'effets déclarée, en refusant tout nom inconnu."""
    if not isinstance(brut, list) or not brut:
        raise CapabilityError(
            f"Outil '{tool_id}' : `effects` doit être une liste non vide "
            f"parmi {sorted(e.value for e in Effect)}."
        )
    effets = set()
    for nom in brut:
        try:
            effets.add(Effect(nom))
        except ValueError as erreur:
            raise CapabilityError(
                f"Outil '{tool_id}' : effet inconnu {nom!r}. "
                f"Attendu parmi {sorted(e.value for e in Effect)}."
            ) from erreur
    return frozenset(effets)


def _lire_portee(tool_id: str, brut: Any) -> DataScope:
    """Convertit la portée de données déclarée, en refusant tout nom inconnu."""
    try:
        return DataScope(brut)
    except ValueError as erreur:
        raise CapabilityError(
            f"Outil '{tool_id}' : portée de données inconnue {brut!r}. "
            f"Attendue parmi {sorted(s.value for s in DataScope)}."
        ) from erreur


def parse_capability(tool_id: str, config: Dict[str, Any]) -> ToolCapability:
    """
    Lit la capacité d'un outil depuis son entrée de registre.

    Args:
        tool_id: L'identifiant de l'outil.
        config: L'entrée de registre de l'outil.

    Returns:
        La capacité déclarée, ou celle de `undeclared()` si le bloc est absent.

    Raises:
        CapabilityError: Si le bloc est présent mais incohérent ou mal formé.
    """
    brut = (config or {}).get("capability")
    if brut is None:
        return undeclared(tool_id)
    if not isinstance(brut, dict):
        raise CapabilityError(
            f"Outil '{tool_id}' : `capability` doit être un bloc, pas {type(brut).__name__}."
        )

    champs = {
        "effects": _lire_effets(tool_id, brut.get("effects")),
        "data_scope": _lire_portee(tool_id, brut.get("data_scope")),
        "requires_approval": bool(brut.get("requires_approval", True)),
        "unattended": bool(brut.get("unattended", False)),
        "reason": str(brut.get("reason", "")),
    }
    capacite = ToolCapability(
        tool_id=tool_id,
        declared=True,
        pre_approved=_lire_pre_approbations(tool_id, brut.get("pre_approved"), champs),
        **champs,
    )
    _verifier_coherence(capacite)
    return capacite


# ----------------------------------------------------------------------
# Chargement
# ----------------------------------------------------------------------

@dataclass
class CapabilityRegistry:
    """
    Les capacités de tous les outils du registre.

    Construite une fois, relue à volonté. Elle ne charge aucun outil : lire une
    capacité ne doit jamais exécuter le code de l'outil concerné.
    """

    capabilities: Dict[str, ToolCapability] = field(default_factory=dict)
    registry_path: str = ""

    def get(self, tool_id: str) -> ToolCapability:
        """
        Retourne la capacité d'un outil.

        Un outil absent du registre reçoit la même réponse restrictive qu'un
        outil présent mais non déclaré : dans les deux cas, rien n'autorise
        à le laisser tourner seul.
        """
        return self.capabilities.get(tool_id) or undeclared(tool_id)

    def declared_ids(self) -> List[str]:
        """Les identifiants des outils qui déclarent une capacité, triés."""
        return sorted(
            tool_id for tool_id, cap in self.capabilities.items() if cap.declared
        )

    def undeclared_ids(self) -> List[str]:
        """Les identifiants des outils sans déclaration, triés."""
        return sorted(
            tool_id for tool_id, cap in self.capabilities.items() if not cap.declared
        )

    def with_effect(self, effect: Effect) -> List[str]:
        """Les outils produisant cet effet, triés."""
        return sorted(
            tool_id for tool_id, cap in self.capabilities.items() if cap.has(effect)
        )

    def with_scope(self, scope: DataScope) -> List[str]:
        """Les outils atteignant cette classe de données, triés."""
        return sorted(
            tool_id for tool_id, cap in self.capabilities.items() if cap.touches(scope)
        )

    def unattended_ids(self) -> List[str]:
        """Les outils qu'une routine peut exécuter sans humain, triés."""
        return sorted(
            tool_id for tool_id, cap in self.capabilities.items() if cap.unattended
        )


def load_capabilities(registry_path: Optional[str] = None) -> CapabilityRegistry:
    """
    Charge les capacités depuis le registre d'outils.

    Args:
        registry_path: Chemin du registre. Par défaut `tools/tools.yaml`.

    Returns:
        Le registre des capacités. Vide si le fichier est absent — l'absence de
        registre rend la couche muette, pas permissive.

    Raises:
        CapabilityError: Si une déclaration est incohérente. Une incohérence est
            une erreur de configuration : elle doit arrêter le démarrage, pas
            produire un silence.
    """
    chemin = registry_path or REGISTRE_PAR_DEFAUT
    try:
        with open(chemin, "r", encoding="utf-8") as fichier:
            donnees = yaml.safe_load(fichier) or {}
    except FileNotFoundError:
        return CapabilityRegistry(capabilities={}, registry_path=chemin)

    capacites: Dict[str, ToolCapability] = {}
    for config in donnees.get("tools", []) or []:
        tool_id = (config or {}).get("id")
        if tool_id:
            capacites[tool_id] = parse_capability(tool_id, config)
    return CapabilityRegistry(capabilities=capacites, registry_path=chemin)


# ----------------------------------------------------------------------
# Les questions que les couches suivantes posent
# ----------------------------------------------------------------------

def may_run_unattended(
    tool_id: str,
    registry: Optional[CapabilityRegistry] = None,
    arguments: Any = None,
) -> Tuple[bool, str]:
    """
    Une routine ou un agent peuvent-ils exécuter cet outil sans personne devant ?

    C'est la question du moteur de routines et du chemin des agents. La réponse
    par défaut est non, et elle vient toujours avec sa raison : un refus sans
    motif est indébogable.

    `arguments` permet à un appel de tomber dans une **borne pré-approuvée** :
    `terminal` reste sous portillon, `python -m pytest` ne l'est pas. Sans
    `arguments`, la question porte sur l'outil entier, ce qui est le pire cas.

    Args:
        tool_id: L'identifiant de l'outil.
        registry: Le registre déjà chargé, sinon il est relu.
        arguments: Le premier argument de l'appel, quand il est connu.

    Returns:
        Le verdict et sa raison.
    """
    registre = registry or load_capabilities()
    capacite = registre.get(tool_id)

    if not capacite.declared:
        return False, capacite.reason

    if arguments is not None:
        borne = capacite.pre_approval_for(arguments)
        if borne is not None:
            return True, (
                f"Borne pré-approuvée « {borne.operation} » "
                f"({borne.approved_by}, {borne.approved_on}) : {borne.rationale}"
            )

    if capacite.requires_approval:
        return False, "L'outil exige une approbation humaine à chaque exécution."
    if not capacite.unattended:
        return False, capacite.reason or "L'outil ne se déclare pas exécutable sans humain."
    return True, "Déclaré exécutable sans humain au registre."


def may_reach(
    tool_id: str, scope: DataScope, registry: Optional[CapabilityRegistry] = None
) -> Tuple[bool, str]:
    """
    Cet outil peut-il atteindre cette classe de données ?

    Args:
        tool_id: L'identifiant de l'outil.
        scope: La classe de données visée.
        registry: Le registre déjà chargé, sinon il est relu.

    Returns:
        Le verdict et sa raison.
    """
    registre = registry or load_capabilities()
    capacite = registre.get(tool_id)

    if not capacite.declared:
        return False, capacite.reason
    if capacite.data_scope != scope:
        return False, (
            f"L'outil est déclaré sur la portée '{capacite.data_scope.value}', "
            f"pas sur '{scope.value}'."
        )
    return True, f"Déclaré sur la portée '{scope.value}'."


def capability_report(registry_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Ce que le registre déclare, et ce qu'il laisse en blanc.

    Le rapport nomme ses propres lacunes : un outil non déclaré y apparaît, il
    n'est pas compté comme sûr par omission.

    Args:
        registry_path: Chemin du registre. Par défaut `tools/tools.yaml`.

    Returns:
        Le décompte, la couverture, et la liste des outils non déclarés.
    """
    registre = load_capabilities(registry_path)
    total = len(registre.capabilities)
    declares = registre.declared_ids()

    return {
        "registry_path": registre.registry_path,
        "tools": total,
        "declared": len(declares),
        "undeclared": registre.undeclared_ids(),
        "coverage": round(len(declares) / total, 4) if total else 0.0,
        "by_effect": {
            effet.value: registre.with_effect(effet) for effet in Effect
        },
        "by_scope": {
            portee.value: registre.with_scope(portee) for portee in DataScope
        },
        "unattended": registre.unattended_ids(),
    }
