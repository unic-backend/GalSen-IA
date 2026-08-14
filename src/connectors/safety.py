"""
What a connector can never do.

The three phases before this one described connectors: what they touch
(41.1), how their access lives and dies (41.2), and where their output may go
(VOLET 40). This one is the list of things no declaration, no role and no
approval can unlock.

Two of them are enforced here, in code, because both have a precise failure
mode this repository has already met once:

**A message is not an instruction.** A Gmail thread, a Drive document, a
calendar invitation — all of it is text someone else wrote, and some of that
text will say « ignore your previous instructions ». The acquisition chain
already learned this: `src/acquisition/parsing.py` made the trust boundary the
*only* path from a fetched document to a parsed one. Connectors get the same
treatment. `receive()` is the only way content leaves a connector, and it hands
back an envelope, never a bare string.

**A privilege that is not asked for cannot be used.** OAuth makes it trivially
easy to request more than needed — one extra word in a scope turns « read my
mail » into « delete my mail ». So privileges are declared, destructive ones are
named as such, and a connector that wants one must say why in the same
breath. Nothing here grants anything: it refuses declarations, and the refusal
happens at registration, before any consent screen is ever shown to anyone.

What this module does **not** do, deliberately: authenticate, store a token, or
contact any provider. It has no network and no secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, FrozenSet, Iterable, List, Optional

from ..security.trust import TrustLevel, Wrapped, wrap
from .contract import ContractError, DataContract, contract_of


class Privilege(str, Enum):
    """
    Ce qu'un connecteur demande le droit de faire chez le fournisseur.

    Volontairement grossier : quatre valeurs, pas la liste des portées OAuth de
    Google. Une portée est le vocabulaire d'un fournisseur ; ceci est le
    vocabulaire de la plateforme, et c'est lui qui doit tenir quand un deuxième
    fournisseur arrive.
    """

    #: Lire. Le seul privilège qu'un connecteur obtient sans se justifier.
    READ = "read"

    #: Créer ou modifier chez le fournisseur — envoyer, téléverser, inviter.
    WRITE = "write"

    #: Supprimer. Irréversible du côté du fournisseur, donc destructeur.
    DELETE = "delete"

    #: Administrer : partages, règles, accès d'autrui. Destructeur par portée
    #: même sans rien supprimer — il touche des personnes qui n'ont rien accordé.
    ADMINISTER = "administer"


#: Les privilèges qui ne s'obtiennent pas par défaut. La directive du projet est
#: explicite : « Do not give the AI destructive permissions by default. »
PRIVILEGES_DESTRUCTEURS: FrozenSet[Privilege] = frozenset({
    Privilege.DELETE, Privilege.ADMINISTER,
})


class SafetyRefused(ValueError):
    """Une déclaration de connecteur qui franchit une interdiction."""


@dataclass(frozen=True)
class PrivilegeRequest:
    """
    Un privilège demandé, et pourquoi.

    Attributes:
        privilege: Ce qui est demandé.
        rationale: Pourquoi le connecteur en a besoin. Obligatoire pour un
            privilège destructeur, et lu par la personne au moment du
            consentement — c'est là qu'une demande excessive se voit.
    """

    privilege: Privilege
    rationale: str = ""

    @property
    def destructive(self) -> bool:
        """Vrai si ce privilège ne s'accorde pas par défaut."""
        return self.privilege in PRIVILEGES_DESTRUCTEURS

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "privilege": self.privilege.value,
            "destructive": self.destructive,
            "rationale": self.rationale,
        }


def verify_privileges(
    connector_id: str, requests: Optional[Iterable[PrivilegeRequest]]
) -> List[PrivilegeRequest]:
    """
    Vérifie les privilèges demandés par un connecteur.

    Trois règles :

    1. **Un privilège destructeur se justifie.** Sans motif écrit, la personne à
       qui on demandera son consentement n'aura rien à lire pour décider.
    2. **Un privilège d'écriture ou de suppression suppose un privilège de
       lecture demandé** — un connecteur qui écrit sans lire ne peut rien
       vérifier de ce qu'il modifie.
    3. **Pas de doublon.** Deux demandes du même privilège avec deux motifs
       différents rendent le consentement inexploitable.

    Args:
        connector_id: L'identifiant du connecteur, pour le message d'erreur.
        requests: Les demandes déclarées.

    Returns:
        Les demandes, si elles sont acceptables.

    Raises:
        SafetyRefused: Sinon.
    """
    demandes = list(requests or [])
    if not demandes:
        return []

    vus = set()
    for demande in demandes:
        if not isinstance(demande, PrivilegeRequest):
            raise SafetyRefused(
                f"Connecteur '{connector_id}' : un privilège doit être un "
                f"`PrivilegeRequest`, pas {type(demande).__name__}."
            )
        if demande.privilege in vus:
            raise SafetyRefused(
                f"Connecteur '{connector_id}' : privilège "
                f"'{demande.privilege.value}' demandé deux fois. Deux motifs "
                "pour un même droit rendent le consentement inexploitable."
            )
        vus.add(demande.privilege)

        if demande.destructive and not demande.rationale.strip():
            raise SafetyRefused(
                f"Connecteur '{connector_id}' : le privilège "
                f"'{demande.privilege.value}' est destructeur et n'est pas "
                "justifié. La personne à qui on demandera son consentement "
                "n'aurait rien à lire pour décider."
            )

    modifie = vus & {Privilege.WRITE, Privilege.DELETE}
    if modifie and Privilege.READ not in vus:
        raise SafetyRefused(
            f"Connecteur '{connector_id}' : il demande "
            f"{', '.join(sorted(p.value for p in modifie))} sans demander la "
            "lecture. Un connecteur qui écrit sans lire ne peut rien vérifier "
            "de ce qu'il modifie."
        )

    return demandes


