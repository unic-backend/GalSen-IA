"""
The curriculum as an institutional record, not as something a model remembers.

One sentence decides the shape of this module: **GalSen IA does not define the
curriculum.** A ministry does. So a curriculum object here is not knowledge the
platform produced — it is a record the platform received, and everything about
it is built to make that distinction impossible to blur:

- **Objects are frozen.** A canonical unit cannot be edited after creation. A
  correction is a *new version*, published by an authority, with its own dates
  and its own hash. Mutating one in place would leave no trace that the official
  text ever said something else.
- **Nothing exists without provenance.** No authority, no source document, no
  hash — no object. This is the same rule `entities.py` already applies to
  knowledge fragments, narrowed: for curriculum, only an official tier counts.
- **Identity is deterministic.** `unit_id` is derived from the dimensions that
  define the unit — version, grade, subject, period. Two imports of the same
  official record produce the same identifier, which is what makes the
  cross-user consistency guarantee (directive VI) testable rather than hoped for.
- **Test data says so.** A fixture carries `NON_OFFICIAL_TEST_DATA` in its
  authority, and `is_official()` returns False for it. Engineering needs
  fixtures; nobody needs a fixture that can pass for a ministry document.

What this module deliberately does **not** contain: any Senegalese curriculum
content. The structure is here; the content arrives when an authority provides
it. `docs/darra-j/integration-map.md` states the expected honest end state —
*architecture ready, official curriculum data pending*.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

#: Ce qu'une autorité de test écrit dans son nom. Un objet qui le porte n'est
#: **jamais** officiel, quoi qu'il déclare par ailleurs.
MARQUE_TEST = "NON_OFFICIAL_TEST_DATA"


class CurriculumStatus(str, Enum):
    """
    Où en est une version de curriculum.

    Reprend la machine d'états de `src/acquisition/record.py` — laquelle exige
    déjà une décision **humaine** pour sortir de `PARSED` — et ajoute les deux
    états que seul un curriculum a : publié, et remplacé.

    `SUPERSEDED` ne veut pas dire supprimé. Une version remplacée reste
    interrogeable : une question sur une année scolaire passée doit rendre le
    curriculum de cette année-là, pas celui d'aujourd'hui.
    """

    INGESTED = "INGESTED"
    PARSED = "PARSED"
    VALIDATION_REQUIRED = "VALIDATION_REQUIRED"
    VALIDATED = "VALIDATED"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


#: Les seuls états dans lesquels un objet peut répondre comme **fait officiel**.
#: `VALIDATED` n'y est pas : validé veut dire « quelqu'un a relu », publié veut
#: dire « l'autorité l'a mis en vigueur ».
ETATS_CANONIQUES = frozenset({CurriculumStatus.PUBLISHED, CurriculumStatus.SUPERSEDED})

#: Transitions permises. Une version publiée ne redevient pas brouillon : elle
#: est remplacée par une autre, ce qui laisse les deux lisibles.
TRANSITIONS: Dict[CurriculumStatus, frozenset] = {
    CurriculumStatus.INGESTED: frozenset({
        CurriculumStatus.PARSED, CurriculumStatus.REJECTED,
    }),
    CurriculumStatus.PARSED: frozenset({
        CurriculumStatus.VALIDATION_REQUIRED, CurriculumStatus.REJECTED,
    }),
    CurriculumStatus.VALIDATION_REQUIRED: frozenset({
        CurriculumStatus.VALIDATED, CurriculumStatus.REJECTED,
    }),
    CurriculumStatus.VALIDATED: frozenset({
        CurriculumStatus.PUBLISHED, CurriculumStatus.REJECTED,
    }),
    CurriculumStatus.PUBLISHED: frozenset({CurriculumStatus.SUPERSEDED}),
    CurriculumStatus.SUPERSEDED: frozenset(),
    CurriculumStatus.REJECTED: frozenset(),
}


class CanonicalRefused(ValueError):
    """
    Un objet canonique qui ne peut pas exister tel qu'il est décrit.

    Levée, jamais rendue en valeur : un objet canonique à moitié valide est
    exactement ce que ce module existe pour empêcher.
    """


@dataclass(frozen=True)
class Provenance:
    """
    D'où vient ce fait, et comment on peut le retrouver.

    Attributes:
        authority: L'autorité qui publie — un ministère, une institution.
        source_tier: Le rang de la source, au sens de `SourceTier`.
        source_document: L'identifiant ou l'URL du document officiel.
        document_title: Son titre.
        document_hash: L'empreinte du document source.
        publication_date: Quand l'autorité l'a publié (ISO), si connue.
        effective_date: Quand il entre en vigueur (ISO), si connue.
        ingested_at: Quand la plateforme l'a reçu.
        extraction_method: Comment le texte a été tiré du document.
        extraction_confidence: Ce que l'extraction dit d'elle-même, entre 0 et 1.
        validation_status: L'état de validation humaine.
    """

    authority: str
    source_tier: str
    source_document: str
    document_title: str = ""
    document_hash: str = ""
    publication_date: str = ""
    effective_date: str = ""
    ingested_at: float = 0.0
    extraction_method: str = "unspecified"
    extraction_confidence: Optional[float] = None
    validation_status: str = CurriculumStatus.INGESTED.value

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "authority": self.authority,
            "source_tier": self.source_tier,
            "source_document": self.source_document,
            "document_title": self.document_title,
            "document_hash": self.document_hash,
            "publication_date": self.publication_date,
            "effective_date": self.effective_date,
            "ingested_at": self.ingested_at,
            "extraction_method": self.extraction_method,
            "extraction_confidence": self.extraction_confidence,
            "validation_status": self.validation_status,
        }

    @property
    def is_test_data(self) -> bool:
        """Vrai si cette provenance est une fixture d'ingénierie."""
        return MARQUE_TEST in f"{self.authority} {self.source_document}"

    def documentary_fields(self) -> Dict[str, Any]:
        """
        Ce qui décrit le **document**, sans ce qui décrit notre réception.

        `ingested_at`, `extraction_*` et `validation_status` disent quand *nous*
        avons reçu le texte et ce que *nous* en avons fait ; ils ne disent rien
        de ce que l'autorité a publié. Les inclure dans une empreinte rendrait
        deux imports du même décret officiellement différents — défaut trouvé
        en rejouant un import, pas en relisant le code.
        """
        return {
            "authority": self.authority,
            "source_tier": self.source_tier,
            "source_document": self.source_document,
            "document_title": self.document_title,
            "document_hash": self.document_hash,
            "publication_date": self.publication_date,
            "effective_date": self.effective_date,
        }


