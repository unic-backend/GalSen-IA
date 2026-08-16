"""
Structured creative intent — and the difference between what was asked and what
was assumed.

Directive §5 says the CreativeEngine *must NOT rely only on natural-language
prompts*, and the reason is not that prompts are imprecise. It is that a prompt
cannot say which of its parts came from the user. "A 60-second vertical
documentary" and "a documentary" are the same object once both have been turned
into a generation call: one had a duration and an aspect, the other had defaults
that somebody's code chose. Three steps later nobody can tell them apart, and
the delivery is judged against constraints the client never set.

So every field here carries **who stated it**: `STATED` when it came from the
request, `INFERRED` when something derived it and said so, `UNSPECIFIED` when
nobody has. An `UNSPECIFIED` field becomes a question, and **a representation
with open questions is not executable** — `ready()` refuses it rather than
filling the gaps.

Nothing here re-parses natural language. `src/media/tools/intent.py` already
turns a request into structured fields and already refuses to complete what was
not said; this module *composes* it and adds what the creative layer needs on
top: entities, references with their consent checked, and the provenance of
every field. A second parser would drift from the first, which is the failure
this repository has paid for four times.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

#: D'où vient la valeur d'un champ. La distinction est le contenu même du
#: module : une valeur déduite et une valeur demandée doivent rester
#: distinguables jusqu'à la livraison.
DECLARE = "STATED"
DEDUIT = "INFERRED"
NON_PRECISE = "UNSPECIFIED"
PROVENANCES = (DECLARE, DEDUIT, NON_PRECISE)

#: Les modalités par lesquelles une intention peut arriver (§47).
MODALITES = ("text", "speech", "image", "video", "audio", "document")

#: L'état d'une représentation.
PRETE = "READY"
CLARIFICATION_REQUISE = "CLARIFICATION_REQUIRED"


class RepresentationRefused(ValueError):
    """Une représentation impossible à construire ou à exécuter telle quelle."""


@dataclass(frozen=True)
class Field:
    """
    Un champ de l'intention, avec la trace de qui l'a posé.

    Attributes:
        name: Le nom du champ.
        value: Sa valeur. `None` quand personne ne l'a posée.
        provenance: `STATED`, `INFERRED` ou `UNSPECIFIED`.
        source: Ce qui a fourni la valeur — la demande, un module, une règle.
        question: Ce qu'il faut demander quand le champ n'est pas posé.
    """

    name: str
    value: Any = None
    provenance: str = NON_PRECISE
    source: str = ""
    question: str = ""

    def __post_init__(self) -> None:
        if self.provenance not in PROVENANCES:
            raise RepresentationRefused(
                f"Provenance « {self.provenance} » non déclarée. Déclarées : "
                f"{list(PROVENANCES)}."
            )
        if self.provenance == NON_PRECISE and self.value is not None:
            raise RepresentationRefused(
                f"« {self.name} » porte une valeur et se dit non précisé. "
                "L'un des deux est faux, et c'est exactement la confusion que "
                "ce champ existe pour empêcher."
            )
        if self.provenance == NON_PRECISE and not str(self.question or "").strip():
            raise RepresentationRefused(
                f"« {self.name} » n'est pas précisé et ne porte aucune "
                "question. Un manque sans question ne se comble jamais : il "
                "se remplit tout seul, par un défaut que personne n'a choisi."
            )
        if self.provenance == DEDUIT and not str(self.source or "").strip():
            raise RepresentationRefused(
                f"« {self.name} » est déduit sans source. Une déduction "
                "anonyme est indiscernable d'une demande."
            )

    @property
    def known(self) -> bool:
        """Vrai quand quelqu'un ou quelque chose a posé la valeur."""
        return self.provenance != NON_PRECISE

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {"name": self.name, "value": self.value,
                "provenance": self.provenance, "source": self.source,
                "question": self.question}