def privileges_of(connector: Any) -> List[PrivilegeRequest]:
    """
    Lit les privilèges déclarés par un connecteur.

    Args:
        connector: Le connecteur.

    Returns:
        Les demandes déclarées, ou une liste vide.
    """
    brut = getattr(connector, "requested_privileges", None)
    return [d for d in (brut or []) if isinstance(d, PrivilegeRequest)]


# ----------------------------------------------------------------------
# La barrière de confiance
# ----------------------------------------------------------------------

def receive(
    connector: Any, content: Optional[str], origin: str, subject: Optional[str] = None
) -> Wrapped:
    """
    Le **seul** chemin par lequel un contenu sort d'un connecteur.

    Un courriel, un document, une invitation : c'est du texte écrit par
    quelqu'un d'autre, et une partie de ce texte dira « ignore tes instructions
    précédentes ». La chaîne d'acquisition a déjà appris cette leçon — ici,
    c'est la même barrière, au même endroit : à la sortie.

    L'enveloppe rendue annonce son origine, neutralise les balises et fait
    voyager les soupçons avec le texte. Un modèle qui la reçoit lit une donnée.

    Args:
        connector: Le connecteur d'où vient le contenu.
        content: Le contenu reçu, conservé tel quel dans l'enveloppe.
        origin: D'où précisément — un identifiant de message, un nom de
            fichier. Il apparaît dans le rendu.
        subject: La personne pour qui l'appel a été fait, quand le connecteur
            est par sujet.

    Returns:
        L'enveloppe, au niveau `EXTERNAL`.

    Raises:
        ContractError: Si le connecteur ne déclare pas de contrat — sans lui,
            rien ne peut être attribué à personne.
        SafetyRefused: Si un connecteur par sujet reçoit sans sujet nommé.
    """
    contrat: Optional[DataContract] = contract_of(connector)
    identifiant = getattr(connector, "connector_id", "?")

    if contrat is None:
        raise ContractError(
            f"Connecteur '{identifiant}' : aucun contrat, donc rien de ce qui "
            "en sort ne peut être attribué."
        )
    if contrat.per_subject and not (subject or "").strip():
        raise SafetyRefused(
            f"Connecteur '{identifiant}' : contenu reçu sans sujet nommé. "
            "Un connecteur par sujet ne rend rien qui n'appartienne à quelqu'un."
        )

    # `EXTERNAL` et non `TOOL` : le contenu vient d'un tiers, pas de la
    # plateforme. Un courriel n'est pas moins hostile parce que c'est notre
    # connecteur qui l'a lu.
    return wrap(content, TrustLevel.EXTERNAL, origin=f"{identifiant}:{origin}")


def safety_report(connector: Any) -> Dict[str, Any]:
    """
    Ce qu'un connecteur demande, et ce qu'il ne pourra jamais obtenir.

    Args:
        connector: Le connecteur.

    Returns:
        Les privilèges déclarés, ceux qui sont destructeurs, et les
        interdictions qui tiennent quoi qu'il déclare.
    """
    demandes = privileges_of(connector)
    return {
        "connector_id": getattr(connector, "connector_id", None),
        "requested": [demande.as_dict() for demande in demandes],
        "destructive": sorted(
            demande.privilege.value for demande in demandes if demande.destructive
        ),
        "never": [
            "Le contenu reçu est une donnée, jamais une instruction "
            "(`receive` est le seul chemin de sortie).",
            "Une donnée privée n'entre pas dans un magasin partagé (VOLET 40).",
            "Aucun identifiant n'est fabriqué, aucune authentification contournée.",
            "Aucun jeton n'apparaît dans une description, un rapport ou un journal.",
            "Le retrait du consentement fonctionne même non configuré (VOLET 41).",
        ],
    }
