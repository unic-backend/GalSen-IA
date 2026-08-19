"""
`ProviderPrivacyPolicy` : où part la donnée, et ce qui en découle
(K07, ADR-031 décisions 3 et 4).

## Le seul type que les audits ont trouvé réellement absent

K00 a comparé la plateforme aux quinze types de registre que §11 réclame :
`ProviderRegistry` existe **deux fois**, `ModelRegistry`, `GenerationRequest`,
`ProviderCapability`, `ProviderLicense`, `ProviderCost`, `ProviderLatency` et
`ProviderAvailability` existent comme types ou comme champs. Un seul manquait —
celui-ci. §20 demande où vont les médias de la personne, s'ils sont conservés,
si l'exécution locale est possible ; rien ne pouvait l'écrire.

K01 a fourni le cas concret : `higgsfield-ai/skills` envoie invites et médias à
une API commerciale hébergée, et la plateforme n'avait aucun endroit où le noter
là où un routeur puisse en tenir compte.

## Pourquoi ce champ décide de la confiance

ADR-031 a d'abord fait dériver la confiance d'un nœud de génération de
`CreativeProvider.invocation`. C'était faux, et K04.1 l'a mesuré :
`adapt_declared()` calcule ce champ **depuis la licence du dépôt** —
`OUT_OF_PROCESS` si copyleft, `IN_PROCESS` sinon. Un fournisseur joint par HTTP
chez un tiers y ressort donc `IN_PROCESS`, et sa sortie aurait porté `TOOL`,
le niveau réservé aux composants de la plateforme.

`data_destination` répond à la question directement, et son `UNKNOWN` retombe du
côté sûr.

## Ce que ce module ne fait pas

**Il ne devine aucune valeur.** Aucun fournisseur n'a de politique aujourd'hui :
personne n'a lu ses conditions ni observé ses sockets. `UNKNOWN` est donc la
réponse honnête, et elle rend chaque nœud de génération `EXTERNAL`. C'est
inconfortable et c'est juste.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...security.trust import TrustLevel

#: Où part la donnée.
LOCAL_SEULEMENT = "LOCAL_ONLY"
HOTE_TIERS = "THIRD_PARTY_HOST"
DESTINATION_INCONNUE = "UNKNOWN"
DESTINATIONS = (LOCAL_SEULEMENT, HOTE_TIERS, DESTINATION_INCONNUE)

#: Ce qu'il advient de la donnée une fois arrivée.
AUCUNE_CONSERVATION = "NONE"
CONSERVATION_TRANSITOIRE = "TRANSIENT"
CONSERVEE = "RETAINED"
CONSERVATION_INCONNUE = "UNKNOWN"
CONSERVATIONS = (AUCUNE_CONSERVATION, CONSERVATION_TRANSITOIRE, CONSERVEE,
                 CONSERVATION_INCONNUE)

#: La force de la réponse — le même vocabulaire que le corpus applique déjà aux
#: licences, pour la même raison : une déclaration n'est pas une lecture.
AUTORITAIRE = "AUTHORITATIVE"
DECLARE = "DECLARED"
AUCUNE_PREUVE = "NONE"
PREUVES = (AUTORITAIRE, DECLARE, AUCUNE_PREUVE)


class PrivacyRefused(ValueError):
    """Une politique de confidentialité impossible telle quelle."""


@dataclass(frozen=True)
class ProviderPrivacyPolicy:
    """
    Ce qu'on sait de ce qu'un fournisseur fait des données qu'on lui envoie.

    Attributes:
        provider_id: Le fournisseur concerné.
        data_destination: Où part la donnée, parmi `DESTINATIONS`.
        host: L'hôte nommé, quand il y en a un.
        retention: Ce qu'il en advient, parmi `CONSERVATIONS`.
        local_execution_possible: `True`, `False`, ou `None` = non établi.
        accepts_personal_data: Si le fournisseur accepte contractuellement des
            données personnelles. `None` = non établi.
        verified_from: L'URL où la réponse a été lue. Vide quand rien n'a été lu.
        evidence: La force de la réponse, parmi `PREUVES`.
    """

    provider_id: str
    data_destination: str = DESTINATION_INCONNUE
    host: Optional[str] = None
    retention: str = CONSERVATION_INCONNUE
    local_execution_possible: Optional[bool] = None
    accepts_personal_data: Optional[bool] = None
    verified_from: str = ""
    evidence: str = AUCUNE_PREUVE

    def __post_init__(self) -> None:
        if not str(self.provider_id).strip():
            raise PrivacyRefused("Une politique sans fournisseur ne s'applique "
                                 "à rien.")
        for valeur, declarees, nom in (
            (self.data_destination, DESTINATIONS, "destination"),
            (self.retention, CONSERVATIONS, "conservation"),
            (self.evidence, PREUVES, "preuve"),
        ):
            if valeur not in declarees:
                raise PrivacyRefused(
                    f"{nom.capitalize()} « {valeur} » non déclarée. Déclarées : "
                    f"{list(declarees)}."
                )
        if self.data_destination == HOTE_TIERS and not self.host:
            raise PrivacyRefused(
                "Une destination tierce sans hôte nommé ne se vérifie pas : "
                "« ailleurs » n'est pas une réponse."
            )
        if self.evidence != AUCUNE_PREUVE and not self.verified_from:
            raise PrivacyRefused(
                f"Une preuve « {self.evidence} » sans source ne se recoupe pas."
            )

    @property
    def trust_level(self) -> TrustLevel:
        """
        Le niveau de confiance de ce qui revient de ce fournisseur.

        `LOCAL_ONLY` rend `TOOL`. Tout le reste — hôte tiers **et inconnu** —
        rend `EXTERNAL` : une destination non établie n'est pas une permission,
        et se tromper du côté sévère coûte une vérification de trop, tandis que
        l'autre côté fait passer du contenu tiers pour une sortie de la
        plateforme.
        """
        if self.data_destination == LOCAL_SEULEMENT:
            return TrustLevel.TOOL
        return TrustLevel.EXTERNAL

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "provider_id": self.provider_id,
            "data_destination": self.data_destination,
            "host": self.host,
            "retention": self.retention,
            "local_execution_possible": self.local_execution_possible,
            "accepts_personal_data": self.accepts_personal_data,
            "verified_from": self.verified_from,
            "evidence": self.evidence,
            "trust_level": self.trust_level.value,
        }


def unknown_policy(provider_id: str) -> ProviderPrivacyPolicy:
    """
    La politique d'un fournisseur dont personne n'a rien établi.

    Args:
        provider_id: Le fournisseur.

    Returns:
        Une politique entièrement `UNKNOWN`. C'est l'état de **tous** les
        fournisseurs de ce dépôt aujourd'hui, et le rendre explicitement vaut
        mieux que l'absence de politique, qui se lit comme une absence de
        problème.
    """
    return ProviderPrivacyPolicy(provider_id=provider_id)


def may_send_personal_reference(policy: ProviderPrivacyPolicy) -> Dict[str, Any]:
    """
    Dit si une référence à une personne réelle peut partir chez ce fournisseur.

    Args:
        policy: La politique du fournisseur.

    Returns:
        `allowed` et `reason`. Le refus nomme **le geste qui le lève** : lire
        les conditions, ou installer le fournisseur et observer ses sockets.

    Note:
        C'est la porte que K02 a posée pour les licences, appliquée à la
        confidentialité : **`UNKNOWN` n'est pas une permission**. Le visage de
        quelqu'un ne part pas chez un hôte que personne n'a vérifié, faute
        précisément que personne ne l'ait vérifié.
    """
    if policy.data_destination == LOCAL_SEULEMENT:
        return {"allowed": True, "reason": ""}
    if policy.data_destination == DESTINATION_INCONNUE:
        return {
            "allowed": False,
            "reason": (f"La destination des données de « {policy.provider_id} » "
                       "n'est pas établie. Lire ses conditions, ou l'installer "
                       "et observer s'il ouvre une socket, lève ce refus."),
        }
    if policy.accepts_personal_data is True:
        return {"allowed": True, "reason": ""}
    return {
        "allowed": False,
        "reason": (f"« {policy.provider_id} » envoie à « {policy.host} » et "
                   "rien n'établit qu'il accepte des données personnelles."),
    }


def privacy_report() -> Dict[str, Any]:
    """
    Ce que la politique de confidentialité déclare, et ce qu'elle refuse.

    Returns:
        Les vocabulaires déclarés et les règles tenues.
    """
    return {
        "destinations": list(DESTINATIONS),
        "retentions": list(CONSERVATIONS),
        "evidence_levels": list(PREUVES),
        "trust_mapping": {
            LOCAL_SEULEMENT: TrustLevel.TOOL.value,
            HOTE_TIERS: TrustLevel.EXTERNAL.value,
            DESTINATION_INCONNUE: TrustLevel.EXTERNAL.value,
        },
        "rules": [
            "UNKNOWN retombe sur EXTERNAL : une destination non établie n'est "
            "pas une permission.",
            "Une destination tierce sans hôte nommé est refusée.",
            "Une preuve sans source est refusée.",
            "Aucune valeur n'est devinée : aujourd'hui tout est UNKNOWN.",
        ],
    }
