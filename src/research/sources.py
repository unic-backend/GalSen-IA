"""
Normaliser une source récupérée, et lui attacher sa provenance
(R07.1, STEP 7 partiel, STEP 8 et STEP 9).

## Ce module n'écrit pas un troisième système de provenance

STEP 9 le dit : *« s'intégrer au système de provenance existant, ne pas créer
d'architecture concurrente »*. Deux existent déjà et sont légitimement
différents — `acquisition/` enregistre d'où vient un **fait**, `creative/jobs.py`
d'où vient un **artefact**. Un résultat de recherche est une source de fait,
donc la famille est `acquisition/`.

Mais `AcquiredDocument` est une machine à états lourde : découverte → décision →
**approbation humaine** → récupération → dix contrôles qualité → manifeste. Un
résultat de recherche ne passe pas par là **pour être lu**. Il y passe seulement
si quelqu'un propose de le faire **entrer dans la connaissance**.

Ce module tient donc les deux bouts : un enregistrement léger qui porte les dix
champs de STEP 9, et **un pont** — `to_acquisition_candidate()` — vers le
système existant, au moment où la question devient l'ingestion.

## `confidence` ne peut pas être un nombre inventé

STEP 9 demande une confiance. La plateforme refuse partout les scores sans
mesure : `security/posture.py` refuse de se noter, ADR-026 refuse un score de
qualité de fournisseur, `routing.py` refuse de classer sur un chiffre absent.

Ici, la confiance est donc **`None` par défaut**, et une valeur ne peut pas être
posée sans dire **comment** elle a été établie. C'est la règle que le chargeur du
corpus a déjà imposée une fois, en refusant `identity_consistency` tant que
l'entrée ne nommait pas sa méthode.

## `validation_status` réutilise l'échelle qui existe

`creative/language/observation.py` porte déjà les six états que STEP 8 demande —
`OBSERVED`, `CANDIDATE`, `CORROBORATED`, `VALIDATED`, `OFFICIAL`, `UNKNOWN` — et
`promote_by_frequency()` **plafonne à `CORROBORATED`, quel que soit le compte** :
mille observations d'une erreur restent une erreur observée mille fois.

Une source récupérée entre donc en `OBSERVED`. Rien dans ce module ne la promeut
au-delà, et **rien n'entre dans la connaissance globale automatiquement**
(STEP 7) : `propose_for_knowledge()` rend une proposition, pas une ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from ..creative.jobs import fingerprint
from ..creative.language.observation import (
    CORROBORE,
    ETATS,
    OBSERVE,
    OFFICIEL,
    VALIDE,
)
from .safety import as_data, check_url

#: Les natures de source déclarées. Une nature inconnue est refusée pour être
#: **ajoutée ici** : elle décide de la façon dont la source sera lue et citée.
TYPES_DE_SOURCE = (
    "web_page",
    "search_result",
    "forum_thread",
    "code_repository",
    "issue_thread",
    "academic_paper",
    "encyclopedia",
    "feed_item",
    "video_transcript",
    "social_post",
)

#: Les états qu'une source récupérée ne peut **jamais** atteindre par le seul
#: fait d'avoir été récupérée. Une autorité se constate ailleurs.
ETATS_HORS_DE_PORTEE = (VALIDE, OFFICIEL)


class SourceRefused(ValueError):
    """Une source impossible à normaliser telle quelle."""


def _maintenant() -> str:
    """L'instant courant, en ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ResearchSource:
    """
    Une source récupérée, avec les dix champs de STEP 9.

    Attributes:
        source_url: L'URL. Requise : sans elle, rien n'est vérifiable.
        source_type: La nature, parmi `TYPES_DE_SOURCE`.
        provider: Le fournisseur qui l'a rapportée.
        provider_version: Sa version déclarée, ou `UNKNOWN`.
        retrieval_timestamp: Quand elle a été récupérée, ISO 8601 UTC.
        query: La requête qui l'a fait remonter, telle qu'écrite.
        content_hash: L'empreinte du contenu, quand il y en a un. Vide quand la
            source est un simple résultat de recherche sans corps récupéré —
            **vide veut dire « pas de contenu », jamais « contenu vide »**.
        source_metadata: Ce que le fournisseur a rapporté en plus, tel quel.
        confidence: `None` = **jamais établie**. Une valeur exige une base.
        confidence_basis: Comment la confiance a été établie. Vide seulement si
            `confidence` est `None`.
        validation_status: Un état de `ETATS`. Par défaut `OBSERVED`.
        title: Le titre rapporté, quand il y en a un.
    """

    source_url: str
    source_type: str
    provider: str
    query: str
    provider_version: str = "UNKNOWN"
    retrieval_timestamp: str = field(default_factory=_maintenant)
    content_hash: str = ""
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None
    confidence_basis: str = ""
    validation_status: str = OBSERVE
    title: str = ""

    def __post_init__(self) -> None:
        if not str(self.source_url).strip():
            raise SourceRefused(
                "Une source sans URL n'est pas vérifiable, donc n'est pas une "
                "source."
            )
        if self.source_type not in TYPES_DE_SOURCE:
            raise SourceRefused(
                f"Nature « {self.source_type} » non déclarée. Déclarées : "
                f"{list(TYPES_DE_SOURCE)}."
            )
        if not str(self.provider).strip():
            raise SourceRefused(
                "Une source sans fournisseur ne se recoupe pas : on ne saurait "
                "pas quoi réparer si elle se révélait fausse."
            )
        if self.validation_status not in ETATS:
            raise SourceRefused(
                f"État « {self.validation_status} » non déclaré. Déclarés : "
                f"{list(ETATS)}."
            )
        if self.validation_status in ETATS_HORS_DE_PORTEE:
            raise SourceRefused(
                f"Une source récupérée ne peut pas naître « "
                f"{self.validation_status} ». Une autorité se constate "
                "ailleurs ; l'avoir trouvée sur le web ne l'établit pas."
            )
        if self.confidence is not None:
            if not 0.0 <= float(self.confidence) <= 1.0:
                raise SourceRefused(
                    f"Confiance {self.confidence} hors de [0, 1]."
                )
            if not self.confidence_basis.strip():
                raise SourceRefused(
                    f"Confiance {self.confidence} sans base. Un chiffre dont "
                    "personne ne dit comment il a été obtenu se comporte comme "
                    "une mesure sans en être une."
                )
        elif self.confidence_basis.strip():
            raise SourceRefused(
                "Une base de confiance sans confiance ne dit rien : soit les "
                "deux, soit aucune."
            )

    @property
    def has_content(self) -> bool:
        """Vrai quand un contenu a été récupéré et empreinté."""
        return bool(self.content_hash)

    def as_dict(self) -> Dict[str, Any]:
        """La provenance sérialisée — les dix champs de STEP 9."""
        return {
            "source_url": self.source_url,
            "source_type": self.source_type,
            "provider": self.provider,
            "provider_version": self.provider_version,
            "retrieval_timestamp": self.retrieval_timestamp,
            "query": self.query,
            "content_hash": self.content_hash,
            "source_metadata": dict(self.source_metadata),
            "confidence": self.confidence,
            "confidence_basis": self.confidence_basis,
            "validation_status": self.validation_status,
            "title": self.title,
        }


