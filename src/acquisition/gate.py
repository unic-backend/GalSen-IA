"""
Le portillon : décider, faire approuver, puis seulement récupérer (ADR-021, étape 4).

Les trois pièces existaient et ne se touchaient pas : `plan_collection()` décide,
le portillon d'ADR-006 fait approuver, `fetcher.fetch()` récupère. Rien ne
garantissait l'**ordre**, et un ordre non garanti n'est pas un ordre.

## Ce que ce module rend impossible

1. **Récupérer sans avoir décidé.** La décision est prise pour chaque URL avant
   qu'une seule requête parte. Décider après avoir téléchargé rend la décision
   décorative : la requête est déjà arrivée chez quelqu'un.
2. **Récupérer sans approbation.** Un lot sans demande, avec une demande en
   attente, ou avec une demande refusée, ne récupère rien.
3. **Réutiliser une approbation ailleurs.** L'approbation porte l'empreinte du
   lot exact — mêmes URL, même source, même licence. Ajouter une URL après
   l'accord change l'empreinte et invalide l'accord. Sans cela, « approuver
   trois documents de l'ANSD » autoriserait n'importe quoi.

## L'approbation est par lot, et c'est délibéré

Trente demandes se cliquent sans être lues. Une demande — *N documents, de cette
source, sous cette licence* — est un portillon qu'une personne exerce vraiment.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ..knowledge_engine.collection import plan_collection
from ..knowledge_engine.source_registry import RANGS_ACQUERABLES, load_registry
from .fetcher import FetchRefused, fetch
from .record import AcquiredDocument, AcquisitionStatus

#: Agent au nom duquel la demande d'approbation est déposée.
AGENT = "acquisition"

#: Action déclarée au portillon. Une action nommée est une action qu'on peut
#: retrouver dans le journal d'audit.
ACTION = "collect_document_batch"


class GateRefused(ValueError):
    """La récupération est refusée : la décision, l'approbation ou l'ordre manque."""


def _maintenant() -> str:
    """Retourne l'instant courant en ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def _empreinte(source: str, licence: str, urls: List[str]) -> str:
    """
    Empreinte d'un lot : ce sur quoi l'approbation porte exactement.

    Trier les URL rend l'empreinte indépendante de l'ordre de découverte ; en
    ajouter une après l'accord la change, et l'accord ne vaut plus.
    """
    matiere = "|".join([source, licence] + sorted(urls))
    return hashlib.sha256(matiere.encode("utf-8")).hexdigest()[:32]


@dataclass
class CollectionBatch:
    """Un lot de documents décidés ensemble, approuvés ensemble."""

    source_name: str
    licence: str
    usage: str = ""
    documents: List[AcquiredDocument] = field(default_factory=list)
    refused: List[Dict[str, str]] = field(default_factory=list)
    fingerprint: str = ""
    approval_id: Optional[str] = None

    @property
    def urls(self) -> List[str]:
        """Les URL encore candidates, dans l'ordre où elles ont été décidées."""
        return [document.source_url for document in self.documents]

    def to_dict(self) -> Dict[str, Any]:
        """Retourne le lot sous une forme sérialisable."""
        return {
            "source": self.source_name,
            "licence": self.licence,
            "usage": self.usage,
            "candidates": len(self.documents),
            "refused": list(self.refused),
            "fingerprint": self.fingerprint,
            "approval_id": self.approval_id,
            "documents": [document.to_dict() for document in self.documents],
        }