def _exiger(valeur: Any, champ: str, objet: str) -> str:
    """Exige un champ non vide, en disant lequel manque et pour quoi."""
    texte = str(valeur or "").strip()
    if not texte:
        raise CanonicalRefused(
            f"{objet} : le champ « {champ} » est vide. Un objet canonique sans "
            f"{champ} ne peut pas être retrouvé, cité, ni contredit — trois "
            "choses qu'un fait institutionnel doit permettre."
        )
    return texte


def make_provenance(
    authority: str,
    source_tier: str,
    source_document: str,
    **extra: Any,
) -> Provenance:
    """
    Construit une provenance, ou refuse.

    Args:
        authority: L'autorité qui publie.
        source_tier: Le rang de la source.
        source_document: Le document officiel.
        **extra: Les champs facultatifs de `Provenance`.

    Returns:
        La provenance.

    Raises:
        CanonicalRefused: Si l'autorité, le rang ou le document manquent. Ce
            sont les trois questions auxquelles « d'où vient ce fait ? » doit
            pouvoir répondre.
    """
    return Provenance(
        authority=_exiger(authority, "authority", "Provenance"),
        source_tier=_exiger(source_tier, "source_tier", "Provenance"),
        source_document=_exiger(source_document, "source_document", "Provenance"),
        ingested_at=extra.pop("ingested_at", time.time()),
        **extra,
    )