def normalize(raw: Dict[str, Any], provider: str, query: str,
              source_type: str, provider_version: str = "UNKNOWN",
              content: Optional[str] = None,
              check_address: bool = True) -> ResearchSource:
    """
    Transforme la sortie brute d'un fournisseur en source normalisée.

    Args:
        raw: Ce que le fournisseur a rendu. Conservé tel quel dans
            `source_metadata`, moins les champs promus.
        provider: Le fournisseur.
        query: La requête, telle qu'écrite.
        source_type: La nature, parmi `TYPES_DE_SOURCE`.
        provider_version: La version déclarée du fournisseur.
        content: Le corps récupéré, quand il y en a un. Il est **empreinté**,
            jamais stocké ici.
        check_address: Si l'URL doit passer le garde de R06.

    Returns:
        La source normalisée.

    Raises:
        SourceRefused: URL absente, nature inconnue, ou URL refusée par le garde.

    Note:
        **Rien n'est deviné.** Un titre absent reste vide, une date absente reste
        absente ; aucune n'est dérivée d'une autre. C'est la règle que
        `AcquiredDocument` tient déjà — `publication_date` n'est jamais tirée de
        `retrieval_date`.
    """
    url = str(raw.get("url") or raw.get("source_url") or "").strip()
    if not url:
        raise SourceRefused(
            f"Le fournisseur « {provider} » a rendu un résultat sans URL. "
            "Rien ne permettrait de le recouper."
        )
    if check_address:
        verdict = check_url(url, resolve=False)
        if not verdict.allowed:
            motifs = " ; ".join(r["reason"] for r in verdict.refusals)
            raise SourceRefused(f"URL refusée par le garde : {motifs}")

    promus = {"url", "source_url", "title"}
    return ResearchSource(
        source_url=url,
        source_type=source_type,
        provider=provider,
        provider_version=provider_version,
        query=query,
        content_hash=fingerprint(content) if content else "",
        source_metadata={k: v for k, v in raw.items() if k not in promus},
        title=str(raw.get("title") or ""),
    )


def normalized_content(source: ResearchSource,
                       content: Optional[str]) -> Dict[str, Any]:
    """
    Rend le contenu d'une source **comme donnée**, avec sa provenance.

    Args:
        source: La source normalisée.
        content: Le contenu récupéré.

    Returns:
        L'enveloppe de `safety.as_data()`, plus la provenance complète.

    Note:
        Les deux voyagent ensemble et c'est le point : un contenu sans
        provenance ne peut pas être recoupé, une provenance sans enveloppe
        laisse le contenu passer pour une instruction.
    """
    enveloppe = as_data(content, source.source_url, source.provider)
    enveloppe["provenance"] = source.as_dict()
    return enveloppe


