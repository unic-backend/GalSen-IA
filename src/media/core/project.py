"""
A production that remembers every state it was ever in.

Directive §18 asks for a project manifest with versions, and ends on the rule
that gives the whole thing its shape: **never destroy previous versions.** That
sentence is easy to agree with and easy to break, because the natural way to
write an editor is to mutate the current state — and once a timeline is mutated
in place, the version that a client approved yesterday is gone.

So versions here are not a convenience. They are the storage model:

- **A version is frozen.** `ProjectVersion` is an immutable dataclass; there is
  no setter, no `update()`, and no method on the project that reaches into one.
  Producing a new state means appending a new version built from the previous
  one.
- **There is no delete.** Not a guarded delete, not a soft delete: the class has
  no method for it. A version can be marked `SUPERSEDED`, which is what
  `CurriculumRegistry` already does for published curriculum — same reasoning,
  different domain: an answer about last week must still find what was approved
  last week.
- **Identity and content are separate hashes.** `version_id` says *which state
  this is*; `content_hash` says *what it contains*. Darra J paid for conflating
  them once: re-importing an identical document looked like a different record.

Two further rules come straight from the directive.

**Generated content stays distinguishable from sourced content** (§31). Every
artifact declares its origin, and a sourced one carries licence and hash. The
manifest can never claim provenance it was not given — an artifact with no
source says so rather than defaulting to something reassuring.

**A user correction is recorded, not promoted** (§17). Corrections accumulate on
the project as evidence; turning one into a permanent rule is a separate,
deliberate act. A system that silently learns "the client always wants this"
from one correction will eventually apply it to a client who never asked.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

#: Marque portée par tout artefact produit par un modèle. Elle vit **dans**
#: l'objet et survit donc à la sérialisation, à la copie et au stockage — la
#: même précaution que `NON_OFFICIAL_TEST_DATA` dans Darra J.
ORIGINE_GENEREE = "AI_GENERATED"
ORIGINE_SOURCEE = "SOURCED"
ORIGINE_INCONNUE = "UNKNOWN_ORIGIN"

#: Les origines qu'un artefact peut déclarer.
ORIGINES = (ORIGINE_GENEREE, ORIGINE_SOURCEE, ORIGINE_INCONNUE)


class ProjectRefused(ValueError):
    """Une opération qui ferait perdre un état, ou en inventerait un."""


class VersionStatus(str, Enum):
    """
    Ce qu'une version est devenue.

    Aucun état ne signifie « supprimée ». Une version remplacée devient
    `SUPERSEDED` et reste lisible : une question sur ce qui a été approuvé la
    semaine dernière doit encore trouver ce qui a été approuvé la semaine
    dernière.
    """

    DRAFT = "DRAFT"
    RENDERED = "RENDERED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


#: Les états depuis lesquels une version peut encore devenir la version courante.
ETATS_VIVANTS = (VersionStatus.DRAFT, VersionStatus.RENDERED, VersionStatus.APPROVED)


@dataclass(frozen=True)
class Artifact:
    """
    Un média rattaché à une production, avec son origine.

    Attributes:
        artifact_id: Son identité.
        kind: `video`, `audio`, `image`, `font`, `music`, `sfx`…
        path: Où il se trouve.
        origin: `AI_GENERATED`, `SOURCED` ou `UNKNOWN_ORIGIN`.
        source: D'où il vient, pour un artefact sourcé.
        licence: Sous quelle licence, pour un artefact sourcé.
        sha256: Son empreinte, quand elle a été calculée.
        produced_by: Le modèle ou l'outil qui l'a produit, pour un généré.
    """

    artifact_id: str
    kind: str
    path: str = ""
    origin: str = ORIGINE_INCONNUE
    source: str = ""
    licence: str = ""
    sha256: str = ""
    produced_by: str = ""

    def __post_init__(self) -> None:
        if self.origin not in ORIGINES:
            raise ProjectRefused(
                f"Origine « {self.origin} » inconnue. Les origines déclarées "
                f"sont {ORIGINES} : en inventer une rendrait indistinguable ce "
                "qui a été généré de ce qui a été fourni."
            )

    @property
    def is_generated(self) -> bool:
        """Vrai pour un artefact produit par un modèle."""
        return self.origin == ORIGINE_GENEREE

    @property
    def provenance_complete(self) -> bool:
        """
        Vrai quand l'origine est justifiée par ce qu'elle exige.

        Un artefact sourcé sans source ni licence n'est pas « probablement
        libre » : il est **incomplet**, et le dire est la seule façon de ne pas
        fabriquer une provenance (§31).
        """
        if self.origin == ORIGINE_SOURCEE:
            return bool(self.source.strip() and self.licence.strip())
        if self.origin == ORIGINE_GENEREE:
            return bool(self.produced_by.strip())
        return False

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "artifact_id": self.artifact_id, "kind": self.kind,
            "path": self.path, "origin": self.origin, "source": self.source,
            "licence": self.licence, "sha256": self.sha256,
            "produced_by": self.produced_by,
            "provenance_complete": self.provenance_complete,
        }


@dataclass(frozen=True)
class Correction:
    """
    Ce qu'une personne a corrigé, conservé **sans** être promu en règle.

    Attributes:
        at: Quand.
        by: Qui.
        target: Ce qui a été corrigé — une scène, un plan, un sous-titre.
        before: L'état d'avant.
        after: L'état voulu.
        note: Ce que la personne a dit.
    """

    at: float
    by: str
    target: str
    before: str = ""
    after: str = ""
    note: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "at": self.at, "by": self.by, "target": self.target,
            "before": self.before, "after": self.after, "note": self.note,
            "promoted_to_rule": False,
            "why": (
                "Une correction est une **preuve**, pas une règle. La promouvoir "
                "demande un acte délibéré : apprendre en silence « le client "
                "veut toujours ceci » finit par l'appliquer à un client qui ne "
                "l'a jamais demandé."
            ),
        }


@dataclass(frozen=True)
class ProjectVersion:
    """
    Un état complet d'une production, figé.

    Il n'existe aucun moyen de modifier une version. Produire un nouvel état
    consiste à en **ajouter** une, construite à partir de celle-ci.

    Attributes:
        version_id: Son identité, stable.
        number: Son rang, à partir de 1.
        status: Où elle en est.
        objective: Ce que la production doit accomplir.
        script: Le texte, quand il existe.
        scenes: Les scènes planifiées.
        timeline: La timeline calculée.
        artifacts: Les médias rattachés.
        models: Les modèles employés, par rôle.
        prompts: Les invites employées, par rôle.
        quality_checks: Les résultats de contrôle qualité.
        outputs: Les fichiers produits.
        created_at: Quand elle a été créée.
        created_by: Qui l'a créée.
        derived_from: La version dont elle est issue.
    """

    version_id: str
    number: int
    status: VersionStatus = VersionStatus.DRAFT
    objective: str = ""
    script: str = ""
    scenes: Tuple[Dict[str, Any], ...] = ()
    timeline: Tuple[Dict[str, Any], ...] = ()
    artifacts: Tuple[Artifact, ...] = ()
    models: Dict[str, str] = field(default_factory=dict)
    prompts: Dict[str, str] = field(default_factory=dict)
    quality_checks: Tuple[Dict[str, Any], ...] = ()
    outputs: Tuple[str, ...] = ()
    created_at: float = 0.0
    created_by: str = ""
    derived_from: str = ""

    def content_hash(self) -> str:
        """
        L'empreinte de ce que la version **contient**.

        Distincte de `version_id` : l'identité dit *quel état c'est*, l'empreinte
        dit *ce qu'il y a dedans*. Deux versions au contenu identique doivent se
        reconnaître, ce qui permet de dire « rien n'a changé » sans comparer les
        objets.

        `created_at` et `created_by` n'y entrent pas : deux enregistrements du
        même contenu à deux instants sont le même contenu. Darra J a payé cette
        confusion une fois.
        """
        graine = json.dumps({
            "objective": self.objective,
            "script": self.script,
            "scenes": list(self.scenes),
            "timeline": list(self.timeline),
            "artifacts": [a.as_dict() for a in self.artifacts],
            "models": dict(sorted(self.models.items())),
            "prompts": dict(sorted(self.prompts.items())),
            "outputs": list(self.outputs),
        }, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(graine.encode("utf-8")).hexdigest()

    @property
    def generated_artifacts(self) -> Tuple[Artifact, ...]:
        """Les artefacts produits par un modèle."""
        return tuple(a for a in self.artifacts if a.is_generated)

    @property
    def artifacts_without_provenance(self) -> Tuple[Artifact, ...]:
        """
        Les artefacts dont l'origine n'est pas justifiée.

        Rendus séparément parce qu'ils bloquent une livraison : une production
        qui sort avec un média dont personne ne sait d'où il vient est un
        problème juridique avant d'être un problème technique.
        """
        return tuple(a for a in self.artifacts if not a.provenance_complete)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, avec l'empreinte de contenu."""
        return {
            "version_id": self.version_id,
            "number": self.number,
            "status": self.status.value,
            "objective": self.objective,
            "script": self.script,
            "scenes": list(self.scenes),
            "timeline": list(self.timeline),
            "artifacts": [a.as_dict() for a in self.artifacts],
            "models": dict(self.models),
            "prompts": dict(self.prompts),
            "quality_checks": list(self.quality_checks),
            "outputs": list(self.outputs),
            "created_at": self.created_at,
            "created_by": self.created_by,
            "derived_from": self.derived_from,
            "content_hash": self.content_hash(),
        }


