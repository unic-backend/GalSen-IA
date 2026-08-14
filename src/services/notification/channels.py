"""
Delivery channels: where a notification can go, and where it will not.

Until now a notification went into the platform's own store and stopped there.
That is a real channel — it is what the six existing routes read — but it is the
only one, and it requires someone to come and look. The events wave III added
are precisely the ones nobody is sitting in front of: a routine stopping at
three in the morning is not read by someone who is already reading.

This module declares the channels, states which of them can actually run, and
refuses two things.

**A channel without credentials never claims to have sent anything.** It reports
`NOT_CONFIGURED` with the exact variables it is missing. No credential is
fabricated, no default endpoint is invented, and nothing is read from anywhere
but the environment. An unconfigured channel that reported "delivered" would be
the worst possible outcome: the platform would believe someone had been warned.

**A shared destination never carries someone's private notification.** A team
room or a supervision endpoint is read by more people than the person a
notification is addressed to. What belongs to the platform goes there; what
belongs to a person does not — the same boundary as everywhere else (VOLET 40),
applied at the point where content leaves the machine.

Channels are declared in `config/notifications/channels.yaml`: adding one must
not require touching this file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

#: Fichier de déclaration des canaux, relatif à la racine du dépôt.
FICHIER_CANAUX = Path(__file__).resolve().parents[3] / "config" / "notifications" / "channels.yaml"


class ChannelState(str, Enum):
    """Ce qu'un canal peut faire, réellement."""

    #: Utilisable maintenant.
    AVAILABLE = "AVAILABLE"

    #: Déclaré, écrit, et sans les identifiants nécessaires. Ce n'est pas une
    #: panne : c'est l'état normal d'un canal que personne n'a encore branché.
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass
class DeliveryChannel:
    """
    Un canal déclaré.

    Attributes:
        channel_id: Son identifiant.
        description: Ce qu'il est, en clair.
        kind: `internal` (la boîte de la plateforme) ou `external`.
        shared: Vrai si sa destination est lue par plus de monde que le
            destinataire d'une notification.
        requires: Les variables d'environnement nécessaires. **Leurs noms
            seulement** : leurs valeurs ne sont ni lues, ni journalisées, ni
            rapportées.
    """

    channel_id: str
    description: str
    kind: str = "external"
    shared: bool = False
    requires: List[str] = field(default_factory=list)

    @property
    def missing(self) -> List[str]:
        """Les variables attendues qui ne sont pas posées."""
        return [nom for nom in self.requires if not (os.environ.get(nom) or "").strip()]

    @property
    def state(self) -> ChannelState:
        """L'état du canal, mesuré à l'instant où on le demande."""
        return (
            ChannelState.NOT_CONFIGURED if self.missing else ChannelState.AVAILABLE
        )

    def accepts(self, recipient: Optional[str]) -> Tuple[bool, str]:
        """
        Ce canal peut-il porter une notification adressée ainsi ?

        Args:
            recipient: Le destinataire de la notification. `None` pour ce qui
                appartient à la plateforme.

        Returns:
            Le verdict et sa raison.
        """
        if self.shared and recipient:
            return False, (
                f"Le canal « {self.channel_id} » est partagé : sa destination "
                "est lue par plus de monde que le destinataire. Une "
                "notification qui appartient à quelqu'un n'y sort pas."
            )
        if self.state is ChannelState.NOT_CONFIGURED:
            return False, (
                f"Canal « {self.channel_id} » non configuré : il manque "
                f"{', '.join(self.missing)}."
            )
        return True, f"Canal « {self.channel_id} » disponible."

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable. Aucune valeur de secret n'y figure."""
        return {
            "channel_id": self.channel_id,
            "description": self.description,
            "kind": self.kind,
            "shared": self.shared,
            "requires": list(self.requires),
            "missing": self.missing,
            "state": self.state.value,
        }


