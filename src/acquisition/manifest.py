"""
De document vérifié à entrée de manifeste — proposée, jamais appliquée (ADR-021, étape 9).

C'est la dernière étape avant le pilote, et la plus facile à rater : il serait
simple d'appeler `ingest_file()` directement sur un document `VERIFIED`. Ce
serait une acquisition qui écrit dans la base sans que personne l'ait relue, et
le portillon de l'étape 4 n'aurait servi qu'à autoriser une requête HTTP.

## Ce que ce module produit

Une **proposition** : une entrée de manifeste en `DRAFT`, prête à être relue,
complétée et collée dans un fichier de corpus (`docs/knowledge/README.md`). Elle
n'est écrite nulle part, et aucune connaissance n'est créée.

## D'où vient chaque champ

| Champ | Origine | Pourquoi |
|---|---|---|
| `url`, `title`, `publication_date` | le document | ce qu'il dit de lui-même |
| `author`, `scope`, `subject` | **le registre** | l'autorité ne vient jamais du document |
| `language` | la **détection**, marquée comme telle | déclarée serait plus sûr ; personne ne l'a déclarée |
| `source_category` | le registre | c'est la règle du chapitre 03 |

## Ce qui reste à une personne

Confirmer la langue détectée, trancher un sujet quand la source en déclare
plusieurs, et **appliquer**. La proposition dit ce qui est incertain plutôt que
de le lisser : une entrée qui a l'air complète ne se relit pas.
"""

from typing import Any, Dict, List, Optional

from ..knowledge_engine.source_registry import load_registry
from .language import INCONNU
from .record import AcquiredDocument, AcquisitionStatus

#: Statut de toute proposition. Il n'y en a pas d'autre : ce module ne produit
#: rien qui puisse être pris pour une entrée validée.
BROUILLON = "DRAFT"


class ManifestRefused(ValueError):
    """Une proposition a été demandée pour un document qui n'est pas prêt."""