def plan_batch(
    urls: List[str],
    licence: str = "",
    robots_txt: str = "",
    agent: str = "*",
    registre: Optional[Dict[str, Any]] = None,
) -> CollectionBatch:
    """
    Décide, URL par URL, **avant** que la moindre requête parte.

    Args:
        urls: Les adresses candidates.
        licence: Licence déclarée pour ce lot. Vide = inconnue → `reference_only`.
        robots_txt: Le fichier du domaine, déjà récupéré.
        agent: L'agent déclaré, pour lire `robots.txt`.
        registre: Registre déjà chargé.

    Returns:
        Le lot : les candidats retenus en `DISCOVERED`, les autres **déjà
        refusés avec leur raison**. Rien n'est téléchargé ici.

    Raises:
        GateRefused: Si le lot est vide, ou si ses URL relèvent de sources
            différentes — une approbation porte sur *une* source, sinon la
            personne qui approuve ne sait pas ce qu'elle approuve.
    """
    if not urls:
        raise GateRefused("Un lot vide n'a rien à faire approuver.")

    registre = registre or load_registry()
    lot = CollectionBatch(source_name="", licence=licence.strip() or "inconnue")
    sources: set = set()

    for url in urls:
        plan = plan_collection(
            url, licence=licence, robots_txt=robots_txt, agent=agent, registre=registre
        )
        if not plan["allowed"]:
            lot.refused.append({"url": url, "reason": plan["reason"]})
            continue

        sources.add(plan["source"])
        lot.usage = plan["usage"]
        lot.documents.append(_candidat(url, plan, registre))

    if len(sources) > 1:
        raise GateRefused(
            "Un lot mélange plusieurs sources : "
            + ", ".join(sorted(sources))
            + ". Une approbation porte sur une source, sinon la personne qui "
            "approuve ne sait pas ce qu'elle approuve."
        )

    lot.source_name = next(iter(sources), "")
    lot.fingerprint = _empreinte(lot.source_name, lot.licence, lot.urls)
    return lot


def _candidat(url: str, plan: Dict[str, Any], registre: Dict[str, Any]) -> AcquiredDocument:
    """Assemble l'enregistrement d'un candidat retenu, avec ce que le registre sait déjà."""
    inscrite = next(
        (e for e in registre["sources"] if e["name"] == plan["source"]), None
    )
    return AcquiredDocument(
        source_url=url,
        institution=plan["source"],
        source_tier=inscrite["tier"].value if inscrite else "unknown",
        country=inscrite["country"] if inscrite else "unknown",
        domain=inscrite["domain"] if inscrite else "unknown",
        license_or_usage_status=plan["usage"],
        provenance={
            "scope": plan["scope"],
            "registry_category": plan["category"],
            "licence_declared": plan["licence"],
        },
    )


def submit_batch(context: Any, lot: CollectionBatch) -> Optional[str]:
    """
    Dépose **une** demande d'approbation pour tout le lot.

    Args:
        context: Objet portant `submit_approval(action, description, metadata)`.
        lot: Le lot rendu par `plan_batch`.

    Returns:
        L'identifiant de la demande, retenu sur le lot.

    Raises:
        GateRefused: Si le lot ne contient aucun candidat. Faire approuver zéro
            document donnerait une approbation sans objet, réutilisable.
    """
    if not lot.documents:
        raise GateRefused(
            "Aucun candidat retenu : il n'y a rien à approuver, et une approbation "
            "sans objet serait une approbation réutilisable."
        )

    lot.approval_id = context.submit_approval(
        action=ACTION,
        description=(
            f"Récupérer {len(lot.documents)} document(s) depuis {lot.source_name} "
            f"(licence : {lot.licence}, usage : {lot.usage})."
        ),
        metadata={
            "source": lot.source_name,
            "licence": lot.licence,
            "usage": lot.usage,
            "count": len(lot.documents),
            "fingerprint": lot.fingerprint,
            "urls": list(lot.urls),
        },
    )
    return lot.approval_id


def _verifier_l_approbation(lot: CollectionBatch, demande: Any) -> None:
    """
    Vérifie que l'accord existe, qu'il est donné, et qu'il porte sur **ce** lot.

    Raises:
        GateRefused: Avec la raison exacte — absente, en attente, refusée, ou
            portant sur autre chose.
    """
    if lot.approval_id is None:
        raise GateRefused(
            "Aucune approbation n'a été demandée pour ce lot. La décision précède "
            "la requête, et l'accord précède la récupération."
        )
    if demande is None:
        raise GateRefused(f"Approbation « {lot.approval_id} » introuvable.")

    statut = str(getattr(demande, "status", "") or "")
    if statut != "approved":
        raise GateRefused(
            f"Approbation « {lot.approval_id} » au statut « {statut or 'inconnu'} » : "
            "seul « approved » ouvre la récupération."
        )

    empreinte = (getattr(demande, "metadata", None) or {}).get("fingerprint")
    if empreinte != lot.fingerprint:
        raise GateRefused(
            "L'approbation ne porte pas sur ce lot : son empreinte diffère. "
            "Ajouter une URL après l'accord ne l'étend pas — cela l'invalide."
        )