@dataclass(frozen=True)
class EntityRef:
    """
    Une entité de la production, éventuellement adossée à une référence.

    Attributes:
        entity_id: Son identité dans la production.
        entity_type: Ce qu'elle est — humain, animal, véhicule, objet…
        reference_id: La `ReferenceEntity` qui la conditionne, s'il y en a une.
        fidelity: Son importance visuelle : `HERO`, `SUPPORTING`,
            `BACKGROUND` ou `CROWD` (§20).
        role: Son rôle narratif, quand il est connu.
    """

    entity_id: str
    entity_type: str
    reference_id: Optional[str] = None
    fidelity: str = "SUPPORTING"
    role: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {"entity_id": self.entity_id, "entity_type": self.entity_type,
                "reference_id": self.reference_id, "fidelity": self.fidelity,
                "role": self.role}


#: Les champs qu'une production doit poser avant d'être exécutable, avec la
#: question à poser quand ils manquent. Écrites une fois : la même question,
#: quel que soit l'appelant.
CHAMPS_REQUIS = {
    "domain": (
        "Quel type de production ? Aucune structure n'est appliquée par "
        "défaut : en forcer une produit une vidéo qui suit un plan que "
        "personne n'a choisi (§6)."
    ),
    "duration_seconds": (
        "Quelle durée ? Elle décide du montage entier ; une durée choisie ici "
        "ne se distinguerait plus d'une durée demandée."
    ),
    "aspect": (
        "Quel format de diffusion ? Il décide du cadrage de chaque "
        "incrustation (§22)."
    ),
}


