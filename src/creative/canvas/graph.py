"""
Le graphe : des nœuds, des arêtes légales, et un ordre — côté serveur
(K07, ADR-031 décision 1).

## Ce que le graphe est, et ce qu'il n'est pas

Il **est** un modèle : des nœuds typés, des arêtes dont la légalité se vérifie,
un ordre topologique, et un plan d'exécution. Il **n'a aucune opinion sur son
rendu** : un client peut le dessiner avec React Flow, en SVG, ou pas du tout,
l'orchestration est la même. C'est ce qui le distingue d'un OpenCanvas embarqué
— K01 a mesuré qu'il n'y avait de toute façon rien d'importable, l'intelligence
de ces implémentations vivant dans un arbre React.

## Les trois refus

- **Types différents** — refusé, en nommant les deux (`ports.py`).
- **Cycle** — refusé. Un graphe créatif qui se renvoie sa propre sortie n'a pas
  d'ordre défini, et en inventer un inventerait un résultat.
- **Entrée requise non branchée** — le nœud reste `BLOCKED` et **la nomme**.
  Elle n'est jamais remplie par un défaut : c'est exactement le geste qui, dans
  l'implémentation auditée, transforme une focale non prévue en chaîne vide.

## Ce que le graphe produit

Un **plan**, pas un résultat. L'exécution passe par l'orchestrateur existant, et
aujourd'hui aucun nœud de génération ne peut tourner : rien dans cette
plateforme ne produit une image ni une vidéo (K00, mesuré). Le graphe le dit
plutôt que de le laisser découvrir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ...security.trust import TrustLevel
from .ports import Port, edge_is_legal

#: Ce qui décide du niveau de confiance de la sortie d'un nœud de génération :
#: la destination des données, pas le type du nœud (ADR-031 décision 3).
DECIDE_PAR_LE_FOURNISSEUR = "PROVIDER"


class GraphRefused(ValueError):
    """Un graphe ou une arête impossible tel quel."""


@dataclass(frozen=True)
class NodeType:
    """
    Un type de nœud : ses ports, et d'où vient la confiance de sa sortie.

    Attributes:
        name: Le nom du type.
        inputs: Les ports d'entrée.
        outputs: Les ports de sortie.
        trust: Le niveau de confiance de la sortie, ou
            `DECIDE_PAR_LE_FOURNISSEUR` quand il dépend de la destination des
            données — ce qui est le cas de tout nœud qui appelle un fournisseur.
    """

    name: str
    inputs: Tuple[Port, ...] = ()
    outputs: Tuple[Port, ...] = ()
    trust: Any = TrustLevel.TOOL

    def input(self, name: str) -> Port:
        """Le port d'entrée nommé."""
        for port in self.inputs:
            if port.name == name:
                return port
        raise GraphRefused(
            f"Le type « {self.name} » n'a pas d'entrée « {name} ». Entrées : "
            f"{[p.name for p in self.inputs]}."
        )

    def output(self, name: str) -> Port:
        """Le port de sortie nommé."""
        for port in self.outputs:
            if port.name == name:
                return port
        raise GraphRefused(
            f"Le type « {self.name} » n'a pas de sortie « {name} ». Sorties : "
            f"{[p.name for p in self.outputs]}."
        )


#: Les types de nœud déclarés, avec leur niveau de confiance.
#:
#: Le tableau est la correspondance que K00 a trouvée manquante : la frontière
#: de confiance existe depuis longtemps dans `security/trust.py`, mais **aucun
#: type de nœud n'y était rattaché**. Les nœuds de génération, eux, n'ont pas de
#: niveau fixe : il dépend de où part la donnée (`privacy.py`).
TYPES_DE_NOEUD: Dict[str, NodeType] = {
    "prompt": NodeType(
        "prompt", outputs=(Port("text", "text"),), trust=TrustLevel.USER),
    "intent": NodeType(
        "intent", inputs=(Port("text", "text"),),
        outputs=(Port("intent", "intent"),), trust=TrustLevel.USER),
    "image_upload": NodeType(
        "image_upload", outputs=(Port("image", "image"),),
        trust=TrustLevel.DOCUMENT),
    "audio_upload": NodeType(
        "audio_upload", outputs=(Port("audio", "audio"),),
        trust=TrustLevel.DOCUMENT),
    "reference": NodeType(
        "reference", inputs=(Port("image", "image"),),
        outputs=(Port("reference", "reference"),), trust=TrustLevel.DEVELOPER),
    "world": NodeType(
        "world", outputs=(Port("world", "world"),), trust=TrustLevel.TOOL),
    "style": NodeType(
        "style", outputs=(Port("style", "style"),), trust=TrustLevel.DEVELOPER),
    "direction": NodeType(
        "direction", outputs=(Port("direction", "direction"),),
        trust=TrustLevel.DEVELOPER),
    "knowledge": NodeType(
        "knowledge", inputs=(Port("text", "text"),),
        outputs=(Port("analysis", "analysis"),), trust=TrustLevel.RETRIEVED),
    "image_generation": NodeType(
        "image_generation",
        inputs=(Port("intent", "intent"),
                Port("reference", "reference", required=False),
                Port("style", "style", required=False),
                Port("direction", "direction", required=False)),
        outputs=(Port("image", "image"),),
        trust=DECIDE_PAR_LE_FOURNISSEUR),
    "video_generation": NodeType(
        "video_generation",
        inputs=(Port("intent", "intent"),
                Port("image", "image", required=False),
                Port("direction", "direction", required=False)),
        outputs=(Port("video", "video"),),
        trust=DECIDE_PAR_LE_FOURNISSEUR),
}