class MediaProject:
    """
    Une production, et toutes les versions par lesquelles elle est passée.

    La classe n'expose **aucune** suppression. Ce n'est pas une omission : une
    suppression gardée finit toujours par être appelée avec le bon argument.
    """

    def __init__(
        self, objective: str, project_id: str = "", created_by: str = "",
    ) -> None:
        """
        Ouvre une production sur un objectif.

        Args:
            objective: Ce que la production doit accomplir.
            project_id: Son identité. Tirée au sort si absente.
            created_by: Qui l'ouvre.

        Raises:
            ProjectRefused: Sans objectif. Une production sans objectif ne peut
                être ni planifiée ni jugée : rien ne dirait si elle a réussi.
        """
        if not str(objective or "").strip():
            raise ProjectRefused(
                "Aucun objectif. Une production sans objectif ne peut être ni "
                "planifiée ni jugée — rien ne dirait si elle a réussi."
            )

        self._verrou = threading.RLock()
        self.project_id = project_id or f"prj-{uuid.uuid4().hex[:12]}"
        self.objective = objective.strip()
        self.created_at = time.time()
        self.created_by = created_by
        self._versions: List[ProjectVersion] = []
        self._corrections: List[Correction] = []
        self._journal: List[Dict[str, Any]] = []

        self._ajouter(ProjectVersion(
            version_id=f"{self.project_id}-v1",
            number=1,
            objective=self.objective,
            created_at=self.created_at,
            created_by=created_by,
        ))

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------

    def _ajouter(self, version: ProjectVersion) -> ProjectVersion:
        """Ajoute une version et consigne l'écriture."""
        self._versions.append(version)
        self._journal.append({
            "at": time.time(), "action": "version_added",
            "version_id": version.version_id, "number": version.number,
        })
        return version

    @property
    def versions(self) -> Tuple[ProjectVersion, ...]:
        """Toutes les versions, dans l'ordre où elles ont été créées."""
        with self._verrou:
            return tuple(self._versions)

    @property
    def current(self) -> ProjectVersion:
        """
        La version courante : la dernière qui n'a pas été remplacée ou rejetée.

        Returns:
            La plus récente encore vivante, ou la dernière créée si toutes ont
            été retirées — parce qu'il doit toujours exister quelque chose à
            regarder, même quand tout a été rejeté.
        """
        with self._verrou:
            vivantes = [v for v in self._versions if v.status in ETATS_VIVANTS]
            return vivantes[-1] if vivantes else self._versions[-1]

    def get_version(self, version_id: str) -> Optional[ProjectVersion]:
        """Une version par son identité, quel que soit son état."""
        with self._verrou:
            for version in self._versions:
                if version.version_id == version_id:
                    return version
        return None

    def new_version(
        self, created_by: str = "", supersede: bool = True, **changes: Any,
    ) -> ProjectVersion:
        """
        Ajoute une version, construite à partir de la courante.

        Args:
            created_by: Qui la crée.
            supersede: Si la version d'origine devient `SUPERSEDED`. Elle reste
                lisible dans tous les cas — « remplacée » n'est pas « effacée ».
            **changes: Les champs qui changent.

        Returns:
            La nouvelle version.

        Raises:
            ProjectRefused: Pour un champ inconnu. L'ignorer silencieusement
                ferait croire qu'une modification a été prise en compte.
        """
        with self._verrou:
            base = self.current
            interdits = {"version_id", "number", "created_at", "derived_from"}
            inconnus = [
                nom for nom in changes
                if nom in interdits or not hasattr(base, nom)
            ]
            if inconnus:
                raise ProjectRefused(
                    f"Champs non modifiables ou inconnus : {sorted(inconnus)}. "
                    "Les ignorer ferait croire qu'une modification a été prise "
                    "en compte."
                )

            numero = len(self._versions) + 1
            nouvelle = replace(
                base,
                version_id=f"{self.project_id}-v{numero}",
                number=numero,
                created_at=time.time(),
                created_by=created_by,
                derived_from=base.version_id,
                **changes,
            )
            if supersede and base.status in ETATS_VIVANTS:
                self._remplacer(base, VersionStatus.SUPERSEDED)
            return self._ajouter(nouvelle)

    def set_status(
        self, version_id: str, status: VersionStatus, by: str = "",
    ) -> ProjectVersion:
        """
        Change l'état d'une version **en la remplaçant**, jamais en la mutant.

        Args:
            version_id: La version.
            status: Son nouvel état.
            by: Qui décide.

        Returns:
            La version portant le nouvel état.

        Raises:
            ProjectRefused: Si la version est inconnue, ou si l'on tente
                d'approuver une version déjà remplacée — approuver un état que
                quelqu'un a dépassé publierait autre chose que ce qui a été vu.
        """
        with self._verrou:
            version = self.get_version(version_id)
            if version is None:
                raise ProjectRefused(f"Version « {version_id} » inconnue.")
            if (version.status is VersionStatus.SUPERSEDED
                    and status is VersionStatus.APPROVED):
                raise ProjectRefused(
                    "Cette version a été remplacée. L'approuver publierait un "
                    "état que quelqu'un a déjà dépassé."
                )
            return self._remplacer(version, status, by)

    def _remplacer(
        self, version: ProjectVersion, status: VersionStatus, by: str = "",
    ) -> ProjectVersion:
        """
        Réécrit l'entrée d'une version avec un nouvel état.

        Le contenu, lui, n'est jamais touché : `content_hash()` est identique
        avant et après. Un changement d'état n'est pas un changement d'œuvre.
        """
        index = self._versions.index(version)
        remplacee = replace(version, status=status)
        self._versions[index] = remplacee
        self._journal.append({
            "at": time.time(), "action": "status_changed",
            "version_id": version.version_id,
            "from": version.status.value, "to": status.value, "by": by,
        })
        return remplacee

    # ------------------------------------------------------------------
    # Corrections
    # ------------------------------------------------------------------

    def record_correction(
        self, by: str, target: str, before: str = "", after: str = "",
        note: str = "",
    ) -> Correction:
        """
        Consigne une correction humaine, sans en tirer de règle.

        Args:
            by: Qui corrige.
            target: Ce qui est corrigé.
            before: L'état d'avant.
            after: L'état voulu.
            note: Ce que la personne a dit.

        Returns:
            La correction consignée.

        Raises:
            ProjectRefused: Sans auteur. Une correction anonyme ne peut être ni
                discutée ni retirée.
        """
        if not str(by or "").strip():
            raise ProjectRefused(
                "Correction sans auteur : elle ne pourrait être ni discutée ni "
                "retirée."
            )
        correction = Correction(
            at=time.time(), by=by, target=target, before=before, after=after,
            note=note,
        )
        with self._verrou:
            self._corrections.append(correction)
        return correction

    @property
    def corrections(self) -> Tuple[Correction, ...]:
        """Les corrections consignées, dans l'ordre."""
        with self._verrou:
            return tuple(self._corrections)

    # ------------------------------------------------------------------
    # Manifeste
    # ------------------------------------------------------------------

    def manifest(self) -> Dict[str, Any]:
        """
        Le manifeste complet de la production (§18).

        Returns:
            L'objectif, toutes les versions, les corrections, et ce qui bloque
            une livraison. Aucune version n'est omise : un manifeste qui ne
            montre que l'état courant ne permet pas de revenir en arrière.
        """
        with self._verrou:
            courante = self.current
            return {
                "project_id": self.project_id,
                "objective": self.objective,
                "created_at": self.created_at,
                "created_by": self.created_by,
                "current_version": courante.version_id,
                "version_count": len(self._versions),
                "versions": [v.as_dict() for v in self._versions],
                "corrections": [c.as_dict() for c in self._corrections],
                "artifacts_without_provenance": [
                    a.as_dict() for a in courante.artifacts_without_provenance
                ],
                "generated_artifacts": [
                    a.artifact_id for a in courante.generated_artifacts
                ],
                "history": list(self._journal),
                "note": (
                    "Aucune version n'est jamais détruite. Une version "
                    "remplacée devient `SUPERSEDED` et reste lisible : une "
                    "question sur ce qui a été approuvé la semaine dernière "
                    "doit encore trouver ce qui a été approuvé la semaine "
                    "dernière."
                ),
            }