class CreativeRepresentation:
    """
    L'intention d'une production, sous une forme que l'on peut interroger.

    Ce n'est pas une invite : chaque champ sait qui l'a posé, et un champ que
    personne n'a posé porte sa question au lieu d'une valeur par défaut.
    """

    def __init__(self, intent: str, intent_source: str = "text",
                 representation_id: str = "") -> None:
        """
        Ouvre une représentation sur une intention.

        Args:
            intent: La demande, **conservée telle quelle**.
            intent_source: La modalité par laquelle elle est arrivée.
            representation_id: Son identité. Tirée au sort si absente.

        Raises:
            RepresentationRefused: Sur une intention vide, ou une modalité non
                déclarée.
        """
        if not str(intent or "").strip():
            raise RepresentationRefused(
                "Aucune intention. Une production sans intention ne peut être "
                "ni planifiée ni jugée — rien ne dirait si elle a réussi."
            )
        if intent_source not in MODALITES:
            raise RepresentationRefused(
                f"Modalité « {intent_source} » non déclarée. Déclarées : "
                f"{list(MODALITES)}."
            )

        self.representation_id = representation_id or f"crea-{uuid.uuid4().hex[:12]}"
        self.intent = intent.strip()
        self.intent_source = intent_source
        self.created_at = time.time()
        self._champs: Dict[str, Field] = {}
        self._entites: List[EntityRef] = []
        self._references: List[str] = []
        self._contraintes: List[str] = []

        for nom, question in CHAMPS_REQUIS.items():
            self._champs[nom] = Field(name=nom, question=question)

    # ------------------------------------------------------------------
    # Champs
    # ------------------------------------------------------------------

    def state(self, name: str, value: Any, source: str = "request") -> Field:
        """
        Pose un champ **demandé** par l'utilisateur.

        Args:
            name: Le champ.
            value: Ce qui a été demandé.
            source: D'où vient la demande.
        """
        champ = Field(name=name, value=value, provenance=DECLARE, source=source)
        self._champs[name] = champ
        return champ

    def infer(self, name: str, value: Any, source: str) -> Field:
        """
        Pose un champ **déduit**, en nommant ce qui l'a déduit.

        Args:
            name: Le champ.
            value: La valeur déduite.
            source: Le module ou la règle qui l'a produite. Obligatoire : une
                déduction anonyme est indiscernable d'une demande.
        """
        champ = Field(name=name, value=value, provenance=DEDUIT, source=source)
        self._champs[name] = champ
        return champ

    def field(self, name: str) -> Field:
        """
        Un champ, ou son absence **déclarée**.

        Un champ inconnu rend un `Field` `UNSPECIFIED` portant une question
        générique, jamais `None` : un appelant qui reçoit `None` finit par le
        traiter comme une valeur vide.
        """
        existant = self._champs.get(name)
        if existant is not None:
            return existant
        return Field(
            name=name,
            question=f"« {name} » n'a pas été posé, et rien ne le devine.",
        )

    @property
    def fields(self) -> Tuple[Field, ...]:
        """Tous les champs, triés par nom."""
        return tuple(self._champs[nom] for nom in sorted(self._champs))

    # ------------------------------------------------------------------
    # Entités et références
    # ------------------------------------------------------------------

    def add_entity(self, entity: EntityRef) -> EntityRef:
        """Ajoute une entité à la production."""
        self._entites.append(entity)
        return entity

    @property
    def entities(self) -> Tuple[EntityRef, ...]:
        """Les entités déclarées."""
        return tuple(self._entites)

    def attach_reference(self, reference: Any, use: str,
                         at_scope: str = "PROJECT") -> Dict[str, Any]:
        """
        Rattache une référence, **après avoir vérifié son consentement**.

        Args:
            reference: Une `ReferenceEntity`.
            use: L'usage sous lequel elle serait employée.
            at_scope: La portée de cet usage.

        Returns:
            La décision. Une référence refusée n'est pas rattachée, et la
            raison du refus est rendue telle quelle.

        Raises:
            RepresentationRefused: Si l'objet fourni ne sait pas répondre sur
                son propre consentement. Une référence qui ne peut pas être
                interrogée sur ce point ne peut pas être employée.
        """
        if not hasattr(reference, "usable"):
            raise RepresentationRefused(
                "Cet objet n'expose pas `usable()` : impossible de vérifier à "
                "quoi son sujet a consenti, donc impossible de l'employer."
            )
        verdict = reference.usable(use, at_scope)
        if verdict["allowed"]:
            self._references.append(reference.reference_id)
        return {"reference_id": reference.reference_id, **verdict}

    @property
    def references(self) -> Tuple[str, ...]:
        """Les références effectivement rattachées."""
        return tuple(self._references)

    def add_constraint(self, constraint: str) -> str:
        """Ajoute une contrainte de continuité ou de production."""
        self._contraintes.append(constraint)
        return constraint

    # ------------------------------------------------------------------
    # État
    # ------------------------------------------------------------------

    def clarifications(self) -> List[Dict[str, str]]:
        """
        Les questions ouvertes, dans l'ordre des champs.

        Returns:
            Une question par champ non posé. C'est la sortie utile d'une
            représentation incomplète : un plan complet appuyé sur des champs
            devinés se lit comme une décision prise.
        """
        return [
            {"field": champ.name, "question": champ.question}
            for champ in self.fields if not champ.known
        ]

    def ready(self) -> Dict[str, Any]:
        """
        Dit si la représentation est exécutable, et sinon ce qui manque.

        Returns:
            `READY` seulement quand tous les champs requis sont posés. Sinon
            `CLARIFICATION_REQUIRED` avec les questions — jamais un plan
            complété d'office.
        """
        questions = self.clarifications()
        return {
            "status": PRETE if not questions else CLARIFICATION_REQUISE,
            "clarifications": questions,
            "stated": [c.name for c in self.fields if c.provenance == DECLARE],
            "inferred": [c.name for c in self.fields if c.provenance == DEDUIT],
            "note": (
                "Exécutable : chaque champ requis a été posé."
                if not questions else
                f"{len(questions)} question(s) ouverte(s). Rien n'est deviné à "
                "la place de qui commande la production."
            ),
        }

    def as_dict(self) -> Dict[str, Any]:
        """
        La représentation complète, absences comprises.

        Les champs déduits sont listés **à part** des champs demandés : à la
        livraison, la différence entre ce que le client a dit et ce que la
        plateforme a supposé est la seule chose qui permette d'arbitrer.
        """
        return {
            "representation_id": self.representation_id,
            "intent": self.intent,
            "intent_source": self.intent_source,
            "created_at": self.created_at,
            "fields": [c.as_dict() for c in self.fields],
            "stated": [c.name for c in self.fields if c.provenance == DECLARE],
            "inferred": [c.name for c in self.fields if c.provenance == DEDUIT],
            "unspecified": [c.name for c in self.fields if not c.known],
            "entities": [e.as_dict() for e in self._entites],
            "references": list(self._references),
            "constraints": list(self._contraintes),
            "readiness": self.ready(),
        }


