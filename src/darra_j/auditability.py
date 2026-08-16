"""
Answering "why did the system say that?" all the way back to a signed document.

Directive XXXVII asks for institutional auditability, and an education ministry
means something specific by it. Not "there are logs." The question a curriculum
audit actually asks is: *this sentence was shown to a child — who decided it?*
An answer that stops at "the retrieval matched unit u-10" has not answered it.

So a curriculum trail is a chain with a person at the end:

    answer → checks that passed → unit → version → publication decision
           → the human who took it → source document → authority

Two properties make it an audit rather than a story.

**It stops where the evidence stops.** A missing link is reported as missing,
by name. A trail that quietly omits the publication decision because nobody
recorded one would read as complete, and the one thing an auditor needs to know
is precisely whether a human signed off.

**It never names a child.** Learner references pass through
`privacy.redact_learner` before they enter a trail, because an audit trail that
names children is an audit trail nobody can hand to an inspector. The digest is
stable, so one learner stays followable through an entire incident.

The trail reuses what already exists — `registry.provenance_of`,
`registry.history`, and the platform's `/observability/trail/{id}` shape — rather
than opening a second place where the truth about a decision is kept.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .firewall import CANONIQUE, answer
from .privacy import redact_learner
from .registry import TROUVE, CurriculumRegistry
from .resolution import CurriculumQuery

#: Les maillons qu'une piste de curriculum doit porter. Un maillon absent est
#: **nommé** : une piste qui omet la décision de publication se lirait comme
#: complète alors que c'est justement ce qu'un auditeur vient vérifier.
MAILLONS = (
    "answer", "checks", "unit", "version", "publication_decision",
    "decided_by", "source_document", "authority",
)

#: L'état d'un maillon.
PRESENT = "PRESENT"
ABSENT = "MISSING"


def curriculum_trail(
    unit_id: str,
    registry: CurriculumRegistry,
    viewer_ref: str = "",
    subject_ref: str = "",
) -> Dict[str, Any]:
    """
    Remonte d'un enregistrement jusqu'à la personne qui l'a publié.

    Args:
        unit_id: L'unité citée dans la réponse.
        registry: Le registre.
        viewer_ref: Qui a posé la question, si un apprenant est concerné.
        subject_ref: L'apprenant concerné, s'il y en a un.

    Returns:
        La chaîne complète, maillon par maillon, avec ceux qui manquent
        **nommés**. Les références d'apprenant sont réduites à leur empreinte :
        une piste qui nomme des enfants est une piste qu'on ne peut remettre à
        personne.
    """
    provenance = registry.provenance_of(unit_id)
    if provenance.get("status") != TROUVE:
        return {
            "unit_id": unit_id,
            "complete": False,
            "links": {"unit": _maillon(ABSENT, "Unité inconnue du registre.")},
            "missing": [nom for nom in MAILLONS if nom != "unit"],
            "reason": (
                "Aucune piste : l'unité citée n'existe pas dans le registre. "
                "Reconstruire une chaîne plausible ici serait fabriquer une "
                "décision institutionnelle."
            ),
        }

    version = provenance.get("version") or {}
    decision = _decision_de_publication(registry, version.get("version_id", ""))

    maillons = {
        "unit": _maillon(PRESENT, provenance["unit"]["official_title"],
                         content_hash=provenance["unit"]["content_hash"]),
        "version": _maillon(
            PRESENT if version else ABSENT,
            version.get("version_id", "Version absente du registre."),
            status=version.get("status"),
        ),
        "publication_decision": _maillon(
            PRESENT if decision else ABSENT,
            decision.get("action", "Aucune décision de publication consignée.")
            if decision else
            "Aucune décision de publication consignée.",
        ),
        "decided_by": _maillon(
            PRESENT if decision and decision.get("decided_by") else ABSENT,
            (decision or {}).get("decided_by")
            or "Aucun décideur nommé : c'est exactement ce qu'un auditeur vient "
               "vérifier.",
        ),
        "source_document": _maillon(
            PRESENT if provenance.get("source_document") else ABSENT,
            provenance.get("source_document") or "Aucun document source.",
            document_hash=provenance.get("document_hash"),
        ),
        "authority": _maillon(
            PRESENT if provenance.get("authority") else ABSENT,
            provenance.get("authority") or "Aucune autorité déclarée.",
            source_tier=provenance.get("source_tier"),
        ),
    }

    manquants = [nom for nom, lien in maillons.items() if lien["state"] == ABSENT]

    piste: Dict[str, Any] = {
        "unit_id": unit_id,
        "complete": not manquants,
        "links": maillons,
        "missing": manquants,
        "is_official": provenance.get("is_official", False),
        "reason": (
            "Chaîne complète : la réponse remonte à un document publié par une "
            "autorité nommée, sur décision d'une personne nommée."
            if not manquants else
            "Chaîne incomplète. Les maillons manquants sont nommés : une piste "
            "qui les tairait se lirait comme complète."
        ),
    }
    if subject_ref or viewer_ref:
        piste["viewer"] = redact_learner(viewer_ref)
        piste["subject"] = redact_learner(subject_ref)
        piste["privacy_note"] = (
            "Références réduites à leur empreinte : une piste qui nomme des "
            "enfants est une piste qu'on ne peut remettre à personne."
        )
    return piste


def _maillon(etat: str, valeur: str, **extra: Any) -> Dict[str, Any]:
    """Un maillon de la chaîne, avec son état."""
    return {"state": etat, "value": valeur, **extra}


def _decision_de_publication(
    registry: CurriculumRegistry, version_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrouve, dans le journal du registre, la décision de publication.

    Les clés sont celles que `CurriculumRegistry._consigner` écrit réellement —
    `action`, `vers`, `decided_by`. Les deviner (`from`/`to`) aurait produit une
    recherche qui ne trouve jamais rien, et donc une piste qui déclare en
    silence qu'aucun décideur n'a été consigné.
    """
    if not version_id:
        return None
    for entree in registry.history(limit=1000):
        if entree.get("target") != version_id:
            continue
        if entree.get("action") == "version_advanced" and \
                entree.get("vers") == "PUBLISHED":
            return {**entree, "action": "version_advanced → published"}
    return None