def project_report() -> Dict[str, Any]:
    """
    Ce que le noyau de projet garantit, et ce qu'il refuse.

    Returns:
        Les états, les origines, et les règles tenues.
    """
    return {
        "version_states": [etat.value for etat in VersionStatus],
        "living_states": [etat.value for etat in ETATS_VIVANTS],
        "origins": list(ORIGINES),
        "rules": [
            "Aucune suppression n'existe : la classe n'a pas de méthode pour "
            "ça. Une suppression gardée finit toujours par être appelée avec "
            "le bon argument.",
            "Une version est **figée** : produire un nouvel état consiste à en "
            "ajouter une, jamais à modifier celle d'avant.",
            "Identité et contenu sont deux empreintes : `version_id` dit quel "
            "état c'est, `content_hash` dit ce qu'il contient.",
            "Un changement d'état ne change pas le contenu — l'empreinte est "
            "identique avant et après.",
            "Un artefact déclare son origine ; un artefact sourcé sans source "
            "ni licence est **incomplet**, jamais « probablement libre ».",
            "Une correction est une preuve, pas une règle : la promouvoir "
            "demande un acte délibéré.",
        ],
        "does_not": [
            "Supprimer une version, même remplacée.",
            "Modifier une version existante.",
            "Approuver une version déjà remplacée.",
            "Deviner la provenance d'un artefact.",
            "Transformer une correction en règle permanente toute seule.",
        ],
    }
