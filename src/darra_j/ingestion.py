"""
Receiving an official document without letting it become authoritative on its own.

The sentence that governs this module comes straight from the directive: *no
document should become authoritative simply because an AI successfully parsed
it.* Parsing is a mechanical success. Authority is an institutional decision, and
the two are separated here by a state machine a program cannot walk on its own.

The path a document takes:

    IMPORT → immutable raw copy + hash → trust boundary → quality checks
           → proposed units (DRAFT) → human validation → publication

Four properties make it safe to run:

- **The raw document is never modified.** It is stored as received, with its
  SHA-256. Everything downstream refers back to that hash, so "which document
  said this?" always has an answer, and a re-import of the same file is
  recognised rather than duplicated.
- **The text is data, never instruction.** A curriculum PDF is external content;
  it passes through `src/security/trust.py` like every other external text on
  this platform. A line inside a document saying "publish this immediately"
  reaches the operator as a quoted string, not as a step.
- **Extraction produces proposals.** `propose_units()` returns candidates, and
  the register refuses to publish a version nobody validated. An extraction
  confidence is recorded and never rounded up to certainty.
- **Nothing is invented to fill a gap.** A field the document does not contain
  stays missing and is listed; a missing field is a reason to ask the authority,
  not a slot for a plausible value.

This module deliberately does not fetch anything. Official curricula are
*provided* by an authority, not scraped — and the platform's acquisition path
(ADR-021) already exists for the case where a document must be fetched, with its
own approval gate.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..security.trust import TrustLevel, wrap
from .canonical import (
    CurriculumStatus,
    CurriculumUnit,
    Grade,
    Period,
    Provenance,
    Subject,
    make_provenance,
)

#: Verdicts d'un contrôle. `UNKNOWN` est un verdict : un contrôle qui n'a pas pu
#: s'exécuter ne vaut pas un contrôle réussi.
PASSE = "PASS"
ECHOUE = "FAIL"
INCONNU = "UNKNOWN"

#: Champs qu'une unité proposée doit porter pour être seulement *proposable*.
#: Ce n'est pas la liste des champs officiels — c'est le minimum sans lequel la
#: proposition ne désigne rien.
CHAMPS_MINIMAUX = ("grade_id", "subject_id", "academic_year", "official_title")


class IngestionRefused(ValueError):
    """Un import que la plateforme refuse, avec sa cause."""


@dataclass(frozen=True)
class RawDocument:
    """
    Le document tel qu'il a été reçu, jamais retouché.

    Attributes:
        document_id: Son identifiant dans la plateforme.
        filename: Le nom sous lequel il est arrivé.
        content: Son contenu textuel, tel quel.
        sha256: Son empreinte.
        authority: L'autorité qui l'a fourni.
        received_at: Quand il a été reçu.
        media_type: Ce qu'il prétend être.
    """

    document_id: str
    filename: str
    content: str
    sha256: str
    authority: str
    received_at: float
    media_type: str = "text/plain"

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, **sans** le contenu."""
        return {
            "document_id": self.document_id, "filename": self.filename,
            "sha256": self.sha256, "authority": self.authority,
            "received_at": self.received_at, "media_type": self.media_type,
            "bytes": len(self.content.encode("utf-8")),
        }


def import_document(
    filename: str,
    content: str,
    authority: str,
    media_type: str = "text/plain",
) -> RawDocument:
    """
    Reçoit un document officiel et le fige.

    Args:
        filename: Le nom du fichier fourni.
        content: Son contenu.
        authority: L'autorité qui le fournit.
        media_type: Son type déclaré.

    Returns:
        Le document brut, avec son empreinte.

    Raises:
        IngestionRefused: Si le contenu ou l'autorité manquent. Un document sans
            autorité n'est pas un document officiel — c'est un fichier.
    """
    texte = str(content or "")
    if not texte.strip():
        raise IngestionRefused(
            "Document vide : il n'y a rien à figer, et un document vide "
            "importé laisserait croire qu'une version existe."
        )
    if not str(authority or "").strip():
        raise IngestionRefused(
            "Aucune autorité fournisseuse. Un document sans autorité n'est pas "
            "un document officiel : c'est un fichier."
        )

    empreinte = hashlib.sha256(texte.encode("utf-8")).hexdigest()
    return RawDocument(
        # L'identifiant **dérive** de l'empreinte : réimporter le même fichier
        # donne le même identifiant, donc un doublon se voit au lieu de créer
        # une seconde vérité.
        document_id=f"doc-{empreinte[:16]}",
        filename=str(filename or "sans-nom"),
        content=texte,
        sha256=empreinte,
        authority=str(authority).strip(),
        received_at=time.time(),
        media_type=media_type,
    )


