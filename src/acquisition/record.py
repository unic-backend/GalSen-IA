"""
Ce qu'est un document candidat, et par quels états il passe (ADR-021, étape 2).

Un document découvert n'est pas une connaissance. Il n'a pas de provenance
complète, il n'est pas passé par la barrière de confiance, personne ne l'a
approuvé. Le représenter par un `KnowledgeItem` le ferait entrer dans la base
par le seul fait d'exister, et c'est exactement ce que ce chantier refuse.

D'où ce module : un enregistrement **à part**, avec sa propre machine à états,
qui ne devient une connaissance qu'à la toute fin, par l'ingestion existante.

## Trois règles, et chacune est du code

1. **Aucune transition sans raison.** Un document qui s'arrête sans motif est
   une panne du pipeline, pas une propriété du document. La raison est exigée à
   l'appel, pas suggérée par une convention.
2. **`REJECTED` est terminal, `QUARANTINED` ne l'est pas.** La quarantaine est
   le cas récupérable : quelqu'un tranche. En sortir vers `VERIFIED` demande
   **un acteur humain** — c'est la seule transition que le pipeline ne peut pas
   se donner à lui-même.
3. **`publication_date` n'est jamais la date de récupération.** Aucun chemin de
   ce module ne l'assigne depuis `retrieval_date` ; un document récupéré
   aujourd'hui n'est pas un document publié aujourd'hui, et une base qui
   confond les deux classera un décret de 1998 comme courant.

## Ce que ce module ne fait pas

Il ne va pas sur le réseau, ne lit aucun fichier, n'appelle aucun modèle. Il
tient un état et refuse les transitions impossibles. Le reste est ailleurs, et
ce module est ce qui permet de le tester ailleurs sans rien acquérir.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

#: Valeur d'un champ que personne n'a établi. `unknown` n'est pas « absent »,
#: et surtout pas « sans importance » : c'est une lacune qui se transmet à toute
#: réponse construite sur ce document.
INCONNU = "unknown"

#: Acteur d'une transition. Seul `HUMAIN` peut sortir de la quarantaine.
PIPELINE = "pipeline"
HUMAIN = "human"


class AcquisitionStatus(Enum):
    """Où en est un document candidat."""

    DISCOVERED = "DISCOVERED"      # une URL, rien d'autre
    FETCHED = "FETCHED"            # les octets sont là
    PARSED = "PARSED"              # texte et métadonnées extraits
    VERIFIED = "VERIFIED"          # les contrôles de qualité passent
    QUARANTINED = "QUARANTINED"    # récupérable : une personne tranche
    REJECTED = "REJECTED"          # terminal, avec sa raison
    INGESTED = "INGESTED"          # entré dans la base par l'ingestion existante


#: Statuts dont on ne sort pas. `REJECTED` est un refus motivé, `INGESTED` la
#: fin du chemin — les deux se relisent, aucun ne se reprend.
STATUTS_TERMINAUX = frozenset({AcquisitionStatus.REJECTED, AcquisitionStatus.INGESTED})

#: Les transitions permises. Tout ce qui n'est pas ici est refusé : une machine
#: à états qui accepte n'importe quel saut ne mesure rien.
TRANSITIONS: Dict[AcquisitionStatus, frozenset] = {
    AcquisitionStatus.DISCOVERED: frozenset({
        AcquisitionStatus.FETCHED,
        AcquisitionStatus.QUARANTINED,
        AcquisitionStatus.REJECTED,
    }),
    AcquisitionStatus.FETCHED: frozenset({
        AcquisitionStatus.PARSED,
        AcquisitionStatus.QUARANTINED,
        AcquisitionStatus.REJECTED,
    }),
    AcquisitionStatus.PARSED: frozenset({
        AcquisitionStatus.VERIFIED,
        AcquisitionStatus.QUARANTINED,
        AcquisitionStatus.REJECTED,
    }),
    AcquisitionStatus.VERIFIED: frozenset({
        AcquisitionStatus.INGESTED,
        AcquisitionStatus.QUARANTINED,
        AcquisitionStatus.REJECTED,
    }),
    # La quarantaine se résout dans les deux sens, jamais vers l'ingestion
    # directe : un document tiré de la quarantaine repasse par `VERIFIED`, donc
    # par les contrôles, au lieu de les contourner par le haut.
    AcquisitionStatus.QUARANTINED: frozenset({
        AcquisitionStatus.VERIFIED,
        AcquisitionStatus.REJECTED,
    }),
    AcquisitionStatus.REJECTED: frozenset(),
    AcquisitionStatus.INGESTED: frozenset(),
}

#: Transitions qu'aucun automate ne peut décider seul. Sortir un document de la
#: quarantaine, c'est trancher ce que la mesure n'a pas su trancher.
TRANSITIONS_HUMAINES = frozenset({
    (AcquisitionStatus.QUARANTINED, AcquisitionStatus.VERIFIED),
})

#: Provenance minimale pour entrer dans la couche de confiance (conception §5.2).
#: `publication_date` n'y est **pas** : un document officiel non daté reste un
#: document officiel, et l'exiger viderait le pilote. Il entre avec sa lacune,
#: et la lacune se voit.
PROVENANCE_MINIMALE = (
    "source_url",
    "institution",
    "source_tier",
    "retrieval_date",
    "content_hash",
    "license_or_usage_status",
)


class AcquisitionRefused(ValueError):
    """Une transition impossible, ou une transition sans raison."""


def _maintenant() -> str:
    """Retourne l'instant courant en ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AcquiredDocument:
    """
    Un document candidat, de sa découverte à son entrée — ou à son refus.

    Tous les champs de provenance valent `unknown` tant que personne ne les a
    établis. Aucun n'est déduit d'un autre : `publication_date` en particulier
    n'est jamais tirée de `retrieval_date`.
    """

    source_url: str
    institution: str = INCONNU
    source_tier: str = INCONNU
    canonical_url: str = INCONNU
    publisher: str = INCONNU
    document_title: str = INCONNU
    document_type: str = INCONNU
    publication_date: str = INCONNU
    retrieval_date: str = INCONNU
    language: str = INCONNU
    language_declared: str = INCONNU
    country: str = INCONNU
    jurisdiction: str = INCONNU
    domain: str = INCONNU
    content_hash: str = INCONNU
    text_hash: str = INCONNU
    license_or_usage_status: str = INCONNU
    provenance: Dict[str, Any] = field(default_factory=dict)

    status: AcquisitionStatus = AcquisitionStatus.DISCOVERED
    history: List[Dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Consigne l'état initial, pour qu'aucun état ne soit sans trace."""
        if not str(self.source_url or "").strip():
            raise AcquisitionRefused("Un document candidat sans URL n'est pas un candidat.")
        if not self.history:
            self.history.append({
                "from": "",
                "to": self.status.value,
                "reason": "Candidat découvert.",
                "actor": PIPELINE,
                "at": _maintenant(),
            })

    # ------------------------------------------------------------------
    # La machine à états
    # ------------------------------------------------------------------

    def transition(
        self,
        vers: AcquisitionStatus,
        reason: str,
        actor: str = PIPELINE,
        at: Optional[str] = None,
    ) -> "AcquiredDocument":
        """
        Fait passer le document à un autre statut, avec la raison qui l'explique.

        Args:
            vers: Le statut visé.
            reason: Pourquoi. **Exigée** : un document arrêté sans motif est une
                panne du pipeline, pas une propriété du document.
            actor: `pipeline` ou `human`. Sortir de la quarantaine vers
                `VERIFIED` exige `human` — c'est la seule décision que
                l'automate ne peut pas se donner à lui-même.
            at: Horodatage, injectable pour les tests.

        Returns:
            Le document lui-même, pour enchaîner.

        Raises:
            AcquisitionRefused: Transition interdite, raison vide, ou décision
                humaine prise par le pipeline.
        """
        if not str(reason or "").strip():
            raise AcquisitionRefused(
                f"Transition {self.status.value} → {vers.value} sans raison. "
                "Un document arrêté sans motif ne se relit pas."
            )

        permises = TRANSITIONS[self.status]
        if vers not in permises:
            attendues = ", ".join(sorted(statut.value for statut in permises)) or "aucune"
            raise AcquisitionRefused(
                f"Transition {self.status.value} → {vers.value} interdite. "
                f"Depuis {self.status.value}, seules sont permises : {attendues}."
            )

        if (self.status, vers) in TRANSITIONS_HUMAINES and actor != HUMAIN:
            raise AcquisitionRefused(
                f"Sortir de la quarantaine vers {vers.value} demande une personne. "
                "La quarantaine est précisément ce que la mesure n'a pas su trancher."
            )

        self.history.append({
            "from": self.status.value,
            "to": vers.value,
            "reason": reason.strip(),
            "actor": actor,
            "at": at or _maintenant(),
        })
        self.status = vers
        return self

    @property
    def is_terminal(self) -> bool:
        """Indique si le document ne peut plus changer d'état."""
        return self.status in STATUTS_TERMINAUX

    # ------------------------------------------------------------------
    # La provenance
    # ------------------------------------------------------------------

    def provenance_gaps(self) -> List[str]:
        """
        Retourne les champs de provenance que personne n'a établis.

        Publié plutôt que sous-entendu : une réponse bâtie sur ce document
        hérite de ces lacunes, et elle doit pouvoir les nommer.
        """
        champs = (
            "source_url", "canonical_url", "publisher", "institution",
            "document_title", "document_type", "publication_date",
            "retrieval_date", "language", "country", "jurisdiction", "domain",
            "content_hash", "text_hash", "license_or_usage_status", "source_tier",
        )
        return [nom for nom in champs if str(getattr(self, nom) or INCONNU) == INCONNU]

    def provenance_is_sufficient(self) -> bool:
        """
        Indique si la provenance suffit pour entrer dans la couche de confiance.

        `publication_date` n'est pas exigée : un document officiel non daté reste
        un document officiel, et l'exiger viderait le pilote. Il entre avec sa
        lacune, et la lacune se voit dans `provenance_gaps()`.
        """
        return all(
            str(getattr(self, nom) or INCONNU) != INCONNU for nom in PROVENANCE_MINIMALE
        )

    def missing_for_trusted_layer(self) -> List[str]:
        """Retourne ce qui manque pour la provenance minimale, ou une liste vide."""
        return [
            nom for nom in PROVENANCE_MINIMALE
            if str(getattr(self, nom) or INCONNU) == INCONNU
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Retourne l'enregistrement sous une forme sérialisable."""
        return {
            "source_url": self.source_url,
            "canonical_url": self.canonical_url,
            "publisher": self.publisher,
            "institution": self.institution,
            "document_title": self.document_title,
            "document_type": self.document_type,
            "publication_date": self.publication_date,
            "retrieval_date": self.retrieval_date,
            "language": self.language,
            "language_declared": self.language_declared,
            "country": self.country,
            "jurisdiction": self.jurisdiction,
            "domain": self.domain,
            "content_hash": self.content_hash,
            "text_hash": self.text_hash,
            "license_or_usage_status": self.license_or_usage_status,
            "source_tier": self.source_tier,
            "provenance": dict(self.provenance),
            "verification_status": self.status.value,
            "provenance_gaps": self.provenance_gaps(),
            "missing_for_trusted_layer": self.missing_for_trusted_layer(),
            "history": list(self.history),
        }


def acquisition_report(documents: Iterable[AcquiredDocument]) -> Dict[str, Any]:
    """
    Décrit un lot de documents candidats.

    Un lot dont on ne sait pas dire pourquoi chaque document s'est arrêté n'a
    rien prouvé : les refus et les quarantaines sortent **avec leur raison**,
    pas seulement avec leur nombre.
    """
    lot = list(documents)
    par_statut: Dict[str, int] = {statut.value: 0 for statut in AcquisitionStatus}
    for document in lot:
        par_statut[document.status.value] += 1

    def _derniere_raison(document: AcquiredDocument) -> Dict[str, str]:
        return {
            "source_url": document.source_url,
            "reason": document.history[-1]["reason"] if document.history else "",
        }

    return {
        "documents": len(lot),
        "by_status": par_statut,
        "rejected": [
            _derniere_raison(d) for d in lot if d.status is AcquisitionStatus.REJECTED
        ],
        "quarantined": [
            _derniere_raison(d) for d in lot if d.status is AcquisitionStatus.QUARANTINED
        ],
        "insufficient_provenance": [
            {"source_url": d.source_url, "missing": d.missing_for_trusted_layer()}
            for d in lot if not d.provenance_is_sufficient()
        ],
        "note": (
            "Rien n'est acquis ici : ce module tient un état. Un document en "
            "quarantaine attend une personne ; un document refusé porte sa raison."
        ),
    }
