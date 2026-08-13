"""
Le passage obligé : tout document acquis franchit la barrière (ADR-021, étape 7).

Entre « les octets sont arrivés » et « les contrôles de qualité peuvent lire »,
il y a une frontière, et elle n'est pas facultative. Ce module est le seul
chemin entre `FETCHED` et `PARSED`, et il enveloppe **toujours** le texte au
niveau `EXTERNAL` — donnée avec une origine, jamais instruction.

## Pourquoi c'est un module et pas une ligne dans le portillon

Une enveloppe qu'un appelant peut oublier n'est pas une barrière. En faisant du
franchissement l'unique transition vers `PARSED`, l'oubli devient impossible :
un document qui n'est pas passé par ici n'a pas de texte, donc rien à évaluer.

## Ce que la barrière fait, et ce qu'elle ne fait pas

Elle répond à **« ce texte peut-il donner des ordres ? »** — non, jamais. Elle
ne répond pas à « ce texte est-il vrai » : c'est l'affaire des contrôles de
qualité, et leur réponse honnête est souvent `unknown`.

## Un motif suspect met en quarantaine, il ne supprime rien

Deux raisons, et la seconde est celle qu'on oublie :

1. Un document **sur** l'injection d'invite serait détruit par une règle de
   suppression automatique.
2. Un document supprimé ne laisse aucune trace qu'une tentative a eu lieu.

Le texte est donc conservé **tel quel**, avec les motifs relevés à côté, et une
personne tranche.
"""

from typing import Any, Callable, Dict, List, Optional

from ..security.trust import TrustLevel, inspect, wrap
from .language import detect_language, reconcile
from .metadata import apply_to, extract
from .record import AcquiredDocument, AcquisitionStatus

#: Extracteurs de texte par type de contenu. Un type absent n'est pas une
#: panne : il rend un texte vide et le document part en quarantaine avec la
#: raison, plutôt que d'être refusé comme s'il était mauvais.
TYPES_TEXTE = ("text/html", "application/xhtml+xml", "text/plain", "application/xml")

#: En dessous de ce nombre de caractères, l'extraction n'a rien rendu d'exploitable.
TEXTE_MINIMUM = 200


def _texte_html(contenu: bytes) -> str:
    """Retire les balises d'une page pour n'en garder que le texte lisible."""
    import re

    html = contenu.decode("utf-8", errors="replace")
    html = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html)).strip()