@dataclass(frozen=True)
class EducationSystem:
    """
    Le système éducatif dont relève un curriculum.

    Existe pour que le Sénégal soit **le premier**, pas le seul : la directive
    XLIII demande que le cœur ne code en dur aucune hypothèse nationale. Un pays,
    une autorité, un calendrier ; le reste est configuration.

    Attributes:
        country: Le code pays ISO-3166 alpha-2, en minuscules.
        system_id: L'identifiant du système éducatif.
        official_name: Son nom officiel.
        language: La langue de référence des documents officiels.
    """

    country: str
    system_id: str
    official_name: str = ""
    language: str = "fr"

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "country": self.country, "system_id": self.system_id,
            "official_name": self.official_name, "language": self.language,
        }


@dataclass(frozen=True)
class Grade:
    """
    Un niveau scolaire, tel que le système éducatif le nomme.

    Aucun niveau n'est déclaré ici. `CI`, `CP`, `CE1`… viendront du système
    éducatif importé : les écrire dans le code serait décider à la place de
    l'autorité, et la directive III l'interdit explicitement — *do not assume
    the final official structure if it has not been provided*.
    """

    grade_id: str
    official_name: str
    cycle: str = ""
    level: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "grade_id": self.grade_id, "official_name": self.official_name,
            "cycle": self.cycle, "level": self.level,
        }


@dataclass(frozen=True)
class Subject:
    """Une matière, avec les autres noms sous lesquels on la demande."""

    subject_id: str
    official_name: str
    aliases: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "subject_id": self.subject_id, "official_name": self.official_name,
            "aliases": list(self.aliases),
        }


@dataclass(frozen=True)
class Period:
    """
    Quand, dans l'année scolaire.

    `week` seul ne veut rien dire : la semaine 10 de 2026 et celle de 2027 ne
    portent pas le même contenu. L'année scolaire fait donc partie de la période,
    et la directive XXVI en fait une règle plutôt qu'une précaution.
    """

    academic_year: str
    term: Optional[int] = None
    month: Optional[int] = None
    week: Optional[int] = None
    sequence: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "academic_year": self.academic_year, "term": self.term,
            "month": self.month, "week": self.week, "sequence": self.sequence,
        }

    def key(self) -> str:
        """La clé stable d'une période, pour l'identité d'une unité."""
        return "|".join(
            f"{nom}={valeur}" for nom, valeur in sorted(self.as_dict().items())
            if valeur is not None
        )


@dataclass(frozen=True)
class CurriculumVersion:
    """
    Une version officielle du curriculum, adressable pour toujours.

    Attributes:
        version_id: Son identifiant.
        education_system: Le système dont elle relève.
        academic_year: L'année scolaire qu'elle régit.
        status: Où elle en est.
        provenance: D'où elle vient.
        published_at: Quand la plateforme l'a publiée.
        supersedes: La version qu'elle remplace, s'il y en a une.
    """

    version_id: str
    education_system: EducationSystem
    academic_year: str
    provenance: Provenance
    status: CurriculumStatus = CurriculumStatus.INGESTED
    published_at: Optional[float] = None
    supersedes: Optional[str] = None

    @property
    def is_official(self) -> bool:
        """
        Vrai seulement si cette version peut porter un fait officiel.

        Trois conditions, et aucune n'est déductible des deux autres : l'état
        est canonique, la provenance vient d'un rang officiel, et ce n'est pas
        une fixture d'ingénierie.
        """
        return (
            self.status in ETATS_CANONIQUES
            and self.provenance.source_tier.startswith("TIER_A")
            and not self.provenance.is_test_data
        )

    def content_hash(self) -> str:
        """
        L'empreinte de la version, calculée sur ce qui la **définit**.

        La provenance n'y entre que par ses champs documentaires : rejouer le
        même import doit donner la même empreinte, sinon « inchangé » devient
        indémontrable et le registre refuserait un import identique.
        """
        return _empreinte({
            "version_id": self.version_id,
            "system": self.education_system.as_dict(),
            "academic_year": self.academic_year,
            "provenance": self.provenance.documentary_fields(),
        })

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "version_id": self.version_id,
            "education_system": self.education_system.as_dict(),
            "academic_year": self.academic_year,
            "status": self.status.value,
            "provenance": self.provenance.as_dict(),
            "published_at": self.published_at,
            "supersedes": self.supersedes,
            "is_official": self.is_official,
            "content_hash": self.content_hash(),
        }