def from_request(text: str, source: str = "text") -> CreativeRepresentation:
    """
    Construit une représentation à partir d'une demande en langage naturel.

    Args:
        text: La demande.
        source: La modalité d'arrivée.

    Returns:
        La représentation, avec les champs que l'analyse a **réellement**
        trouvés dans la phrase et les autres restés ouverts.

        L'analyse vient de `src/media/tools/intent.py`, qui refuse déjà de
        compléter ce qui n'a pas été dit. Un second analyseur finirait par
        diverger du premier — et ce dépôt a payé quatre fois ce mode de
        défaillance.
    """
    from ..media.tools.intent import AMBIGU, NON_PRECISE as INTENT_NON_PRECISE
    from ..media.tools.intent import parse_request

    demande = parse_request(text)
    representation = CreativeRepresentation(intent=text, intent_source=source)

    if demande.domain not in (INTENT_NON_PRECISE, AMBIGU):
        representation.state("domain", demande.domain,
                             source="src/media/tools/intent.py")
    if demande.duration_seconds is not None:
        representation.state("duration_seconds", demande.duration_seconds,
                             source="src/media/tools/intent.py")
    if demande.aspect not in (INTENT_NON_PRECISE, AMBIGU):
        representation.state("aspect", demande.aspect,
                             source="src/media/tools/intent.py")
    if demande.language not in (INTENT_NON_PRECISE, AMBIGU):
        representation.state("language", demande.language,
                             source="src/media/tools/intent.py")
    for domaine in demande.source_domains:
        representation.add_constraint(f"matière d'origine : {domaine}")

    return representation


def representation_report() -> Dict[str, Any]:
    """
    Ce que la représentation garantit, et ce qu'elle refuse.

    Returns:
        Le vocabulaire déclaré et les règles tenues.
    """
    return {
        "provenances": list(PROVENANCES),
        "modalities": list(MODALITES),
        "required_fields": sorted(CHAMPS_REQUIS),
        "states": [PRETE, CLARIFICATION_REQUISE],
        "rules": [
            "Chaque champ sait **qui l'a posé**. Une durée demandée et une "
            "durée choisie par du code deviennent le même objet dès qu'on les "
            "passe à un générateur — et la livraison est alors jugée sur des "
            "contraintes que le client n'a jamais fixées.",
            "Un champ non posé porte sa **question**, jamais une valeur par "
            "défaut : un manque sans question se remplit tout seul.",
            "Une déduction **nomme sa source** ; une déduction anonyme est "
            "indiscernable d'une demande.",
            "Une représentation avec des questions ouvertes n'est **pas "
            "exécutable**.",
            "Une référence n'est rattachée qu'après vérification de son "
            "consentement, et un objet incapable de répondre là-dessus est "
            "refusé.",
            "L'analyse du langage naturel vient de `src/media/tools/intent.py` "
            "— un second analyseur divergerait du premier.",
        ],
        "does_not": [
            "Choisir une durée, un domaine ou un format à la place du demandeur.",
            "Confondre ce qui a été demandé avec ce qui a été déduit.",
            "Rattacher une référence sans vérifier son consentement.",
            "Réimplémenter l'analyse de la demande.",
        ],
    }
