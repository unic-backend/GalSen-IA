"""
The connector data contract: what a connector touches, and on whose behalf.

The existing `Connector` contract (ADR-007) answers three questions without
performing any business action: who are you, are you configured, do you answer.
That was enough while every connector spoke to a *machine* — an SMTP relay, an
object store — with the platform's own credentials.

The Google connectors do not. Gmail, Drive and Calendar read **a person's**
data, and two questions the old contract never asked become the whole problem:

- **What class of data does this connector reach?** The isolation boundary
  (`src/security/isolation.py`) derives ownership from that answer, so a caller
  cannot label a private message as public.
- **On whose behalf?** A connector reading one mailbox is bound to one subject.
  A connector that reaches private data without being bound to anyone cannot
  isolate anything — there is no one to isolate it *for*.

This module makes both answers **mandatory and checked at registration**, using
the same vocabulary as the tool registry so the two never drift apart. A
connector that does not declare its contract is not registered: an undeclared
integration is exactly the kind that later turns out to have been reading
everything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional

from ..security.isolation import Owner, owner_for
from ..tool.capabilities import DataScope, Effect


class ContractError(ValueError):
    """Un contrat de connecteur absent ou incohérent. Levé à l'enregistrement."""


@dataclass(frozen=True)
class DataContract:
    """
    Ce qu'un connecteur touche, et ce qu'il en conserve.

    Attributes:
        data_scope: La classe de données atteinte, au vocabulaire des capacités
            d'outils. C'est elle qui décide de la propriété de tout ce que le
            connecteur rend.
        per_subject: Le connecteur agit-il pour le compte d'une personne nommée ?
        effects: Ce que le connecteur fait au monde.
        retention: Ce que le connecteur garde après un appel, en clair. « rien »
            est une réponse valide et c'est la meilleure ; le silence n'en est
            pas une.
        rationale: Pourquoi ce contrat est celui-là.
    """

    data_scope: DataScope
    per_subject: bool
    effects: FrozenSet[Effect]
    retention: str
    rationale: str = ""

    def owner_of(self, subject: Optional[str] = None) -> Owner:
        """
        Le propriétaire de ce que ce connecteur rend.

        Args:
            subject: Le sujet pour le compte de qui l'appel a été fait.

        Returns:
            Le propriétaire, déduit de la portée déclarée.

        Raises:
            IsolationError: Si la portée est privée sans sujet nommé.
        """
        return owner_for(self.data_scope, subject)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, pour l'API et l'audit."""
        return {
            "data_scope": self.data_scope.value,
            "per_subject": self.per_subject,
            "effects": sorted(effet.value for effet in self.effects),
            "retention": self.retention,
            "rationale": self.rationale,
        }


def verify_contract(connector_id: str, contract: Any) -> DataContract:
    """
    Vérifie le contrat d'un connecteur, ou refuse l'enregistrement.

    Quatre règles. Les deux premières sont les seules qui comptent vraiment ;
    les deux autres empêchent une déclaration de ne rien dire.

    1. **Portée privée et lien à une personne vont ensemble, dans les deux
       sens.** Un connecteur qui atteint la donnée de quelqu'un sans être lié à
       quelqu'un n'isole rien — il n'y a personne pour qui isoler. Et un
       connecteur lié à une personne qui se déclare public ferait entrer cette
       personne dans le magasin commun.
    2. **Un connecteur privé dit ce qu'il conserve.** Le silence sur la
       rétention est la façon la plus courante de garder des données sans
       l'avoir décidé.
    3. Les effets sont déclarés et non vides.
    4. Le contrat existe.

    Args:
        connector_id: L'identifiant du connecteur, pour le message d'erreur.
        contract: Le contrat déclaré.

    Returns:
        Le contrat, s'il est cohérent.

    Raises:
        ContractError: Sinon.
    """
    if contract is None:
        raise ContractError(
            f"Connecteur '{connector_id}' : aucun contrat de données déclaré. "
            "Une intégration non déclarée est exactement celle dont on découvre "
            "plus tard qu'elle lisait tout."
        )
    if not isinstance(contract, DataContract):
        raise ContractError(
            f"Connecteur '{connector_id}' : le contrat doit être un "
            f"`DataContract`, pas {type(contract).__name__}."
        )

    prive = contract.data_scope is DataScope.USER_PRIVATE
    if prive and not contract.per_subject:
        raise ContractError(
            f"Connecteur '{connector_id}' : il atteint la donnée d'une personne "
            "sans être lié à une personne. Il n'y a personne pour qui isoler."
        )
    if contract.per_subject and not prive:
        raise ContractError(
            f"Connecteur '{connector_id}' : il est lié à une personne mais se "
            f"déclare '{contract.data_scope.value}'. Cette donnée entrerait "
            "dans le magasin commun."
        )
    if prive and not contract.retention.strip():
        raise ContractError(
            f"Connecteur '{connector_id}' : un connecteur privé doit dire ce "
            "qu'il conserve. Le silence sur la rétention est la façon la plus "
            "courante de garder des données sans l'avoir décidé."
        )
    if not contract.effects:
        raise ContractError(
            f"Connecteur '{connector_id}' : les effets doivent être déclarés."
        )

    return contract


def contract_of(connector: Any) -> Optional[DataContract]:
    """
    Lit le contrat d'un connecteur, sans exiger qu'il en ait un.

    Args:
        connector: Le connecteur.

    Returns:
        Son contrat, ou `None` s'il n'en déclare aucun.
    """
    contrat = getattr(connector, "data_contract", None)
    return contrat if isinstance(contrat, DataContract) else None


def conformance(connector: Any) -> Dict[str, Any]:
    """
    Ce qu'un connecteur respecte du contrat, et ce qu'il laisse en blanc.

    Utilisé par les tests et par l'API. Le rapport **nomme les manques** : un
    connecteur incomplet y apparaît au lieu de passer pour conforme.

    Args:
        connector: Le connecteur à examiner.

    Returns:
        Le détail des obligations, et le verdict global.
    """
    obligations: Dict[str, bool] = {}
    manques: List[str] = []

    for nom in ("connector_id", "kind", "describe", "is_configured", "check"):
        present = hasattr(connector, nom)
        obligations[nom] = present
        if not present:
            manques.append(nom)

    contrat = contract_of(connector)
    obligations["data_contract"] = contrat is not None
    if contrat is None:
        manques.append("data_contract")

    coherent = True
    raison = ""
    if contrat is not None:
        try:
            verify_contract(getattr(connector, "connector_id", "?"), contrat)
        except ContractError as erreur:
            coherent = False
            raison = str(erreur)
            manques.append("contrat incohérent")

    return {
        "connector_id": getattr(connector, "connector_id", None),
        "obligations": obligations,
        "contract": contrat.as_dict() if contrat else None,
        "coherent": coherent,
        "reason": raison,
        "missing": manques,
        "conformant": not manques,
    }