@dataclass(frozen=True)
class CurriculumUnit:
    """
    Ce que l'autorité dit qu'on étudie, à un niveau, dans une matière, à une
    période donnée.

    **Gelée.** Une correction est une nouvelle version, pas une modification :
    changer le texte en place effacerait la trace de ce que l'officiel disait
    avant, et c'est précisément cette trace qu'un curriculum institutionnel doit
    garder.

    Le champ `official_title` et les autres champs `official_*` viennent du
    document. Rien dans cette classe ne les produit, ne les complète ni ne les
    reformule : la reformulation est le travail de la couche pédagogique, qui
    lit cet objet sans le toucher (directive IV).
    """

    version_id: str
    grade: Grade
    subject: Subject
    period: Period
    official_title: str
    provenance: Provenance
    official_description: str = ""
    competencies: Tuple[str, ...] = ()
    objectives: Tuple[str, ...] = ()
    prerequisites: Tuple[str, ...] = ()
    activities: Tuple[str, ...] = ()
    evaluation_requirements: Tuple[str, ...] = ()
    unit_id: str = field(default="")

    def __post_init__(self) -> None:
        """Vérifie l'objet et lui donne son identité déterministe."""
        _exiger(self.version_id, "version_id", "CurriculumUnit")
        _exiger(self.official_title, "official_title", "CurriculumUnit")
        _exiger(self.grade.grade_id, "grade.grade_id", "CurriculumUnit")
        _exiger(self.subject.subject_id, "subject.subject_id", "CurriculumUnit")
        _exiger(self.period.academic_year, "period.academic_year", "CurriculumUnit")
        _exiger(self.provenance.authority, "provenance.authority", "CurriculumUnit")

        if not self.unit_id:
            # `object.__setattr__` parce que la classe est gelée : l'identité est
            # calculée une fois, à la création, et ne change plus.
            object.__setattr__(self, "unit_id", self.derived_id())

    def derived_id(self) -> str:
        """
        L'identité déterministe d'une unité.

        Deux imports du même enregistrement officiel doivent produire le même
        identifiant — c'est ce qui rend la garantie de cohérence entre usagers
        (directive VI) vérifiable au lieu d'espérée.
        """
        return _empreinte({
            "version_id": self.version_id,
            "grade": self.grade.grade_id,
            "subject": self.subject.subject_id,
            "period": self.period.key(),
        })[:32]

    def content_hash(self) -> str:
        """
        L'empreinte du **contenu** officiel de l'unité.

        Distincte de `unit_id` : l'identité dit *de quoi on parle*, l'empreinte
        dit *ce qui est écrit*. Deux versions successives d'une même semaine
        partagent la seconde question et pas la première.
        """
        return _empreinte({
            "official_title": self.official_title,
            "official_description": self.official_description,
            "competencies": list(self.competencies),
            "objectives": list(self.objectives),
            "prerequisites": list(self.prerequisites),
            "activities": list(self.activities),
            "evaluation_requirements": list(self.evaluation_requirements),
        })

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "unit_id": self.unit_id,
            "version_id": self.version_id,
            "grade": self.grade.as_dict(),
            "subject": self.subject.as_dict(),
            "period": self.period.as_dict(),
            "official_title": self.official_title,
            "official_description": self.official_description,
            "competencies": list(self.competencies),
            "objectives": list(self.objectives),
            "prerequisites": list(self.prerequisites),
            "activities": list(self.activities),
            "evaluation_requirements": list(self.evaluation_requirements),
            "provenance": self.provenance.as_dict(),
            "content_hash": self.content_hash(),
        }


