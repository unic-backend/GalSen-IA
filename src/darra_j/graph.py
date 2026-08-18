"""
The educational graph — derived from the official record, never authored.

Directive XXIX asks for grade → subject → unit → objective → prerequisite →
exercise → mastery. The chain is easy to draw and easy to get wrong in one
specific way: a graph is the most convincing artefact a platform can produce.
Nobody reads an edge and asks who decided it. So the rule here is the same one
that governs everything upstream, applied to a shape that hides it better:

**Every edge is derived, and says from which official field.** A `requires` edge
exists because a unit's `prerequisites` field names something — not because two
units look related, not because the order of weeks suggests it. `derived_from`
carries the unit and the field, so any edge can be traced back to a published
document.

**A prerequisite that resolves to nothing stays unresolved, by name.** Official
prerequisites are written as text — "La division euclidienne" — not as
identifiers. Matching them to units is an *exact* match on the official title,
in folded form, and nothing else. The near-miss temptation is real and was paid
for once already (`find_country`, VOLET 69): a fuzzy match here would silently
declare that a child must master a unit the ministry never pointed to. An
unresolved prerequisite is reported as `dangling` with its literal text, which
is a fact a curriculum team can act on.

**A cycle is reported, never broken.** If A requires B and B requires A in a
published curriculum, that is an institutional defect, and the graph's job is to
make it visible. Silently dropping one edge would produce a plausible ordering
and hide the problem forever.

An empty registry produces an empty graph that says it is empty — the expected
state until an authority provides data.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .registry import CurriculumRegistry

#: Les natures de nœud (directive XXIX). `exercise` et `mastery` sont rattachés
#: par les VOLETs 9 et 15 ; ils sont déclarés ici pour que la forme du graphe
#: soit lisible d'un seul endroit.
NOEUD_NIVEAU = "grade"
NOEUD_MATIERE = "subject"
NOEUD_UNITE = "unit"
NOEUD_OBJECTIF = "objective"

#: Les natures d'arête. Chacune dit **de quel champ officiel** elle vient.
ARETE_CONTIENT = "contains"
ARETE_VISE = "targets"
ARETE_EXIGE = "requires"

#: Ce qu'un prérequis peut devenir.
RESOLU = "RESOLVED"
PENDANT = "DANGLING"


def _replie(texte: str) -> str:
    """Ramène un libellé à sa forme comparable : sans accent, sans casse."""
    decompose = unicodedata.normalize("NFKD", str(texte or ""))
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(sans_accent.casefold().split())


@dataclass(frozen=True)
class Edge:
    """
    Une arête, et le champ officiel dont elle vient.

    Attributes:
        source: Le nœud d'origine.
        target: Le nœud d'arrivée.
        kind: `contains`, `targets` ou `requires`.
        derived_from: L'unité et le champ officiel qui la portent. Sans cela,
            une arête serait une affirmation que personne ne peut contester —
            et un graphe est l'artefact le plus convaincant qu'une plateforme
            puisse produire.
    """

    source: str
    target: str
    kind: str
    derived_from: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "source": self.source, "target": self.target, "kind": self.kind,
            "derived_from": self.derived_from,
        }


@dataclass
class EducationalGraph:
    """
    Le graphe d'une version de curriculum, tel qu'il est **dérivé**.

    Attributes:
        version_id: La version dont il vient.
        nodes: Les nœuds, par identifiant.
        edges: Les arêtes.
        dangling: Les prérequis officiels qui ne désignent aucune unité, avec
            leur texte littéral.
    """

    version_id: str = ""
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    dangling: List[Dict[str, str]] = field(default_factory=list)

    def prerequisites_of(self, unit_id: str) -> List[str]:
        """Les unités qu'une unité exige, directement."""
        return sorted(
            arete.target for arete in self.edges
            if arete.kind == ARETE_EXIGE and arete.source == unit_id
        )

    def unlocked_by(self, unit_id: str) -> List[str]:
        """Les unités qui exigent celle-ci, directement."""
        return sorted(
            arete.source for arete in self.edges
            if arete.kind == ARETE_EXIGE and arete.target == unit_id
        )

    def objectives_of(self, unit_id: str) -> List[str]:
        """Les objectifs officiels visés par une unité."""
        return sorted(
            arete.target for arete in self.edges
            if arete.kind == ARETE_VISE and arete.source == unit_id
        )

    def chain_to(self, unit_id: str) -> Dict[str, Any]:
        """
        Tout ce qu'il faut avoir vu avant une unité, dans l'ordre.

        Args:
            unit_id: L'unité visée.

        Returns:
            La chaîne des prérequis, du plus profond au plus proche, et les
            cycles rencontrés. Un cycle est **rendu**, jamais coupé : couper
            produirait un ordre plausible et cacherait le défaut pour toujours.
        """
        ordre: List[str] = []
        cycles: List[List[str]] = []
        en_cours: List[str] = []
        vus: Set[str] = set()

        def _descendre(courant: str) -> None:
            if courant in en_cours:
                debut = en_cours.index(courant)
                cycles.append(en_cours[debut:] + [courant])
                return
            if courant in vus:
                return
            en_cours.append(courant)
            for prerequis in self.prerequisites_of(courant):
                _descendre(prerequis)
            en_cours.pop()
            vus.add(courant)
            if courant != unit_id:
                ordre.append(courant)

        _descendre(unit_id)
        return {
            "unit_id": unit_id,
            "before": ordre,
            "cycles": cycles,
            "reason": (
                "Chaîne dérivée des prérequis officiels."
                if not cycles else
                "Un cycle existe dans les prérequis publiés. Il est rendu tel "
                "quel : le couper produirait un ordre plausible et cacherait un "
                "défaut institutionnel."
            ),
        }

    def cycles(self) -> List[List[str]]:
        """Tous les cycles de prérequis du graphe, sans en casser aucun."""
        trouves: List[List[str]] = []
        connus: Set[frozenset] = set()
        for identifiant, noeud in self.nodes.items():
            if noeud["kind"] != NOEUD_UNITE:
                continue
            for cycle in self.chain_to(identifiant)["cycles"]:
                empreinte = frozenset(cycle)
                if empreinte not in connus:
                    connus.add(empreinte)
                    trouves.append(cycle)
        return trouves

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, avec ce qui manque."""
        par_nature: Dict[str, int] = {}
        for noeud in self.nodes.values():
            par_nature[noeud["kind"]] = par_nature.get(noeud["kind"], 0) + 1

        return {
            "version_id": self.version_id,
            "node_count": len(self.nodes),
            "nodes_by_kind": par_nature,
            "edge_count": len(self.edges),
            "edges": [arete.as_dict() for arete in self.edges],
            "dangling_prerequisites": list(self.dangling),
            "cycles": self.cycles(),
            "empty": not self.nodes,
            "note": (
                "Graphe **dérivé** du registre officiel. Chaque arête porte le "
                "champ dont elle vient ; aucune n'est déduite d'une "
                "ressemblance."
                if self.nodes else
                "Graphe vide : aucune unité officielle dans cette version. "
                "C'est l'état attendu tant qu'aucune autorité n'a fourni de "
                "données."
            ),
        }


def build_graph(
    registry: CurriculumRegistry, version_id: str,
) -> EducationalGraph:
    """
    Dérive le graphe d'une version, sans rien y ajouter.

    Args:
        registry: Le registre.
        version_id: La version à dériver.

    Returns:
        Le graphe. Les prérequis sont rapprochés des unités par **égalité
        exacte** du titre officiel replié, jamais par ressemblance : un
        rapprochement approché déclarerait en silence qu'un enfant doit
        maîtriser une unité que le ministère n'a jamais désignée.
    """
    graphe = EducationalGraph(version_id=version_id)
    unites = registry.units_in_version(version_id)

    par_titre: Dict[str, List[str]] = {}
    for unite in unites:
        par_titre.setdefault(_replie(unite.official_title), []).append(unite.unit_id)

    for unite in unites:
        niveau = f"grade:{unite.grade.grade_id}"
        matiere = f"subject:{unite.grade.grade_id}:{unite.subject.subject_id}"

        graphe.nodes.setdefault(niveau, {
            "kind": NOEUD_NIVEAU, "label": unite.grade.official_name,
        })
        graphe.nodes.setdefault(matiere, {
            "kind": NOEUD_MATIERE, "label": unite.subject.official_name,
        })
        graphe.nodes[unite.unit_id] = {
            "kind": NOEUD_UNITE, "label": unite.official_title,
            "content_hash": unite.content_hash(),
        }

        _ajouter(graphe, niveau, matiere, ARETE_CONTIENT, unite.unit_id, "grade")
        _ajouter(graphe, matiere, unite.unit_id, ARETE_CONTIENT, unite.unit_id,
                 "subject")

        for objectif in unite.objectives:
            identifiant = f"objective:{unite.unit_id}:{_replie(objectif)}"
            graphe.nodes[identifiant] = {
                "kind": NOEUD_OBJECTIF, "label": objectif,
            }
            _ajouter(graphe, unite.unit_id, identifiant, ARETE_VISE,
                     unite.unit_id, "objectives")

        for prerequis in unite.prerequisites:
            cibles = par_titre.get(_replie(prerequis), [])
            if not cibles:
                graphe.dangling.append({
                    "unit_id": unite.unit_id,
                    "text": prerequis,
                    "status": PENDANT,
                    "reason": (
                        "Ce prérequis officiel ne désigne aucune unité de cette "
                        "version. Il est rendu tel quel : le rapprocher d'une "
                        "unité au titre voisin déclarerait un prérequis que "
                        "personne n'a publié."
                    ),
                })
                continue
            for cible in cibles:
                _ajouter(graphe, unite.unit_id, cible, ARETE_EXIGE,
                         unite.unit_id, "prerequisites")

    return graphe


def _ajouter(
    graphe: EducationalGraph, source: str, cible: str, nature: str,
    unite_id: str, champ: str,
) -> None:
    """Ajoute une arête en nommant le champ officiel dont elle vient."""
    arete = Edge(
        source=source, target=cible, kind=nature,
        derived_from=f"{unite_id}.{champ}",
    )
    if arete not in graphe.edges:
        graphe.edges.append(arete)


def graph_report(graph: Optional[EducationalGraph] = None) -> Dict[str, Any]:
    """
    Ce que le graphe garantit, et ce qu'il refuse de déduire.

    Args:
        graph: Un graphe à décrire, facultatif.

    Returns:
        Les natures de nœud et d'arête, l'état du graphe donné, et les règles.
    """
    rapport: Dict[str, Any] = {
        "node_kinds": [NOEUD_NIVEAU, NOEUD_MATIERE, NOEUD_UNITE, NOEUD_OBJECTIF],
        "edge_kinds": [ARETE_CONTIENT, ARETE_VISE, ARETE_EXIGE],
        "rules": [
            "Chaque arête porte le **champ officiel** dont elle vient : un "
            "graphe est l'artefact le plus convaincant qu'une plateforme "
            "puisse produire, et personne ne demande qui a décidé une arête.",
            "Les prérequis sont rapprochés par **égalité exacte** du titre "
            "officiel : un rapprochement approché déclarerait un prérequis que "
            "personne n'a publié.",
            "Un prérequis qui ne désigne rien reste `DANGLING`, avec son texte "
            "littéral — c'est un fait sur lequel une équipe curriculaire peut "
            "agir.",
            "Un cycle est **rendu**, jamais coupé : couper produirait un ordre "
            "plausible et cacherait un défaut institutionnel.",
            "Un registre vide donne un graphe vide qui le dit.",
        ],
        "does_not": [
            "Créer une arête que le curriculum officiel ne porte pas.",
            "Rapprocher deux titres voisins.",
            "Ordonner des unités par ressemblance ou par numéro de semaine.",
            "Réparer un curriculum incohérent.",
        ],
    }
    if graph is not None:
        rapport["graph"] = graph.as_dict()
    return rapport