def explain_answer(
    query: CurriculumQuery, registry: CurriculumRegistry,
) -> Dict[str, Any]:
    """
    Répond à « pourquoi le système a-t-il dit cela ? ».

    Args:
        query: La question posée.
        registry: Le registre.

    Returns:
        La réponse, **les vérifications franchies ou non**, et la piste jusqu'au
        document. Un refus est audité aussi : savoir pourquoi le système n'a
        rien dit vaut autant que savoir pourquoi il a dit quelque chose.
    """
    reponse = answer(query, registry)
    audit: Dict[str, Any] = {
        "answer_type": reponse.get("answer_type"),
        "checks": reponse.get("checks", []),
        "failed_checks": [
            verification["check"] for verification in reponse.get("checks", [])
            if not verification["passed"]
        ],
        "reason": reponse.get("reason", ""),
    }
    if reponse.get("answer_type") == CANONIQUE:
        audit["trail"] = curriculum_trail(reponse["unit_id"], registry)
    else:
        audit["trail"] = None
        audit["note"] = (
            "Un refus est audité aussi : savoir pourquoi le système n'a rien "
            "dit vaut autant que savoir pourquoi il a dit quelque chose."
        )
    return audit


def auditability_report() -> Dict[str, Any]:
    """
    Ce que la piste institutionnelle garantit, et ce qu'elle refuse.

    Returns:
        Les maillons, les états, et les règles tenues.
    """
    return {
        "links": list(MAILLONS),
        "link_states": [PRESENT, ABSENT],
        "rules": [
            "Une piste de curriculum finit sur une **personne** : « la "
            "récupération a trouvé u-10 » ne répond pas à « qui l'a décidé ».",
            "Un maillon absent est **nommé** : une piste qui tairait la "
            "décision de publication se lirait comme complète.",
            "Un refus est audité comme une réponse — les vérifications non "
            "franchies sont rendues.",
            "Aucune référence d'apprenant en clair : une piste qui nomme des "
            "enfants ne peut être remise à personne.",
            "La piste réutilise le registre et son journal : une seconde source "
            "de vérité sur une décision serait une seconde chose à contredire.",
        ],
        "does_not": [
            "Reconstruire une chaîne plausible pour une unité inconnue.",
            "Supposer un décideur quand aucun n'a été consigné.",
            "Écrire le nom d'un élève dans une trace.",
            "Tenir un journal parallèle à celui du registre.",
        ],
    }
