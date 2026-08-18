"""
A reference entity: what was observed, from where, and how well.

Directive §9 forbids reducing a reference to one embedding, and the reason
becomes obvious the moment you try. Three photos of someone, all frontal: the
face is well observed, the back of the head was never seen. An embedding cannot
say that. It produces a vector of the same shape either way, and everything
downstream treats the invented half exactly like the observed half — which is
how a generated back-of-head becomes indistinguishable from a photographed one.

So an observation here carries **its own evidence**: what was measured, by what,
from which source media, and with what confidence. A field nobody observed is
`ABSENT` and stays `ABSENT`. §10 says it plainly: *do not fabricate hidden
geometry.*

Two structural refusals, both from ADR-025:

- **There is no delete method.** A revoked reference becomes `REVOKED` and keeps
  its record. `src/media/core/project.py` made the same choice for the same
  reason: a guarded delete eventually gets called with the right argument.
- **A reference with no consent scope cannot be used.** Not guarded, not
  warned — `usable()` returns the refusal and names what is missing.

The entity type is open (§6): human, animal, vehicle, product, robot, creature,
2D, 3D, environment. §4 is explicit that the examples in the directive are test
scenarios, not architectural limits, and an architecture that assumes references
are people has to be rebuilt the first time someone uploads their shop.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .consent import ACTIF, EXPIRE, REVOQUE, ConsentScope, Revocation, authorize

#: Les types d'entité déclarés (§6). La liste est ouverte par conception : un
#: type inconnu est refusé pour être **ajouté ici**, pas deviné à l'usage.
TYPES_D_ENTITE = (
    "human", "animal", "vehicle", "product", "object", "robot",
    "creature", "character_2d", "character_3d", "environment", "other",
)

#: D'où vient la valeur d'un champ. `AI_DERIVED` existe pour que ce qu'un
#: modèle a proposé ne se confonde jamais avec ce qu'on a mesuré.
MESURE = "MEASURED"
DERIVE = "AI_DERIVED"
DECLARE = "DECLARED"
ABSENT = "ABSENT"
ORIGINES = (MESURE, DERIVE, DECLARE, ABSENT)

#: Ce qu'un fournisseur sait faire d'un champ (§9).
SUPPORTE = "SUPPORTED"
PARTIEL = "PARTIAL"
INCONNU = "UNKNOWN"
NON_SUPPORTE = "UNSUPPORTED"
STATUTS_DE_CAPACITE = (SUPPORTE, PARTIEL, INCONNU, NON_SUPPORTE)

#: Les genres de média source acceptés.
GENRES_DE_MEDIA = ("image", "video", "audio")


class ReferenceRefused(ValueError):
    """Une référence impossible à déclarer ou à employer telle quelle."""


@dataclass(frozen=True)
class SourceMedium:
    """
    Un média fourni, et son empreinte.

    Attributes:
        medium_id: Son identité.
        kind: `image`, `video` ou `audio`.
        path: Où il se trouve.
        sha256: Son empreinte. **Obligatoire** : sans elle, « supprimez le
            fichier que j'ai envoyé » ne peut pas être tenu à travers les
            copies.
        uploaded_by: Qui l'a fourni.
        uploaded_on: Quand.
        analysed: Si une analyse a été menée.
        analysis_status: Ce que l'analyse a donné, ou pourquoi elle n'a pas eu
            lieu.
    """

    medium_id: str
    kind: str
    path: str
    sha256: str
    uploaded_by: str = ""
    uploaded_on: float = field(default_factory=time.time)
    analysed: bool = False
    analysis_status: str = ""

    def __post_init__(self) -> None:
        if self.kind not in GENRES_DE_MEDIA:
            raise ReferenceRefused(
                f"Genre « {self.kind} » non déclaré. Déclarés : "
                f"{list(GENRES_DE_MEDIA)}."
            )
        if not str(self.sha256 or "").strip():
            raise ReferenceRefused(
                f"« {self.path} » sans empreinte. Sans elle, une suppression "
                "demandée ne peut pas être suivie à travers les copies, et la "
                "promesse faite à la personne serait invérifiable."
            )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "medium_id": self.medium_id, "kind": self.kind, "path": self.path,
            "sha256": self.sha256, "uploaded_by": self.uploaded_by,
            "uploaded_on": self.uploaded_on, "analysed": self.analysed,
            "analysis_status": self.analysis_status,
        }


@dataclass(frozen=True)
class Observation:
    """
    Ce qui a été constaté sur un champ, avec sa preuve.

    Attributes:
        field_name: Le champ observé — `dominant_colours`, `dimensions`…
        value: Ce qui a été constaté. `None` quand rien ne l'a été.
        origin: D'où vient la valeur, parmi `ORIGINES`.
        measured_by: **Obligatoire** pour une valeur `MEASURED` : sans l'outil
            nommé, un chiffre n'est pas une mesure.
        observed_from: Les médias sources qui l'ont fourni.
        confidence: De 0 à 1, quand elle a un sens.
        reason: Pourquoi le champ est absent, le cas échéant.
    """

    field_name: str
    value: Any = None
    origin: str = ABSENT
    measured_by: str = ""
    observed_from: Tuple[str, ...] = ()
    confidence: Optional[float] = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.origin not in ORIGINES:
            raise ReferenceRefused(
                f"Origine « {self.origin} » non déclarée. Déclarées : "
                f"{list(ORIGINES)} — ce qu'un modèle a proposé ne doit jamais "
                "se confondre avec ce qu'on a mesuré."
            )
        if self.origin == MESURE and not str(self.measured_by or "").strip():
            raise ReferenceRefused(
                f"« {self.field_name} » est déclaré MEASURED sans outil de "
                "mesure. Un chiffre dont personne ne sait comment il a été "
                "obtenu n'est pas une mesure."
            )
        if self.origin == ABSENT and self.value is not None:
            raise ReferenceRefused(
                f"« {self.field_name} » porte une valeur alors qu'il est "
                "déclaré ABSENT. L'un des deux est faux."
            )
        if self.origin == ABSENT and not str(self.reason or "").strip():
            raise ReferenceRefused(
                f"« {self.field_name} » est absent sans raison. « Pas observé » "
                "et « observé et vide » appellent des actions différentes."
            )
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ReferenceRefused(
                f"Confiance {self.confidence} hors de [0, 1]."
            )

    @property
    def is_evidence(self) -> bool:
        """Vrai quand la valeur vient d'une mesure ou d'une déclaration humaine."""
        return self.origin in (MESURE, DECLARE)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "field": self.field_name, "value": self.value,
            "origin": self.origin, "measured_by": self.measured_by,
            "observed_from": list(self.observed_from),
            "confidence": self.confidence, "reason": self.reason,
        }


class ReferenceEntity:
    """
    Une référence réutilisable : ce qu'elle est, ce qu'on en sait, ce qu'on peut
    en faire.

    **Aucune méthode ne supprime.** Une référence révoquée passe à `REVOKED` et
    garde son registre : une suppression gardée finit par être appelée avec le
    bon argument, et effacer la trace d'une décision de confidentialité détruit
    la preuve qu'elle a été honorée.
    """

    def __init__(
        self, entity_type: str, reference_id: str = "",
        consent: Optional[ConsentScope] = None, created_by: str = "",
    ) -> None:
        """
        Déclare une référence.

        Args:
            entity_type: Un type parmi `TYPES_D_ENTITE`.
            reference_id: Son identité. Tirée au sort si absente.
            consent: La portée du consentement. `None` = **inutilisable**.
            created_by: Qui l'a déclarée.

        Raises:
            ReferenceRefused: Sur un type non déclaré. Une référence dont le
                type est deviné se retrouve conditionnée comme une personne
                alors que c'est une boutique.
        """
        if entity_type not in TYPES_D_ENTITE:
            raise ReferenceRefused(
                f"Type « {entity_type} » non déclaré. Déclarés : "
                f"{list(TYPES_D_ENTITE)}. Le deviner ferait traiter une "
                "boutique comme une personne."
            )
        self._verrou = threading.RLock()
        self.reference_id = reference_id or f"ref-{uuid.uuid4().hex[:12]}"
        self.entity_type = entity_type
        self.created_by = created_by
        self.created_at = time.time()
        self._consent = consent
        self._state = ACTIF
        self._revocation: Optional[Revocation] = None
        self._media: List[SourceMedium] = []
        self._observations: Dict[str, Observation] = {}
        self._versions: List[Dict[str, Any]] = []
        self._journal: List[Dict[str, Any]] = []
        self._consigner("created", entity_type=entity_type)

    # ------------------------------------------------------------------
    # Registre interne
    # ------------------------------------------------------------------

    def _consigner(self, action: str, **detail: Any) -> None:
        """Consigne un acte. Le journal n'est jamais purgé."""
        self._journal.append({"at": time.time(), "action": action, **detail})

    @property
    def state(self) -> str:
        """L'état courant : `ACTIVE`, `REVOKED` ou `EXPIRED`."""
        with self._verrou:
            if self._state == ACTIF and self._consent is not None \
                    and self._consent.expired():
                return EXPIRE
            return self._state

    @property
    def consent(self) -> Optional[ConsentScope]:
        """La portée accordée, ou `None` quand aucune ne l'a été."""
        return self._consent

    @property
    def journal(self) -> Tuple[Dict[str, Any], ...]:
        """Tout ce qui a été fait à cette référence, dans l'ordre."""
        with self._verrou:
            return tuple(self._journal)

    # ------------------------------------------------------------------
    # Médias et observations
    # ------------------------------------------------------------------

    def add_medium(self, medium: SourceMedium) -> SourceMedium:
        """
        Rattache un média source.

        Raises:
            ReferenceRefused: Sur une référence révoquée — lui ajouter de la
                matière après un retrait de consentement la contredirait.
        """
        with self._verrou:
            if self.state == REVOQUE:
                raise ReferenceRefused(
                    f"« {self.reference_id} » est révoquée : on ne lui ajoute "
                    "pas de matière après un retrait de consentement."
                )
            self._media.append(medium)
            self._consigner("medium_added", medium_id=medium.medium_id,
                            kind=medium.kind, sha256=medium.sha256)
            return medium

    @property
    def media(self) -> Tuple[SourceMedium, ...]:
        """Les médias rattachés."""
        with self._verrou:
            return tuple(self._media)

    def observe(self, observation: Observation) -> Observation:
        """
        Enregistre une observation sur un champ.

        Une deuxième observation du même champ **remplace** la précédente et la
        version antérieure est conservée : une référence apprend, et ce qu'elle
        croyait avant reste consultable.
        """
        with self._verrou:
            ancienne = self._observations.get(observation.field_name)
            if ancienne is not None:
                self._versions.append({
                    "at": time.time(), "field": observation.field_name,
                    "superseded": ancienne.as_dict(),
                })
            self._observations[observation.field_name] = observation
            self._consigner("observed", field=observation.field_name,
                            origin=observation.origin)
            return observation

    def observation(self, field_name: str) -> Observation:
        """
        L'observation d'un champ, ou une absence **déclarée**.

        Un champ jamais observé rend une `Observation` `ABSENT` avec sa raison,
        et non `None` : un appelant qui reçoit `None` finit par le traiter comme
        une valeur vide, ce qui est une autre affirmation.
        """
        with self._verrou:
            existante = self._observations.get(field_name)
            if existante is not None:
                return existante
        return Observation(
            field_name=field_name, origin=ABSENT,
            reason=("Jamais observé sur cette référence. Ce n'est pas une "
                    "valeur vide : personne n'a regardé."),
        )

    @property
    def observations(self) -> Tuple[Observation, ...]:
        """Toutes les observations, triées par champ."""
        with self._verrou:
            return tuple(self._observations[c]
                         for c in sorted(self._observations))

    @property
    def versions(self) -> Tuple[Dict[str, Any], ...]:
        """Les observations remplacées, dans l'ordre où elles l'ont été."""
        with self._verrou:
            return tuple(self._versions)

    # ------------------------------------------------------------------
    # Consentement
    # ------------------------------------------------------------------

    def grant(self, consent: ConsentScope) -> ConsentScope:
        """
        Attache ou remplace la portée du consentement.

        Raises:
            ReferenceRefused: Sur une référence révoquée. Un consentement
                retiré ne se réaccorde pas en écrivant par-dessus : c'est une
                nouvelle référence, avec un nouvel accord.
        """
        with self._verrou:
            if self._state == REVOQUE:
                raise ReferenceRefused(
                    f"« {self.reference_id} » a été révoquée. Réaccorder par "
                    "écrasement effacerait le retrait ; il faut une nouvelle "
                    "référence et un nouvel accord."
                )
            self._consent = consent
            self._consigner("consent_granted", granted_by=consent.granted_by,
                            scope=consent.scope,
                            uses=list(consent.permitted_uses))
            return consent

    def revoke(self, by: str, reason: str = "",
               derived: Tuple[str, ...] = ()) -> Revocation:
        """
        Retire le consentement. **Terminal pour l'usage.**

        Args:
            by: Qui retire.
            reason: Pourquoi, si la personne le dit.
            derived: Les artefacts connus comme dérivant de cette référence.

        Returns:
            La révocation, conservée pour toujours. Les artefacts dérivés sont
            **nommés** : sans cette liste, « supprimez ma référence » ne peut
            pas être tenu, puisque rien ne dirait ce qui en descend.
        """
        with self._verrou:
            revocation = Revocation(revoked_by=by, reason=reason,
                                    propagated_to=tuple(derived))
            self._state = REVOQUE
            self._revocation = revocation
            self._consigner("revoked", by=by, reason=reason,
                            propagated_to=list(derived))
            return revocation

    @property
    def revocation(self) -> Optional[Revocation]:
        """La révocation, si elle a eu lieu."""
        return self._revocation

    def usable(self, use: str, at_scope: str = "PROJECT") -> Dict[str, Any]:
        """
        Dit si la référence peut servir à cet usage, et sinon pourquoi.

        Args:
            use: L'usage demandé.
            at_scope: La portée où il aurait lieu.

        Returns:
            L'autorisation et sa raison. C'est le seul point d'entrée : rien
            d'autre ne décide, et un appelant qui ne passe pas par là contourne
            le consentement de quelqu'un.
        """
        return authorize(self._consent, use, at_scope, self.state)

    # ------------------------------------------------------------------
    # Rapport
    # ------------------------------------------------------------------

    def manifest(self) -> Dict[str, Any]:
        """
        Tout ce qu'on sait de la référence, absences comprises.

        Returns:
            Le type, l'état, le consentement, les médias, les observations et
            les champs **jamais observés**. Ces derniers sont la partie utile :
            un manifeste qui ne montre que ce qui est rempli laisse croire que
            le reste n'existe pas.
        """
        with self._verrou:
            observees = [o for o in self._observations.values()
                         if o.is_evidence]
            derivees = [o for o in self._observations.values()
                        if o.origin == DERIVE]
            return {
                "reference_id": self.reference_id,
                "entity_type": self.entity_type,
                "state": self.state,
                "created_by": self.created_by,
                "created_at": self.created_at,
                "consent": self._consent.as_dict() if self._consent else None,
                "consent_note": (
                    None if self._consent else
                    "Aucun consentement : la référence est **inutilisable**. "
                    "L'absence de portée est l'absence de permission."
                ),
                "revocation": (self._revocation.as_dict()
                               if self._revocation else None),
                "media": [m.as_dict() for m in self._media],
                "observations": [o.as_dict() for o in self.observations],
                "measured_fields": sorted(o.field_name for o in observees),
                "ai_derived_fields": sorted(o.field_name for o in derivees),
                "superseded": list(self._versions),
                "journal": list(self._journal),
                "note": (
                    "Les champs dérivés d'un modèle sont listés séparément des "
                    "champs mesurés. Les confondre ferait passer une "
                    "proposition pour une observation."
                ),
            }