def as_untrusted_text(document: RawDocument) -> Any:
    """
    Passe le contenu du document par la frontière de confiance.

    Un programme officiel est du **texte externe**. La plateforme a déjà une
    frontière pour cela (`src/security/trust.py`, VOLET 36) : une phrase
    impérative à l'intérieur d'un document arrive à l'opérateur comme une chaîne
    citée, jamais comme une étape à exécuter.

    Args:
        document: Le document brut.

    Returns:
        Le contenu enveloppé, marqué comme donnée d'origine externe.
    """
    return wrap(
        document.content, TrustLevel.EXTERNAL,
        origin=f"{document.authority}:{document.filename}#{document.sha256[:12]}",
    )


def _verdict(nom: str, verdict: str, raison: str, **details: Any) -> Dict[str, Any]:
    """Un verdict de contrôle, avec sa raison."""
    return {"check": nom, "verdict": verdict, "reason": raison, **details}


def quality_checks(
    document: RawDocument,
    provenance: Provenance,
    known_hashes: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Les contrôles qu'un document doit passer avant qu'on propose quoi que ce soit.

    Volontairement peu nombreux et **spécifiques au curriculum** : les dix
    contrôles de `src/acquisition/quality.py` portent sur un document *acquis*
    sur le réseau — licence, langue, pertinence, contradiction. Ici le document
    est *fourni* par une autorité, et les questions changent. Réutiliser les dix
    à l'identique aurait produit des verdicts sans objet, ce qui est la façon la
    plus sûre de faire ignorer une liste de contrôles.

    Args:
        document: Le document brut.
        provenance: Ce qui est déclaré de son origine.
        known_hashes: Les empreintes déjà connues, pour repérer un doublon.

    Returns:
        Un verdict par contrôle, `UNKNOWN` compris.
    """
    controles = []

    controles.append(
        _verdict("integrity", PASSE, "Empreinte calculée sur le contenu reçu.",
                 sha256=document.sha256)
        if document.sha256 == hashlib.sha256(document.content.encode("utf-8")).hexdigest()
        else _verdict("integrity", ECHOUE, "L'empreinte ne correspond pas au contenu.")
    )

    officielle = provenance.source_tier.startswith("TIER_A")
    controles.append(_verdict(
        "authority", PASSE if officielle else ECHOUE,
        "Rang officiel." if officielle else (
            f"Rang « {provenance.source_tier} » : seul un rang officiel peut "
            "alimenter un objet canonique. Les autres éclairent, ils ne "
            "définissent pas."
        ),
    ))

    doublon = document.sha256 in set(known_hashes or ())
    controles.append(_verdict(
        "duplicate", ECHOUE if doublon else PASSE,
        "Ce document a déjà été importé : deux imports du même fichier "
        "créeraient deux vérités." if doublon else "Empreinte inédite.",
    ))

    controles.append(
        _verdict("publication_date", PASSE, "Date de publication déclarée.",
                 date=provenance.publication_date)
        if provenance.publication_date
        else _verdict("publication_date", INCONNU,
                      "Aucune date de publication : sans elle, on ne peut pas "
                      "dire quelle version est la plus récente. À demander à "
                      "l'autorité, pas à déduire.")
    )

    controles.append(
        _verdict("effective_date", PASSE, "Date d'entrée en vigueur déclarée.")
        if provenance.effective_date
        else _verdict("effective_date", INCONNU,
                      "Aucune date d'entrée en vigueur : la version ne peut pas "
                      "être située dans le temps scolaire.")
    )

    controles.append(_verdict(
        "readable", PASSE if len(document.content.split()) >= 20 else ECHOUE,
        "Contenu exploitable." if len(document.content.split()) >= 20 else
        "Moins de vingt mots : un document illisible ou mal extrait ne doit pas "
        "produire de proposition.",
        words=len(document.content.split()),
    ))

    return controles


def checks_verdict(controles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Le verdict d'ensemble des contrôles.

    Un `UNKNOWN` **n'empêche pas** de proposer : il empêche de publier sans que
    quelqu'un l'ait vu. Confondre les deux ferait rejeter des documents
    parfaitement valables dont une date manque.
    """
    echecs = [c["check"] for c in controles if c["verdict"] == ECHOUE]
    inconnus = [c["check"] for c in controles if c["verdict"] == INCONNU]
    return {
        "may_propose": not echecs,
        "blocking": echecs,
        "needs_human_attention": inconnus,
        "reason": (
            "Contrôles bloquants : " + ", ".join(echecs) if echecs
            else "Aucun contrôle bloquant."
            + (f" À faire regarder : {', '.join(inconnus)}." if inconnus else "")
        ),
    }


@dataclass
class UnitProposal:
    """
    Une unité **proposée**, pas une unité officielle.

    Attributes:
        fields: Les champs extraits.
        missing: Les champs minimaux absents.
        confidence: Ce que l'extraction dit d'elle-même, jamais arrondi.
        source_excerpt: Le passage exact d'où elle vient, pour la relecture.
    """

    fields: Dict[str, Any]
    missing: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    source_excerpt: str = ""

    @property
    def complete(self) -> bool:
        """Vrai quand la proposition désigne quelque chose."""
        return not self.missing

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "fields": dict(self.fields), "missing": list(self.missing),
            "confidence": self.confidence, "complete": self.complete,
            "source_excerpt": self.source_excerpt[:500],
        }