def corroborate(sources: Tuple[ResearchSource, ...]) -> Dict[str, Any]:
    """
    Compare des sources indépendantes sur un même sujet.

    Args:
        sources: Les sources rapportées, quel que soit leur fournisseur.

    Returns:
        Le nombre de **sources distinctes** — par URL, pas par résultat — le
        nombre de fournisseurs distincts, et l'état que la seule répétition
        autorise.

    Note:
        L'état vient de `promote_by_frequency()`, qui **plafonne à
        `CORROBORATED`**. Ni ce module ni aucun autre ne promeut une source
        récupérée à `VALIDATED` ou `OFFICIAL` : cela se constate ailleurs.

        Deux résultats du même fournisseur pointant la même URL comptent pour
        **un**. Sinon un fournisseur bavard corroborerait tout seul, ce qui est
        exactement l'inverse d'un recoupement.
    """
    from ..creative.language.observation import promote_by_frequency

    urls = {s.source_url for s in sources}
    fournisseurs = {s.provider for s in sources}
    etat = promote_by_frequency(len(urls))
    return {
        "distinct_sources": len(urls),
        "distinct_providers": len(fournisseurs),
        "status": etat,
        "capped_at": CORROBORE,
        "note": ("La répétition ne fait pas l'autorité : l'état plafonne à "
                 "CORROBORATED, quel que soit le compte."),
    }


def to_acquisition_candidate(source: ResearchSource) -> Dict[str, Any]:
    """
    Le pont vers le système de provenance existant (STEP 9).

    Args:
        source: La source normalisée.

    Returns:
        Les champs attendus par `acquisition.record.AcquiredDocument`, les
        inconnus laissés à `unknown` plutôt que devinés.

    Note:
        **Ceci ne crée aucun document et n'ingère rien.** C'est une projection
        de champs, offerte à qui décidera de proposer l'ingestion. Le chemin
        d'acquisition garde sa porte d'approbation humaine, et ce module ne la
        contourne pas.
    """
    from ..acquisition.record import INCONNU as ACQ_INCONNU

    return {
        "source_url": source.source_url,
        "institution": ACQ_INCONNU,
        "source_tier": ACQ_INCONNU,
        "retrieval_date": source.retrieval_timestamp,
        "content_hash": source.content_hash or ACQ_INCONNU,
        "license_or_usage_status": ACQ_INCONNU,
        "document_title": source.title or ACQ_INCONNU,
        "provenance": {
            "research_provider": source.provider,
            "research_provider_version": source.provider_version,
            "research_query": source.query,
            "research_source_type": source.source_type,
            "research_validation_status": source.validation_status,
        },
    }


def propose_for_knowledge(sources: Tuple[ResearchSource, ...]
                          ) -> Dict[str, Any]:
    """
    Propose des sources pour la connaissance — **sans rien y insérer** (STEP 7).

    Args:
        sources: Les sources retenues.

    Returns:
        Une proposition `DRAFT` : les candidats projetés vers le format
        d'acquisition, l'état de corroboration, et ce qui manque encore.

    Note:
        La directive est explicite : *« ne pas insérer automatiquement
        l'information récupérée dans la base de connaissance globale »*. Cette
        fonction **rend une proposition** et ne touche à aucun magasin. Le
        chemin d'acquisition (ADR-021) garde son approbation humaine, ses dix
        contrôles qualité et sa frontière de confiance.
    """
    if not sources:
        raise SourceRefused(
            "Une proposition sans source ne propose rien."
        )
    recoupement = corroborate(sources)
    manquants = sorted({
        champ for champ in ("institution", "source_tier",
                            "license_or_usage_status")
    })
    return {
        "state": "DRAFT",
        "ingested": False,
        "candidates": [to_acquisition_candidate(s) for s in sources],
        "corroboration": recoupement,
        "missing_before_ingestion": manquants,
        "requires_human_approval": True,
        "note": ("Rien n'est entré dans la connaissance. La porte "
                 "d'approbation humaine d'ADR-021 n'est pas contournée, et "
                 "trois champs de provenance minimale restent à établir."),
    }


def sources_report() -> Dict[str, Any]:
    """
    Ce que la normalisation garantit, et ce qu'elle refuse.

    Returns:
        Le vocabulaire et les règles tenues.
    """
    return {
        "source_types": list(TYPES_DE_SOURCE),
        "validation_states": list(ETATS),
        "unreachable_states": list(ETATS_HORS_DE_PORTEE),
        "default_state": OBSERVE,
        "reused": [
            "creative.language.observation (l'échelle de statut)",
            "creative.jobs.fingerprint (l'empreinte)",
            "acquisition.record (le format de provenance)",
            "research.safety (le garde d'URL et l'enveloppe)",
        ],
        "rules": [
            "Une confiance sans base est refusée, et l'inverse aussi.",
            "Une source récupérée ne naît jamais VALIDATED ni OFFICIAL.",
            "La corroboration compte des URL distinctes, pas des résultats : un "
            "fournisseur bavard ne se corrobore pas tout seul.",
            "`content_hash` vide veut dire « pas de contenu », jamais "
            "« contenu vide ».",
            "Rien n'entre dans la connaissance : la proposition est un DRAFT "
            "et l'approbation humaine reste requise.",
            "Aucun champ n'est déduit d'un autre.",
        ],
    }
