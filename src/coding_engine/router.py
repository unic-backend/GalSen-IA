"""
Choix du moteur de codage (ADR-028).

Le routeur ne connaît **aucun** des trois moteurs par son nom. Il ne manipule
que des capacités : un moteur ajouté demain est routé sans qu'une ligne d'ici
change, ce qui est la raison d'être de cette couche.

Le choix se fait en deux temps :

1. **Deviner ce que la demande exige.** Une table de signaux relie des tournures
   de langage à des capacités. Elle est déclarative et bilingue, parce que la
   plateforme parle français à ses utilisateurs et que ses moteurs sont
   documentés en anglais.
2. **Marquer les moteurs.** Un moteur dont la spécialité est la capacité
   déduite marque fort ; un moteur qui la couvre sans en faire sa spécialité
   marque peu. À égalité, l'ordre d'enregistrement décide — un routage doit
   être reproductible.

Ce que le routeur **ne** fait pas : préférer un moteur parce qu'il est mieux
connu. Un moteur indisponible n'est jamais choisi, et l'absence de tout moteur
est rapportée, jamais compensée par un choix au hasard.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from src.coding_engine.interfaces import CodingEngineAdapter
from src.coding_engine.types import CodingCapability, CodingTask

# Signaux de langage → capacité exigée. La table est le seul endroit à modifier
# pour affiner le routage ; elle ne cite aucun moteur.
SIGNAUX: Dict[CodingCapability, Sequence[str]] = {
    CodingCapability.ISSUE_RESOLUTION: (
        r"\bissue\b", r"\bbug\b", r"\bbogue\b", r"\bcorrige[rz]?\b", r"\bfix\b",
        r"\brégression\b", r"\bregression\b", r"\bplante\b", r"\bcrash\b",
        r"\btrace(back)?\b", r"\bstack ?trace\b", r"\berreur\b.*\bproduction\b",
        r"\benquête[rz]?\b", r"\binvestigate\b", r"\bpourquoi ça échoue\b",
    ),
    CodingCapability.AUTONOMOUS_IMPLEMENTATION: (
        r"\bimplémente[rz]?\b", r"\bimplement\b", r"\bfonctionnalité complète\b",
        r"\bcomplete feature\b", r"\bde bout en bout\b", r"\bend[- ]to[- ]end\b",
        r"\bitère[rz]?\b", r"\biterate\b", r"\bjusqu'à ce que.*(passe|marche)\b",
        r"\buntil (it|the tests?) (work|pass)\b", r"\bconstruis\b", r"\bbuild\b",
    ),
    CodingCapability.TARGETED_EDIT: (
        r"\bmodifie[rz]?\b", r"\bmodify\b", r"\bchange\b", r"\brenomme[rz]?\b",
        r"\brename\b", r"\bdans (le fichier|ce fichier|les fichiers)\b",
        r"\bin (this|the) files?\b", r"\bremplace[rz]?\b", r"\breplace\b",
        r"\bajoute[rz]? (un|une|le|la) (paramètre|argument|champ|méthode)\b",
    ),
    CodingCapability.TEST_EXECUTION: (
        r"\blance[rz]? les tests\b", r"\brun the tests?\b", r"\bpytest\b",
        r"\bsuite de tests\b", r"\btest suite\b", r"\bvérifie[rz]? que ça passe\b",
    ),
}

# Une spécialité vaut plus qu'une capacité couverte : c'est ce qui distingue
# « sait faire » de « fait le mieux ».
POIDS_SPECIALITE = 3
POIDS_CAPACITE = 1


@dataclass(frozen=True)
class RoutingDecision:
    """
    Le moteur retenu et la raison de ce choix.

    Attributes:
        engine_id: Moteur choisi, ou `None` si aucun ne convient.
        reason: Pourquoi, en clair. Un routage sans explication est
            impossible à corriger quand il se trompe.
        inferred_capabilities: Capacités déduites de la demande.
        considered: Moteurs examinés et leur score.
        rejected: Moteurs écartés, avec le motif.
    """

    engine_id: Optional[str]
    reason: str
    inferred_capabilities: List[CodingCapability]
    considered: Dict[str, int]
    rejected: Dict[str, str]


def infer_capabilities(instruction: str) -> List[CodingCapability]:
    """
    Déduit les capacités exigées par une demande.

    Args:
        instruction: La demande, en français ou en anglais.

    Returns:
        Les capacités reconnues, dans l'ordre de la table. Liste vide quand
        rien n'est reconnu — le routeur retombe alors sur les capacités
        couvertes, plutôt que d'inventer une intention.
    """
    texte = (instruction or "").lower()
    return [
        capacite
        for capacite, motifs in SIGNAUX.items()
        if any(re.search(motif, texte) for motif in motifs)
    ]


class CodingRouter:
    """Choisit le moteur le mieux placé pour une tâche."""

    def __init__(self, adapters: Sequence[CodingEngineAdapter]):
        """
        Initialise le routeur.

        Args:
            adapters: Les adaptateurs enregistrés, dans l'ordre de préférence
                pour départager les égalités.
        """
        self._adapters = list(adapters)

    def route(
        self,
        task: CodingTask,
        available: Optional[Dict[str, bool]] = None,
    ) -> RoutingDecision:
        """
        Choisit un moteur pour une tâche.

        Args:
            task: La tâche à router.
            available: État de disponibilité par moteur. Un moteur absent de
                cette table est considéré disponible ; un moteur à `False` n'est
                jamais choisi, quel que soit son score.

        Returns:
            La décision, avec les scores et les motifs d'écart.
        """
        disponibilite = available or {}
        ecartes: Dict[str, str] = {}
        exigees = list(task.capabilities) or infer_capabilities(task.instruction)

        if task.engine_id:
            return self._route_impose(task, disponibilite, exigees)

        scores: Dict[str, int] = {}
        for adaptateur in self._adapters:
            if not disponibilite.get(adaptateur.engine_id, True):
                ecartes[adaptateur.engine_id] = "indisponible"
                continue
            if exigees and not adaptateur.supports(exigees):
                manquantes = set(exigees) - set(adaptateur.capabilities)
                ecartes[adaptateur.engine_id] = (
                    "ne couvre pas : " + ", ".join(sorted(c.value for c in manquantes))
                )
                continue
            scores[adaptateur.engine_id] = self._score(adaptateur, exigees)

        if not scores:
            return RoutingDecision(
                engine_id=None,
                reason="Aucun moteur de codage disponible ne couvre cette demande.",
                inferred_capabilities=exigees, considered={}, rejected=ecartes,
            )

        # `max` sur l'ordre d'enregistrement : à score égal, le premier
        # enregistré gagne, donc le routage est reproductible.
        meilleur = max(scores, key=lambda identifiant: (scores[identifiant], -self._rang(identifiant)))
        return RoutingDecision(
            engine_id=meilleur,
            reason=self._expliquer(meilleur, exigees),
            inferred_capabilities=exigees, considered=scores, rejected=ecartes,
        )

    # ------------------------------------------------------------------
    # Détail
    # ------------------------------------------------------------------

    def _route_impose(
        self, task: CodingTask, disponibilite: Dict[str, bool],
        exigees: List[CodingCapability],
    ) -> RoutingDecision:
        """Traite le cas d'un moteur imposé par l'appelant."""
        connus = {a.engine_id for a in self._adapters}
        if task.engine_id not in connus:
            return RoutingDecision(
                engine_id=None,
                reason=f"Moteur « {task.engine_id} » inconnu. Moteurs enregistrés : "
                       + ", ".join(sorted(connus)),
                inferred_capabilities=exigees, considered={},
                rejected={task.engine_id: "inconnu"},
            )
        if not disponibilite.get(task.engine_id, True):
            return RoutingDecision(
                engine_id=None,
                reason=f"Moteur « {task.engine_id} » imposé mais indisponible. "
                       f"Un autre moteur ne serait pas ce qui a été demandé.",
                inferred_capabilities=exigees, considered={},
                rejected={task.engine_id: "indisponible"},
            )
        return RoutingDecision(
            engine_id=task.engine_id, reason="Moteur imposé par l'appelant.",
            inferred_capabilities=exigees, considered={task.engine_id: 0}, rejected={},
        )

    def _score(
        self, adaptateur: CodingEngineAdapter, exigees: List[CodingCapability]
    ) -> int:
        """Marque un moteur face aux capacités exigées."""
        if not exigees:
            # Rien de reconnu dans la demande : on préfère le moteur le plus
            # polyvalent, sans deviner une intention qui n'a pas été exprimée.
            return len(adaptateur.capabilities)

        specialite = getattr(adaptateur, "primary_capability", None)
        total = 0
        for capacite in exigees:
            if capacite == specialite:
                total += POIDS_SPECIALITE
            elif capacite in adaptateur.capabilities:
                total += POIDS_CAPACITE
        return total

    def _rang(self, engine_id: str) -> int:
        """Position d'enregistrement, pour départager à score égal."""
        for rang, adaptateur in enumerate(self._adapters):
            if adaptateur.engine_id == engine_id:
                return rang
        return len(self._adapters)

    def _expliquer(self, engine_id: str, exigees: List[CodingCapability]) -> str:
        """Rédige la raison du choix."""
        if not exigees:
            return (
                f"« {engine_id} » retenu : rien dans la demande ne désigne une "
                f"capacité précise, c'est le moteur le plus polyvalent disponible."
            )
        noms = ", ".join(c.value for c in exigees)
        return f"« {engine_id} » retenu pour : {noms}."