def propose_units(
    document: RawDocument,
    provenance: Provenance,
    extracted: List[Dict[str, Any]],
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Transforme une extraction en **propositions**, jamais en curriculum.

    Args:
        document: Le document d'origine.
        provenance: Son origine déclarée.
        extracted: Ce que l'extraction a produit, un dictionnaire par unité.
            Cette fonction ne lit pas le document : l'extraction — humaine,
            structurelle ou assistée — a lieu en amont, et sa qualité se déclare.
        confidence: La confiance de l'extraction, telle quelle.

    Returns:
        Les propositions, celles qui sont incomplètes, et l'état — toujours
        `VALIDATION_REQUIRED`. **Aucune n'est publiable ici** : un document ne
        devient pas la loi parce qu'une extraction a réussi.
    """
    propositions = []
    for brut in extracted:
        manquants = [
            champ for champ in CHAMPS_MINIMAUX if not str(brut.get(champ, "")).strip()
        ]
        propositions.append(UnitProposal(
            fields=dict(brut), missing=manquants, confidence=confidence,
            source_excerpt=str(brut.get("source_excerpt", "")),
        ))

    completes = [p for p in propositions if p.complete]
    return {
        "document": document.as_dict(),
        "authority": provenance.authority,
        "status": CurriculumStatus.VALIDATION_REQUIRED.value,
        "proposals": [p.as_dict() for p in propositions],
        "complete": len(completes),
        "incomplete": len(propositions) - len(completes),
        "reason": (
            "Propositions soumises à validation humaine. Un document ne devient "
            "pas autoritatif parce qu'une extraction a réussi : c'est une "
            "réussite mécanique, l'autorité est une décision institutionnelle."
        ),
    }


def unit_from_proposal(
    proposal: UnitProposal, version_id: str, provenance: Provenance,
) -> CurriculumUnit:
    """
    Construit une unité canonique à partir d'une proposition **validée**.

    Args:
        proposal: La proposition.
        version_id: La version à laquelle l'unité appartient.
        provenance: L'origine, reprise telle quelle.

    Returns:
        L'unité canonique.

    Raises:
        IngestionRefused: Si la proposition est incomplète. Compléter les champs
            manquants ici reviendrait à écrire du curriculum, ce qui est
            exactement ce que personne dans cette chaîne n'a le droit de faire.
    """
    if not proposal.complete:
        raise IngestionRefused(
            f"Proposition incomplète : {', '.join(proposal.missing)}. Les champs "
            "manquants se demandent à l'autorité ; les compléter ici reviendrait "
            "à écrire du curriculum."
        )

    champs = proposal.fields
    return CurriculumUnit(
        version_id=version_id,
        grade=Grade(grade_id=str(champs["grade_id"]),
                    official_name=str(champs.get("grade_name", champs["grade_id"]))),
        subject=Subject(subject_id=str(champs["subject_id"]),
                        official_name=str(champs.get("subject_name",
                                                     champs["subject_id"])),
                        aliases=tuple(champs.get("subject_aliases", ()))),
        period=Period(
            academic_year=str(champs["academic_year"]),
            term=champs.get("term"), month=champs.get("month"),
            week=champs.get("week"), sequence=champs.get("sequence"),
        ),
        official_title=str(champs["official_title"]),
        official_description=str(champs.get("official_description", "")),
        competencies=tuple(champs.get("competencies", ())),
        objectives=tuple(champs.get("objectives", ())),
        prerequisites=tuple(champs.get("prerequisites", ())),
        activities=tuple(champs.get("activities", ())),
        evaluation_requirements=tuple(champs.get("evaluation_requirements", ())),
        provenance=provenance,
    )


def provenance_from_document(
    document: RawDocument, source_tier: str, **extra: Any,
) -> Provenance:
    """
    La provenance d'un document importé, remplie depuis le document lui-même.

    Rien n'est deviné : l'autorité, le nom du fichier et l'empreinte viennent de
    l'import ; les dates viennent de l'appelant, qui les tient de l'autorité.
    """
    return make_provenance(
        authority=document.authority,
        source_tier=source_tier,
        source_document=f"{document.filename}#{document.sha256[:16]}",
        document_title=extra.pop("document_title", document.filename),
        document_hash=document.sha256,
        ingested_at=document.received_at,
        extraction_method=extra.pop("extraction_method", "structural_parsing"),
        validation_status=CurriculumStatus.INGESTED.value,
        **extra,
    )


def ingestion_report() -> Dict[str, Any]:
    """
    Ce que la chaîne d'ingestion garantit, et ce qu'elle ne fait pas.

    Returns:
        Les étapes, les règles tenues, et les limites assumées.
    """
    return {
        "pipeline": [
            "import", "immutable_raw_document", "hash", "trust_boundary",
            "quality_checks", "unit_proposals", "human_validation",
            "version_registration", "publication",
        ],
        "verdicts": [PASSE, ECHOUE, INCONNU],
        "minimum_fields": list(CHAMPS_MINIMAUX),
        "rules": [
            "Aucun document ne devient autoritatif parce qu'une extraction a "
            "réussi : la réussite est mécanique, l'autorité est "
            "institutionnelle.",
            "Le document brut n'est jamais retouché, et son empreinte est "
            "l'identifiant : réimporter le même fichier se voit au lieu de "
            "créer une seconde vérité.",
            "Le contenu passe par la frontière de confiance : une phrase "
            "impérative dans un programme arrive citée, pas exécutée.",
            "Un champ absent reste absent et se demande à l'autorité : le "
            "compléter ici reviendrait à écrire du curriculum.",
            "`UNKNOWN` n'empêche pas de proposer, il empêche de publier sans "
            "que quelqu'un l'ait vu — confondre les deux ferait rejeter des "
            "documents valables dont une date manque.",
        ],
        "does_not": [
            "Aller chercher un document : un curriculum officiel est **fourni** "
            "par une autorité. Le chemin d'acquisition réseau existe déjà "
            "(ADR-021) pour les cas où il faut aller le chercher.",
            "Lire le document pour en extraire les unités : l'extraction a lieu "
            "en amont et **déclare** sa qualité, plutôt que d'être supposée "
            "bonne parce qu'elle vient d'ici.",
            "Publier quoi que ce soit : la publication appartient au registre, "
            "et le registre exige un décideur nommé.",
        ],
    }