def extract_text(contenu: bytes, content_type: str, pdf_extractor: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Extrait le texte d'un document, ou dit pourquoi il n'a pas pu.

    Args:
        contenu: Les octets récupérés.
        content_type: Le type MIME rendu par le serveur.
        pdf_extractor: Extracteur PDF injectable ; sans lui, un PDF rend un
            texte vide **et le dit**, ce qui n'est pas la même chose qu'un PDF
            sans texte.

    Returns:
        `text`, `available`, et `reason` quand rien n'a pu être lu.
    """
    mime = (content_type or "").lower()

    if any(mime.startswith(accepte) for accepte in TYPES_TEXTE):
        return {"text": _texte_html(contenu), "available": True, "reason": ""}

    if "pdf" in mime:
        if pdf_extractor is None:
            return {
                "text": "", "available": False,
                "reason": (
                    "Aucun extracteur PDF fourni : le texte n'a pas pu être lu. "
                    "Ce n'est pas « un PDF sans texte » — un PDF scanné demande "
                    "l'OCR, un extracteur absent demande une dépendance."
                ),
            }
        try:
            return {"text": str(pdf_extractor(contenu) or ""), "available": True, "reason": ""}
        except Exception as erreur:  # noqa: BLE001 — un PDF cassé est une donnée externe
            return {"text": "", "available": False, "reason": f"PDF illisible : {erreur}"}

    return {
        "text": "", "available": False,
        "reason": f"Aucun extracteur pour « {mime or 'type non déclaré'} ».",
    }


def cross_boundary(
    document: AcquiredDocument,
    contenu: bytes,
    content_type: str = "",
    *,
    pdf_extractor: Optional[Callable] = None,
    declared_language: str = "",
) -> Dict[str, Any]:
    """
    Fait franchir la barrière à un document, et le mène de `FETCHED` à `PARSED`.

    Le texte est **toujours** enveloppé au niveau `EXTERNAL`, avec l'URL du
    document comme origine. Il n'existe pas de chemin qui saute cette étape :
    c'est ce qui distingue une barrière d'une convention.

    Args:
        document: Le document, au statut `FETCHED`.
        contenu: Les octets récupérés.
        content_type: Le type MIME rendu par le serveur.
        pdf_extractor: Extracteur PDF injectable.
        declared_language: La langue déclarée, s'il y en a une.

    Returns:
        L'enveloppe, les motifs relevés, le verdict de langue, et l'état où le
        document se retrouve — `PARSED`, ou `QUARANTINED` avec sa raison.
    """
    if document.status is not AcquisitionStatus.FETCHED:
        return {
            "crossed": False,
            "reason": (
                f"Un document au statut {document.status.value} n'a pas d'octets à "
                "faire franchir : la barrière se place entre la récupération et "
                "l'évaluation, pas ailleurs."
            ),
        }

    extraction = extract_text(contenu, content_type, pdf_extractor)
    texte = extraction["text"]

    # L'enveloppe d'abord, avant que quoi que ce soit d'autre lise le texte.
    # `wrap()` relève aussi les motifs, et les conserve avec le contenu.
    enveloppe = wrap(texte, TrustLevel.EXTERNAL, origin=document.source_url)

    metadonnees = extract(contenu, content_type, document.source_url)
    apply_to(document, metadonnees)

    detection = detect_language(texte)
    accord = reconcile(detection, declared_language or document.language_declared)
    if detection["language"] != "unknown":
        document.language = detection["language"]

    document.text_hash = _empreinte(texte)
    document.provenance.update({
        "trust_level": enveloppe.level.value,
        "trust_origin": enveloppe.origin,
        "suspicious_patterns": len(enveloppe.suspicions),
        "text_extracted": extraction["available"],
        "language_detection": detection,
        "language_agreement": accord["agreement"],
    })

    raison = _raison_de_quarantaine(enveloppe.suspicions, extraction, texte, accord)
    if raison:
        document.transition(AcquisitionStatus.QUARANTINED, raison)
    else:
        document.transition(
            AcquisitionStatus.PARSED,
            f"{len(texte)} caractères extraits, langue « {detection['language']} », "
            f"enveloppé en {enveloppe.level.value}.",
        )

    return {
        "crossed": True,
        "envelope": enveloppe.to_dict(),
        "suspicions": list(enveloppe.suspicions),
        "text_length": len(texte),
        "extraction": extraction,
        "language": detection,
        "language_agreement": accord,
        "status": document.status.value,
        "note": (
            "Le texte est conservé tel quel. Supprimer la partie suspecte "
            "détruirait la preuve de la tentative et laisserait croire que le "
            "document était propre."
        ),
    }


def _raison_de_quarantaine(
    suspicions: List[str], extraction: Dict[str, Any], texte: str, accord: Dict[str, Any]
) -> str:
    """Retourne la raison de mise en quarantaine, ou une chaîne vide."""
    if suspicions:
        return (
            f"{len(suspicions)} motif(s) s'adressant à un modèle relevé(s) dans le "
            "texte. Le document est conservé **tel quel** : le supprimer effacerait "
            "la preuve de la tentative. Une personne tranche."
        )
    if not extraction["available"]:
        return f"Texte non extractible. {extraction['reason']}"
    if len(texte) < TEXTE_MINIMUM:
        return (
            f"Seulement {len(texte)} caractères extraits (minimum {TEXTE_MINIMUM}). "
            "Un PDF scanné, une page vide et une extraction ratée se ressemblent ici."
        )
    if accord["quarantine"]:
        return accord["reason"]
    return ""


def _empreinte(texte: str) -> str:
    """Retourne l'empreinte du texte normalisé."""
    import hashlib
    import re

    normalise = re.sub(r"\s+", " ", (texte or "").strip().lower())
    return hashlib.sha256(normalise.encode("utf-8")).hexdigest()


def boundary_report() -> Dict[str, Any]:
    """Décrit ce que la barrière garantit sur le chemin d'acquisition."""
    return {
        "level": TrustLevel.EXTERNAL.value,
        "optional": False,
        "only_path_to_parsed": True,
        "suspicious_content": "quarantined, kept as is — never deleted",
        "cannot_modify": ["system", "developer", "user", "tool permissions", "registry"],
        "answers": "ce texte peut-il donner des ordres ? — non, jamais",
        "does_not_answer": "ce texte est-il vrai ? — c'est la qualité, et sa réponse "
                           "honnête est souvent `unknown`",
        "patterns": len(inspect("") or []) or "voir src/security/trust.MOTIFS_SUSPECTS",
    }