def file_digest(path: str) -> str:
    """
    L'empreinte SHA-256 d'un fichier.

    Args:
        path: Le fichier à empreindre.

    Returns:
        L'empreinte hexadécimale.

    Raises:
        ReferenceRefused: Si le fichier n'existe pas. Une empreinte de rien
            serait une empreinte valide de la chaîne vide, et deux fichiers
            absents se ressembleraient parfaitement.
    """
    if not os.path.isfile(path):
        raise ReferenceRefused(
            f"« {path} » n'existe pas. L'empreinte de rien vaut celle de la "
            "chaîne vide, et deux absences se ressembleraient parfaitement."
        )
    empreinte = hashlib.sha256()
    with open(path, "rb") as fichier:
        for bloc in iter(lambda: fichier.read(65536), b""):
            empreinte.update(bloc)
    return empreinte.hexdigest()


def reference_report() -> Dict[str, Any]:
    """
    Ce que la référence garantit, et ce qu'elle refuse.

    Returns:
        Le vocabulaire déclaré et les règles tenues.
    """
    return {
        "entity_types": list(TYPES_D_ENTITE),
        "origins": list(ORIGINES),
        "capability_statuses": list(STATUTS_DE_CAPACITE),
        "rules": [
            "Une référence n'est **pas un vecteur** : chaque champ porte son "
            "origine, son outil de mesure et les médias qui l'ont fourni. Un "
            "plongement rend la même forme qu'on ait vu la nuque ou non.",
            "Un champ jamais observé rend une absence **déclarée**, jamais "
            "`None` : un appelant qui reçoit `None` finit par le lire comme "
            "une valeur vide.",
            "Une valeur `MEASURED` nomme son outil ; sans lui, ce n'est pas "
            "une mesure.",
            "Ce qu'un modèle a proposé est `AI_DERIVED` et listé à part : le "
            "confondre avec une observation ferait générer une nuque et la "
            "présenter comme photographiée.",
            "**Aucune méthode ne supprime.** Une référence révoquée garde son "
            "registre, et la révocation nomme ce qui en dérive.",
            "Le type d'entité est ouvert : une architecture qui suppose que "
            "les références sont des personnes se refait au premier magasin.",
        ],
        "does_not": [
            "Fabriquer une géométrie qu'on n'a pas vue.",
            "Utiliser une référence sans portée de consentement.",
            "Effacer une révocation.",
            "Réaccorder un consentement retiré par écrasement.",
        ],
    }