def _empreinte(donnees: Dict[str, Any]) -> str:
    """L'empreinte SHA-256 d'une structure, calculée de façon stable."""
    serialise = json.dumps(donnees, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialise.encode("utf-8")).hexdigest()


def may_transition(
    depuis: CurriculumStatus, vers: CurriculumStatus
) -> Tuple[bool, str]:
    """
    Cette transition d'état est-elle permise ?

    Args:
        depuis: L'état actuel.
        vers: L'état visé.

    Returns:
        `(permise, motif)`. Le motif nomme la cause : un refus muet fait
        réessayer à l'identique.
    """
    permises = TRANSITIONS.get(depuis, frozenset())
    if vers in permises:
        return True, ""
    if depuis in (CurriculumStatus.SUPERSEDED, CurriculumStatus.REJECTED):
        return False, (
            f"« {depuis.value} » est terminal. Une version remplacée reste "
            "interrogeable pour les questions historiques, mais elle ne "
            "redevient pas courante."
        )
    return False, (
        f"Transition « {depuis.value} » → « {vers.value} » non permise. "
        f"Depuis {depuis.value}, seuls {sorted(e.value for e in permises)} "
        "sont atteignables. Une version publiée ne redevient pas un brouillon : "
        "elle est remplacée, ce qui laisse les deux lisibles."
    )


def fixture_provenance(document: str = "fixture") -> Provenance:
    """
    Une provenance pour les fixtures d'ingénierie, **jamais officielle**.

    L'ingénierie a besoin de données ; personne n'a besoin d'une fixture qui
    puisse passer pour un document ministériel. La marque est dans l'autorité
    elle-même, donc elle survit à la sérialisation, à la copie et au stockage.
    """
    return make_provenance(
        authority=f"{MARQUE_TEST} — synthetic engineering fixture",
        source_tier="TIER_D_DISCOVERY_ONLY",
        source_document=f"{MARQUE_TEST}:{document}",
        extraction_method="handwritten_fixture",
        validation_status=CurriculumStatus.INGESTED.value,
    )


def canonical_report() -> Dict[str, Any]:
    """
    Ce que le modèle canonique garantit, et ce qu'il ne contient pas.

    Returns:
        Les règles tenues, les états, et l'état réel du contenu — vide, et le
        disant.
    """
    return {
        "statuses": [statut.value for statut in CurriculumStatus],
        "canonical_statuses": sorted(e.value for e in ETATS_CANONIQUES),
        "test_marker": MARQUE_TEST,
        "rules": [
            "Un objet canonique est **gelé** : une correction est une nouvelle "
            "version, jamais une modification — sinon la trace de ce que "
            "l'officiel disait avant disparaît.",
            "Rien n'existe sans provenance : autorité, rang et document sont "
            "exigés à la construction.",
            "L'identité d'une unité est **dérivée** de ses dimensions : deux "
            "imports du même enregistrement officiel donnent le même "
            "identifiant, ce qui rend la cohérence entre usagers vérifiable.",
            "Une fixture porte sa marque dans son autorité : elle n'est jamais "
            "officielle, quoi qu'elle déclare par ailleurs.",
            "`PUBLISHED` et `SUPERSEDED` répondent ; `VALIDATED` non — validé "
            "veut dire « quelqu'un a relu », publié veut dire « l'autorité l'a "
            "mis en vigueur ».",
        ],
        "does_not": [
            "Contenir le moindre curriculum sénégalais : la structure est ici, "
            "le contenu vient d'une autorité.",
            "Déclarer les niveaux scolaires : les écrire dans le code serait "
            "décider à la place de l'autorité.",
            "Reformuler un champ officiel : la pédagogie lit cet objet, elle ne "
            "le touche pas.",
        ],
    }