def acquire(
    lot: CollectionBatch,
    manager: Any,
    *,
    allowed_content_types: Optional[List[str]] = None,
    robots_txt: Optional[str] = None,
    rate_limit_rps: float = 0.2,
    fetch_fn: Callable[..., Any] = fetch,
) -> Dict[str, Any]:
    """
    Récupère les documents d'un lot **approuvé**, et seulement ceux-là.

    Args:
        lot: Le lot, déjà soumis au portillon.
        manager: Le gestionnaire d'approbations (`get(request_id)`).
        allowed_content_types: Types déclarés par la source au registre.
        robots_txt: Le fichier du domaine, si déjà connu.
        rate_limit_rps: Débit autorisé pour cet hôte.
        fetch_fn: Le récupérateur, injectable pour les tests.

    Returns:
        Le compte de ce qui a été récupéré, **les octets sous `contents`** pour
        que l'appelant les fasse franchir la barrière, et ce qui a échoué —
        chaque échec avec sa raison.

    Raises:
        GateRefused: Approbation absente, non accordée, ou portant sur un autre
            lot. **Aucune requête n'est envoyée dans ces cas.**
    """
    _verifier_l_approbation(lot, manager.get(lot.approval_id))

    recuperes, echecs, contenus = 0, [], {}
    for document in lot.documents:
        if document.status is not AcquisitionStatus.DISCOVERED:
            continue
        try:
            resultat = fetch_fn(
                document.source_url,
                allowed_content_types=allowed_content_types,
                robots_txt=robots_txt,
                rate_limit_rps=rate_limit_rps,
            )
        except FetchRefused as refus:
            document.transition(AcquisitionStatus.REJECTED, str(refus))
            echecs.append({"url": document.source_url, "reason": str(refus)})
            continue

        # Les octets sont rendus à l'appelant, jamais rangés dans
        # l'enregistrement : un contenu de plusieurs mégaoctets dans un objet
        # qu'on sérialise et journalise finirait par être recopié partout.
        contenus[document.source_url] = {
            "body": resultat.body, "content_type": resultat.content_type,
        }
        # La date de récupération est **ici** qu'elle se pose : c'est le moment
        # où le document a été reçu. Elle manquait, et comme elle fait partie de
        # la provenance minimale, aucun document n'atteignait jamais `VERIFIED`
        # — un défaut que seul un passage de bout en bout pouvait montrer.
        document.retrieval_date = _maintenant()
        document.provenance["approval_id"] = lot.approval_id
        document.provenance["http_status"] = resultat.status
        document.content_hash = hashlib.sha256(resultat.body).hexdigest()
        document.document_type = resultat.content_type
        document.transition(
            AcquisitionStatus.FETCHED,
            f"HTTP {resultat.status}, {resultat.size} octets, {resultat.content_type}.",
        )
        recuperes += 1

    return {
        "source": lot.source_name,
        "approval_id": lot.approval_id,
        "fetched": recuperes,
        "contents": contenus,
        "failed": echecs,
        "refused_before_fetch": list(lot.refused),
        "note": (
            "La décision précède la requête, et l'accord précède la récupération. "
            "Les documents refusés au plan n'ont jamais été demandés au serveur."
        ),
    }


def gate_report(registre: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Décrit l'état du portillon d'acquisition, sans rien acquérir."""
    registre = registre or load_registry()
    activees = [e for e in registre["sources"] if e["enabled"]]
    return {
        "action": ACTION,
        "agent": AGENT,
        "approval_scope": "un lot, une source, une licence",
        "enabled_sources": [e["name"] for e in activees],
        "acquirable_sources": [
            e["name"] for e in activees if e["tier"] in RANGS_ACQUERABLES
        ],
        "note": (
            "Une approbation porte l'empreinte de son lot : ajouter une URL après "
            "l'accord l'invalide au lieu de l'étendre."
        ),
    }