@dataclass(frozen=True)
class CanvasNode:
    """
    Un nœud du graphe.

    Attributes:
        node_id: L'identifiant, unique dans le graphe.
        type_name: Le type, parmi `TYPES_DE_NOEUD`.
        label: Un nom lisible, purement documentaire.
    """

    node_id: str
    type_name: str
    label: str = ""

    def __post_init__(self) -> None:
        if not str(self.node_id).strip():
            raise GraphRefused("Un nœud sans identifiant ne s'adresse pas.")
        if self.type_name not in TYPES_DE_NOEUD:
            raise GraphRefused(
                f"Type de nœud « {self.type_name} » non déclaré. Déclarés : "
                f"{sorted(TYPES_DE_NOEUD)}."
            )

    @property
    def node_type(self) -> NodeType:
        """Le type déclaré de ce nœud."""
        return TYPES_DE_NOEUD[self.type_name]


@dataclass(frozen=True)
class Edge:
    """Une arête, du port de sortie d'un nœud vers le port d'entrée d'un autre."""

    source_id: str
    source_port: str
    target_id: str
    target_port: str

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {"source_id": self.source_id, "source_port": self.source_port,
                "target_id": self.target_id, "target_port": self.target_port}


@dataclass
class CanvasGraph:
    """
    Le graphe : des nœuds, des arêtes, et rien qui décide à la place de qui que
    ce soit.
    """

    nodes: Dict[str, CanvasNode] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node_id: str, type_name: str,
                 label: str = "") -> CanvasNode:
        """
        Ajoute un nœud.

        Args:
            node_id: L'identifiant voulu.
            type_name: Le type déclaré.
            label: Un nom lisible.

        Returns:
            Le nœud créé.

        Raises:
            GraphRefused: Identifiant déjà pris, ou type non déclaré.
        """
        if node_id in self.nodes:
            raise GraphRefused(
                f"Le nœud « {node_id} » existe déjà. Deux nœuds de même "
                "identifiant rendraient une arête ambiguë."
            )
        noeud = CanvasNode(node_id=node_id, type_name=type_name, label=label)
        self.nodes[node_id] = noeud
        return noeud

    def connect(self, source_id: str, source_port: str,
                target_id: str, target_port: str) -> Edge:
        """
        Relie deux ports, si l'arête est légale.

        Args:
            source_id: Le nœud source.
            source_port: Son port de sortie.
            target_id: Le nœud cible.
            target_port: Son port d'entrée.

        Returns:
            L'arête créée.

        Raises:
            GraphRefused: Nœud inconnu, port inconnu, types différents, entrée
                déjà branchée, ou cycle.
        """
        for identifiant in (source_id, target_id):
            if identifiant not in self.nodes:
                raise GraphRefused(f"Nœud « {identifiant} » inconnu.")
        sortie = self.nodes[source_id].node_type.output(source_port)
        entree = self.nodes[target_id].node_type.input(target_port)

        verdict = edge_is_legal(sortie, entree)
        if not verdict["legal"]:
            raise GraphRefused(verdict["reason"])

        for arete in self.edges:
            if (arete.target_id, arete.target_port) == (target_id, target_port):
                raise GraphRefused(
                    f"L'entrée « {target_port} » de « {target_id} » est déjà "
                    f"branchée sur « {arete.source_id} ». Deux sources pour une "
                    "entrée demanderaient d'en choisir une, et ce choix "
                    "n'appartient pas au graphe."
                )

        candidate = Edge(source_id, source_port, target_id, target_port)
        if self._creerait_un_cycle(candidate):
            raise GraphRefused(
                f"« {source_id} » → « {target_id} » ferme un cycle. Un graphe "
                "créatif cyclique n'a pas d'ordre défini, et en inventer un "
                "inventerait un résultat."
            )
        self.edges.append(candidate)
        return candidate

    def _creerait_un_cycle(self, candidate: Edge) -> bool:
        """Vrai si l'arête proposée rend le graphe cyclique."""
        aretes = self.edges + [candidate]
        sortants: Dict[str, List[str]] = {}
        for arete in aretes:
            sortants.setdefault(arete.source_id, []).append(arete.target_id)

        vus: Dict[str, int] = {}

        def descend(noeud: str) -> bool:
            etat = vus.get(noeud, 0)
            if etat == 1:
                return True
            if etat == 2:
                return False
            vus[noeud] = 1
            for suivant in sortants.get(noeud, ()):
                if descend(suivant):
                    return True
            vus[noeud] = 2
            return False

        return any(descend(identifiant) for identifiant in list(self.nodes))

    def unconnected_required_inputs(self) -> List[Dict[str, str]]:
        """
        Les entrées requises que rien n'alimente.

        Returns:
            Une entrée par port, **nommé**. Aucune n'est remplie par un défaut.
        """
        branchees = {(a.target_id, a.target_port) for a in self.edges}
        manquantes = []
        for identifiant, noeud in self.nodes.items():
            for port in noeud.node_type.inputs:
                if port.required and (identifiant, port.name) not in branchees:
                    manquantes.append({"node_id": identifiant,
                                       "port": port.name,
                                       "port_type": port.port_type})
        return manquantes

    def topological_order(self) -> List[str]:
        """
        L'ordre d'exécution.

        Returns:
            Les identifiants de nœud, dans un ordre où chaque nœud vient après
            ses sources. Déterministe : à graphe égal, ordre égal — un ordre qui
            changerait d'un appel à l'autre rendrait un plan irreproductible.
        """
        entrants = {identifiant: 0 for identifiant in self.nodes}
        sortants: Dict[str, List[str]] = {i: [] for i in self.nodes}
        for arete in self.edges:
            entrants[arete.target_id] += 1
            sortants[arete.source_id].append(arete.target_id)

        prets = sorted(i for i, n in entrants.items() if n == 0)
        ordre: List[str] = []
        while prets:
            courant = prets.pop(0)
            ordre.append(courant)
            for suivant in sorted(sortants[courant]):
                entrants[suivant] -= 1
                if entrants[suivant] == 0:
                    prets.append(suivant)
            prets.sort()
        if len(ordre) != len(self.nodes):
            raise GraphRefused(
                "Le graphe contient un cycle : aucun ordre ne peut être rendu."
            )
        return ordre

    def trust_of(self, node_id: str,
                 provider_trust: Optional[Any] = None) -> Any:
        """
        Le niveau de confiance de la sortie d'un nœud.

        Args:
            node_id: Le nœud.
            provider_trust: Pour un nœud de génération, le niveau que
                `privacy.py` déduit de la destination des données.

        Returns:
            Un `TrustLevel`.

        Raises:
            GraphRefused: Pour un nœud de génération sans niveau fourni. Il
                n'est **pas** rattrapé par un défaut : un défaut serait
                forcément trop généreux ou trop sévère, et le premier des deux
                ferait passer un contenu tiers pour une sortie de la plateforme.
        """
        if node_id not in self.nodes:
            raise GraphRefused(f"Nœud « {node_id} » inconnu.")
        declare = self.nodes[node_id].node_type.trust
        if declare != DECIDE_PAR_LE_FOURNISSEUR:
            return declare
        if provider_trust is None:
            raise GraphRefused(
                f"« {node_id} » appelle un fournisseur : sa confiance dépend de "
                "où part la donnée, et rien ne l'a fournie. Aucun défaut n'est "
                "posé ici (ADR-031, décision 3)."
            )
        return provider_trust

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable du graphe."""
        return {
            "nodes": [{"node_id": n.node_id, "type": n.type_name,
                       "label": n.label} for n in self.nodes.values()],
            "edges": [a.as_dict() for a in self.edges],
        }


def graph_report() -> Dict[str, Any]:
    """
    Ce que le graphe déclare, et ce qu'il refuse.

    Returns:
        Les types de nœud avec leur confiance, et les règles tenues.
    """
    return {
        "node_types": {
            nom: {
                "inputs": [p.as_dict() for p in t.inputs],
                "outputs": [p.as_dict() for p in t.outputs],
                "trust": (t.trust if isinstance(t.trust, str)
                          else t.trust.value),
            } for nom, t in TYPES_DE_NOEUD.items()
        },
        "count": len(TYPES_DE_NOEUD),
        "rules": [
            "Une arête est légale seulement si les deux types sont égaux.",
            "Un cycle est refusé : aucun ordre ne s'invente.",
            "Une entrée requise non branchée laisse le nœud bloqué, nommée.",
            "Une entrée n'accepte qu'une source.",
            "L'ordre est déterministe à graphe égal.",
            "La confiance d'un nœud de génération vient du fournisseur, "
            "jamais d'un défaut.",
        ],
    }
