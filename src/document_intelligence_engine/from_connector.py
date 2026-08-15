"""
Documents that arrive from a connector — and never lose whose they are.

The document engine was written for files this platform was handed. A document
pulled from someone's Drive or mailbox is a different object in exactly one way,
and it is the way that matters: **it belongs to a person**, and nothing about its
content says so. A PDF does not carry its owner. The connector does.

That is the whole job of this module: carry ownership across the join, so that a
document arriving from Awa's drive can never be returned to Fatou's search.

Four rules, each with a failure it prevents.

**The owner comes from the connector's data contract, never from the caller.**
`DataContract.owner_of(subject)` already refuses a private scope with no subject.
Letting a caller name the owner would make the whole isolation boundary a
suggestion.

**A document from a private scope is stamped private, or it does not enter.**
The search provider (VOLET 54) withholds documents that declare nothing — which
is safe, but a document that enters undeclared is invisible rather than
protected, and invisible looks like a bug. It is stamped at the door.

**The content is EXTERNAL data.** A memo saying "ignore your previous
instructions" is a memo. It crosses the boundary through `receive()` or it does
not cross.

**A private document never enters the public knowledge base.** That rule was
written in VOLET 46 for memory; this is the same rule at the door where documents
arrive, and it is enforced by refusing the ingestion rather than by hoping the
next layer notices.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.connectors.contract import DataContract, contract_of
from src.connectors.safety import receive
from src.security.isolation import IsolationError, OwnerKind
from src.tool.capabilities import DataScope

from .types import DocumentItem, DocumentType

#: Visibilité déclarée d'un document public. La même chaîne que le fournisseur
#: de recherche lit (VOLET 54) : deux orthographes de « public » feraient un
#: document invisible que personne ne saurait expliquer.
VISIBILITE_PUBLIQUE = "public"

#: Visibilité d'un document qui appartient à quelqu'un.
VISIBILITE_PRIVEE = "private"


class IngestionRefused(ValueError):
    """Une ingestion refusée, avec sa raison."""


def _type_de(mime_type: str) -> DocumentType:
    """
    Le type de document, d'après le type MIME déclaré par le fournisseur.

    Inconnu vaut `TXT` : un type deviné faux fait échouer un chargeur, un type
    absent fait échouer l'ingestion entière.
    """
    correspondances = {
        "application/pdf": DocumentType.PDF,
        "text/markdown": DocumentType.MARKDOWN,
        "text/csv": DocumentType.CSV,
        "text/html": DocumentType.HTML,
    }
    return correspondances.get(str(mime_type or "").split(";")[0].strip(), DocumentType.TXT)


def document_from_connector(
    connector: Any,
    subject: Optional[str],
    document_id: str,
    title: str,
    content: Any,
    mime_type: str = "",
    origin: str = "",
) -> Dict[str, Any]:
    """
    Construit un document à partir de ce qu'un connecteur a rapporté.

    Args:
        connector: Le connecteur d'origine, qui porte le contrat de données.
        subject: La personne pour le compte de qui l'appel a été fait.
        document_id: L'identifiant chez le fournisseur.
        title: Le titre déclaré par le fournisseur.
        content: Le contenu rapatrié.
        mime_type: Son type, quand il est connu.
        origin: D'où il vient, pour la trace.

    Returns:
        Le document, son propriétaire, et le contenu enveloppé en donnée.

    Raises:
        IngestionRefused: Sans contrat, ou si une portée privée n'a pas de
            sujet nommé.
    """
    contrat: Optional[DataContract] = contract_of(connector)
    if contrat is None:
        raise IngestionRefused(
            "Ce connecteur ne déclare aucun contrat de données : impossible de "
            "savoir à qui appartient ce qu'il rapporte. Un document sans "
            "propriétaire est un document qui finira chez quelqu'un d'autre."
        )

    try:
        # Le propriétaire est **déduit** du contrat, jamais nommé par
        # l'appelant : le laisser choisir ferait de toute la frontière
        # d'isolation une suggestion.
        proprietaire = contrat.owner_of(subject)
    except IsolationError as refus:
        raise IngestionRefused(
            f"Propriétaire indéterminable : {refus}"
        ) from None

    prive = proprietaire.kind is OwnerKind.USER
    # `receive` est le **seul** chemin de sortie d'un connecteur (VOLET 42) :
    # il prend le connecteur lui-même, parce que c'est lui qui répond de
    # l'origine du texte.
    texte = content if isinstance(content, str) else (
        content.decode("utf-8", errors="replace") if isinstance(content, bytes)
        else str(content)
    )
    enveloppe = receive(
        connector, texte, origin=origin or f"connector:{document_id}",
        subject=subject,
    )

    document = DocumentItem(
        document_id=document_id,
        document_type=_type_de(mime_type),
        title=title or document_id,
        content=enveloppe.text,
        metadata={
            # L'origine telle que la frontière l'a écrite : elle nomme le
            # connecteur. Deux origines différentes dans le même objet
            # obligeraient à choisir laquelle croire.
            "source": enveloppe.origin,
            "mime_type": mime_type,
            # Estampillé à la porte : un document qui entre sans déclaration
            # est invisible plutôt que protégé, et invisible ressemble à un
            # bogue.
            "visibility": VISIBILITE_PRIVEE if prive else VISIBILITE_PUBLIQUE,
            "user_id": proprietaire.subject if prive else None,
            "data_scope": contrat.data_scope.value,
            "trust_level": enveloppe.level.value,
        },
    )

    return {
        "document": document,
        "owner": proprietaire.to_dict() if hasattr(proprietaire, "to_dict") else {
            "kind": proprietaire.kind.value, "subject": proprietaire.subject,
        },
        "private": prive,
        "wrapped": enveloppe,
        "note": (
            "Contenu traité comme **donnée externe** : un mémo qui dit "
            "« ignore tes instructions » est un mémo."
        ),
    }


def may_enter_knowledge_base(connector: Any) -> tuple:
    """
    Ce que ce connecteur rapporte peut-il entrer dans la base publique ?

    La règle du VOLET 46, appliquée à la porte où les documents arrivent : une
    donnée privée n'entre pas dans une base lue par tout le monde. Elle est
    refusée **ici**, plutôt qu'espérée refusée par la couche suivante.

    Args:
        connector: Le connecteur.

    Returns:
        Le verdict et sa raison.
    """
    contrat = contract_of(connector)
    if contrat is None:
        return False, (
            "Aucun contrat de données : ce qui n'a pas de propriétaire déclaré "
            "n'entre pas dans une base commune."
        )
    if contrat.data_scope is DataScope.USER_PRIVATE:
        return False, (
            "Portée privée : le contenu de la boîte ou du disque d'une personne "
            "n'entre jamais dans la base publique. C'est la règle du VOLET 46, "
            "appliquée à la porte plutôt qu'espérée plus loin."
        )
    return True, f"Portée « {contrat.data_scope.value} » : entrée possible."


def ingestion_report(connector: Any = None) -> Dict[str, Any]:
    """
    Ce que cette jonction garantit, et ce qu'elle ne fait pas.

    Args:
        connector: Un connecteur, pour rapporter son cas précis.

    Returns:
        Les règles tenues et l'état du connecteur donné.
    """
    rapport: Dict[str, Any] = {
        "rules": [
            "Le propriétaire vient du **contrat du connecteur**, jamais de "
            "l'appelant : le laisser choisir ferait de la frontière "
            "d'isolation une suggestion.",
            "Un document de portée privée est **estampillé** à la porte. Sans "
            "estampille il serait invisible plutôt que protégé, et invisible "
            "ressemble à un bogue.",
            "Le contenu est une donnée externe : un mémo qui dit « ignore tes "
            "instructions » est un mémo.",
            "Une donnée privée n'entre jamais dans la base publique — refusée "
            "ici, pas espérée refusée plus loin.",
        ],
        "does_not": [
            "Récupérer quoi que ce soit : ce module reçoit ce qu'un connecteur "
            "a rapporté, il n'appelle aucun fournisseur.",
            "Deviner un propriétaire : une portée privée sans sujet refuse.",
            "Lire un document natif Google : il n'a pas d'octets à télécharger.",
        ],
    }
    if connector is not None:
        permis, motif = may_enter_knowledge_base(connector)
        contrat = contract_of(connector)
        rapport["connector"] = {
            "contract": contrat.as_dict() if contrat else None,
            "may_enter_knowledge_base": permis,
            "reason": motif,
        }
    return rapport