def propose(
    document: AcquiredDocument,
    *,
    registre: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Propose une entrée de manifeste pour un document vérifié.

    Args:
        document: Le document, au statut `VERIFIED`.
        registre: Registre déjà chargé.

    Returns:
        L'entrée en `DRAFT`, ce qui reste incertain, et ce que ce module ne
        décide pas. **Rien n'est écrit.**

    Raises:
        ManifestRefused: Si le document n'est pas `VERIFIED`. Proposer pour un
            document en quarantaine ferait entrer par la proposition ce que les
            contrôles ont retenu.
    """
    if document.status is not AcquisitionStatus.VERIFIED:
        raise ManifestRefused(
            f"Document au statut {document.status.value} : seul un document "
            "`VERIFIED` se propose. Proposer pour un document en quarantaine "
            "ferait entrer par la proposition ce que les contrôles ont retenu."
        )

    registre = registre or load_registry()
    inscrite = next(
        (e for e in registre["sources"] if e["name"] == document.institution), None
    )

    incertain: List[str] = []
    sujets = list(inscrite["subjects"]) if inscrite else []
    if not sujets:
        incertain.append(
            "subject : la source n'en déclare aucun au registre — à choisir à la main"
        )
    elif len(sujets) > 1:
        incertain.append(
            f"subject : la source en déclare {len(sujets)} ({', '.join(sujets)}), "
            "le premier est proposé"
        )

    langue = document.language
    if langue == INCONNU:
        langue = None
        incertain.append(
            "language : non détectée. Une langue sans liste de marqueurs — le "
            "sérère — rend `unknown`, et c'est le résultat correct"
        )
    else:
        detection = document.provenance.get("language_detection") or {}
        marque = "détectée" if detection.get("reviewed", True) else (
            "détectée par une liste **non relue par un locuteur**"
        )
        incertain.append(f"language : « {langue} » {marque}, jamais déclarée — à confirmer")

    if document.publication_date == INCONNU:
        incertain.append(
            "publication_date : inconnue. Un document officiel non daté reste un "
            "document officiel, et la lacune entre avec lui"
        )

    entree = {
        "url": document.source_url,
        "title": document.document_title if document.document_title != INCONNU else None,
        "author": document.institution,
        "publication_date": (
            document.publication_date if document.publication_date != INCONNU else None
        ),
        "source_category": inscrite["category"].value if inscrite else None,
        "scope": inscrite["scope"] if inscrite else None,
        "subject": sujets[0] if sujets else None,
        "language": langue,
        "usage": document.license_or_usage_status,
        "content_hash": document.content_hash,
        "retrieved_at": document.retrieval_date,
        "status": BROUILLON,
    }

    return {
        "status": "proposed",
        "entry": entree,
        "requires_human_confirmation": True,
        "uncertain": incertain,
        "applied": False,
        "not_decided": [
            "l'application de la proposition : elle appartient à une personne",
            "le rang et la catégorie : ils viennent du registre, jamais du document",
            "la résolution d'un désaccord : les contradictions sont rapportées, "
            "jamais résolues",
        ],
        "note": (
            "Rien n'a été écrit et aucune connaissance n'a été créée. L'entrée est "
            "à relire, à compléter, puis à ingérer avec `DocumentIngestor`."
        ),
    }


def propose_batch(
    documents: List[AcquiredDocument], registre: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Propose un manifeste pour un lot, et dit **pourquoi** chaque document écarté l'est.

    Un lot dont on ne sait pas dire ce qui n'a pas abouti n'a rien prouvé : les
    documents non vérifiés sortent avec leur statut et leur dernière raison.
    """
    registre = registre or load_registry()
    entrees, ecartes = [], []

    for document in documents:
        if document.status is not AcquisitionStatus.VERIFIED:
            ecartes.append({
                "url": document.source_url,
                "status": document.status.value,
                "reason": document.history[-1]["reason"] if document.history else "",
            })
            continue
        entrees.append(propose(document, registre=registre))

    return {
        "proposed": len(entrees),
        "entries": [proposition["entry"] for proposition in entrees],
        "uncertain": {
            proposition["entry"]["url"]: proposition["uncertain"]
            for proposition in entrees if proposition["uncertain"]
        },
        "excluded": ecartes,
        "applied": False,
        "note": (
            "Un manifeste proposé, jamais écrit. Le passage à la base reste "
            "`DocumentIngestor.ingest_file()`, après relecture humaine."
        ),
    }


def to_yaml(entrees: List[Dict[str, Any]]) -> str:
    """
    Rend le manifeste proposé sous la forme qu'une personne peut coller.

    Le rendu porte l'avertissement en tête : un fichier qui ressemble à un
    manifeste valide finit par être utilisé comme tel.
    """
    import yaml

    entete = (
        "# PROPOSITION — relire avant usage (ADR-021, étape 9).\n"
        "# Rien n'a été ingéré. Chaque entrée est en DRAFT : confirmer la langue\n"
        "# détectée, trancher le sujet, compléter ce qui manque, puis ingérer.\n"
    )
    corps = yaml.safe_dump(
        {"documents": [dict(entree) for entree in entrees]},
        allow_unicode=True, sort_keys=False,
    )
    return entete + corps


def manifest_report() -> Dict[str, Any]:
    """Décrit ce que ce module produit, et ce qu'il ne fait jamais."""
    return {
        "produces": "une entrée de manifeste en DRAFT",
        "writes_files": False,
        "creates_knowledge": False,
        "requires_status": AcquisitionStatus.VERIFIED.value,
        "fields_from_registry": ["author", "source_category", "scope", "subject"],
        "fields_from_document": ["url", "title", "publication_date", "content_hash"],
        "fields_from_measurement": ["language", "usage", "retrieved_at"],
        "note": (
            "L'autorité vient du registre, jamais du document. La langue vient "
            "d'une détection et le dit : déclarée serait plus sûr, mais personne "
            "ne l'a déclarée."
        ),
    }