class ChannelRegistry:
    """
    Les canaux déclarés, et ce qu'ils peuvent porter.

    Ne livre rien par lui-même : il dit ce qui **pourrait** partir et ce qui ne
    peut pas. Tant qu'aucun canal externe n'a d'identifiants, c'est toute la
    vérité disponible — et la dire est préférable à laisser croire.
    """

    def __init__(self, channels: Optional[List[DeliveryChannel]] = None) -> None:
        """
        Args:
            channels: Les canaux. Ceux du fichier de déclaration par défaut.
        """
        self._canaux: Dict[str, DeliveryChannel] = {
            canal.channel_id: canal
            for canal in (channels if channels is not None else load_channels())
        }

    def get(self, channel_id: str) -> Optional[DeliveryChannel]:
        """Retourne un canal, ou `None`."""
        return self._canaux.get(channel_id)

    def all_channels(self) -> List[DeliveryChannel]:
        """Tous les canaux déclarés, triés."""
        return [self._canaux[nom] for nom in sorted(self._canaux)]

    def available(self) -> List[DeliveryChannel]:
        """Les canaux réellement utilisables."""
        return [c for c in self.all_channels() if c.state is ChannelState.AVAILABLE]

    def delivery_plan(self, recipient: Optional[str] = None) -> Dict[str, Any]:
        """
        Ce qui partirait pour une notification adressée ainsi, et ce qui ne
        partirait pas.

        Args:
            recipient: Le destinataire, ou `None` pour la plateforme.

        Returns:
            Le verdict de chaque canal, avec sa raison.
        """
        verdicts = []
        for canal in self.all_channels():
            accepte, motif = canal.accepts(recipient)
            verdicts.append({
                "channel_id": canal.channel_id,
                "state": canal.state.value,
                "would_deliver": accepte,
                "reason": motif,
            })
        return {
            "recipient_kind": "user" if recipient else "platform",
            "channels": verdicts,
            "delivering": [v["channel_id"] for v in verdicts if v["would_deliver"]],
        }

    def channels_report(self) -> Dict[str, Any]:
        """
        L'état des canaux, et ce que cette couche ne fait pas.

        Returns:
            Les canaux, leur état, et les règles tenues.
        """
        canaux = self.all_channels()
        return {
            "channels": [c.as_dict() for c in canaux],
            "available": [c.channel_id for c in canaux
                          if c.state is ChannelState.AVAILABLE],
            "not_configured": [c.channel_id for c in canaux
                               if c.state is ChannelState.NOT_CONFIGURED],
            "rules": [
                "Un canal sans identifiants ne prétend jamais avoir envoyé : "
                "il rapporte NOT_CONFIGURED et nomme ce qui manque.",
                "Une destination partagée ne porte pas la notification de "
                "quelqu'un : ce qui appartient à la plateforme y va, ce qui "
                "appartient à une personne n'y va pas.",
                "Aucun identifiant n'est fabriqué et aucun point d'entrée par "
                "défaut n'est inventé : tout vient de l'environnement.",
            ],
            "does_not": [
                "Envoyer réellement vers un canal externe : aucun n'a "
                "d'identifiants dans cette installation, et un envoi simulé "
                "ferait croire que quelqu'un a été prévenu.",
                "Réessayer une livraison : il n'y a pas encore de livraison à "
                "réessayer.",
            ],
        }


def load_channels(path: Optional[Path] = None) -> List[DeliveryChannel]:
    """
    Charge les canaux déclarés.

    Args:
        path: Le fichier de déclaration. Celui du dépôt par défaut.

    Returns:
        Les canaux. Une liste vide si le fichier est absent — un fichier
        manquant laisse la plateforme sans canal externe, ce qui est sûr.
    """
    fichier = path if path is not None else FICHIER_CANAUX
    if not fichier.exists():
        return []

    with open(fichier, "r", encoding="utf-8") as flux:
        declaration = yaml.safe_load(flux) or {}

    canaux = []
    for identifiant, valeurs in (declaration.get("channels") or {}).items():
        valeurs = valeurs or {}
        canaux.append(DeliveryChannel(
            channel_id=identifiant,
            description=valeurs.get("description", ""),
            kind=valeurs.get("kind", "external"),
            shared=bool(valeurs.get("shared", False)),
            requires=list(valeurs.get("requires") or []),
        ))
    return canaux
